# spark

NVIDIA DGX Spark (GB10 Grace-Blackwell) workstation. Used for the
compute-heavy threads — biggest RAM budget of any node in this lab, so
it's the right place for wide vectorized PPO runs and multi-seed
batches that would OOM on gym1.

## Connection

```bash
ssh spark@192.168.1.136      # hostname: spark-3e2d
```

No key needed if you're ssh'ing from a host with an authorized pubkey
already on file; otherwise ask the user.

## Working Directory

Two paths matter on this node:

- `~/Documents/TorchTrade/torchtrade-pkg/` — editable install of the
  `torchtrade` Python package (commit **bd33096**, same as local submodule
  at setup time). Do **not** `git pull` here — it's a tar snapshot, not a
  real git clone.
- `~/research-lab-sessions/xlstm-microbar-rl/sources/` — pre-staged copy
  of this session's `sources/` directory (utils, pretrained encoder,
  training reference script). Investigators should read files from here
  and write experiment outputs to sibling directories, **not** into
  sources/.

Scratch / outputs: put per-run artifacts in
`~/research-lab-sessions/xlstm-microbar-rl/runs/<thread-id>/`.

## Hardware

- **GPU**: NVIDIA GB10 (Grace-Blackwell Superchip), compute capability
  **12.1** (Blackwell), CUDA 13.0, driver 580.142
- **GPU memory**: ~119 GB free of 124 GB (unified) — huge headroom
- **CPU**: 20 × ARM Cortex-X925 @ up to 100% scaling
- **System RAM**: **121 GiB unified** (same pool as GPU on Grace-Blackwell)
- **Arch**: aarch64 Ubuntu 24.04.4 LTS, kernel 6.17.0-1014-nvidia
- **Python**: 3.12.3 (system + venv)

## Environment Setup

Already provisioned. The Python environment lives in **`~/jupyterlab/.venv`**
(a preexisting jupyterlab venv that was extended with RL + trading deps
for this session). The research-lab-specific packages pulled in during
setup were:

| Package | Version | Notes |
|---------|---------|-------|
| `torch` | 2.9.0+cu130 | **DO NOT UPGRADE** — only this NVIDIA-built wheel reaches GB10. `pip install torch` from upstream will replace it with a CPU-only wheel. |
| `torchrl` | 0.11.1 | aarch64 wheel |
| `tensordict` | 0.11.0 | aarch64 wheel |
| `hydra-core` | 1.3.2 | |
| `omegaconf` | 2.3.0 | |
| `wandb` | 0.26.0 | |
| `numba` | 0.65.0 | via llvmlite 0.47.0, aarch64 |
| `torchtrade` | 0.0.1 (editable) | from `~/Documents/TorchTrade/torchtrade-pkg/` |
| `ccxt`, `alpaca-py`, `python-binance`, `pybit`, `ta` | (various) | pulled in as transitive torchtrade deps; not used by offline SLTP training |

Pre-existing deps already in the jupyterlab venv and reused as-is:
`torchvision 0.24.0`, `pandas 2.3.2`, `datasets 4.1.0`, `numpy 2.1.0`,
`transformers 4.56.1`, `accelerate 1.10.1`, `tqdm 4.67.1`.

Full pip freeze snapshot (for rollback) is on spark at
`/tmp/jupyterlab_venv_snapshot.txt`.

If the venv breaks, the fastest recovery is to reinstall the lab-specific
deps against the pinned torch:

```bash
~/jupyterlab/.venv/bin/pip install --upgrade-strategy only-if-needed \
    'torch==2.9.0+cu130' torchrl tensordict hydra-core omegaconf wandb numba
cd ~/Documents/TorchTrade/torchtrade-pkg && ~/jupyterlab/.venv/bin/pip install -e .
```

## Run Command

Always use the full interpreter path (the jupyterlab venv activate script
is not sourced by default, so `python` on the SSH login shell points at
`/usr/bin/python3` with no torch installed):

```bash
~/jupyterlab/.venv/bin/python <script> [args]
```

For overnight runs via `nohup`, export PATH and set HOME explicitly to
survive the detached shell:

```bash
ssh spark@192.168.1.136 "nohup bash -lc '\
  export PATH=\$HOME/jupyterlab/.venv/bin:\$PATH && \
  cd ~/research-lab-sessions/xlstm-microbar-rl/runs/<thread-id> && \
  python <script> [args]' > run.log 2>&1 &"
```

## Utilization

100%

## Constraints & Gotchas

- **GB10 compute capability warning** (functional, not a blocker): torch
  2.9.0+cu130 ships SASS kernels compiled up to SM 12.0, but GB10 is SM
  12.1. CUDA runtime falls back to JIT-compiling kernels via PTX on
  first call. You'll see this warning every script start:

  ```
  UserWarning: Found GPU0 NVIDIA GB10 which is of cuda capability 12.1.
  Minimum and Maximum cuda capability supported by this version of PyTorch
  is (8.0) - (12.0)
  ```

  First-iteration latency is ~10-30% higher than a warm run; subsequent
  iterations use the JIT-cached kernels and run at normal speed. Do
  **not** use first-batch timings as a benchmark.

- **Parallelism capacity**: 121 GiB unified RAM can theoretically fit
  ~30 concurrent PPO processes at gym1's 2.5 GB footprint. In practice,
  **cap at 4 concurrent processes** on this node for the first runs —
  we haven't stress-tested memory contention or the PTX JIT cache
  under concurrency. Observe memory/GPU utilization and scale up.

- **Keep envs on CPU** (same project-wide constraint as gym1 / local):
  `VectorizedSequentialTradingEnv*` stores tensors as plain Python
  attributes, not `nn.Buffer`s, so `env.to("cuda")` is a no-op on its
  data. Build the env on CPU and use `SyncDataCollector(device="cuda")`
  to bridge observations to the GPU for the policy forward pass.

- **torchtrade submodule is NOT a git repo on this node.** It was
  tar-shipped from the local submodule. Commit ID (`bd33096`) is
  recorded in this file and in the session README only. If you need to
  update torchtrade on spark, re-run the tar-pipe from local — don't
  try to `git pull`.

- **The in-place `.venv` at `~/Documents/TorchTrade/torchtrade-llm-experiments/.venv`
  is BROKEN** (dangling symlink to an x86_64 python on the local
  machine). Do not use it. Only `~/jupyterlab/.venv` is the real env.

## Verified on setup (2026-04-14)

- CUDA smoke: 4096×4096 FP32 matmul in ~260 ms
- `torchrl 0.11.1`, `tensordict 0.11.0` core imports succeed
- `VectorizedSequentialTradingEnvSLTP` instantiates with
  `leverage=3, initial_cash=400`
- Action space: 19 discrete actions confirmed
- Frozen encoder `sources/encoder_frozen_microbar.pt` loads with zero
  missing / unexpected keys via the config stored inside the checkpoint
- 3-step env rollout produces valid rewards (shape `(num_envs, 1)`)
