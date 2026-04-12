"""Research Lab Dashboard.

Launch:
    uv run streamlit run dashboard.py
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from harness.runner import load_results

REPO_ROOT = Path(__file__).resolve().parent
AUTORESEARCH_DIR = REPO_ROOT / "autoresearch"
REFRESH_INTERVAL = 10


# ─── Data Loading ────────────────────────────────────────────────────────────


def load_proposal(session_dir: Path) -> dict:
    """Parse research_proposal.md for dashboard display."""
    path = session_dir / "research_proposal.md"
    if not path.exists():
        return {"question": "Unknown", "metric": "primary_metric", "hardware": "unknown",
                "hypothesis": "", "investigators": 2}
    text = path.read_text()
    info = {"question": "", "metric": "primary_metric", "hardware": "local",
            "hypothesis": "", "investigators": 2}

    sections = text.split("## ")
    for section in sections:
        header = section.split("\n")[0].strip()
        content_lines = [
            l.strip() for l in section.split("\n")[1:]
            if l.strip() and not l.strip().startswith("<!--")
        ]
        if header == "Research Question":
            info["question"] = content_lines[0] if content_lines else ""
        elif header == "Hypothesis":
            info["hypothesis"] = content_lines[0] if content_lines else ""

    subsections = text.split("### ")
    for section in subsections:
        lines = section.strip().split("\n")
        header = lines[0].strip()
        content_lines = [
            l.strip() for l in lines[1:]
            if l.strip() and not l.strip().startswith("<!--")
        ]
        if header == "Primary Metric":
            for l in content_lines:
                if l.startswith("**") and "**" in l[2:]:
                    info["metric"] = l.split("**")[1]
                    break
        elif header == "Hardware":
            if content_lines:
                info["hardware"] = content_lines[0]
        elif header == "Investigators":
            if content_lines:
                try:
                    info["investigators"] = int(content_lines[0])
                except ValueError:
                    pass

    return info


def load_threads(session_dir: Path) -> list[dict]:
    """Load all thread info."""
    threads_dir = session_dir / "threads"
    if not threads_dir.exists():
        return []

    threads = []
    for thread_dir in sorted(threads_dir.iterdir()):
        if not thread_dir.is_dir() or thread_dir.name.startswith("."):
            continue

        thread = {"name": thread_dir.name, "path": thread_dir}

        status_path = thread_dir / "status.md"
        thread["status"] = status_path.read_text().strip() if status_path.exists() else "unknown"

        brief_path = thread_dir / "brief.md"
        thread["has_brief"] = brief_path.exists()
        thread["hypothesis"] = ""
        if brief_path.exists():
            brief_text = brief_path.read_text()
            for line in brief_text.split("## Hypothesis")[-1].split("\n")[1:]:
                if line.strip():
                    thread["hypothesis"] = line.strip()
                    break

        thread["has_findings"] = (thread_dir / "findings.md").exists()

        # Count experiments — flexible matching
        log_path = thread_dir / "log.md"
        thread["experiment_count"] = 0
        if log_path.exists():
            log_text = log_path.read_text()
            count = len(re.findall(r"###?\s+[Ee]xp(?:eriment)?\s*\d", log_text))
            if count == 0:
                count = log_text.count("### ")
            thread["experiment_count"] = count

        threads.append(thread)

    return threads


def load_knowledge_graph(session_dir: Path) -> list[dict]:
    """Load knowledge graph nodes."""
    kg_path = session_dir / "knowledge_graph.jsonl"
    if not kg_path.exists():
        return []
    nodes = []
    with open(kg_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    nodes.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return nodes


def load_research_log(session_dir: Path) -> str:
    log_path = session_dir / "research_log.md"
    return log_path.read_text() if log_path.exists() else ""


def is_stopped(session_dir: Path) -> bool:
    return (session_dir / ".stop_autoresearch").exists()


def stop_session(session_dir: Path) -> None:
    (session_dir / ".stop_autoresearch").write_text(
        f"Stopped from dashboard at {datetime.now().isoformat()}\n"
    )


def resume_session(session_dir: Path) -> None:
    stop_file = session_dir / ".stop_autoresearch"
    if stop_file.exists():
        stop_file.unlink()


def get_sessions() -> list[Path]:
    if not AUTORESEARCH_DIR.exists():
        return []
    return sorted(
        [d for d in AUTORESEARCH_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")],
        reverse=True,
    )


def check_paper(session_dir: Path) -> dict:
    paper_dir = session_dir / "paper"
    info = {"exists": False, "reviews": 0, "has_notebook": False, "has_pdf": False}
    if paper_dir.exists():
        info["exists"] = (paper_dir / "paper.tex").exists()
        info["has_pdf"] = (paper_dir / "paper.pdf").exists()
        info["has_notebook"] = (paper_dir / "reproduce.ipynb").exists()
        info["reviews"] = len(list(paper_dir.glob("review_*.md")))
    return info


def _readable_name(raw_name: str) -> str:
    """Convert 001_reward_shaping to 'Reward Shaping'."""
    # Strip leading number prefix
    name = re.sub(r"^\d+_", "", raw_name)
    return name.replace("_", " ").title()


# ─── Charts ──────────────────────────────────────────────────────────────────


def _clamp_metric(value, cap=100):
    """Clamp extreme metric values (e.g., PF=999 from zero-loss trades)."""
    if value is None:
        return 0
    if abs(value) > cap:
        return cap if value > 0 else -cap
    return value


def build_metric_chart(results: list[dict], metric_key: str) -> go.Figure:
    """Primary metric progression chart."""
    all_with_metrics = [r for r in results if r.get("metrics")]
    kept = [r for r in all_with_metrics if (r.get("decision") or r.get("status", "")).upper() == "KEEP"]

    fig = go.Figure()

    if all_with_metrics:
        fig.add_trace(go.Scatter(
            x=list(range(1, len(all_with_metrics) + 1)),
            y=[_clamp_metric(r["metrics"].get(metric_key, 0)) for r in all_with_metrics],
            mode="markers",
            name="All runs",
            marker=dict(
                size=8,
                color=[
                    "#22c55e" if (r.get("decision") or r.get("status", "")).upper() == "KEEP"
                    else "#ef4444" if (r.get("status") or "").upper() in ("CRASH", "ERROR", "TIMEOUT")
                    else "#94a3b8"
                    for r in all_with_metrics
                ],
                opacity=0.6,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                f"{metric_key}: %{{y:.4f}}<br>"
                "%{customdata[1]}<br>"
                "%{customdata[2]}"
                "<extra></extra>"
            ),
            customdata=[
                [
                    r["run_id"],
                    r.get("decision") or r.get("status", "?"),
                    (r.get("description") or "")[:80],
                ]
                for r in all_with_metrics
            ],
        ))

    if kept:
        running_best = []
        current_best = float("-inf")
        for r in kept:
            val = _clamp_metric(r["metrics"].get(metric_key, 0))
            if val > current_best:
                current_best = val
            running_best.append(current_best)

        kept_indices = [
            i + 1 for i, r in enumerate(all_with_metrics)
            if (r.get("decision") or r.get("status", "")).upper() == "KEEP"
        ]

        fig.add_trace(go.Scatter(
            x=kept_indices, y=running_best,
            mode="lines+markers", name="Best so far",
            line=dict(color="#22c55e", width=2),
            marker=dict(size=10, color="#22c55e"),
        ))

    fig.update_layout(
        title=dict(text=f"{metric_key}", font=dict(size=14)),
        xaxis_title="Experiment #", yaxis_title=metric_key,
        template="plotly_dark", height=350,
        margin=dict(l=50, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    return fig


def build_knowledge_graph_chart(nodes: list[dict]) -> go.Figure:
    """Build interactive knowledge graph."""
    if not nodes:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark", height=350,
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
            title="Knowledge Graph",
        )
        return fig

    id_to_idx = {n["id"]: i for i, n in enumerate(nodes)}

    # Depth by parent chain
    depths = {}
    for n in nodes:
        depth = 0
        pid = n.get("parent")
        visited = set()
        while pid and pid in id_to_idx and pid not in visited:
            visited.add(pid)
            depth += 1
            pid = nodes[id_to_idx[pid]].get("parent")
        depths[n["id"]] = depth

    # Group by thread
    threads = {}
    for n in nodes:
        t = n.get("thread") or "unknown"
        if t not in threads:
            threads[t] = []
        threads[t].append(n["id"])

    # Positions
    x_pos, y_pos = {}, {}
    thread_x = 0
    for thread_name, node_ids in sorted(threads.items()):
        for i, nid in enumerate(node_ids):
            x_pos[nid] = thread_x + i * 1.5
            y_pos[nid] = -depths[nid] * 1.5
        thread_x += len(node_ids) * 1.5 + 2

    # Edges
    edge_x, edge_y = [], []
    for n in nodes:
        pid = n.get("parent")
        if pid and pid in id_to_idx:
            edge_x.extend([x_pos[pid], x_pos[n["id"]], None])
            edge_y.extend([y_pos[pid], y_pos[n["id"]], None])

    fig = go.Figure()

    if edge_x:
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(color="#475569", width=1.5),
            hoverinfo="none", showlegend=False,
        ))

    # Node positions
    node_x = [x_pos[n["id"]] for n in nodes]
    node_y = [y_pos[n["id"]] for n in nodes]

    # Colors by outcome
    node_colors = []
    for n in nodes:
        outcome = n.get("outcome", "neutral")
        if outcome == "positive":
            node_colors.append("#22c55e")
        elif outcome == "negative":
            node_colors.append("#ef4444")
        else:
            node_colors.append("#64748b")

    # Hover text
    hover_texts = []
    for n in nodes:
        title = n.get("title", n.get("id", "?"))
        lines = [f"<b>{title}</b>"]
        if n.get("what"):
            lines.append(f"<b>What:</b> {n['what'][:120]}")
        if n.get("why"):
            lines.append(f"<b>Why:</b> {n['why'][:120]}")
        decision = n.get("decision", "?")
        outcome = n.get("outcome", "?")
        lines.append(f"<b>Outcome:</b> {outcome} | <b>Decision:</b> {decision}")
        if n.get("vs_baseline"):
            lines.append(f"<b>vs baseline:</b> {n['vs_baseline'][:80]}")
        result = n.get("result", {})
        if result:
            metrics_str = " | ".join(f"{k}={v}" for k, v in list(result.items())[:3])
            lines.append(f"<b>Metrics:</b> {metrics_str}")
        for insight in (n.get("insights") or [])[:2]:
            lines.append(f"  - {insight[:80]}")
        hover_texts.append("<br>".join(lines))

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode="markers",
        marker=dict(size=18, color=node_colors, line=dict(color="#334155", width=1.5)),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        showlegend=False,
    ))

    # Thread labels
    for thread_name, node_ids in sorted(threads.items()):
        avg_x = sum(x_pos[nid] for nid in node_ids) / len(node_ids)
        max_y = max(y_pos[nid] for nid in node_ids)
        fig.add_annotation(
            x=avg_x, y=max_y + 1,
            text=_readable_name(thread_name),
            showarrow=False,
            font=dict(size=11, color="#94a3b8"),
        )

    fig.update_layout(
        title=dict(text=f"Knowledge Graph ({len(nodes)} nodes)", font=dict(size=14)),
        template="plotly_dark", height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hoverlabel=dict(bgcolor="#1e293b", font_size=12, font_color="#e2e8f0", align="left"),
    )

    return fig


# ─── Main Dashboard ──────────────────────────────────────────────────────────


def main():
    st.set_page_config(
        page_title="Artificial Agent Lab",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    .thread-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
        border-left: 4px solid;
    }
    .thread-active { border-left-color: #3b82f6; }
    .thread-concluded { border-left-color: #22c55e; }
    .thread-abandoned { border-left-color: #64748b; }
    .lab-header {
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Sidebar ─────────────────────────────────────────────────────────────

    sessions = get_sessions()

    with st.sidebar:
        st.title("Research Lab")

        if not sessions:
            st.warning("No sessions found. Run `scripts/init_session.py`.")
            return

        session_names = [s.name for s in sessions]
        selected_idx = st.selectbox(
            "Session", range(len(session_names)),
            format_func=lambda i: session_names[i],
        )
        session_dir = sessions[selected_idx]
        proposal = load_proposal(session_dir)

        st.markdown("---")
        st.markdown(f"**Question:** {proposal['question']}")
        if proposal.get("hypothesis"):
            st.markdown(f"**Hypothesis:** {proposal['hypothesis']}")
        st.markdown(f"**Metric:** `{proposal['metric']}`")
        st.markdown(f"**Hardware:** `{proposal['hardware']}`")
        st.markdown(f"**Investigators:** {proposal['investigators']}")

        st.markdown("---")

        # Stop/Resume
        stopped = is_stopped(session_dir)
        if stopped:
            st.error("Research STOPPED")
            if st.button("Resume", type="primary", use_container_width=True):
                resume_session(session_dir)
                st.rerun()
        else:
            st.success("Research ACTIVE")
            if st.button("Stop Research", type="secondary", use_container_width=True):
                stop_session(session_dir)
                st.rerun()

        st.markdown("---")
        refresh = st.slider("Refresh (s)", 5, 60, REFRESH_INTERVAL)

    # ── Load Data ───────────────────────────────────────────────────────────

    results = load_results(session_dir)
    threads = load_threads(session_dir)
    metric_key = proposal["metric"]
    paper = check_paper(session_dir)
    kg_nodes = load_knowledge_graph(session_dir)

    # ── Header Metrics ──────────────────────────────────────────────────────

    total = len(results)
    kept = [r for r in results if (r.get("decision") or r.get("status", "")).upper() == "KEEP"]
    crashed = [r for r in results if (r.get("status") or "").upper() in ("CRASH", "ERROR", "TIMEOUT")]
    discarded = [r for r in results if (r.get("decision") or r.get("status", "")).upper() == "DISCARD"]

    best_value = None
    best_run = None
    if kept:
        # Filter out inf/extreme values (e.g., PF=999 from zero-loss trades with few trades)
        reasonable = [r for r in kept if _clamp_metric(
            (r.get("primary_value") or r.get("metrics", {}).get(metric_key, 0)), cap=100
        ) < 100]
        if reasonable:
            best_entry = max(reasonable, key=lambda r: (r.get("primary_value") or r.get("metrics", {}).get(metric_key)) or float("-inf"))
        else:
            best_entry = max(kept, key=lambda r: (r.get("primary_value") or r.get("metrics", {}).get(metric_key)) or float("-inf"))
        best_value = best_entry.get("primary_value") or best_entry.get("metrics", {}).get(metric_key)
        best_run = best_entry.get("run_id")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Experiments", total)
    with col2:
        st.metric("Kept / Discarded", f"{len(kept)} / {len(discarded)}")
    with col3:
        active_threads = sum(1 for t in threads if t["status"] == "active")
        st.metric("Threads", f"{len(threads)} ({active_threads} active)")
    with col4:
        if best_value is not None:
            st.metric(f"Best {metric_key}", f"{best_value:.2f}", help=f"From {best_run}")
        else:
            st.metric(f"Best {metric_key}", "—")
    with col5:
        st.metric("Knowledge Nodes", len(kg_nodes))

    # ── Count experiments per thread from results.jsonl ───────────────────

    thread_exp_counts = {}
    thread_keeps = {}
    for r in results:
        t = r.get("thread") or ""
        # Also try extracting thread from run_id prefix (e.g., "001_exp01" → "001")
        if not t and r.get("run_id"):
            prefix = r["run_id"].split("_")[0]
            for thread in threads:
                if thread["name"].startswith(prefix):
                    t = thread["name"]
                    break
        thread_exp_counts[t] = thread_exp_counts.get(t, 0) + 1
        decision = (r.get("decision") or r.get("status", "")).upper()
        if decision == "KEEP":
            thread_keeps[t] = thread_keeps.get(t, 0) + 1

    # ── Threads + Chart ─────────────────────────────────────────────────────

    threads_col, chart_col = st.columns([2, 3])

    with threads_col:
        st.markdown('<div class="lab-header">Research Threads</div>', unsafe_allow_html=True)

        if not threads:
            st.info("Waiting for PI to open threads...")
        else:
            for t in threads:
                status = t["status"]
                css_class = f"thread-{status}" if status in ("active", "concluded", "abandoned") else "thread-active"
                status_labels = {"active": "Active", "concluded": "Done", "abandoned": "Abandoned"}
                label = status_labels.get(status, status)

                readable = _readable_name(t["name"])
                hypothesis = t["hypothesis"][:90] if t["hypothesis"] else "No hypothesis"

                # Use results.jsonl count (ground truth), fall back to log count
                exp_count = thread_exp_counts.get(t["name"], t["experiment_count"])
                keep_count = thread_keeps.get(t["name"], 0)
                findings = " · Has findings" if t["has_findings"] else ""

                exp_str = f"{exp_count} exp ({keep_count} kept)" if keep_count else f"{exp_count} exp"

                st.markdown(f"""<div class="thread-card {css_class}">
