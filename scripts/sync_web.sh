#!/bin/bash
# 把前端工作副本（D:\llmloop\web）同步进仓库存档（~/llmloop/web）。
#
# 为什么需要：前端在 Windows 侧开发（npm/vite 在 WSL 里跑 UNC 路径很慢），
# 但代码必须进 git 仓库，否则硬盘一坏就全没了，老师也看不到进展。
#
# 用法：
#   bash scripts/sync_web.sh          # 同步并显示差异
#   bash scripts/sync_web.sh --commit # 同步 + 自动提交（不推送）
#
# 约定：D 盘是工作副本，仓库 web/ 是存档。不要反过来改仓库那份。

set -u

SRC="/mnt/d/llmloop/web"
DST="/home/ace/llmloop/web"

if [ ! -d "$SRC" ]; then
  echo "✗ 找不到前端工作副本：$SRC"
  exit 1
fi
if [ ! -d "$DST" ]; then
  echo "✗ 仓库里还没有 web/，先手动建一次"
  exit 1
fi

echo "同步 $SRC → $DST"
echo "（排除 node_modules / dist / .vite）"
echo

# 用 rsync 排除大目录；没有 rsync 就退回 cp
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude 'node_modules' \
    --exclude 'dist' \
    --exclude '.vite' \
    --exclude '.git' \
    "$SRC/" "$DST/"
else
  echo "（没有 rsync，用 cp 覆盖）"
  cp -r "$SRC/src" "$SRC/index.html" "$SRC/package.json" \
        "$SRC/package-lock.json" "$SRC/tsconfig.json" \
        "$SRC/vite.config.ts" "$SRC/README.md" "$DST/" 2>/dev/null
fi

cd /home/ace/llmloop || exit 1
if git diff --quiet -- web/ && git diff --cached --quiet -- web/; then
  echo "✓ 没有变化，仓库存档已是最新"
  exit 0
fi

echo "=== 变更 ==="
git diff --stat -- web/
echo

if [ "${1:-}" = "--commit" ]; then
  git add web/
  git commit -q -m "同步前端：$(date '+%m-%d %H:%M') 的工作副本"
  echo "✓ 已提交（还没推送，用 bash scripts/push.sh 推）"
else
  echo "想提交就加 --commit，或手动 git add web/ && git commit"
fi
