<p align="center">
  <img src="docs/images/logo.png" alt="Artificial Agent Lab" width="500">
</p>

<p align="center">
  An autonomous research lab powered by AI agents. Drop your code, papers, and notes — a PI agent and PhD investigators run experiments, build a knowledge graph, and write a paper.
</p>

---

## How It Works

You provide four things:
1. **Source material** — code, papers, notes, data (anything the lab should read and work with)
2. **Skills** — domain knowledge that guides how agents research and write (optional but recommended)
3. **Compute nodes** — machines the lab can run experiments on (local, remote GPUs, clusters)
4. **Research proposal** — what to investigate, how to measure success

The lab does the rest:

```
                 ┌───────────────────────────────────────┐
                 │  PI Agent (Principal Investigator)    │
sources/         │                                       │
skills/    ───►  │  Reads everything → opens threads →   │
proposal.md      │  dispatches PhDs → reviews findings   │
compute_nodes/   │  → generates new ideas → repeat       │
                 │                                       │
                 │  ┌──────────┐      ┌──────────┐       │
                 │  │  phd_1   │      │  phd_2   │       │
                 │  │          │      │          │       │
                 │  │ Runs exp │      │ Runs exp │       │
                 │  │ on nodeA │      │ on nodeB │       │
                 │  └────┬─────┘      └────┬─────┘       │
                 │       └───────┬─────────┘             │
                 │               ▼                       │
                 │     PI reviews findings,              │
                 │     opens next thread                 │
                 │               │                       │
                 │               ▼                       │
                 │     When done: writes paper           │
                 └───────────────────────────────────────┘
                                 │
                                 ▼
                 results.jsonl + knowledge_graph.jsonl
                 + paper/paper.pdf + reproduce.ipynb
```

## Quick Start

### 1. Install

```bash
git clone git@github.com:BY571/artificial-agent-lab.git
cd artificial-agent-lab

# Install dependencies
uv sync
# Or without uv:
pip install -r requirements.txt
```

Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-agent-sdk).

### 2. Define Your Compute Nodes

Each machine you want the lab to use needs a file in `compute_nodes/`. A `local.md` is included by default.

To add a remote machine, copy the template:

```bash
cp compute_nodes/TEMPLATE.md compute_nodes/my-gpu-server.md
```

Then fill in:

```markdown
# my-gpu-server

## Connection
ssh user@192.168.1.100

## Working Directory
~/projects/artificial-agent-lab

## Hardware
NVIDIA A100 80GB, 64 CPU cores, 256GB RAM

## Environment Setup
git clone ... && cd artificial-agent-lab && uv sync

## Run Command
uv run python <script> [args]

## Utilization
100%

## Constraints
- Max 2 parallel training processes
- Always use --no-sync if uv lock differs from local
```

The number of investigators is automatically set to match the number of compute nodes (or you can override it manually in the research proposal).

### 3. Create a Research Session

```bash
uv run python scripts/init_session.py --name "my-research" --sources /path/to/my/code
```

This creates `autoresearch/<date>_my-research/` with:

```
autoresearch/2026-04-12_my-research/
├── research_proposal.md     # ← You fill this in
├── sources/                 # ← Your code, papers, notes (auto-copied from --sources)
├── skills/                  # ← Domain knowledge files (you add these)
├── threads/                 # Research threads (created by the PI)
├── results.jsonl            # Experiment results (append-only)
├── knowledge_graph.jsonl    # What was tried, learned, worth exploring next
├── research_log.md          # PI's strategic decisions
└── runs/                    # Per-run artifacts
```

### 4. Add Source Material

Drop everything the lab needs into `sources/`:

```bash
# Code to experiment with
cp train.py model.py config.yaml autoresearch/<session>/sources/

# Reference papers
cp reference_paper.pdf autoresearch/<session>/sources/

# Colleague's notes or preliminary results
cp findings_so_far.md autoresearch/<session>/sources/

# Data files or pointers
cp dataset_readme.md autoresearch/<session>/sources/
```

Investigators read everything in `sources/` before starting experiments.

### 5. Add Skills (Recommended)

Skills are `.md` files with domain knowledge that get injected into agent prompts. They guide **how** agents work — both during research AND paper writing.

```bash
# Research skills — domain-specific patterns and best practices
cp pytorch-training.md autoresearch/<session>/skills/
cp evaluation-protocol.md autoresearch/<session>/skills/

# Paper writing skills — how to create good visualizations, structure, etc.
cp scientific-plotting.md autoresearch/<session>/skills/
cp latex-conventions.md autoresearch/<session>/skills/
```

Example skill file (`skills/evaluation-protocol.md`):
```markdown
# Evaluation Protocol

## Metrics
Always report: accuracy, F1, precision, recall.
Use macro-averaging for multi-class.

## Validation
- 3-fold cross-validation minimum
- Hold out last 20% of data chronologically (no random split for time series)
- Always report mean ± std across folds

## Plots
- Use seaborn with the "paper" context for publication-ready figures
- Save as PDF, not PNG
- Always include error bars or confidence intervals
```

Skills are optional but highly recommended — they prevent investigators from making domain-specific mistakes and produce better papers.

