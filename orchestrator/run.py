"""Entry point for the research lab orchestrator.

Usage:
    python -m orchestrator.run autoresearch/2026-04-11_my-research/

Reads the research proposal, sets up the PI agent with investigators,
and starts the research loop on a dedicated git branch.
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from orchestrator.config import load_proposal_config
from orchestrator.pi import run_pi_loop

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_main_branch() -> str:
    """Detect the main branch name (main or master)."""
    for name in ("main", "master"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", name],
            cwd=REPO_ROOT, capture_output=True,
        )
        if result.returncode == 0:
            return name
    return "main"


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.stdout.strip()


def create_research_branch(session_name: str) -> str:
    """Create and checkout a git branch for this research session.

    Always branches from the main branch to keep research sessions
    independent. If the branch already exists, checks it out instead.
    """
    main = get_main_branch()
    branch = f"research/{session_name}"

    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=REPO_ROOT, capture_output=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "checkout", branch], cwd=REPO_ROOT, check=True)
        return branch

    current = get_current_branch()
    if current != main:
        print(f"  Switching to {main} before creating research branch...")
        subprocess.run(["git", "checkout", main], cwd=REPO_ROOT, check=True)

    subprocess.run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, check=False)
    subprocess.run(["git", "checkout", "-b", branch], cwd=REPO_ROOT, check=True)

    # Commit session files and push so remote compute nodes can access them
    subprocess.run(["git", "add", "autoresearch/"], cwd=REPO_ROOT, check=False)
    subprocess.run(
        ["git", "commit", "-m", f"Init session {session_name}"],
        cwd=REPO_ROOT, capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=REPO_ROOT, check=False,
    )

    return branch


def main():
    parser = argparse.ArgumentParser(description="Run research lab orchestrator")
    parser.add_argument(
        "session_dir",
        help="Path to the session directory (e.g. autoresearch/2026-04-11_my-research)",
    )
    parser.add_argument(
        "--no-branch",
        action="store_true",
        help="Stay on current branch instead of creating a research branch",
    )
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.is_absolute():
        session_dir = REPO_ROOT / session_dir

    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}")
        sys.exit(1)

    proposal_path = session_dir / "research_proposal.md"
    if not proposal_path.exists():
        print(f"No research_proposal.md found in {session_dir}")
        sys.exit(1)

    config = load_proposal_config(proposal_path)
    print(f"Research session: {session_dir.name}")
    print(f"  Primary metric: {config['metric']}")
    print(f"  Hardware: {config['hardware']}")
    print(f"  Investigators: {config['investigators']}")
    print(f"  Seeds: {config['seeds']}")

    if not args.no_branch:
        branch = create_research_branch(session_dir.name)
        print(f"  Branch: {branch}")
    else:
        print("  Branch: (staying on current branch)")

    (session_dir / "threads").mkdir(exist_ok=True)

    asyncio.run(run_pi_loop(session_dir, config))


if __name__ == "__main__":
    main()
