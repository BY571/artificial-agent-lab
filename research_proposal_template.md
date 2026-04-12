# Research Proposal: [NAME]

## Research Question

<!-- What are you trying to learn, build, or improve? Be specific. -->

## Background

<!-- What do you already know? Link to source material in sources/. -->

## Hypothesis

<!-- What do you think will work and why? -->

## Success Criteria

<!-- How do we know the research succeeded? Be concrete and measurable. -->

## Starting Ideas

<!-- 3-5 concrete things to try first. Be specific. -->
1. ...
2. ...
3. ...

## Source Material

<!-- What's in the sources/ directory and how should investigators use it? -->
<!-- Examples: -->
<!--   - sources/train.py — the main training script to modify -->
<!--   - sources/paper.pdf — reference paper with the baseline approach -->
<!--   - sources/notes.md — colleague's preliminary findings -->
<!--   - sources/data/ — dataset to use for experiments -->

## Skills

<!-- Optional: domain knowledge files in skills/ that investigators should use. -->
<!-- Drop .md files with domain-specific patterns, APIs, conventions, or techniques. -->
<!-- These get loaded into both PI and investigator prompts automatically. -->
<!-- Examples: -->
<!--   - skills/pytorch-training.md — PyTorch training patterns and best practices -->
<!--   - skills/data-preprocessing.md — how to handle the specific data format -->
<!--   - skills/evaluation-protocol.md — how to properly evaluate results -->

## Configuration

### Primary Metric

<!-- The metric used for KEEP/DISCARD decisions -->
**metric_name** (higher is better)

### Hardware

<!-- Which compute node(s) to use. Must match a file in compute_nodes/. -->
local

### Investigators

<!-- How many parallel research threads to pursue. -->
<!-- If omitted or set to "auto", defaults to the number of compute nodes. -->
<!-- e.g., hardware: local+gpu1+gpu2 → 3 investigators automatically. -->
auto

### Seeds

<!-- How many seeds per experiment for validation -->
3

### Max Experiment Duration

<!-- How long a single experiment can run before timeout -->
1 hour

### Research Budget

<!-- Total wall-clock time for research (excluding paper writing). -->
<!-- Format: Nh or Nm. Set to "unlimited" for no limit. -->
4h

### Rate Limit Policy

<!-- What to do when the API rate limit is hit: wait or stop -->
wait

### Web Search

<!-- Allow investigators to search the web for papers and techniques -->
true

### Final Output

<!-- What to produce when research concludes. -->
<!-- Options: -->
<!--   paper — full LaTeX research paper with figures and reproduce notebook -->
<!--   summary — markdown summary of findings (faster, no LaTeX needed) -->
paper

### Paper Review Rounds

<!-- How many draft → review → revise cycles (only used if output = paper) -->
3

## Scope & Constraints

### What investigators may modify
- Any files in `sources/` that are meant to be experimented with
- New files in the session directory

### What investigators must NOT modify
- `research_proposal.md` — this file (read-only)
- `harness/` — shared utilities

### Rules
- Record every experiment in results.jsonl
- PI updates research_log.md after each thread review
- Investigators update their thread's log.md after each experiment
