# Thread Brief: [THREAD_NAME]

## Hypothesis

What do we expect to find and why?

## Scope

What specific changes should the investigator explore?
Be concrete — list 3-5 specific things to try.

1. ...
2. ...
3. ...

## Experiment Budget

How many experiments before the investigator should report back.

- **Minimum**: 3 experiments (enough to see a trend)
- **Maximum**: 8 experiments (avoid tunnel vision)
- **Report early if**: primary metric improves by >20% over baseline, or 3 consecutive failures

## Success Criteria

How do we know this thread succeeded?
E.g., "Sharpe > 1.8 with B&H R² < 0.7" or "identify which feature matters most"

## Baseline

The current best result to beat:
- Run: [run_id]
- Primary metric: [value]
- Description: [what produced it]

## Compute Node

Which node to run experiments on. Read `compute_nodes/<node>.md` for connection details, run command, and constraints.

- **Node**: [node name, e.g., local or my-gpu-server]
- **Utilization**: [from the node file, e.g., 50% — scale resources accordingly]

## Constraints

Any restrictions on what the investigator may or may not change.