<strong style="color:#e2e8f0;">{readable}</strong>
<span style="float:right;color:#94a3b8;font-size:12px;">{label} · {exp_str}{findings}</span>
<br><span style="color:#94a3b8;font-size:13px;">{hypothesis}</span>
</div>""", unsafe_allow_html=True)

        # Paper
        if paper["exists"]:
            st.markdown('<div class="lab-header" style="margin-top:12px;">Paper</div>', unsafe_allow_html=True)
            cols = []
            if paper["has_pdf"]:
                cols.append("PDF ready")
            elif paper["exists"]:
                cols.append("LaTeX written")
            if paper["has_notebook"]:
                cols.append("Notebook")
            cols.append(f"{paper['reviews']} reviews")
            st.markdown(" · ".join(cols))

            # Download buttons
            if paper["has_pdf"]:
                pdf_path = session_dir / "paper" / "paper.pdf"
                st.download_button(
                    "Download Paper (PDF)",
                    data=pdf_path.read_bytes(),
                    file_name="paper.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

    with chart_col:
        if results:
            st.plotly_chart(build_metric_chart(results, metric_key), use_container_width=True)
        else:
            st.info("Waiting for first experiment results...")

    # ── Knowledge Graph ─────────────────────────────────────────────────────

    if kg_nodes:
        st.plotly_chart(build_knowledge_graph_chart(kg_nodes), use_container_width=True)

        selected_node = st.selectbox(
            "Inspect node",
            options=[n["id"] for n in kg_nodes],
            format_func=lambda nid: f"{_readable_name(nid)}: {next((n.get('title','') for n in kg_nodes if n['id']==nid), '')}",
            key="kg_node_select",
        )
        if selected_node:
            node = next((n for n in kg_nodes if n["id"] == selected_node), None)
            if node:
                with st.expander(f"{_readable_name(node['id'])} — {node.get('title', '')}", expanded=True):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**What:** {node.get('what', 'N/A')}")
                        st.markdown(f"**Why:** {node.get('why', 'N/A')}")
                        st.markdown(f"**How:** {node.get('how', 'N/A')}")
                    with col_b:
                        outcome = node.get("outcome", "?")
                        decision = node.get("decision", "?")
                        st.markdown(f"**Outcome:** {outcome} | **Decision:** {decision}")
                        st.markdown(f"**vs baseline:** {node.get('vs_baseline', 'N/A')}")
                        result = node.get("result", {})
                        if result:
                            st.json(result)
                    if node.get("insights"):
                        st.markdown("**Insights:**")
                        for ins in node["insights"]:
                            st.markdown(f"- {ins}")
                    if node.get("worth_exploring_next"):
                        st.markdown("**Worth exploring next:**")
                        for exp in node["worth_exploring_next"]:
                            st.markdown(f"- {exp}")
                    if node.get("failures_and_warnings"):
                        st.markdown("**Warnings:**")
                        for w in node["failures_and_warnings"]:
                            st.markdown(f"- {w}")

    # ── Research Log ────────────────────────────────────────────────────────

    with st.expander("PI Research Log", expanded=False):
        log_text = load_research_log(session_dir)
        if log_text:
            st.markdown(log_text)
        else:
            st.info("No research log entries yet.")

    # ── Results Table ───────────────────────────────────────────────────────

    with st.expander("Full Results Table", expanded=False):
        if results:
            import pandas as pd
            rows = []
            for r in results:
                decision = r.get("decision") or r.get("status", "?")
                metrics = r.get("metrics", {})
                row = {
                    "run_id": r.get("run_id"),
                    "thread": _readable_name(r.get("thread", "")) if r.get("thread") else "",
                    "decision": decision,
                    metric_key: metrics.get(metric_key, r.get("primary_value")),
                    "description": (r.get("description") or "")[:60],
                }
                # Add all metrics dynamically
                for k, v in metrics.items():
                    if k != metric_key and k not in ("all_evals",):
                        row[k] = v
                rows.append(row)
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Auto-refresh ────────────────────────────────────────────────────────
    time.sleep(refresh)
    st.rerun()


if __name__ == "__main__":
    main()
