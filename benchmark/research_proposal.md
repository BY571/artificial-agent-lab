# Research Proposal: cifar10-benchmark

## Research Question

How high can we push CIFAR-10 test accuracy using the provided CNN architecture as a starting point, with standard training techniques and no pretrained models?

## Background

The baseline is a 3-layer CNN (SimpleCNN in `sources/model.py`) trained with SGD for 10 epochs. It achieves ~70% test accuracy. State-of-the-art on CIFAR-10 is 99%+ with modern architectures, but even simple improvements (augmentation, scheduling, regularization, deeper networks) should push this baseline well past 85%.

The training script (`sources/train.py`) outputs metrics in `===METRICS_JSON===` format. CIFAR-10 auto-downloads via torchvision.

## Hypothesis

A combination of data augmentation (random crops, horizontal flips), learning rate scheduling (cosine annealing), regularization (dropout, weight decay), and architecture improvements (batch normalization, residual connections, more layers) should achieve >85% test accuracy.

## Success Criteria

- **test_accuracy > 85%** confirmed across 2 seeds
- No pretrained models — train from scratch
- Training time < 5 minutes per experiment (GPU auto-detected)

## Starting Ideas

1. **Data augmentation**: Add random horizontal flip and random crop with padding to the training transforms. This is the single highest-impact change for CIFAR-10.
2. **Learning rate schedule**: Replace constant LR with cosine annealing or step decay. Train for more epochs (30-50 instead of 10).
3. **Batch normalization**: Add BatchNorm after each conv layer. Stabilizes training and often improves accuracy 2-5%.
4. **Regularization**: Add dropout (0.25-0.5) before the classifier, and weight decay (1e-4) to the optimizer.
5. **Architecture depth**: Try a deeper network (5-6 conv layers) or add residual connections.

## Source Material

- `sources/train.py` — training script with CLI args (--epochs, --lr, --batch-size, --seed)
- `sources/model.py` — SimpleCNN baseline (3 conv layers, ~70% accuracy)
- Dataset: CIFAR-10 (auto-downloads via torchvision)

## Configuration

### Primary Metric
**test_accuracy** (higher is better)

### Hardware
local

### Investigators
auto

### Seeds
2

### Max Experiment Duration
10 minutes

### Research Budget
15m

### Rate Limit Policy
wait

### Web Search
false

### Final Output
summary

### Paper Review Rounds
1

## Scope & Constraints

### What investigators may modify
- `sources/train.py` — training loop, transforms, optimizer, scheduler
- `sources/model.py` — model architecture
- New files as needed

### What investigators must NOT modify
- `research_proposal.md` — this file
- Must keep the `===METRICS_JSON===` output format in train.py
- Must use CIFAR-10 (no other datasets)
- No pretrained models or weights

### Rules
- Record every experiment in results.jsonl
- Write knowledge nodes to knowledge_graph.jsonl
- Each experiment should be reproducible with a seed
