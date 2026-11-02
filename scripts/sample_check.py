#!/usr/bin/env python3
"""从合成题里抽样，生成人工校验表（参照 ARES 的 PPI 思路）。

为什么要抽样校验：
  RAGAS 官方文档明确要求「合成集必须人工抽样校验，否则会继承 LLM 的幻觉与同质化」。
  ARES 用 PPI（Prediction-Powered Inference）在「少量人工标注 + 大量自动判断」之间
  做统计校正，给出置信区间。

本脚本只做第一步：抽一个可校验的样本，导出成 Excel。
抽样方式：分层随机（按来源分组，保证真实提问和反推题都抽到），固定随机种子可复现。

用法：
    python scripts/sample_check.py --n 30
输出：
    D:/llmloop/抽样校验.xlsx
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def group_of(q: dict) -> str:
    return "doc-synth" if q.get("source") == "doc-synth" else "real"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261102)
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    doc = [q for q in qs if group_of(q) == "doc-synth"]
    real = [q for q in qs if group_of(q) == "real"]
    print(f"题库 {len(qs)} 道：合成 {len(doc)} / 真实 {len(real)}")

    # 分层：按两类在题库中的占比分配抽样数，至少各抽 5 条
    rng = random.Random(a.seed)
    n_doc = max(5, round(a.n * len(doc) / len(qs)))
    n_real = max(5, a.n - n_doc)
    print(f"抽样：合成 {n_doc} 条 + 真实 {n_real} 条 = {n_doc + n_real} 条")

    picked = ([(q, "doc-synth") for q in rng.sample(doc, min(n_doc, len(doc)))]
              + [(q, "real") for q in rng.sample(real, min(n_real, len(real)))])
    rng.shuffle(picked)

    wb = Workbook()
    ws = wb.active
    ws.title = "抽样校验"
    headers = ["#", "判定（T/F/?）", "来源", "问题", "标准答案", "文档原文（答案的依据）", "出处"]
    widths = [5, 14, 12, 44, 40, 56, 40]
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, size=10)
        cell.fill = PatternFill("solid", fgColor="F1EFE8")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30

    for i, (q, src) in enumerate(picked, 1):
        vals = [
            i, "",
            "合成（参数表反推）" if src == "doc-synth" else "真实提问",
            q.get("question", ""),
            q.get("answer", "")[:220],
            (q.get("evidence") or "").replace("¶", " ").strip()[:220],
            (q.get("doc_location") or "").replace("¶", "").strip(),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i + 1, column=c, value=v)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.font = Font(size=10)
        ws.row_dimensions[i + 1].height = 52
        ws.cell(row=i + 1, column=2).fill = PatternFill("solid", fgColor="FFF9E6")

    dst = Path("/mnt/d/llmloop/抽样校验.xlsx")
    if not dst.parent.is_dir():
        dst = ROOT / "out" / "抽样校验.xlsx"
    wb.save(dst)
    print(f"已写出：{dst}")
    print()
    print("=== 前 5 条 ===")
    for i, (q, src) in enumerate(picked[:5], 1):
        tag = "合成" if src == "doc-synth" else "真实"
        print(f"  {i}. [{tag}] {q.get('question','')[:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
