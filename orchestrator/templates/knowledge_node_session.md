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
    "run_id": "001_exp05_phd_1",
    "primary_metric_value": 85.69,
    "description": "Augmentation + BatchNorm + CosineAnnealing + weight decay"
  },

  "threads_summary": {
    "total": 2,
    "concluded": 2,
    "abandoned": 0,
    "best_thread": "001_augmentation"
  },

  "experiments_summary": {
    "total": 10,
    "keep": 4,
    "discard": 5,
    "crash": 1
  },

  "key_insights": [
    "Data augmentation + BatchNorm + cosine annealing stack multiplicatively",
    "Learning rate 0.1 works better than 0.01 when BatchNorm is present",
    "Weight decay provides small but consistent improvement"
  ],

  "what_didnt_work": [
    "High dropout (0.5) — too aggressive for this model size",
    "Training beyond 50 epochs — accuracy plateaus"
  ],

  "recommended_for_future": [
    "Always use early stopping — monitor training curves for peak performance",
    "Asymmetric reward shaping is a strong baseline for futures trading",
    "Consider curriculum learning across market regimes"
  ],

  "tags": ["ppo", "reward-shaping", "btcusdt", "ood-generalization"]
}
```