### 6. Write the Research Proposal

Edit `autoresearch/<session>/research_proposal.md`:

```markdown
# Research Proposal: my-research

## Research Question
Can we improve the model's F1 score on the held-out test set?

## Background
Current best: F1=0.72 using a basic CNN. See sources/baseline_results.md.

## Hypothesis
Adding attention layers and tuning the learning rate schedule
should improve F1 to >0.80.

## Success Criteria
F1 > 0.80 on held-out test, confirmed across 3 seeds.

## Starting Ideas
1. Add self-attention after the conv layers
2. Try cosine annealing LR schedule
3. Increase model depth (4 → 8 layers)
4. Data augmentation (random crops, flips)

## Configuration
### Primary Metric
**f1_score** (higher is better)
### Hardware
local+my-gpu-server
### Investigators
auto
### Seeds
3
### Research Budget
4h
### Web Search
true
### Paper Review Rounds
3
```

### 7. Launch

```bash
uv run python -m orchestrator.run autoresearch/<session>/
```

Or open Claude Code in the repo — it reads `CLAUDE.md`, validates your proposal, and starts the orchestrator automatically.

### 8. Monitor

```bash
uv run streamlit run dashboard.py
```

The dashboard shows:
- **Thread cards** — status, hypothesis, experiment count per thread
- **Metric progression** — primary metric over time
- **Knowledge graph** — interactive visualization of what was explored
- **Paper download** — when the paper is ready

### 9. Stop & Get Your Paper

Click "Stop Research" in the dashboard, or:

```bash
touch autoresearch/<session>/.stop_autoresearch
```

The PI wraps up the current thread and writes a LaTeX paper with reproducibility notebook. When done, merge back to main:

```bash
git checkout main
git merge research/<session-name>
```

## What You Get

After a session, your `autoresearch/<session>/` contains:

| Output | Description |
|--------|-------------|
| `paper/paper.pdf` | LaTeX research paper with figures |
| `paper/reproduce.ipynb` | Notebook to reproduce key results |
| `results.jsonl` | Every experiment with metrics |
| `knowledge_graph.jsonl` | What was tried, why, what was learned |
| `research_log.md` | PI's strategic reasoning |
| `threads/*/findings.md` | Per-thread analysis and recommendations |

## Key Concepts

### Sources vs Skills

| | Sources (`sources/`) | Skills (`skills/`) |
|---|---|---|
| **What** | Code, papers, data, notes | Domain knowledge, best practices |
| **Purpose** | What to research | How to research (and write papers) |
| **Read by** | Investigators | PI + Investigators (injected into prompts) |
| **Examples** | `train.py`, `paper.pdf`, `data/` | `pytorch-patterns.md`, `plotting-guide.md` |

### Compute Nodes

Each machine the lab can use needs a file in `compute_nodes/`:

| Field | Purpose |
|-------|---------|
| Connection | How to reach it (`ssh user@host` or "local") |
| Hardware | What's available (GPU, RAM) |
| Utilization | How much the lab may use (50% = shared machine) |
| Run Command | How to execute experiments |
| Constraints | Parallelism limits, special flags |

Investigators are auto-assigned one per node. With `hardware: local+gpu1+gpu2`, the lab creates `phd_1`, `phd_2`, `phd_3` running in parallel.

### Knowledge Graph

Every experiment produces a knowledge node:
- **what** was changed and **why**
- **outcome**: positive, negative, or neutral
- **insights**: what was learned
- **worth_exploring_next**: ideas for follow-up

The PI and investigators read the graph before planning — avoiding repeated failures and building on discoveries.

### Research Budget

Controls how long the lab researches before writing the paper. Set in the research proposal:

| Setting | Behavior |
|---------|----------|
| `4h` | Research for 4 hours, then write paper. PI gets a soft warning at 75% (3h) and hard cutoff at 100%. |
| `90m` | Research for 90 minutes. |
| `unlimited` | Research indefinitely until you stop it. The PI cannot end on its own — only your stop signal triggers the paper phase. |

The budget clock **pauses** during API rate limit waits, so you get the full research time you requested.

When the budget expires (or you stop it), the PI transitions to the paper writing phase automatically.

### API Rate Limits

When the Claude API rate limit is hit, the lab handles it based on the `rate_limit_policy` in your research proposal:

| Policy | Behavior |
|--------|----------|
| `wait` (default) | Pause research, poll every 5 minutes until the limit resets, then resume. The research budget clock pauses during the wait. |
| `stop` | End the research phase and transition to paper writing. |

With `wait`, the lab survives overnight rate limits — it pauses, waits for reset, and picks up exactly where it left off. No lost progress.

## Design Principles

- **Source-driven**: Drop your materials → the lab reads them and researches
- **Skill-augmented**: Domain knowledge guides both research AND paper writing
- **Hierarchical**: PI thinks strategically, investigators execute
- **Branch-per-session**: Each session is isolated on its own git branch
- **Knowledge compounds**: The graph prevents repeated mistakes across threads
- **Append-only**: results.jsonl and knowledge_graph.jsonl survive crashes
