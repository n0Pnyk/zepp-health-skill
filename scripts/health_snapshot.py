#!/usr/bin/env python3
"""导出健康数据快照供 LLM 分析。

用法：
    python3 scripts/health_snapshot.py [--date YYYY-MM-DD]

输出 JSON 到 stdout，供 OpenClaw / hermes-agent 的 LLM 消费。
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zepp_health.analysis import generate_snapshot
from zepp_health.client import ZeppClient
from zepp_health.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="导出健康数据快照")
    parser.add_argument("--date", help="日期 YYYY-MM-DD（默认今天）")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else None

    config = load_config()
    with ZeppClient(config) as client:
        snapshot = generate_snapshot(client, target_date)

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
