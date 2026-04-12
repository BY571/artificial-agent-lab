"""Shared utilities for the research lab — results loading and stop signal."""
from __future__ import annotations

import json
from pathlib import Path


def load_results(session_dir: str | Path) -> list[dict]:
    """Load all results from a session's results.jsonl."""
    results_path = Path(session_dir) / "results.jsonl"
    if not results_path.exists():
        return []
    results = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return results


def should_stop(session_dir: str | Path) -> bool:
    """Check if the user requested a stop."""
    return (Path(session_dir) / ".stop_autoresearch").exists()
