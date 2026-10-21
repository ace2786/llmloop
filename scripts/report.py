#!/usr/bin/env python3
"""从评测 CSV 算指标：正确率、失败原因分布、「原来对现在错」的题、和预期对比。

第 11 节步骤 5 要求：
  「v0 和 v1 在『测试用』30 道上都跑一遍并人工判分，算正确率变化、
    有没有『原来对现在错』的题，和你的预期对比」

用法：
    python scripts/report.py                      # 自动找 out/ 下所有 CSV
    python scripts/report.py --split test         # 只看测试集
    python scripts/report.py --prediction 0.10    # 修改前写下的预期提升（0.10 = 10 个百分点）

注意：脚本只做统计，不做判分。判分必须人工填在 CSV 里。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

CORRECT = {"对"}
PARTIAL = {"部分对"}
WRONG = {"错"}


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score_of(row: dict) -> str:
    return (row.get("人工判分") or "").strip()


def summarize(rows: list[dict], label: str) -> dict:
    graded = [r for r in rows if score_of(r)]
    ungraded = len(rows) - len(graded)
    n = len(graded)
    if n == 0:
        print(f"  {label}: 尚未判分（{len(rows)} 条待判）")
        return {"label": label, "n": 0, "ungraded": ungraded}

    c = sum(1 for r in graded if score_of(r) in CORRECT)
    p = sum(1 for r in graded if score_of(r) in PARTIAL)
    w = sum(1 for r in graded if score_of(r) in WRONG)
    unknown = n - c - p - w

    reasons = Counter(
        (r.get("失败原因") or "").strip()
        for r in graded
        if score_of(r) in WRONG | PARTIAL and (r.get("失败原因") or "").strip()
    )

    print(f"  {label}")
    print(f"    已判 {n} 条" + (f"（未判 {ungraded} 条）" if ungraded else ""))
    print(f"    对 {c}  /  部分对 {p}  /  错 {w}" + (f"  /  未标 {unknown}" if unknown else ""))
    print(f"    严格正确率 {c}/{n} = {c / n:.1%}")
    print(f"    含部分对  {(c + p)}/{n} = {(c + p) / n:.1%}")
    if reasons:
        print("    失败原因：")
        for k, v in reasons.most_common():
            print(f"      {k:<8} {v:>3} 条  ({v / sum(reasons.values()):.0%})")

    return {
        "label": label,
        "n": n,
        "correct": c,
        "partial": p,
        "wrong": w,
        "strict_acc": c / n,
        "loose_acc": (c + p) / n,
        "reasons": dict(reasons),
    }


def find_regressions(rows_v0: list[dict], rows_v1: list[dict]) -> list[dict]:
    """找出「原来对、现在错」的题。按 题号+模型 对齐。"""
    def key(r):
        return (r.get("题号"), r.get("模型"))

    m0 = {key(r): r for r in rows_v0 if score_of(r)}
    m1 = {key(r): r for r in rows_v1 if score_of(r)}

    reg = []
    for k, r0 in m0.items():
        r1 = m1.get(k)
        if not r1:
            continue
        s0, s1 = score_of(r0), score_of(r1)
        if s0 == "对" and s1 in ("错", "部分对"):
            reg.append(
                {
                    "题号": k[0],
                    "模型": k[1],
                    "v0": s0,
                    "v1": s1,
                    "问题": (r0.get("问题") or "")[:60],
                    "v1理由": (r1.get("判断理由") or "")[:80],
                }
            )
    return reg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["test", "optimize", "all"])
    ap.add_argument("--prediction", type=float, default=None,
                    help="修改前写下的预期提升，单位「个百分点」，如 10 表示 +10pp")
    args = ap.parse_args()

    files = sorted(glob.glob(str(OUT / "week1_*.csv")))
    if not files:
        print(f"out/ 下没有 CSV。先跑 week1.py。", file=sys.stderr)
        return 1

    by_ver = defaultdict(list)
    for p in files:
        rows = load(Path(p))
        if not rows:
            continue
        split = (rows[0].get("所属份") or "").strip()
        ver = (rows[0].get("版本") or "").strip()
        if args.split == "test" and split != "测试用":
            continue
        if args.split == "optimize" and split != "优化用":
            continue
        by_ver[ver].extend(rows)

    if not by_ver:
        print(f"没有匹配 --split {args.split} 的数据", file=sys.stderr)
        return 1

    print("=" * 62)
    print(f"评测报告  split={args.split}")
    print("=" * 62)
    print()

    stats = {}
    for ver in sorted(by_ver):
        print(f"── 版本 {ver} ──")
        stats[ver] = summarize(by_ver[ver], f"版本 {ver}")
        print()

    # 按模型细分
    print("── 按模型细分（严格正确率）──")
    per_model = defaultdict(dict)
    for ver, rows in by_ver.items():
        for m in sorted({r.get("模型") for r in rows if r.get("模型")}):
            sub = [r for r in rows if r.get("模型") == m]
            graded = [r for r in sub if score_of(r)]
            if not graded:
                continue
            c = sum(1 for r in graded if score_of(r) in CORRECT)
            per_model[m][ver] = f"{c}/{len(graded)} = {c / len(graded):.0%}"
    for m, vers in per_model.items():
        print(f"  {m}")
        for ver, v in vers.items():
            print(f"    {ver}: {v}")
    print()

    # v0 vs v1 对比
    versions = sorted(by_ver)
    if "v0" in versions and "v1" in versions:
        print("── v0 → v1 对比 ──")
        s0, s1 = stats["v0"], stats["v1"]
        if s0.get("n") and s1.get("n"):
            d_strict = s1["strict_acc"] - s0["strict_acc"]
            d_loose = s1["loose_acc"] - s0["loose_acc"]
            print(f"  严格正确率：{s0['strict_acc']:.1%} → {s1['strict_acc']:.1%}  "
                  f"（{d_strict * 100:+.1f} 个百分点，{round(d_strict * s0['n']):+d} 道题）")
            print(f"  含部分对　：{s0['loose_acc']:.1%} → {s1['loose_acc']:.1%}  "
                  f"（{d_loose * 100:+.1f} 个百分点）")

            if args.prediction is not None:
                print()
                print(f"  修改前的预期：{args.prediction:+.1f} 个百分点")
                print(f"  实际结果　　：{d_strict * 100:+.1f} 个百分点")
                gap = d_strict * 100 - args.prediction
                if abs(gap) <= 3:
                    print(f"  判断：预期基本准确（差 {gap:+.1f}pp）")
                elif gap > 3:
                    print(f"  判断：预期偏保守（实际好 {gap:+.1f}pp）")
                else:
                    print(f"  判断：预期偏乐观（实际差 {gap:+.1f}pp）")

            print()
            reg = find_regressions(by_ver["v0"], by_ver["v1"])
            if reg:
                print(f"  ★ 「原来对、现在错」的题：{len(reg)} 条")
                for r in reg:
                    print(f"    #{r['题号']} [{r['模型']}] {r['v0']}→{r['v1']}  {r['问题']}")
                    if r["v1理由"]:
                        print(f"        v1 理由：{r['v1理由']}")
            else:
                print("  ✓ 没有「原来对、现在错」的题")
        print()

    # 诚实声明
    n_test = max((s.get("n") or 0) for s in stats.values())
    if n_test and n_test <= 50:
        print("─" * 62)
        print(f"⚠ 样本量声明：测试集只有 {n_test} 道题。")
        print(f"  在这个规模上，{max(1, round(n_test * 0.1))} 道题的差异属于噪声范围，")
        print("  结论只能表述为「机制演示」，不构成统计证据。")
        print("  要谈显著性，需等阶段 2 把测试集扩到 500 道。")
        print("─" * 62)

    return 0


if __name__ == "__main__":
    sys.exit(main())
