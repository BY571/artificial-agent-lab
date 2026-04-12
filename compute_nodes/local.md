# local

## Connection

Local machine — no SSH needed.

## Hardware

- GPU: auto-detected (`torch.cuda.is_available()`)
- Check with `nvidia-smi`

## Run Command

```bash
python <script> [args]
```

## Utilization

100%

## Constraints

- Uses whatever GPU/CPU is available on the local machine
- Scripts should auto-detect GPU: `device = torch.device("cuda" if torch.cuda.is_available() else "cpu")`
