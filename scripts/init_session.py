"""Initialize a new research session.

Usage:
    python scripts/init_session.py --name "my-research"
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parent.parent
AUTORESEARCH_DIR = REPO_ROOT / "autoresearch"
PROPOSAL_TEMPLATE = REPO_ROOT / "research_proposal_template.md"


def main():
    parser = argparse.ArgumentParser(description="Initialize a new research session")
    parser.add_argument("--name", required=True, help="Short name for the session (kebab-case)")
    parser.add_argument("--sources", help="Path to source material to copy into the session")
    args = parser.parse_args()

    session_name = f"{date.today().isoformat()}_{args.name}"
    session_dir = AUTORESEARCH_DIR / session_name

    if session_dir.exists():
        print(f"Session already exists: {session_dir}")
        return

    session_dir.mkdir(parents=True)

    # Copy research proposal template
    proposal_dst = session_dir / "research_proposal.md"
    if PROPOSAL_TEMPLATE.exists():
        content = PROPOSAL_TEMPLATE.read_text()
        content = content.replace("[NAME]", args.name)
        proposal_dst.write_text(content)
    else:
        proposal_dst.write_text(f"# Research Proposal: {args.name}\n\n(Fill in your research brief)\n")

    # Create session structure
    (session_dir / "sources").mkdir()
    (session_dir / "skills").mkdir()
    (session_dir / "threads").mkdir()
    (session_dir / "runs").mkdir()
    (session_dir / "results.jsonl").touch()
    (session_dir / "knowledge_graph.jsonl").touch()

    # Research log
    log = dedent(f"""\
    # Research Log: {args.name}

    PI's strategic log — research direction decisions, thread reviews, and synthesis.

    ## Session Started: {date.today().isoformat()}

    ---

    """)
    (session_dir / "research_log.md").write_text(log)

    # Copy source material if provided
    if args.sources:
        src = Path(args.sources)
        if src.is_dir():
            for item in src.iterdir():
                dst = session_dir / "sources" / item.name
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
            print(f"  Sources copied from {src}")
        elif src.is_file():
            shutil.copy2(src, session_dir / "sources" / src.name)
            print(f"  Source file copied: {src.name}")
        else:
            print(f"  Warning: sources path not found: {src}")

    print(f"Session created: {session_dir}")
    print()
    print(f"  >>> NEXT STEPS <<<")
    print(f"  1. Add source material to: {session_dir / 'sources'}/")
    print(f"     (code, papers, notes, data — anything the lab should read)")
    print(f"  2. Edit the research proposal: {proposal_dst}")
    print(f"  3. Launch: python -m orchestrator.run {session_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
