"""PI (Principal Investigator) agent loop.

The PI reads the research proposal, manages research threads,
dispatches investigators, and synthesizes findings.
Uses the Claude Agent SDK for multi-agent orchestration.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from harness.runner import load_results, should_stop

RATE_LIMIT_POLL_INTERVAL = 300  # 5 minutes between retry attempts

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_prompt(name: str) -> str:
    """Load a system prompt from the prompts directory."""
    return (PROMPTS_DIR / f"{name}.md").read_text()


def load_template(name: str) -> str:
    """Load a thread template from the templates directory."""
    return (TEMPLATES_DIR / f"{name}.md").read_text()


def get_thread_status(session_dir: Path) -> list[dict]:
    """Read all threads and their current status."""
    threads_dir = session_dir / "threads"
    if not threads_dir.exists():
        return []

    threads = []
    for thread_dir in sorted(threads_dir.iterdir()):
        if not thread_dir.is_dir() or thread_dir.name.startswith("."):
            continue

        thread = {"name": thread_dir.name, "path": str(thread_dir)}

        status_path = thread_dir / "status.md"
        if status_path.exists():
            thread["status"] = status_path.read_text().strip()
        else:
            thread["status"] = "unknown"

        brief_path = thread_dir / "brief.md"
        thread["has_brief"] = brief_path.exists()
        if thread["has_brief"]:
            brief_text = brief_path.read_text()
            # Extract hypothesis (first non-empty line after ## Hypothesis)
            for line in brief_text.split("## Hypothesis")[-1].split("\n")[1:]:
                if line.strip():
                    thread["hypothesis"] = line.strip()
                    break

        findings_path = thread_dir / "findings.md"
        thread["has_findings"] = findings_path.exists()
        if thread["has_findings"]:
            thread["findings_preview"] = findings_path.read_text()[:500]

        # Count experiments in this thread's log
        log_path = thread_dir / "log.md"
        if log_path.exists():
            import re
            log_text = log_path.read_text()
            count = len(re.findall(r"###?\s+[Ee]xp(?:eriment)?\s*\d", log_text))
            thread["experiment_count"] = count if count else log_text.count("### ")

        threads.append(thread)

    return threads


def summarize_results(session_dir: Path, config: dict) -> str:
    """Build a summary of experiment results for the PI."""
    results = load_results(session_dir)
    if not results:
        return "No experiments have been run yet."

    metric = config["metric"]
    total = len(results)
    def _decision(r):
        return (r.get("decision") or r.get("status", "")).upper()

    kept = [r for r in results if _decision(r) == "KEEP"]
    discarded = [r for r in results if _decision(r) == "DISCARD"]
    crashed = [r for r in results if (r.get("status") or "").upper() in ("CRASH", "TIMEOUT", "ERROR")]

    lines = [
        f"Total experiments: {total} (KEEP: {len(kept)}, DISCARD: {len(discarded)}, CRASH: {len(crashed)})",
    ]

    if kept:
        best = max(kept, key=lambda r: r.get("primary_value") or float("-inf"))
        lines.append(f"Best {metric}: {best.get('primary_value')} (from {best['run_id']})")
        lines.append(f"Best description: {best.get('description', 'N/A')}")

    # Last 5 experiments
    lines.append("\nRecent experiments:")
    for r in results[-5:]:
        val = r.get("primary_value", "N/A")
        lines.append(f"  {r['run_id']} | {r.get('decision', r.get('status'))} | {metric}={val} | {r.get('description', '')[:60]}")

    return "\n".join(lines)


def format_threads(threads: list[dict]) -> str:
    """Format thread status for the PI prompt."""
    if not threads:
        return "No threads created yet."

    lines = []
    for t in threads:
        status_icon = {"active": "[ACTIVE]", "concluded": "[DONE]", "abandoned": "[ABANDONED]"}.get(t["status"], "[?]")
        parts = [f"  {status_icon} {t['name']}"]
        if t.get("hypothesis"):
            parts.append(f"    Hypothesis: {t['hypothesis']}")
        if t.get("experiment_count"):
            parts.append(f"    Experiments run: {t['experiment_count']}")
        if t.get("has_findings"):
            parts.append(f"    >> Has unreviewed findings")
        lines.append("\n".join(parts))

    return "\n".join(lines)


def _load_session_skills(session_dir: Path) -> str:
    """Load domain skills from the session's skills/ directory.

    Each .md file in skills/ is a domain knowledge pack that gets
    injected into both PI and investigator prompts.
    """
    skills_dir = session_dir / "skills"
    if not skills_dir.exists():
        return ""

    parts = []
    for skill_file in sorted(skills_dir.glob("*.md")):
        parts.append(f"### {skill_file.stem}\n\n{skill_file.read_text()}")

    return "\n\n---\n\n".join(parts) if parts else ""


def load_compute_node(config: dict) -> str:
    """Load compute node details for the investigator."""
    hardware = config["hardware"]
    # Handle multi-node configs like "local+gym1"
    nodes = hardware.split("+")
    parts = []
    for node in nodes:
        node_path = REPO_ROOT / "compute_nodes" / f"{node.strip()}.md"
        if node_path.exists():
            parts.append(node_path.read_text())
        else:
            parts.append(f"Compute node '{node.strip()}': no config file found at {node_path}")
    return "\n\n".join(parts)


# ─── Time Budget ────────────────────────────────────────────────────────────


class TimeBudget:
    """Tracks research time budget, pausing the clock during rate limit waits."""

    def __init__(self, budget_minutes: float | None) -> None:
        self.start_time = time.time()
        self.budget_minutes = budget_minutes
        self._paused_seconds: float = 0

    @property
    def active_elapsed_minutes(self) -> float:
        """Minutes of active research (excluding paused time)."""
        return (time.time() - self.start_time - self._paused_seconds) / 60

    @property
    def effective_start(self) -> float:
        """Start time shifted forward by paused duration (for display functions)."""
        return self.start_time - self._paused_seconds

    def is_expired(self) -> bool:
        if self.budget_minutes is None:
            return False
        return self.active_elapsed_minutes >= self.budget_minutes

    def add_paused(self, seconds: float) -> None:
        self._paused_seconds += seconds

    def format_status(self) -> str:
        return format_time_status(self.effective_start, self.budget_minutes)


def format_time_status(start_time: float, budget_minutes: float | None) -> str:
    """Format elapsed time and remaining budget for the PI prompt."""
    elapsed_m = (time.time() - start_time) / 60

    if budget_minutes is None:
        return f"Elapsed: {_fmt_duration(elapsed_m)}. Budget: unlimited."

    remaining_m = budget_minutes - elapsed_m
    pct = elapsed_m / budget_minutes * 100

    if remaining_m <= 0:
        return (
            f"Elapsed: {_fmt_duration(elapsed_m)}. "
            f"Budget: {_fmt_duration(budget_minutes)} — **BUDGET EXPIRED**. "
            f"Wrap up ALL threads and transition to paper writing NOW."
        )
    elif pct >= 75:
        return (
            f"Elapsed: {_fmt_duration(elapsed_m)} of {_fmt_duration(budget_minutes)} ({pct:.0f}%). "
            f"**{_fmt_duration(remaining_m)} remaining** — start wrapping up current threads. "
            f"Conclude or abandon active threads and prepare to transition to paper writing."
        )
    else:
        return (
            f"Elapsed: {_fmt_duration(elapsed_m)} of {_fmt_duration(budget_minutes)} ({pct:.0f}%). "
            f"{_fmt_duration(remaining_m)} remaining."
        )


def _fmt_duration(minutes: float) -> str:
    """Format minutes into a readable string."""
    if minutes >= 60:
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h}h{m:02d}m" if m else f"{h}h"
    return f"{minutes:.0f}m"


# ─── Prompt Builders ────────────────────────────────────────────────────────


def build_pi_options(session_dir: Path, config: dict) -> ClaudeAgentOptions:
    """Build the ClaudeAgentOptions for the PI agent."""
    pi_prompt = load_prompt("pi")
    investigator_prompt = load_prompt("investigator")
    compute_details = load_compute_node(config)
    brief_template = load_template("thread_brief")
    findings_template = load_template("thread_findings")

    # Load session-level skills (domain knowledge)
    skills_content = _load_session_skills(session_dir)

    # Augment PI prompt with skills, compute nodes, and brief template
    pi_parts = [
        pi_prompt,
        f"## Available Compute Nodes\n\nAssign one node per thread when dispatching investigators.\n\n{compute_details}",
        "## Thread Brief Template\n\nUse this format when writing `brief.md` for new threads:\n",
        f"```markdown\n{brief_template}\n```",
    ]
    if skills_content:
        pi_parts.append(f"## Domain Skills\n\nThe following domain knowledge is available to you and your investigators:\n\n{skills_content}")
    full_pi_prompt = "\n\n".join(pi_parts)

    investigator_tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
    if config.get("web_search", False):
        investigator_tools.extend(["WebSearch", "WebFetch"])

    # Create named investigators: phd_1, phd_2, etc.
    num_investigators = config.get("investigators", 2)
    agents = {}
    for i in range(1, num_investigators + 1):
        name = f"phd_{i}"
        inv_parts = [
            investigator_prompt,
            f"## Your Identity\n\nYou are **{name}**.\n\n"
            f"**run_id format — follow EXACTLY:** `{{thread_num}}_exp{{N}}_{name}`\n\n"
            f"Examples: `001_exp01_{name}`, `001_exp02_{name}`, `002_exp01_{name}`\n\n"
            f"Do NOT invent your own format. Do NOT use `{name}_reward_001` or `{name}_combo_003`. "
            f"Always: `{{thread_num}}_exp{{N}}_{name}`",
            f"## Findings Template\n\nUse this format when writing `findings.md`:\n\n```markdown\n{findings_template}\n```",
            f"## Compute Node\n\n{compute_details}",
            f"## Session\n\nWorking directory: `{session_dir}`",
            f"Primary metric: **{config['metric']}**",
            f"Seeds per experiment: {config['seeds']}",
        ]
        if skills_content:
            inv_parts.append(f"## Domain Skills\n\n{skills_content}")
        full_investigator_prompt = "\n\n".join(inv_parts)
        agents[name] = AgentDefinition(
            description=f"PhD researcher '{name}' — runs experiment loops on a research thread. "
            f"Dispatch to a thread with the thread directory and brief.",
            prompt=full_investigator_prompt,
            tools=investigator_tools,
            model="sonnet",
        )

    # bypassPermissions is required — the parent's permission_mode cascades
    # to subagents in practice (despite SDK docs suggesting otherwise).
    # The PI is restricted to strategic work via its system prompt, not tools.
    # Investigators need Bash to run training scripts.
    return ClaudeAgentOptions(
        agents=agents,
        system_prompt=full_pi_prompt,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        cwd=str(session_dir),
    )


def _load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, skipping blank or malformed lines."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    nodes = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                nodes.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return nodes


def load_knowledge_graph(session_dir: Path) -> str:
    """Load the session knowledge graph for the PI."""
    nodes = _load_jsonl(session_dir / "knowledge_graph.jsonl")
    if not nodes:
        return "No experiments in the knowledge graph yet."

    lines = [f"Knowledge graph: {len(nodes)} experiments"]
    for n in nodes:
        outcome_icon = {"positive": "+", "negative": "-", "neutral": "~"}.get(n.get("outcome", ""), "?")
        lines.append(f"  [{outcome_icon}] {n.get('id', '?')}: {n.get('title', '')} ({n.get('decision', '?')})")
        if n.get("insights"):
            for insight in n["insights"][:2]:
                lines.append(f"      insight: {insight}")
        if n.get("worth_exploring_next"):
            for idea in n["worth_exploring_next"][:1]:
                lines.append(f"      explore: {idea}")

    return "\n".join(lines)


def _gather_session_state(session_dir: Path, config: dict, start_time: float) -> dict:
    """Gather common session state used by prompt builders."""
    threads = get_thread_status(session_dir)
    return {
        "threads": threads,
        "threads_formatted": format_threads(threads),
        "results": summarize_results(session_dir, config),
        "knowledge": load_knowledge_graph(session_dir),
        "research_log": (session_dir / "research_log.md").read_text(),
        "time_status": format_time_status(start_time, config["research_budget_minutes"]),
    }


def build_initial_prompt(session_dir: Path, config: dict, start_time: float) -> str:
    """Build the initial prompt that orients the PI."""
    state = _gather_session_state(session_dir, config, start_time)
    proposal = (session_dir / "research_proposal.md").read_text()

    return f"""You are the PI for research session: {session_dir.name}

