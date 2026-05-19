#!/usr/bin/env python3
"""Export health data snapshot for LLM analysis.

Usage:
    python3 scripts/health_snapshot.py [--date YYYY-MM-DD]

Outputs JSON to stdout for LLM consumption (OpenClaw / hermes-agent).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zepp_health.analysis import generate_snapshot
from zepp_health.client import ZeppClient
from zepp_health.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Export health data snapshot")
    parser.add_argument("--date", help="Date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else None

    config = load_config()
    with ZeppClient(config) as client:
        snapshot = generate_snapshot(client, target_date)

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
