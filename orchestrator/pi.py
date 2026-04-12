"""PI (Principal Investigator) agent loop."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    ToolUseBlock,
)

from harness.runner import load_results, should_stop

RATE_LIMIT_POLL_INTERVAL = 300
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── File Loaders ────────────────────────────────────────────────────────────


def _read(path: Path, default: str = "") -> str:
    return path.read_text() if path.exists() else default


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    nodes = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                nodes.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return nodes


# ─── Session State ───────────────────────────────────────────────────────────


def _get_threads(session_dir: Path) -> list[dict]:
    threads_dir = session_dir / "threads"
    if not threads_dir.exists():
        return []

    threads = []
    for d in sorted(threads_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        t = {
            "name": d.name,
            "path": str(d),
            "status": _read(d / "status.md", "unknown").strip(),
            "has_findings": (d / "findings.md").exists(),
        }
        # Extract hypothesis from brief
        brief = _read(d / "brief.md")
        if "## Hypothesis" in brief:
            for line in brief.split("## Hypothesis")[-1].split("\n")[1:]:
                if line.strip():
                    t["hypothesis"] = line.strip()
                    break
        # Count experiments
        log = _read(d / "log.md")
        if log:
            count = len(re.findall(r"###?\s+[Ee]xp(?:eriment)?\s*\d", log))
            t["experiment_count"] = count or log.count("### ")
        threads.append(t)
    return threads


def _format_threads(threads: list[dict]) -> str:
    if not threads:
        return "No threads created yet."
    lines = []
    for t in threads:
        icon = {"active": "[ACTIVE]", "concluded": "[DONE]", "abandoned": "[ABANDONED]"}.get(t["status"], "[?]")
        parts = [f"  {icon} {t['name']}"]
        if t.get("hypothesis"):
            parts.append(f"    Hypothesis: {t['hypothesis']}")
        if t.get("experiment_count"):
            parts.append(f"    Experiments: {t['experiment_count']}")
        if t.get("has_findings"):
            parts.append(f"    >> Has unreviewed findings")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def _summarize_results(session_dir: Path, metric: str) -> str:
    results = load_results(session_dir)
    if not results:
        return "No experiments yet."

    def dec(r):
        return (r.get("decision") or r.get("status", "")).upper()

    kept = [r for r in results if dec(r) == "KEEP"]
    total = len(results)
    lines = [f"Total: {total} (KEEP: {len(kept)}, DISCARD: {sum(1 for r in results if dec(r) == 'DISCARD')})"]

    if kept:
        best = max(kept, key=lambda r: r.get("primary_value") or float("-inf"))
        lines.append(f"Best {metric}: {best.get('primary_value')} ({best['run_id']})")

    for r in results[-5:]:
        lines.append(f"  {r['run_id']} | {dec(r)} | {metric}={r.get('primary_value', '?')} | {(r.get('description') or '')[:50]}")
    return "\n".join(lines)


def _summarize_knowledge(session_dir: Path) -> str:
    nodes = _load_jsonl(session_dir / "knowledge_graph.jsonl")
    if not nodes:
        return "No knowledge nodes yet."
    lines = [f"Knowledge graph: {len(nodes)} experiments"]
    for n in nodes:
        icon = {"positive": "+", "negative": "-", "neutral": "~"}.get(n.get("outcome", ""), "?")
        lines.append(f"  [{icon}] {n.get('id', '?')}: {n.get('title', '')} ({n.get('decision', '?')})")
        for ins in (n.get("insights") or [])[:2]:
            lines.append(f"      insight: {ins}")
        for idea in (n.get("worth_exploring_next") or [])[:1]:
            lines.append(f"      explore: {idea}")
    return "\n".join(lines)


# ─── Time Budget ─────────────────────────────────────────────────────────────


class TimeBudget:
    def __init__(self, budget_minutes: float | None):
        self.start = time.time()
        self.budget = budget_minutes
        self._paused: float = 0

    @property
    def elapsed(self) -> float:
        return (time.time() - self.start - self._paused) / 60

    def is_expired(self) -> bool:
        return self.budget is not None and self.elapsed >= self.budget

    def add_paused(self, seconds: float):
        self._paused += seconds

    def status(self) -> str:
        m = self.elapsed
        if self.budget is None:
            return f"Elapsed: {_fmt(m)}. Budget: unlimited."
        rem = self.budget - m
        pct = m / self.budget * 100
        if rem <= 0:
            return f"Elapsed: {_fmt(m)}. Budget: {_fmt(self.budget)} — **BUDGET EXPIRED**."
        if pct >= 75:
            return f"Elapsed: {_fmt(m)} of {_fmt(self.budget)} ({pct:.0f}%). **{_fmt(rem)} remaining** — wrap up."
        return f"Elapsed: {_fmt(m)} of {_fmt(self.budget)} ({pct:.0f}%). {_fmt(rem)} remaining."


def _fmt(minutes: float) -> str:
    if minutes >= 60:
        h, m = int(minutes // 60), int(minutes % 60)
        return f"{h}h{m:02d}m" if m else f"{h}h"
    return f"{minutes:.0f}m"


# ─── Prompt Builders ─────────────────────────────────────────────────────────


def _load_compute(config: dict) -> str:
    nodes = config["hardware"].split("+")
    parts = []
    for n in nodes:
        p = REPO_ROOT / "compute_nodes" / f"{n.strip()}.md"
        parts.append(_read(p, f"Node '{n.strip()}': no config found"))
    return "\n\n".join(parts)


def _load_skills(session_dir: Path) -> str:
    skills_dir = session_dir / "skills"
    if not skills_dir.exists():
        return ""
    parts = [f"### {f.stem}\n\n{f.read_text()}" for f in sorted(skills_dir.glob("*.md"))]
    return "\n\n---\n\n".join(parts)


def build_options(session_dir: Path, config: dict) -> ClaudeAgentOptions:
    pi_prompt = _read(PROMPTS_DIR / "pi.md")
    inv_prompt = _read(PROMPTS_DIR / "investigator.md")
    compute = _load_compute(config)
    skills = _load_skills(session_dir)
    brief_tpl = _read(TEMPLATES_DIR / "thread_brief.md")
    findings_tpl = _read(TEMPLATES_DIR / "thread_findings.md")

    # PI system prompt
    pi_parts = [pi_prompt, f"## Compute Nodes\n\n{compute}",
                f"## Thread Brief Template\n\n```markdown\n{brief_tpl}\n```"]
    if skills:
        pi_parts.append(f"## Domain Skills\n\n{skills}")

    # Investigator tools
    tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
    if config.get("web_search"):
        tools.extend(["WebSearch", "WebFetch"])

    # Named investigators
    agents = {}
    for i in range(1, config["investigators"] + 1):
        name = f"phd_{i}"
        inv_parts = [
            inv_prompt,
            f"## Your Identity\n\nYou are **{name}**.\n\n"
            f"**run_id format:** `{{thread_num}}_exp{{N}}_{name}` (e.g. `001_exp01_{name}`). No other format.",
            f"## Findings Template\n\n```markdown\n{findings_tpl}\n```",
            f"## Compute Node\n\n{compute}",
            f"## Session\n\nWorking directory: `{session_dir}`\nPrimary metric: **{config['metric']}**\nSeeds: {config['seeds']}",
        ]
        if skills:
            inv_parts.append(f"## Domain Skills\n\n{skills}")
        agents[name] = AgentDefinition(
            description=f"PhD researcher '{name}' — dispatch to a research thread.",
            prompt="\n\n".join(inv_parts),
            tools=tools,
            model="sonnet",
        )

    return ClaudeAgentOptions(
        agents=agents,
        system_prompt="\n\n".join(pi_parts),
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        cwd=str(session_dir),
    )


def _session_state(session_dir: Path, config: dict, budget: TimeBudget) -> dict:
    threads = _get_threads(session_dir)
    return {
        "threads": threads,
        "threads_fmt": _format_threads(threads),
        "results": _summarize_results(session_dir, config["metric"]),
        "knowledge": _summarize_knowledge(session_dir),
        "log": _read(session_dir / "research_log.md"),
        "time": budget.status(),
    }


def _initial_prompt(session_dir: Path, config: dict, budget: TimeBudget) -> str:
    s = _session_state(session_dir, config, budget)
    proposal = _read(session_dir / "research_proposal.md")
    return f"""You are the PI for: {session_dir.name}