## Research Proposal
{proposal}

## Current Research Log
{state['research_log']}

## Thread Status
{state['threads_formatted']}

## Experiment Results
{state['results']}

## Knowledge Graph
{state['knowledge']}

## Time
{state['time_status']}

## Configuration
- Primary metric: {config['metric']}
- Investigators available: {config['investigators']}
- Seeds per experiment: {config['seeds']}
- Hardware: {config['hardware']}
- Paper review rounds: {config['paper_review_rounds']}

## Instructions

Begin the research loop:

1. Read the research proposal carefully — understand the question, hypothesis, and starting ideas.
2. Open your first research thread(s) based on the starting ideas:
   - Create `threads/001_<name>/` with `brief.md` (hypothesis + scope) and `status.md` (set to "active")
   - You may open up to {config['investigators']} threads at once.
3. Dispatch ALL investigators in a SINGLE response using multiple Agent tool calls:
   - Each investigator gets its own thread and compute node
   - They run in PARALLEL — this is how we maximize hardware utilization
   - Tell each: thread path, what to investigate, baseline, compute node
4. After ALL investigators return, review their findings.
5. Update `research_log.md` with your strategic decision.
6. Decide next: open new threads, continue existing ones, or conclude.

IMPORTANT: Create thread directories and write brief.md/status.md BEFORE dispatching investigators.
IMPORTANT: Always dispatch investigators in PARALLEL — multiple Agent tool calls in ONE response.
"""


def build_continuation_prompt(session_dir: Path, config: dict, start_time: float) -> str:
    """Build the continuation prompt for subsequent PI iterations."""
    state = _gather_session_state(session_dir, config, start_time)

    # Find threads with unreviewed findings
    threads_with_findings = [
        t for t in state["threads"]
        if t.get("has_findings") and t["status"] == "active"
    ]

    parts = [
        f"## Time\n{state['time_status']}",
        "## Updated State",
        f"\n### Threads\n{state['threads_formatted']}",
        f"\n### Results\n{state['results']}",
        f"\n### Knowledge Graph\n{state['knowledge']}",
    ]

    if threads_with_findings:
        parts.append("\n### Unreviewed Findings")
        for t in threads_with_findings:
            parts.append(f"\nThread `{t['name']}` has new findings. Read `{t['path']}/findings.md` to review.")

    # Count how many starting ideas from the proposal have been explored
    num_threads = len(state["threads"])
    concluded = sum(1 for t in state["threads"] if t["status"] == "concluded")
    active = sum(1 for t in state["threads"] if t["status"] == "active")

    parts.append(f"""
