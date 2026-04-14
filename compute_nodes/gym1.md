# gym1

Jetson Orin (Nano) board used for overnight / multi-seed runs.

## Connection

```bash
ssh gym1@192.168.1.135
```

## Working Directory

```
~/Documents/TorchTrade/torchtrade-experiments
```

The session's `sources/` and per-run artifacts should be copied or synced
into a subdir of this path before running. The `torchtrade` submodule is
already pip-installed in the board's `.venv`.

## Hardware

- Jetson Orin, **8 GB unified RAM** shared between CPU and GPU
- CUDA available via the Jetson-specific PyTorch wheel
- Python 3.10 — avoid f-string `=` syntax

## Environment Setup

Already set up. The board has a pre-built `uv`-managed virtual environment.
Do not re-sync dependencies on the board — the Jetson PyTorch wheel is
pinned and `uv sync` would try to replace it with a generic wheel.

## Run Command

Always use `--no-sync` so uv skips dependency resolution:

```bash
cd ~/Documents/TorchTrade/torchtrade-experiments
uv run --no-sync <script> [args]
```

For long runs launched via SSH + `nohup`, export PATH explicitly (the
Jetson `nohup` environment does not source `~/.profile`):

```bash
nohup bash -lc 'export PATH=$HOME/.local/bin:$PATH && \
  cd ~/Documents/TorchTrade/torchtrade-experiments && \
  uv run --no-sync <script> [args]' > run.log 2>&1 &
```

## Utilization

100%

## Constraints

- **One PPO process at a time.** Each PPO training process uses ~2.5 GB
  total; two parallel processes cause swap thrashing and freezes. Run
  seeds **sequentially**, not in parallel, on this node.
- Keep `VectorizedSequentialTradingEnv*` on CPU (see project CLAUDE.md
  — `env.to(device)` is a no-op on plain-attribute tensor state). Use
  `SyncDataCollector(device=cuda)` to bridge obs to the GPU.
- wandb `logger.mode=online` works but expect occasional network hiccups;
  prefer `logger.mode=offline` for unattended overnight runs and `wandb
  sync` after.
