#!/usr/bin/env bash
# 拉取 LlamaFactory 的 Issues（GitHub API）
#
# 说明：
#   - 未登录限额 60 次/小时；单次查询最多返回 1000 条（第 11 页起返回 422）
#   - 所以分两个窗口拉：最新 1000 条 + 用 since 参数拉更早的 1000 条
#   - 有 token 的话限额升到 5000 次/小时，把 GITHUB_TOKEN 设上即可
#
# 用法：
#   bash scripts/fetch_issues.sh
#   GITHUB_TOKEN=ghp_xxx bash scripts/fetch_issues.sh

set -u

REPO="hiyouga/LlamaFactory"
OUT="$(cd "$(dirname "$0")/.." && pwd)/data/issues"
mkdir -p "$OUT/old"

AUTH=()
if [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN")
  echo "使用 GITHUB_TOKEN（限额 5000 次/小时）"
else
  echo "未提供 GITHUB_TOKEN（限额 60 次/小时）"
fi

fetch_window() {
  local label="$1" querystring="$2" dir="$3"
  echo ""
  echo "── $label ──"
  local ok=0 total=0
  for p in $(seq 1 10); do
    local f="$dir/p$(printf %02d "$p").json"
    local code
    code=$(curl -s -m 40 -4 "${AUTH[@]}" -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$REPO/issues?${querystring}&per_page=100&page=$p" \
      -o "$f" -w "%{http_code}")
    local n
    n=$(grep -o '"number":' "$f" 2>/dev/null | wc -l)
    total=$((total + n))
    printf "  page %02d  HTTP %s  %3d 条  累计 %d\n" "$p" "$code" "$n" "$total"
    if [ "$code" != "200" ] || [ "$n" -lt 100 ]; then
      [ "$code" != "200" ] && rm -f "$f"
      break
    fi
    ok=$((ok + 1))
    sleep 1
  done
  echo "  成功页数 $ok，共 $total 条"
}

# 窗口一：最新 1000 条
fetch_window "最新 1000 条" "state=all&sort=created&direction=desc" "$OUT"

# 窗口二：更早的（since 按 updated_at 过滤，能覆盖到 2023 年的老问题）
fetch_window "更早的 1000 条" "state=all&since=2025-01-01T00:00:00Z&sort=created&direction=asc" "$OUT/old"

echo ""
echo "完成。数据在 $OUT"
echo "下一步：python scripts/filter_issues.py"
