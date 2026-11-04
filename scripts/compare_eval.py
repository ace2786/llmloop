#!/usr/bin/env python3
"""对比两份评测 CSV，逐题看判分有没有变。

用途：改动判分逻辑（或把它抽成模块）之后，验证「结果和改之前一模一样」。
      判分是评测的尺子，改了尺子所有历史结论都要重算，所以每次改完必须比对。

用法：
    python scripts/compare_eval.py 旧.csv 新.csv
    python scripts/compare_eval.py 旧.csv 新.csv --ignore-answer   # 只比判分，不比模型回答
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def load(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--ignore-answer", action="store_true", help="只比判分，不比模型回答")
    a = ap.parse_args()

    old_p, new_p = Path(a.old), Path(a.new)
    for p in (old_p, new_p):
        if not p.exists():
            print(f"找不到：{p}")
            return 1

    old, new = load(old_p), load(new_p)
    print(f"旧 {len(old)} 行 / 新 {len(new)} 行")

    if len(old) != len(new):
        print("!! 行数不一致，可能不是同一批题，后面的对比不可靠")

    n = min(len(old), len(new))
    verdict_diff, answer_diff = [], []
    for i in range(n):
        o, w = old[i], new[i]
        if o.get("question") != w.get("question"):
            print(f"!! 第 {i+1} 行题目对不上，跳过后续对比")
            return 1
        if o.get("自动判分") != w.get("自动判分") or o.get("判分依据") != w.get("判分依据"):
            verdict_diff.append((i + 1, o.get("question", ""), o.get("自动判分"), w.get("自动判分")))
        if not a.ignore_answer and o.get("模型回答") != w.get("模型回答"):
            answer_diff.append(i + 1)

    print(f"判分不一致：{len(verdict_diff)} / {n}")
    for row, q, ov, nv in verdict_diff[:10]:
        print(f"  第{row}行 {q[:36]}：{ov} → {nv}")

    if not a.ignore_answer:
        print(f"模型回答不一致：{len(answer_diff)} / {n}"
              + ("（模型有随机性，少量差异正常）" if answer_diff else ""))

    ok = not verdict_diff
    print()
    print("✓ 判分完全一致" if ok else "✗ 判分有变化，需要确认是不是故意的")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
