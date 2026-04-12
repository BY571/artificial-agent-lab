# Research Lab

A general-purpose autonomous research framework. Drop your code, papers, and notes into a session, write a research proposal, and AI agents run experiments indefinitely — systematically improving results and writing a paper when done.

## How It Works

```
You provide source material + research proposal
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  PI Agent (Principal Investigator)                   │
│                                                      │
│  Reads proposal + sources → opens threads →          │
│  dispatches investigators → reviews findings →       │
│  generates new ideas → writes research_log.md        │
│                                                      │
│  ┌─────────────────┐    ┌─────────────────┐          │
│  │ Investigator A   │    │ Investigator B   │         │
│  │ (phd_1)          │    │ (phd_2)          │         │
│  │                  │    │                  │         │
│  │ Reads sources    │    │ Reads sources    │         │
│  │ Runs experiments │    │ Runs experiments │         │
│  │ Uses skills      │    │ Uses skills      │         │
│  │ Reports findings │    │ Reports findings │         │
│  └────────┬─────────┘    └────────┬─────────┘         │
│           │ findings.md           │ findings.md       │
│           └───────────┬───────────┘                   │
│                       ▼                               │
│           PI reviews, synthesizes,                    │
│           generates new hypotheses,                   │
│           opens next thread or writes paper            │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Setup

```bash
git clone git@github.com:BY571/research-lab.git
cd research-lab
pip install claude-agent-sdk streamlit plotly pandas
```

### 2. Configure Compute

Create `compute_nodes/local.md` (already included) or add remote nodes using `compute_nodes/TEMPLATE.md`.

### 3. Create a Research Session

```bash
python scripts/init_session.py --name "my-research" --sources /path/to/my/code
```

This creates `autoresearch/2026-04-12_my-research/` with:
- `sources/` — your code, papers, notes copied here
- `research_proposal.md` — skeleton to fill in
- Empty `results.jsonl`, `knowledge_graph.jsonl`, `research_log.md`

### 4. Add Source Material

Drop everything the lab needs into `sources/`:

```bash
cp my_training_script.py autoresearch/2026-04-12_my-research/sources/
cp reference_paper.pdf autoresearch/2026-04-12_my-research/sources/
cp colleagues_notes.md autoresearch/2026-04-12_my-research/sources/
```

### 5. Write the Research Proposal

Edit `autoresearch/2026-04-12_my-research/research_proposal.md` — fill in the question, hypothesis, success criteria, and starting ideas. Reference the source material.

### 6. Launch

Open Claude Code and say: **"Let's go"**

Or directly:
```bash
python -m orchestrator.run autoresearch/2026-04-12_my-research/
```

### 7. Monitor

```bash
streamlit run dashboard.py
```

### 8. Stop & Get Paper

```bash
touch autoresearch/2026-04-12_my-research/.stop_autoresearch
```

The PI finishes the current thread, writes a LaTeX paper, and exits. Merge results:
```bash
git checkout main && git merge research/2026-04-12_my-research
```

## Session Structure

```
autoresearch/2026-04-12_my-research/
├── research_proposal.md     # Your research brief (read-only)
├── sources/                 # Your code, papers, notes, data
│   ├── train.py             #   (whatever you provide)
│   ├── reference.pdf
│   └── notes.md
├── research_log.md          # PI's strategic log
├── results.jsonl            # All experiment metrics
├── knowledge_graph.jsonl    # Knowledge nodes per experiment
├── threads/                 # Research threads
│   ├── 001_hypothesis_a/
│   │   ├── brief.md         # PI's assignment
│   │   ├── log.md           # Investigator's diary
│   │   ├── findings.md      # Results report
│   │   └── status.md        # active | concluded | abandoned
│   └── 002_hypothesis_b/
├── paper/                   # Final paper (written at end)
│   ├── paper.tex
│   ├── paper.pdf
│   ├── reproduce.ipynb
│   ├── figures/
│   └── review_N.md
└── runs/                    # Per-run artifacts
```

## Research Protocol

### Thread Lifecycle

```
PI opens thread          PI reviews findings       PI decides
     │                        │                        │
     ▼                        ▼                        ▼
 brief.md ──→ Investigator ──→ findings.md ──→ conclude / continue / abandon
              runs experiments                 update status.md
```

### Knowledge Graph

Every experiment produces a knowledge node with: what was tried, why, how, what happened, what was learned, and what to explore next. The PI and investigators read the graph before planning — no repeated failures, builds on discoveries.

### Paper Writing

When research concludes (budget expires or user stops), the PI dispatches an investigator to write a LaTeX paper, reviews it, and iterates for N rounds.

## Design Principles

- **Source-driven**: Drop your code/papers/notes → the lab reads them and researches
- **Hierarchical**: PI thinks strategically, investigators execute, knowledge compounds
- **Branch-per-session**: Each research session is isolated on its own git branch
- **Append-only results**: results.jsonl and knowledge_graph.jsonl survive crashes
- **Unlimited exploration**: With unlimited budget, the PI generates new ideas forever
