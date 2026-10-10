#!/usr/bin/env bash
# 提交并推送站点改动到 GitHub Pages。令牌只从环境变量 GITHUB_PAGES_TOKEN 临时读取,不写入任何文件或 remote URL。
# 用法: ./publish.sh ["提交说明"]
set -euo pipefail
cd "$(dirname "$0")"
: "${GITHUB_PAGES_TOKEN:?需要环境变量 GITHUB_PAGES_TOKEN}"
REPO=richardgist/ue-digest
[ -d .git ] || { git init -q -b main; }
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$REPO.git"
git config user.name  >/dev/null || git config user.name  "richardgist"
git config user.email >/dev/null || git config user.email "richardgist@users.noreply.github.com"
python3 build.py >/dev/null
git add -A
if git diff --cached --quiet; then
  echo "没有改动,无需发布。"
  exit 0
fi
git commit -q -m "${1:-更新周报 $(date +%F)}"
git -c credential.helper= \
    -c 'credential.helper=!f() { echo username=richardgist; echo "password=$GITHUB_PAGES_TOKEN"; }; f' \
    push origin HEAD:main
echo "已推送。站点: https://richardgist.github.io/ue-digest/ (Pages 构建约 1 分钟)"
