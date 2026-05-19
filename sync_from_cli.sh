#!/usr/bin/env bash
# 从 zepp-health CLI 仓库同步核心库文件
# 用法: ./sync_from_cli.sh [cli_repo_path]

set -euo pipefail

CLI_REPO="${1:-../zepp-health}"
CORE_FILES=(__init__.py config.py client.py models.py scoring.py analysis.py report.py)

if [[ ! -d "$CLI_REPO/zepp_health" ]]; then
    echo "错误: 找不到 CLI 仓库核心库目录: $CLI_REPO/zepp_health"
    echo "用法: $0 /path/to/zepp-health"
    exit 1
fi

for f in "${CORE_FILES[@]}"; do
    src="$CLI_REPO/zepp_health/$f"
    dst="zepp_health/$f"
    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        echo "已同步: $f"
    else
        echo "跳过: $f（源文件不存在）"
    fi
done

echo ""
echo "同步完成。请检查变更后提交。"
