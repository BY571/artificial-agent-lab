# Knowledge Node Schema

Append one JSON line to `knowledge_graph.jsonl` after EVERY experiment. This is the lab's memory — future investigators and the PI read it to understand what's been explored and what's worth trying next.

## Required Fields

```json
{
  "id": "001_exp03_phd_1",
  "thread": "001_augmentation",
  "parent": "001_exp02_phd_1",
  "timestamp": "2026-04-12T14:30:00",

  "title": "Added BatchNorm after each conv layer",

  "what": "Added nn.BatchNorm2d(channels) after each Conv2d in model.py, before the ReLU activation.",

  "why": "Experiment 02 added augmentation (+1% accuracy). BatchNorm stabilizes training and often adds 2-5% on CIFAR-10. Combined with augmentation it should compound.",

  "how": "Modified model.py: inserted BatchNorm2d after each of the 3 conv layers. Kept all other settings from exp02 (augmentation, 10 epochs, lr=0.01, seed=42).",

  "outcome": "positive",

  "result": {
    "test_accuracy": 76.76,
    "train_accuracy": 78.5,
    "test_loss": 0.68
  },

  "decision": "KEEP",

  "vs_baseline": "+2.5% accuracy over parent (001_exp02: 74.25%)",

  "insights": [
    "BatchNorm adds consistent improvement on top of augmentation",
    "Training is more stable — loss curve is smoother",
    "Still undertrained at 10 epochs — accuracy likely higher with more epochs"
  ],

  "failures_and_warnings": [
    "10 epochs may not be enough to see full benefit of BatchNorm"
  ],

  "worth_exploring_next": [
    "Train for 30-50 epochs with cosine annealing LR schedule",
    "Try higher initial learning rate (0.1) now that BatchNorm stabilizes training",
    "Add dropout before the classifier to reduce overfitting"
  ],

  "tags": ["architecture", "batchnorm", "improvement"]
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
