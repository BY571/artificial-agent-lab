#!/bin/bash
# Run the CIFAR-10 benchmark.
#
# Usage:
#   bash benchmark/run_benchmark.sh
#
# Creates a session from the benchmark template and launches the orchestrator.

set -e
cd "$(dirname "$0")/.."

SESSION_NAME="$(date +%Y-%m-%d)_cifar10-benchmark"
SESSION_DIR="autoresearch/$SESSION_NAME"

# Create session
python scripts/init_session.py --name "cifar10-benchmark" --sources benchmark/sources

# Copy benchmark proposal and skills
cp benchmark/research_proposal.md "$SESSION_DIR/research_proposal.md"
cp -r benchmark/skills/* "$SESSION_DIR/skills/" 2>/dev/null || true

echo ""
echo "Benchmark session ready: $SESSION_DIR"
echo "Launching orchestrator..."
echo ""

python -m orchestrator.run "$SESSION_DIR"
