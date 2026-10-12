#!/usr/bin/env bash
# 一条命令:抓取 feeds.json 里的外部订阅源 → 去重/滚动保留 → 重建整站(含订阅源页、搜索索引)。
# 不发布;发布请再运行 ./publish.sh "说明"。某个源失败不影响其他源(会在输出和订阅源页的“状态”里显示)。
set -euo pipefail
cd "$(dirname "$0")"
python3 fetch_feeds.py
python3 build.py
