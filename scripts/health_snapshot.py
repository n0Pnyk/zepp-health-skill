#!/usr/bin/env python3
"""Export health data snapshot for LLM analysis.

Usage:
    python3 scripts/health_snapshot.py [--date YYYY-MM-DD] [--check]

Outputs JSON to stdout for LLM consumption (OpenClaw / hermes-agent).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_dependencies() -> bool:
    """Check that all required modules and functions are importable."""
    ok = True

    # Check zepp_health package
    try:
        import zepp_health
        print(f"zepp_health v{zepp_health.__version__}")
    except ImportError as e:
        print(f"FAIL: zepp_health not importable: {e}", file=sys.stderr)
        return False

    # Check generate_snapshot
    try:
        from zepp_health.analysis import generate_snapshot
        print("  generate_snapshot: OK")
    except ImportError as e:
        print(f"  generate_snapshot: FAIL ({e})", file=sys.stderr)
        ok = False

    # Check generate_daily_report
    try:
        from zepp_health.analysis import generate_daily_report
        print("  generate_daily_report: OK")
    except ImportError as e:
        print(f"  generate_daily_report: FAIL ({e})", file=sys.stderr)
        ok = False

    # Check ZeppClient
    try:
        from zepp_health.client import ZeppClient
        print("  ZeppClient: OK")
    except ImportError as e:
        print(f"  ZeppClient: FAIL ({e})", file=sys.stderr)
        ok = False

    # Check load_config
    try:
        from zepp_health.config import load_config
        print("  load_config: OK")
    except ImportError as e:
        print(f"  load_config: FAIL ({e})", file=sys.stderr)
        ok = False

    # Check config.json exists
    from zepp_health.config import _config_search_paths
    paths = _config_search_paths()
    found = False
    for p in paths:
        if p.is_file():
            print(f"  config.json: OK ({p})")
            found = True
            break
    if not found:
        print("  config.json: NOT FOUND (checked: " + ", ".join(str(p) for p in paths) + ")", file=sys.stderr)
        ok = False

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Export health data snapshot")
    parser.add_argument("--date", help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--check", action="store_true", help="Check dependencies and exit")
    args = parser.parse_args()

    if args.check:
        if check_dependencies():
            print("\nAll dependencies OK.")
            sys.exit(0)
        else:
            print("\nSome dependencies failed.", file=sys.stderr)
            sys.exit(1)

    target_date = date.fromisoformat(args.date) if args.date else None

    from zepp_health.analysis import generate_snapshot
    from zepp_health.client import ZeppClient
    from zepp_health.config import load_config

    config = load_config()
    with ZeppClient(config) as client:
        snapshot = generate_snapshot(client, target_date)

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
