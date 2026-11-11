#!/usr/bin/env python3
"""对比两次评测的判定变化：净增多少、退步多少、哪些题变了。

比 compare_eval.py 更进一步：不只报「不一致」，而是按「对/部分对/错」
拆成升级、降级、不变三类，并给出净变化。写报告时直接用这个数。

用法：
    python scripts/diff_verdicts.py 旧.csv 新.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

RANK = {"错": 0, "部分对": 1, "对": 2}


def load(p: Path) -> dict[str, dict]:
    with p.open(encoding="utf-8-sig") as f:
        return {r["question"]: r for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--show", type=int, default=8, help="各方向最多列几条")
    a = ap.parse_args()

    old, new = load(Path(a.old)), load(Path(a.new))
    common = [q for q in old if q in new]
    if not common:
        print("两份文件没有共同题目，无法对比")
        return 1

    up, down, same = [], [], 0
    for q in common:
        o, n = old[q]["自动判分"], new[q]["自动判分"]
        if o == n:
            same += 1
        elif RANK.get(n, 0) > RANK.get(o, 0):
            up.append((q, o, n))
        else:
            down.append((q, o, n))

    def dist(rows: dict[str, dict]) -> Counter:
        return Counter(r["自动判分"] for r in rows.values())

    do, dn = dist({q: old[q] for q in common}), dist({q: new[q] for q in common})
    n = len(common)

    print(f"共同题目 {n} 道")
    print()
    print(f"{'':6} {'对':>4} {'部分对':>6} {'错':>4} {'严格':>8} {'宽松':>8}")
    for tag, d in (("旧", do), ("新", dn)):
        strict = d["对"] / n
        loose = (d["对"] + d["部分对"]) / n
        print(f"{tag:6} {d['对']:>4} {d['部分对']:>6} {d['错']:>4} {strict:>8.1%} {loose:>8.1%}")
    print()
    print(f"升级 {len(up)} 道　降级 {len(down)} 道　不变 {same} 道")
    print(f"严格净变化 {(dn['对']-do['对'])/n:+.1%}（{dn['对']-do['对']:+d} 道）")
    print(f"宽松净变化 {((dn['对']+dn['部分对'])-(do['对']+do['部分对']))/n:+.1%}"
          f"（{(dn['对']+dn['部分对'])-(do['对']+do['部分对']):+d} 道）")

    if up:
        print(f"\n升级的前 {min(a.show, len(up))} 条：")
        for q, o, nn in up[: a.show]:
            print(f"  {o} → {nn}  {q[:52]}")
    if down:
        print(f"\n降级的前 {min(a.show, len(down))} 条：")
        for q, o, nn in down[: a.show]:
            print(f"  {o} → {nn}  {q[:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