### Research Log (current)
{state['research_log'][-2000:]}

## Instructions

Continue the research loop:
1. Review any new findings from completed investigators.
2. Update thread statuses (conclude or abandon threads with clear results).
3. Update `research_log.md` with your synthesis and next direction.
4. **Generate new ideas**: What do the findings so far suggest? Can you combine successful approaches? Are there near-misses worth revisiting? Does the knowledge graph's `worth_exploring_next` point to productive directions?
5. Open NEW threads — from the proposal's starting ideas ({num_threads} threads so far, {concluded} concluded, {active} active) OR from your own generated hypotheses.
6. Dispatch investigator(s) to active or new threads.
7. Only signal RESEARCH COMPLETE when the budget is expiring AND you genuinely believe there are no more productive experiments to run.
""")

    return "\n".join(parts)


def build_paper_prompt(session_dir: Path, config: dict, round_num: int, total_rounds: int) -> str:
    """Build the prompt for the paper writing phase."""
    threads = get_thread_status(session_dir)
    results = summarize_results(session_dir, config)

    if round_num == 1:
        # First round: write the draft
        return f"""## Paper Writing Phase — Round {round_num}/{total_rounds}

Research is complete. Time to write the paper.

Dispatch an investigator to write the first draft:

**Instructions for the investigator:**
- Create the `paper/` directory with `paper/figures/` subdirectory
- Read ALL source material:
  - `research_proposal.md` (question, hypothesis)
  - `research_log.md` (your strategic decisions)
  - `threads/*/findings.md` (all experimental findings)
  - `results.jsonl` (all experiment data)
