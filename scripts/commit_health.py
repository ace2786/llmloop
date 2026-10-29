#!/usr/bin/env python3
"""检查提交节奏，防止「提交挤在一两天」。

老师原话：
    提交挤在一两天，过程看不清——我会把这类提交记录当成过程不可信，
    而不是「最后冲刺很拼」。

用法：
    python scripts/commit_health.py            # 看最近 14 天
    python scripts/commit_health.py --days 30  # 看最近 30 天

退出码：有空白日或过度集中时返回 1（可以接进 pre-push 钩子）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 单日提交超过这个数，且存在空白日 → 判定为「集中爆发」
BURST_THRESHOLD = 5


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20
        ).stdout
    except Exception:  # noqa: BLE001
        return ""


def daily_counts(days: int) -> tuple[list[date], Counter]:
    raw = git("log", f"--since={days} days ago", "--pretty=%ad", "--date=format:%Y-%m-%d")
    cnt = Counter(line.strip() for line in raw.splitlines() if line.strip())
    today = date.today()
    span = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    # 项目首次提交之前的日子不算「空白」——那时候还没有项目
    first = min((date.fromisoformat(d) for d in cnt), default=today)
    span = [d for d in span if d >= first]
    return span, cnt


def streak(cnt: Counter) -> int:
    """从今天往前数，连续有提交的天数。"""
    n = 0
    d = date.today()
    while cnt.get(d.isoformat(), 0) > 0:
        n += 1
        d -= timedelta(days=1)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()

    span, cnt = daily_counts(a.days)
    total = sum(cnt.values())
    empty = [d for d in span if cnt.get(d.isoformat(), 0) == 0]
    peak = max((cnt.get(d.isoformat(), 0) for d in span), default=0)

    print(f"最近 {a.days} 天提交节奏")
    print("=" * 52)
    print(f"总提交 {total} 次 · 有提交 {len(span) - len(empty)} 天 · 空白 {len(empty)} 天")
    print(f"连续提交 {streak(cnt)} 天 · 单日峰值 {peak} 次")
    print()

    print("逐日：")
    for d in span:
        c = cnt.get(d.isoformat(), 0)
        bar = "█" * min(c, 20)
        mark = "  ← 空白" if c == 0 else ""
        print(f"  {d.strftime('%m-%d %a')}  {c:>2} {bar}{mark}")

    print()
    problems = []
    if empty:
        problems.append(f"{len(empty)} 天没有提交：" + "、".join(d.strftime("%m-%d") for d in empty))
    if peak >= BURST_THRESHOLD and empty:
        problems.append(f"单日最多 {peak} 次，同时存在空白日 —— 典型的「集中爆发」，老师会判过程不可信")

    if problems:
        print("✗ 有问题：")
        for p in problems:
            print(f"  · {p}")
        print()
        print("补救方向：从今天起每天至少一次真实提交。不要伪造日期——")
        print("git 的 author date 和 commit date 都能查，造假比不提交严重得多。")
        return 1

    print("✓ 节奏正常：没有空白日，也没有过度集中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
