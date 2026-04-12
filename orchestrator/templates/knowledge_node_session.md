# Session Knowledge Node Schema

The PI appends one JSON line to the repo-level `knowledge_graph.jsonl` when a research session concludes. This builds the lab's long-term memory across all research sessions.

## Schema

```json
{
  "id": "2026-04-07_benchmark",
  "timestamp": "2026-04-07T18:30:00",
  "title": "Positive return on OOD eval with PPO",
  "question": "Can we achieve positive total return on out-of-distribution evaluation data?",
  "hypothesis": "Reward shaping and hyperparameter tuning can produce policies that generalize beyond training distribution",

  "outcome": "positive",
  "success_criteria_met": true,

  "best_result": {
    "run_id": "001_exp03",
    "total_return_pct": 12.5,
    "sharpe_ratio": 0.8,
    "description": "Sortino-style asymmetric reward with early stopping at 3M frames"
  },

  "threads_summary": {
    "total": 4,
    "concluded": 3,
    "abandoned": 1,
    "best_thread": "001_reward_shaping"
  },

  "experiments_summary": {
    "total": 10,
    "keep": 4,
    "discard": 5,
    "crash": 1
  },

  "key_insights": [
    "Training instability after 2M frames — early stopping is critical for this dataset",
    "Asymmetric reward penalties improve OOD generalization significantly",
    "Raw OHLCV features sufficient — adding indicators didn't help",
    "50% utilization on local leaves room for development work"
  ],

  "what_didnt_work": [
    "Drawdown penalty alone — insufficient without reward asymmetry",
    "Higher entropy coefficient — caused learning collapse",
    "Feature engineering with RSI/MACD — no improvement over raw OHLCV"
  ],

  "recommended_for_future": [
    "Always use early stopping — monitor training curves for peak performance",
    "Asymmetric reward shaping is a strong baseline for futures trading",
    "Consider curriculum learning across market regimes"
  ],

  "tags": ["ppo", "reward-shaping", "btcusdt", "ood-generalization"]
}
```
