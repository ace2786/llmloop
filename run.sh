#!/usr/bin/env bash
# 第 1 周一键流程。省得记一堆命令。
#
# 用法：
#   bash run.sh status          看当前进度
#   bash run.sh init            建环境 + 拉数据 + 建索引（只需一次）
#   bash run.sh v0              跑 v0（只跑优化用）
#   bash run.sh blind           生成盲判表
#   bash run.sh merge           判完回填
#   bash run.sh v1              跑 v1（只跑优化用）
#   bash run.sh test            跑测试集（v0 + v1，只在改进做完后）
#   bash run.sh report          出报告
#   bash run.sh check           提交前检查（扫密钥、扫硬编码）

set -u
cd "$(dirname "$0")" || exit 1

PY=.venv/bin/python

need_env() {
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
}

ensure_venv() {
  if [ ! -x "$PY" ]; then
    echo "✗ 没有虚拟环境。先跑：bash run.sh init"
    exit 1
  fi
}

ensure_ollama() {
  if ! curl -s -m 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    echo "→ Ollama 没在跑，先启动"
    bash scripts/start_ollama.sh || exit 1
  fi
}

cmd_status() {
  echo "════════ 第 1 周进度 ════════"
  echo ""
  printf "  环境      : "
  if [ -x "$PY" ]; then echo "✓ venv ($($PY -V 2>&1))"; else echo "✗ 未建"; fi

  printf "  题目索引  : "
  if [ -f data/chunks.jsonl ]; then
    echo "✓ $(wc -l < data/chunks.jsonl) 块"
  else
    echo "✗ 未建"
  fi

  printf "  60 道题   : "
  if [ -f data/questions.json ]; then
    $PY - <<'PYEOF'
import json
from collections import Counter
q = json.load(open("data/questions.json", encoding="utf-8"))
c = Counter(x["split"] for x in q)
print(f"✓ {len(q)} 道（优化用 {c.get('optimize',0)} / 测试用 {c.get('test',0)}）")
PYEOF
  else
    echo "✗ 未定稿（还需人工勾选 60 条）"
  fi

  printf "  v0 优化用 : "
  if [ -f out/week1_optimize_v0.csv ]; then
    echo "✓ $($PY scripts/count_csv.py out/week1_optimize_v0.csv) 条"
  else
    echo "✗ 未跑"
  fi

  printf "  v1 优化用 : "
  if [ -f out/week1_optimize_v1.csv ]; then
    echo "✓ $($PY scripts/count_csv.py out/week1_optimize_v1.csv) 条"
  else
    echo "✗ 未跑"
  fi

  printf "  盲判表    : "
  if [ -f out/to_grade.csv ]; then
    echo "✓ 已判 $($PY scripts/count_csv.py out/to_grade.csv --graded)"
  else
    echo "✗ 未生成"
  fi

  printf "  测试集    : "
  if ls out/week1_test_*.csv >/dev/null 2>&1; then
    echo "✓ $(ls out/week1_test_*.csv | wc -l) 个文件"
  else
    echo "✗ 未跑（改进做完才能跑）"
  fi

  printf "  git 提交  : "
  if git rev-parse --git-dir >/dev/null 2>&1; then
    n=$(git rev-list --count HEAD 2>/dev/null || echo 0)
    if [ "$n" -gt 0 ]; then echo "✓ $n 次"; else echo "✗ 还没有首次提交"; fi
  else
    echo "✗ 未初始化"
  fi
  echo ""
}

cmd_init() {
  echo "→ 建虚拟环境"
  if [ ! -x "$PY" ]; then
    uv venv --python 3.12 .venv || exit 1
  fi
  export UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
  uv pip install --python "$PY" rank_bm25 jieba openpyxl || exit 1

  echo ""
  echo "→ 检查数据"
  if [ ! -d data/LlamaFactory-main ]; then
    echo "  下载 LlamaFactory ..."
    mkdir -p data
    curl -L -o data/llama-factory.tar.gz \
      "https://codeload.github.com/hiyouga/LlamaFactory/tar.gz/refs/heads/main" || exit 1
    tar xzf data/llama-factory.tar.gz -C data/ || exit 1
  else
    echo "  ✓ 仓库已存在"
  fi

  if [ ! -d data/issues ]; then
    echo "  拉 Issues ..."
    bash scripts/fetch_issues.sh || exit 1
  else
    echo "  ✓ Issues 已存在"
  fi

  echo ""
  echo "→ 建索引"
  $PY scripts/build_index.py || exit 1
  echo ""
  echo "✓ 初始化完成"
}

cmd_v0() {
  ensure_venv
  need_env
  ensure_ollama
  $PY week1.py --split optimize --version v0
}

cmd_v1() {
  ensure_venv
  need_env
  ensure_ollama
  $PY week1.py --split optimize --version v1
}

cmd_test() {
  ensure_venv
  need_env
  ensure_ollama
  echo "★ 只在改进做完之后跑，跑完测试集就解封了"
  read -r -p "确认改进已经做完？(yes/no) " ans
  [ "$ans" = "yes" ] || { echo "已取消"; exit 0; }
  $PY week1.py --split test --version v0
  $PY week1.py --split test --version v1
}

cmd_blind() {
  ensure_venv
  $PY scripts/blind.py make --split "${2:-test}"
}

cmd_merge() {
  ensure_venv
  $PY scripts/blind.py merge
}

cmd_report() {
  ensure_venv
  shift || true
  $PY scripts/report.py --split test "$@"
}

cmd_check() {
  ensure_venv
  $PY scripts/precommit_check.py
}

case "${1:-}" in
  status) cmd_status ;;
  init)   cmd_init ;;
  v0)     cmd_v0 ;;
  v1)     cmd_v1 ;;
  test)   cmd_test ;;
  blind)  cmd_blind "$@" ;;
  merge)  cmd_merge ;;
  report) cmd_report "$@" ;;
  check)  cmd_check ;;
  *)
    echo "用法：bash run.sh {status|init|v0|blind|merge|v1|test|report|check}"
    echo ""
    cmd_status
    ;;
esac
