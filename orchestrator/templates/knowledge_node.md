# Knowledge Node Schema

Append one JSON line to `knowledge_graph.jsonl` after EVERY experiment. This is the lab's memory — future investigators and the PI read it to understand what's been explored and what's worth trying next.

## Required Fields

```json
{
  "id": "001_exp03",
  "thread": "001_reward_shaping",
  "parent": "001_exp01",
  "timestamp": "2026-04-07T16:30:00",

  "title": "Sortino-style asymmetric reward",

  "what": "Changed reward_transform.py to penalize negative returns 2x more than positive: r = log_return * (2.0 if negative else 1.0) - 0.2*|unrealized_pnl|",

  "why": "The baseline v10 reward treats gains and losses symmetrically. In trading, avoiding losses matters more than capturing gains (asymmetric risk). Penalizing downside should teach the agent to cut losses faster while still capturing trends.",

  "how": "Modified RewardTransform._step() to multiply log_return by 2.0 when negative, 1.0 when positive. Kept the unrealized PnL penalty at 0.2. Trained with default config (10M frames, seed=42, num_envs=2500) on local node.",

  "outcome": "positive",

  "result": {
    "total_return_pct": 12.5,
    "sharpe_ratio": 0.8,
    "max_drawdown_pct": 18.2,
    "num_trades": 87,
    "buy_hold_r_squared": 0.31
  },

  "decision": "KEEP",

  "vs_baseline": "+31.4% total_return_pct improvement over parent (001_exp01: -18.87%)",

  "insights": [
    "Asymmetric penalty produces tighter drawdowns (18.2% vs 30.7% baseline)",
    "First configuration to achieve positive return on OOD eval data",
    "Trade count dropped from 146 to 87 — agent is more selective",
    "B&H R² still low (0.31) — not a buy-and-hold mimic"
  ],

  "failures_and_warnings": [
    "Training still shows instability after 7M frames — early stopping needed"
  ],

  "worth_exploring_next": [
    "Try asymmetry factor of 3.0 or 4.0 (stronger downside penalty)",
    "Combine with drawdown penalty for double protection",
    "Test with early stopping at 3M frames to avoid overtraining"
  ],

  "tags": ["reward", "asymmetric", "improvement", "positive-return"]
}
```

## Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique ID: `{thread_num}_exp{N}` |
| `thread` | yes | Thread directory name |
| `parent` | yes | ID of the experiment this built on (null for baselines) |
| `timestamp` | yes | ISO timestamp |
| `title` | yes | Short descriptive title |
| `what` | yes | What exactly was changed — file names, code changes, config values |
| `why` | yes | The reasoning — why this change was expected to help |
| `how` | yes | How it was implemented — specific code changes, training config, compute node |
| `outcome` | yes | `"positive"`, `"negative"`, or `"neutral"` — did it improve on the parent? |
| `result` | yes | Key metrics dict |
| `decision` | yes | `"KEEP"` or `"DISCARD"` |
| `vs_baseline` | yes | Comparison to parent — quantify the delta |
| `insights` | yes | List of things learned — what does this result tell us? |
| `failures_and_warnings` | yes | What went wrong or needs caution — even in successful experiments |
| `worth_exploring_next` | yes | Specific follow-up ideas this experiment suggests |
| `tags` | yes | Short labels for filtering: `["reward", "architecture", "improvement", "degenerate"]` |

## Rules

- **Every experiment gets a node** — KEEP, DISCARD, or CRASH
- **Be specific in `what` and `how`** — another investigator should be able to reproduce this from the node alone
- **`insights` is the most important field** — what did you LEARN, not just what happened
- **`worth_exploring_next` feeds future threads** — the PI reads these when deciding what to investigate next
- **`failures_and_warnings` even for successful experiments** — no experiment is perfect, note the caveats
- **`outcome` is relative to parent**, not absolute — a KEEP with negative return but better than parent is still `"positive"`
