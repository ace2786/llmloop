#!/usr/bin/env python3
"""把多个模型的逐题评测结果合成「对错矩阵」——F2 的 IRT 就吃这个。

为什么需要：任务书第 7 节说「不同的免费模型正好就是 F2 需要的『多个被测配置』」。
IRT 要从「多个模型 × 多道题」的对错矩阵里估出每道题的难度和区分度。
只有 1 个模型时，这个矩阵只有一行，IRT 算不出任何东西。

输入：out/eval_<split>_<model>_<stamp>.csv（run_eval.py 的产物）
输出：
  out/model_matrix.csv   每道题 × 每个模型的对错（对=1 / 部分对=0.5 / 错=0）
  out/model_matrix.md    人看的汇总

用法：
    python scripts/build_matrix.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

SCORE = {"对": 1.0, "部分对": 0.5, "错": 0.0}
# 从文件名里抠出模型名：eval_test_<model>_<mmdd_hhmm>[_norag].csv
NAME = re.compile(r"eval_test_(.+?)_(\d{4}_\d{4})(_norag)?\.csv$")


def main() -> int:
    # 每个模型取最新一次「有检索」的结果
    latest: dict[str, Path] = {}
    for p in sorted(glob.glob(str(OUT / "eval_test_*.csv"))):
        m = NAME.search(Path(p).name)
        if not m or m.group(3):  # 跳过无检索的对照组
            continue
        model = m.group(1)
        stamp = m.group(2)
        if model not in latest or stamp > NAME.search(latest[model].name).group(2):
            latest[model] = Path(p)

    if len(latest) < 2:
        print(f"只找到 {len(latest)} 个模型的结果，IRT 至少需要 2 个")
        for k, v in latest.items():
            print(f"  {k}: {v.name}")
        return 1

    print("采用的结果文件：")
    for k, v in latest.items():
        print(f"  {k}: {v.name}")

    # 以题目文本为键（不同模型跑的顺序一致，但用文本更稳）
    matrix: dict[str, dict[str, float]] = {}
    meta: dict[str, dict] = {}
    for model, path in latest.items():
        with path.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                q = r["question"]
                matrix.setdefault(q, {})[model] = SCORE.get(r["自动判分"], 0.0)
                meta.setdefault(q, {"source": r.get("source", ""), "issue": r.get("issue", "")})

    models = sorted(latest)
    rows = []
    for q, sc in matrix.items():
        vals = [sc.get(m) for m in models]
        if any(v is None for v in vals):
            continue  # 有模型没跑这道，跳过
        rows.append({
            "question": q,
            "source": meta[q]["source"],
            "issue": meta[q]["issue"],
            **{m: sc[m] for m in models},
            "avg": sum(sc[m] for m in models) / len(models),
        })
    rows.sort(key=lambda r: r["avg"])

    dst = OUT / "model_matrix.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question", "source", "issue", *models, "avg"])
        w.writeheader()
        w.writerows(rows)

    # 汇总
    n = len(rows)
    print()
    print(f"矩阵：{n} 道题 × {len(models)} 个模型")
    print()
    print("各模型正确率：")
    for m in models:
        s = sum(r[m] for r in rows) / n
        print(f"  {m:<18} {s:.1%}")

    print()
    print("题目难度分布（几个模型答对）：")
    from collections import Counter
    hard = Counter()
    for r in rows:
        got = sum(1 for m in models if r[m] >= 1.0)
        hard[got] += 1
    for k in sorted(hard, reverse=True):
        print(f"  {k}/{len(models)} 个模型答对：{hard[k]} 道")

    print()
    print("两模型一致性：")
    if len(models) == 2:
        a, b = models
        both_ok = sum(1 for r in rows if r[a] >= 1.0 and r[b] >= 1.0)
        only_a = sum(1 for r in rows if r[a] >= 1.0 and r[b] < 1.0)
        only_b = sum(1 for r in rows if r[a] < 1.0 and r[b] >= 1.0)
        none = sum(1 for r in rows if r[a] < 1.0 and r[b] < 1.0)
        print(f"  两个都对 {both_ok}　只有 {a} 对 {only_a}　只有 {b} 对 {only_b}　都不对 {none}")
        print(f"  区分度（只有一个对的比例）：{(only_a + only_b) / n:.1%}")

    print()
    print("最难的 5 道（所有模型都没答对）：")
    for r in rows[:5]:
        print(f"  [{r['source']}] {r['question'][:52]}")

    md = OUT / "model_matrix.md"
    lines = [
        "# 多模型对错矩阵（F2 的输入）",
        "",
        f"共 {n} 道题 × {len(models)} 个模型。",
        "",
        "## 各模型严格正确率",
        "",
        "| 模型 | 正确率 |",
        "|---|---|",
    ]
    for m in models:
        lines.append(f"| {m} | {sum(r[m] for r in rows)/n:.1%} |")
    lines += ["", "## 题目难度分布", "", "| 几个模型答对 | 题数 |", "|---|---|"]
    for k in sorted(hard, reverse=True):
        lines.append(f"| {k}/{len(models)} | {hard[k]} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"已写出：{dst.relative_to(ROOT)}")
    print(f"已写出：{md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