## Research Proposal
{proposal}

## Research Log
{s['log']}

## Threads
{s['threads_fmt']}

## Results
{s['results']}

## Knowledge Graph
{s['knowledge']}

## Time
{s['time']}

## Config
- Metric: {config['metric']}, Investigators: {config['investigators']}, Seeds: {config['seeds']}, Hardware: {config['hardware']}

## Instructions
1. Read the proposal — understand question, hypothesis, starting ideas.
2. Open threads with brief.md + status.md.
3. Dispatch ALL investigators in ONE response (parallel). Each gets a thread + compute node.
4. Review findings, update research_log.md.
5. Open new threads or conclude.

Create thread dirs BEFORE dispatching. Dispatch in PARALLEL.
"""


def _continuation_prompt(session_dir: Path, config: dict, budget: TimeBudget) -> str:
    s = _session_state(session_dir, config, budget)
    threads = s["threads"]
    n_threads = len(threads)
    concluded = sum(1 for t in threads if t["status"] == "concluded")
    active = sum(1 for t in threads if t["status"] == "active")
    unreviewed = [t for t in threads if t.get("has_findings") and t["status"] == "active"]

    parts = [f"## Time\n{s['time']}", f"## Threads\n{s['threads_fmt']}", f"## Results\n{s['results']}", f"## Knowledge Graph\n{s['knowledge']}"]
    if unreviewed:
        parts.append("## Unreviewed Findings\n" + "\n".join(f"- `{t['name']}` has findings.md" for t in unreviewed))
    parts.append(f"""## Log (recent)
{s['log'][-2000:]}