- Write `paper/paper.tex` as a LaTeX research paper
- Generate figures in `paper/figures/`
- Create `paper/reproduce.ipynb` to reproduce key results
- Focus on completeness and accuracy over polish — this is a draft

## Current State
### Threads
{format_threads(threads)}

### Results
{results}
"""
    else:
        # Review and revise round
        return f"""## Paper Writing Phase — Round {round_num}/{total_rounds}

Review the current paper and dispatch an investigator to revise.

1. Read `paper/paper.tex` thoroughly
2. Write your review in `paper/review_{round_num - 1}.md` with:
   - Major issues (must fix)
   - Minor issues (should fix)
   - What's good (keep)
3. Dispatch an investigator to revise based on your feedback

{"**This is the FINAL round.** Instruct the investigator to also verify all numbers trace to results.jsonl, check that reproduce.ipynb runs, and compile with pdflatex." if round_num == total_rounds else ""}
"""


# ─── Rate Limit Handling ───────────────────────────────────────────────────


def _is_rate_limited(text: str) -> bool:
    """Check if a response text indicates a rate limit."""
    lower = text.lower()
    return "hit your limit" in lower or "rate limit" in lower


async def _wait_for_rate_limit_reset(
    pi: ClaudeSDKClient,
    session_dir: Path,
    budget: TimeBudget | None = None,
    context: str = "",
) -> bool:
    """Poll until rate limit clears or stop signal is received.

    If a TimeBudget is provided, paused time is added so the research clock
    does not advance while waiting.

    Returns True if the rate limit cleared, False if a stop signal interrupted.
    """
    print(f"\nRate limit hit{f' during {context}' if context else ''}. "
          f"Polling every 5 min until reset.")
    if budget:
        print("Research budget clock is paused. Stop signal still checked.")

    pause_start = time.time()
    while not should_stop(session_dir):
        await asyncio.sleep(RATE_LIMIT_POLL_INTERVAL)
        waited = _fmt_duration((time.time() - pause_start) / 60)
        print(f"  Checking if rate limit has reset... ({waited} waited)")

        await pi.query("Confirm you can respond. Reply with just: READY")
        is_back = False
        async for msg in pi.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock) and not _is_rate_limited(block.text):
                        is_back = True

        if is_back:
            wait_duration = time.time() - pause_start
            if budget:
                budget.add_paused(wait_duration)
            print(f"  Rate limit cleared after {_fmt_duration(wait_duration / 60)}.\n")
            return True

    return False


# ─── Message Display ───────────────────────────────────────────────────────


def _handle_message(message) -> None:
    """Process and display a message from the PI agent."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)
            elif isinstance(block, ToolUseBlock):
                if block.name == "Agent":
                    print(f"\n>>> PI dispatching investigator: {block.input.get('description', '')}")
                else:
                    print(f"  [tool: {block.name}]")
    elif isinstance(message, ResultMessage):
        if message.total_cost_usd:
            print(f"\n  [cost: ${message.total_cost_usd:.4f}]")


