#!/bin/bash
# 断线自动重试的推送脚本。
#
# 为什么需要它：这台机器直连 GitHub，国际链路时通时断
# （TCP 能连、TLS 握手常被卡住，git 报 "Recv failure: Connection was reset"）。
# 手动重试很烦，这个脚本自动重试，通一次就停。
#
# 用法：
#   bash scripts/push.sh              # 推到 origin/master
#   bash scripts/push.sh origin main  # 指定远程和分支
#
# 重要：push 失败不影响提交记录。commit 是本地操作，老师看的是 commit date。
#       只要本地提交了，什么时候推上去，记录上都是原来那个时间。

set -u

REPO_WSL="/home/ace/llmloop"
REPO_WIN_UNC="//wsl.localhost/Ubuntu/home/ace/llmloop"
REMOTE="${1:-origin}"
BRANCH="${2:-master}"
MAX_TRIES=10

# ---- 判断在哪个环境里跑 ----
if [ -x "/mnt/c/Program Files/Git/cmd/git.exe" ]; then
  # WSL 里：WSL 的 git 没有凭据管理器，借 Windows 的 git 走 UNC 路径
  GIT="/mnt/c/Program Files/Git/cmd/git.exe"
  REPO_ARG="$REPO_WIN_UNC"   # 给 Windows git 用
  REPO="$REPO_WSL"           # 本地检查用
  IN_WSL=1
elif [ -x "/c/Program Files/Git/cmd/git.exe" ]; then
  # Windows Git Bash 里
  GIT="/c/Program Files/Git/cmd/git.exe"
  REPO_ARG="$REPO_WIN_UNC"
  REPO="$REPO_WIN_UNC"
  IN_WSL=0
else
  GIT="git"
  REPO_ARG="$REPO_WSL"
  REPO="$REPO_WSL"
  IN_WSL=0
fi

if [ ! -d "$REPO" ]; then
  echo "✗ 找不到仓库：$REPO"
  exit 1
fi

# ---- 先看有没有东西要推 ----
AHEAD=$("$GIT" -C "$REPO_ARG" rev-list --count "@{u}..HEAD" 2>/dev/null || echo "?")
if [ "$AHEAD" = "0" ]; then
  echo "✓ 本地和远程已经同步，没有要推的提交"
  exit 0
fi
echo "本地领先远程 $AHEAD 个提交，开始推送（最多试 $MAX_TRIES 次）"
echo

# ---- 重试循环 ----
WAIT=2
for i in $(seq 1 $MAX_TRIES); do
  printf "[%d/%d] 推送中… " "$i" "$MAX_TRIES"
  OUT=$("$GIT" -C "$REPO_ARG" push "$REMOTE" "$BRANCH" 2>&1)
  CODE=$?

  if [ $CODE -eq 0 ]; then
    echo "成功"
    echo "$OUT" | tail -3

    # WSL 里的 origin/master 引用是旧的，手动同步一下
    if [ "$IN_WSL" = "1" ]; then
      SHA=$(cd "$REPO_WSL" && git rev-parse HEAD 2>/dev/null)
      if [ -n "${SHA:-}" ]; then
        (cd "$REPO_WSL" && git update-ref "refs/remotes/$REMOTE/$BRANCH" "$SHA" 2>/dev/null)
        echo "已同步本地远程引用 → ${SHA:0:7}"
      fi
    fi
    exit 0
  fi

  # 失败的常见原因分类，给点人话提示
  if echo "$OUT" | grep -qi "Connection was reset\|Could not resolve\|Failed to connect\|timed out"; then
    echo "网络断了"
  elif echo "$OUT" | grep -qi "rejected\|non-fast-forward"; then
    echo "远程有本地没有的提交（需要先 pull）"
    echo "$OUT" | tail -3
    echo
    echo "✗ 这不是网络问题，重试没用。先执行：git pull --rebase $REMOTE $BRANCH"
    exit 2
  elif echo "$OUT" | grep -qi "Authentication\|Permission denied\|could not read Username"; then
    echo "认证失败"
    echo "$OUT" | tail -3
    echo
    echo "✗ 凭据问题，重试没用。检查 Windows 凭据管理器里的 GitHub 凭据。"
    exit 3
  else
    echo "失败（退出码 $CODE）"
    echo "$OUT" | tail -2
  fi

  if [ $i -lt $MAX_TRIES ]; then
    echo "       等 ${WAIT} 秒后重试…"
    sleep $WAIT
    WAIT=$((WAIT * 2))
    [ $WAIT -gt 30 ] && WAIT=30
  fi
done

echo
echo "✗ 试了 $MAX_TRIES 次都没成功。"
echo
echo "  提交没丢 —— 它们在本地仓库里，git log 能看到。"
echo "  push 失败不影响提交记录，老师看的是 commit date。"
echo
echo "  几个办法："
echo "    1. 过一会儿再跑一次这个脚本（链路时通时断，等个时间窗）"
echo "    2. 开代理后重试："
echo "         git config --global http.proxy http://127.0.0.1:7897"
echo "    3. 关代理时要记得清掉："
echo "         git config --global --unset http.proxy"
exit 1