## Instructions
1. Review findings. 2. Update thread statuses. 3. Update research_log.md.
4. **Generate new ideas** from findings, near-misses, knowledge graph.
5. Open new threads ({n_threads} so far, {concluded} concluded, {active} active).
6. Dispatch investigators.
7. Signal RESEARCH COMPLETE only when budget is expiring AND no more productive experiments.""")
    return "\n\n".join(parts)


def _output_prompt(session_dir: Path, config: dict, round_num: int = 0, total: int = 0) -> str:
    s_fmt = _format_threads(_get_threads(session_dir))
    results = _summarize_results(session_dir, config["metric"])

    if config.get("final_output") == "summary":
        return f"""## Summary Phase
Dispatch an investigator to write `paper/summary.md`:
Read research_proposal.md, research_log.md, threads/*/findings.md, results.jsonl.
Sections: Research Question, Approach, Key Results table, Findings, Recommendations. 2-4 pages.
## State\n{s_fmt}\n{results}"""

    if round_num == 1:
        return f"""## Paper Phase — Round {round_num}/{total}
Dispatch an investigator to write paper/paper.tex (LaTeX) + paper/reproduce.ipynb.
Read ALL sources. Generate figures in paper/figures/.
## State\n{s_fmt}\n{results}"""

    return f"""## Paper Phase — Round {round_num}/{total}
Review paper/paper.tex. Write paper/review_{round_num - 1}.md. Dispatch investigator to revise.
{"FINAL ROUND: verify numbers, check notebook runs, compile pdflatex." if round_num == total else ""}"""


# ─── Response Processing ─────────────────────────────────────────────────────


def _is_rate_limited(text: str) -> bool:
    lower = text.lower()
    return "hit your limit" in lower or "rate limit" in lower


async def _process_response(pi: ClaudeSDKClient) -> dict:
    """Process PI response, return flags: got_content, rate_limited, concluded."""
    flags = {"got_content": False, "rate_limited": False, "concluded": False}
    async for msg in pi.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                    flags["got_content"] = True
                    if _is_rate_limited(block.text):
                        flags["rate_limited"] = True
                    if "research complete" in block.text.lower():
                        flags["concluded"] = True
                elif isinstance(block, ToolUseBlock):
                    flags["got_content"] = True
                    if block.name == "Agent":
                        print(f"\n>>> Dispatching: {block.input.get('description', '')}")
                    else:
                        print(f"  [tool: {block.name}]")
    return flags


async def _wait_for_reset(pi: ClaudeSDKClient, session_dir: Path, budget: TimeBudget | None = None) -> bool:
    """Poll until rate limit clears. Returns False if stopped."""
    print("\nRate limit hit. Polling every 5 min...")
    pause_start = time.time()
    while not should_stop(session_dir):
        await asyncio.sleep(RATE_LIMIT_POLL_INTERVAL)
        print(f"  Checking... ({_fmt((time.time() - pause_start) / 60)} waited)")
        await pi.query("Reply with: READY")
        flags = await _process_response(pi)
        if flags["got_content"] and not flags["rate_limited"]:
            wait = time.time() - pause_start
            if budget:
                budget.add_paused(wait)
            print(f"  Cleared after {_fmt(wait / 60)}.\n")
            return True
    return False


# ─── Main Loop ───────────────────────────────────────────────────────────────


async def run_pi_loop(session_dir: Path, config: dict) -> None:
    options = build_options(session_dir, config)
    budget = TimeBudget(config["research_budget_minutes"])
    iteration = 0

    print(f"\nStarting: {session_dir.name}")
    print(f"  Investigators: {config['investigators']}, Metric: {config['metric']}, "
          f"Hardware: {config['hardware']}, Budget: {_fmt(budget.budget) if budget.budget else 'unlimited'}\n")

    async with ClaudeSDKClient(options=options) as pi:
        # Initial orientation
        await pi.query(_initial_prompt(session_dir, config, budget))
        await _process_response(pi)
        iteration += 1

        # Research loop
        while not should_stop(session_dir):
            if budget.is_expired():
                print(f"\nBUDGET EXPIRED ({_fmt(budget.elapsed)} active). Moving to output phase.\n")
                break

            print(f"\n{'='*50}\nIteration {iteration + 1} | {budget.status()}\n{'='*50}\n")
            await pi.query(_continuation_prompt(session_dir, config, budget))
            flags = await _process_response(pi)

            if flags["rate_limited"]:
                if config["rate_limit_policy"] == "stop":
                    break
                await _wait_for_reset(pi, session_dir, budget)
                continue

            if not flags["got_content"]:
                await asyncio.sleep(30)
                continue

            if flags["concluded"]:
                if budget.budget is not None:
                    break
                print("\nUnlimited budget — cannot stop. Keep researching.")
                await pi.query("Budget is UNLIMITED. Open new threads. Keep researching.")
                await _process_response(pi)

            iteration += 1

        # Output phase (always runs, even after stop signal)
        stop_file = session_dir / ".stop_autoresearch"
        if stop_file.exists():
            stop_file.unlink()

        output = config.get("final_output", "paper")
        if output == "summary":
            print(f"\n{'='*50}\nSUMMARY PHASE\n{'='*50}\n")
            await pi.query(_output_prompt(session_dir, config))
            await _process_response(pi)
        else:
            rounds = config["paper_review_rounds"]
            print(f"\n{'='*50}\nPAPER PHASE — {rounds} rounds\n{'='*50}\n")
            r = 1
            while r <= rounds:
                print(f"\n--- Round {r}/{rounds} ---\n")
                await pi.query(_output_prompt(session_dir, config, r, rounds))
                flags = await _process_response(pi)
                if flags["rate_limited"]:
                    if config["rate_limit_policy"] == "stop":
                        break
                    await _wait_for_reset(pi, session_dir)
                    continue
                r += 1

    print(f"\nDone. {iteration} iterations, {_fmt((time.time() - budget.start) / 60)} total.")
    print(f"Results: {session_dir / 'results.jsonl'}")
    print(f"Log: {session_dir / 'research_log.md'}")
    if (session_dir / "paper" / "paper.tex").exists():
        print(f"Paper: {session_dir / 'paper' / 'paper.tex'}")
    if (session_dir / "paper" / "summary.md").exists():
        print(f"Summary: {session_dir / 'paper' / 'summary.md'}")
