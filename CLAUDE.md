# CLAUDE.md — Research Lab Startup Protocol

## What This Is

A general-purpose autonomous research lab. A PI agent manages research threads and dispatches Investigator agents who run experiments, analyze results, and write papers. You are the **startup agent** — validate that everything is ready and launch.

## When the User Says "Let's Go"

Run the pre-flight checklist. If everything passes, start the orchestrator.

---

## Pre-Flight Checklist

### 1. Find the Session

```bash
ls -d autoresearch/*/
```

If no session exists:
```bash
python scripts/init_session.py --name "<name>" --sources "<path-to-source-material>"
```

### 2. Check Source Material

Verify `autoresearch/<session>/sources/` has content — code, papers, notes, data. The investigators need this context.

### 3. Validate the Research Proposal

Read `autoresearch/<session>/research_proposal.md` and verify ALL fields are filled in:

| Field | Required |
|-------|----------|
| Research question | Yes — concrete question |
| Background | Yes — what's already known |
| Hypothesis | Yes — expected outcome |
| Success criteria | Yes — measurable |
| Starting ideas | Yes — at least 2 |
| Source material | Yes — what's in sources/ |
| Primary metric | Yes — bold format |
| Hardware | Yes — matches compute_nodes/ |
| Investigators | Yes — integer |

### 4. Validate Compute Nodes

```bash
ls compute_nodes/<node>.md  # for each node in Hardware field
```

### 5. Validate Git State

Must be on main/master with clean working tree for new sessions.

### 6. Check for Existing Results

If `results.jsonl` is non-empty, this is a **resume**.

---

## Launch

```bash
python -m orchestrator.run autoresearch/<session>/
```

This creates a `research/<session-name>` branch and starts the PI loop.

### Monitor

```bash
streamlit run dashboard.py
```

### Stop

```bash
touch autoresearch/<session>/.stop_autoresearch
```

The PI finishes the current thread, then enters paper writing phase.

When done, merge back:
```bash
git checkout main
git merge research/<session-name>
```

## Benchmark

When the user says "run the benchmark" or "let's benchmark":

```bash
bash benchmark/run_benchmark.sh
```

This runs the CIFAR-10 benchmark — a self-contained ML task that tests the full lab pipeline:
- Simple CNN baseline (~70% accuracy) → goal is >85%
- Includes training script, model, research proposal, and a PyTorch skill
- 1 hour budget, summary output, runs locally
- Tests: thread creation, experiments, knowledge graph, findings, summary writing

The benchmark directory has everything pre-configured. No setup needed beyond having PyTorch and torchvision installed.

## Structure

```
research-lab/
├── CLAUDE.md                      # This file
├── compute_nodes/                 # Compute node definitions
├── orchestrator/                  # PI + Investigator orchestration
│   ├── run.py                     #   Entry point
│   ├── pi.py                      #   PI agent loop
│   ├── config.py                  #   Proposal parser
│   ├── prompts/                   #   Agent protocols
│   │   ├── pi.md
│   │   └── investigator.md
│   └── templates/                 #   Thread document formats
├── dashboard.py                   # Live Streamlit dashboard
├── harness/                       # Shared utilities
│   └── runner.py
├── research_proposal_template.md
├── autoresearch/                  # Sessions
│   └── YYYY-MM-DD_name/
│       ├── research_proposal.md   #   Research brief (read-only)
│       ├── sources/               #   User-provided context material
│       ├── skills/               #   Domain knowledge (.md files)
│       ├── research_log.md        #   PI's strategic log
│       ├── threads/               #   Research threads
│       ├── results.jsonl          #   Experiment results
│       ├── knowledge_graph.jsonl  #   Knowledge nodes
│       └── paper/                 #   Final paper
├── knowledge_graph.jsonl          # Repo-level (across sessions)
├── benchmark/                     # Self-contained benchmark task
│   ├── sources/                   #   CNN + training script
│   ├── skills/                    #   PyTorch patterns
│   ├── research_proposal.md       #   Pre-written proposal
│   └── run_benchmark.sh           #   One-command launcher
└── scripts/
    └── init_session.py
```

## Conventions

- `research_proposal.md` is read-only for agents
- `results.jsonl` is append-only
- `sources/` is read-only for investigators (modify copies, not originals)
- Each session runs on its own `research/<name>` git branch