# ─── Main Loop ──────────────────────────────────────────────────────────────


async def run_pi_loop(session_dir: Path, config: dict) -> None:
    """Run the PI agent loop.

    The PI reads the proposal, manages threads, and dispatches investigators
    using the Claude Agent SDK. The loop has two phases:

    1. Research phase: open threads, dispatch investigators, review findings
       - Time-aware: soft warning at 75% budget, hard cutoff at 100%
    2. Paper phase: write, review, and revise a LaTeX paper

    Args:
        session_dir: Path to the autoresearch session directory.
        config: Parsed research proposal configuration.
    """
    options = build_pi_options(session_dir, config)
    budget = TimeBudget(config["research_budget_minutes"])
    iteration = 0

    budget_str = _fmt_duration(budget.budget_minutes) if budget.budget_minutes else "unlimited"
    print(f"\nStarting PI loop for {session_dir.name}")
    print(f"  Investigators: {config['investigators']}")
    print(f"  Metric: {config['metric']}")
    print(f"  Hardware: {config['hardware']}")
    print(f"  Research budget: {budget_str}")
    print(f"  Paper review rounds: {config['paper_review_rounds']}")
    print()

    async with ClaudeSDKClient(options=options) as pi:
        # ── Research Phase ──────────────────────────────────────────────

        initial_prompt = build_initial_prompt(session_dir, config, budget.effective_start)
        await pi.query(initial_prompt)

        async for message in pi.receive_response():
            _handle_message(message)

        iteration += 1

        # Main PI loop -- continues until stop, budget expired, or PI concludes
        while not should_stop(session_dir):
            if budget.is_expired():
                print(f"\n{'='*60}")
                print(f"RESEARCH BUDGET EXPIRED ({_fmt_duration(budget.active_elapsed_minutes)} active research time)")
                print(f"Transitioning to paper writing phase.")
                print(f"{'='*60}\n")
                break

            print(f"\n{'='*60}")
            print(f"PI iteration {iteration + 1} | {budget.format_status()}")
            print(f"{'='*60}\n")

            continuation = build_continuation_prompt(session_dir, config, budget.effective_start)
            await pi.query(continuation)

            concluded = False
            rate_limited = False
            got_content = False
            async for message in pi.receive_response():
                _handle_message(message)
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            got_content = True
                            if _is_rate_limited(block.text):
                                rate_limited = True
                            if "research complete" in block.text.lower():
                                concluded = True
                        elif isinstance(block, ToolUseBlock):
                            got_content = True

            if rate_limited:
                if config.get("rate_limit_policy", "wait") == "stop":
                    print("\nRate limit hit. Policy: stop. Ending research phase.")
                    break
                await _wait_for_rate_limit_reset(pi, session_dir, budget, context="research")
                continue  # Re-enter the loop without incrementing iteration

            if not got_content:
                print("\nEmpty response from PI. Retrying in 30s...")
                await asyncio.sleep(30)
                continue

            if concluded:
                if budget.budget_minutes is not None:
                    print("\nPI signaled research is complete.")
                    break
                else:
                    print("\nPI signaled research complete, but budget is unlimited. "
                          "Continuing — only the stop signal or budget expiry ends the loop.")
                    # Tell the PI to keep going
                    await pi.query(
                        "Budget is UNLIMITED. You cannot stop research on your own. "
                        "Open new threads — generate new hypotheses from your findings, "
                        "combine successful approaches, stress-test results, or explore "
                        "directions you haven't tried yet. Keep researching."
                    )
                    async for message in pi.receive_response():
                        _handle_message(message)

            iteration += 1

        # ── Paper Writing Phase ─────────────────────────────────────────

        if not should_stop(session_dir):
            total_rounds = config["paper_review_rounds"]
            print(f"\n{'='*60}")
            print(f"PAPER WRITING PHASE — {total_rounds} rounds")
            print(f"{'='*60}\n")

            round_num = 1
            while round_num <= total_rounds and not should_stop(session_dir):
                print(f"\n--- Paper round {round_num}/{total_rounds} ---\n")

                paper_prompt = build_paper_prompt(session_dir, config, round_num, total_rounds)
                await pi.query(paper_prompt)

                paper_rate_limited = False
                async for message in pi.receive_response():
                    _handle_message(message)
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock) and _is_rate_limited(block.text):
                                paper_rate_limited = True

                if paper_rate_limited:
                    if config.get("rate_limit_policy", "wait") == "stop":
                        print("\nRate limit hit during paper phase. Policy: stop.")
                        break
                    await _wait_for_rate_limit_reset(pi, session_dir, context="paper phase")
                    continue  # Retry the same round

                round_num += 1

    # ── Summary ─────────────────────────────────────────────────────────

    total_m = (time.time() - budget.start_time) / 60
    print(f"\nPI loop ended after {iteration} research iterations + paper phase.")
    print(f"Total time: {_fmt_duration(total_m)}")
    if should_stop(session_dir):
        print("Reason: stop signal detected.")
    print(f"Results: {session_dir / 'results.jsonl'}")
    print(f"Research log: {session_dir / 'research_log.md'}")
    paper_path = session_dir / "paper" / "paper.tex"
    if paper_path.exists():
        print(f"Paper: {paper_path}")
