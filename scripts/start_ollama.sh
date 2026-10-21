#!/usr/bin/env bash
# 启动本机 Ollama 服务（幂等：已在跑就不重复启动）
#
# 背景：本机没有 passwordless sudo，也没有 ollama.service 单元，
#       所以只能用用户进程方式起，WSL 重启后需要重新拉起。
#
# 用法：
#   bash scripts/start_ollama.sh
#   bash scripts/start_ollama.sh --status

set -u

LOG_DIR="$HOME/.ollama/logs"
LOG="$LOG_DIR/serve.log"
mkdir -p "$LOG_DIR"

is_up() {
  curl -s -m 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1
}

if [ "${1:-}" = "--status" ]; then
  if is_up; then
    echo "Ollama 运行中：$(curl -s -m 3 http://127.0.0.1:11434/api/version)"
    echo "已装模型："
    ollama list 2>/dev/null | sed 's/^/  /'
  else
    echo "Ollama 未运行"
  fi
  exit 0
fi

if is_up; then
  echo "Ollama 已在运行：$(curl -s -m 3 http://127.0.0.1:11434/api/version)"
  exit 0
fi

echo "启动 ollama serve ..."
nohup ollama serve > "$LOG" 2>&1 &

for _ in $(seq 1 30); do
  sleep 1
  if is_up; then
    echo "✓ 已启动：$(curl -s -m 3 http://127.0.0.1:11434/api/version)"
    echo "  日志：$LOG"
    ollama list 2>/dev/null | sed 's/^/  /'
    exit 0
  fi
done

echo "✗ 启动失败，检查日志：$LOG"
tail -20 "$LOG"
exit 1
