#!/usr/bin/env bash
# Sync core library files from the zepp-health CLI repository
# Usage: ./sync_from_cli.sh [cli_repo_path]

set -euo pipefail

CLI_REPO="${1:-../zepp-health}"
CORE_FILES=(__init__.py config.py client.py models.py scoring.py analysis.py report.py)

if [[ ! -d "$CLI_REPO/zepp_health" ]]; then
    echo "Error: CLI repo core library not found: $CLI_REPO/zepp_health"
    echo "Usage: $0 /path/to/zepp-health"
    exit 1
fi

for f in "${CORE_FILES[@]}"; do
    src="$CLI_REPO/zepp_health/$f"
    dst="zepp_health/$f"
    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        echo "Synced: $f"
    else
        echo "Skipped: $f (source not found)"
    fi
done

echo ""
echo "Sync complete. Please review changes and commit."
