"""Parse research proposal configuration fields."""
from __future__ import annotations

import re
from pathlib import Path


def parse_duration_minutes(value: str) -> float | None:
    """Parse a duration string like '4h', '90m', '1.5h' into minutes.

    Returns None for 'unlimited' or unparseable values.
    """
    value = value.strip().lower()
    if value == "unlimited":
        return None

    match = re.match(r"^(\d+(?:\.\d+)?)\s*(h|m)$", value)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)
    if unit == "h":
        return amount * 60
    return amount


def load_proposal_config(proposal_path: Path) -> dict:
    """Extract configuration values from a research_proposal.md file."""
    text = proposal_path.read_text()
    config = {
        "metric": "primary_metric",
        "hardware": "local",
        "investigators": None,  # None = auto (match compute node count)
        "seeds": 3,
        "research_budget_minutes": None,
        "rate_limit_policy": "wait",
        "web_search": True,
        "final_output": "paper",
        "paper_review_rounds": 3,
    }

    sections = text.split("### ")
    for section in sections:
        lines = section.strip().split("\n")
        header = lines[0].strip()
        content_lines = [
            line.strip()
            for line in lines[1:]
            if line.strip() and not line.strip().startswith("<!--")
        ]

        if header == "Primary Metric":
            for line in content_lines:
                if line.startswith("**") and "**" in line[2:]:
                    config["metric"] = line.split("**")[1]
                    break
        elif header == "Hardware":
            if content_lines:
                config["hardware"] = content_lines[0]
        elif header == "Investigators":
            if content_lines:
                val = content_lines[0].strip().lower()
                if val == "auto":
                    config["investigators"] = None  # resolved below from hardware
                else:
                    try:
                        config["investigators"] = int(val)
                    except ValueError:
                        pass
        elif header == "Seeds":
            if content_lines:
                try:
                    config["seeds"] = int(content_lines[0])
                except ValueError:
                    pass
        elif header == "Research Budget":
            if content_lines:
                config["research_budget_minutes"] = parse_duration_minutes(content_lines[0])
        elif header == "Rate Limit Policy":
            if content_lines:
                policy = content_lines[0].strip().lower()
                if policy in ("wait", "stop"):
                    config["rate_limit_policy"] = policy
        elif header == "Web Search":
            if content_lines:
                config["web_search"] = content_lines[0].strip().lower() == "true"
        elif header == "Final Output":
            if content_lines:
                val = content_lines[0].strip().lower()
                if val in ("paper", "summary"):
                    config["final_output"] = val
        elif header == "Paper Review Rounds":
            if content_lines:
                try:
                    config["paper_review_rounds"] = int(content_lines[0])
                except ValueError:
                    pass

    # Resolve investigator count from compute nodes if set to auto/None
    if config["investigators"] is None:
        nodes = [n.strip() for n in config["hardware"].split("+")]
        config["investigators"] = max(1, len(nodes))

    return config
