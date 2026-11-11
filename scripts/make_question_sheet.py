#!/usr/bin/env python3
"""生成「人写出题表」：挑 40 个内容扎实的文档段落，留空让作者用自己的话提问。

为什么这么做：
  自动从 GitHub issue 起草的通过率只有 10%（见 B012 与 60 条核对表），
  但失败原因是「BM25 抓错了文档」，不是「写不出答案」。
  这里反过来：**先把正确的文档段落定死，再让人对着它提问**，
  答案一定能在原文里找到，质量可控。

分工：
  人负责「提问」——真人语感是模型学不来的，也是这批题的价值所在。
  脚本负责「配答案」——从指定段落里抽，不会编。

用法：
    python scripts/make_question_sheet.py --n 40
输出：
    D:/llmloop/人写出题表.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CJK = re.compile(r"[\u4e00-\u9fff]")
# 有信息量的段落特征：出现参数名、命令、步骤词
USEFUL = re.compile(r"(`[^`]+`|--[a-z-]+|yaml|json|参数|配置|默认|报错|需要|必须|建议|步骤|设置|开启|关闭)")


def pick_chunks(n: int, per_file: int = 6) -> list[dict]:
    chunks = [json.loads(l) for l in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    scored = []
    for c in chunks:
        text = c["text"].strip()
        cn = len(CJK.findall(text))
        if cn < 120:            # 太短，没内容
            continue
        if text.count("![") > 3:  # 一堆图片
            continue
        score = cn / 100 + len(USEFUL.findall(text)) * 1.5
        if c.get("heading"):
            score += 2
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])

    # 按文件分散，避免全是同一个页面
    by_file: dict[str, int] = defaultdict(int)
    out: list[dict] = []
    for _, c in scored:
        f = c["path"]
        if by_file[f] >= per_file:
            continue
        by_file[f] += 1
        out.append(c)
        if len(out) >= n:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()

    picked = pick_chunks(a.n)
    print(f"挑了 {len(picked)} 个段落，来自 {len({c['path'] for c in picked})} 个文件")

    wb = Workbook()
    ws = wb.active
    ws.title = "人写出题"

    ws["A1"] = "怎么用这张表"
    ws["A1"].font = Font(bold=True, size=12)
    ws.merge_cells("A2:D2")
    ws["A2"] = (
        "对着每一行的「文档原文」，用你自己会问的方式，在 D 列写一个问题。"
        "不用写答案——答案脚本会从原文里抽。写不出来就留空，跳过也行。"
        "目标：40 条里写 30 条以上。"
    )
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 46

    headers = ["#", "出处", "文档原文（答案就在这里面）", "你写的问题（人话）"]
    widths = [6, 34, 78, 52]
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = Font(bold=True, size=10)
        cell.fill = PatternFill("solid", fgColor="F1EFE8")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    ws.row_dimensions[4].height = 28

    for idx, c in enumerate(picked, 1):
        row = 4 + idx
        loc = f"{c['path']} > {c['heading']}" if c.get("heading") else c["path"]
        text = c["text"].strip()
        if len(text) > 900:
            text = text[:900] + " …"
        for col, val in enumerate([idx, loc, text, ""], 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.font = Font(size=10)
        ws.row_dimensions[row].height = 96
        ws.cell(row=row, column=4).fill = PatternFill("solid", fgColor="FFF9E6")

    dst = Path("/mnt/d/llmloop/人写出题表.xlsx")
    if not dst.parent.is_dir():
        dst = ROOT / "out" / "人写出题表.xlsx"
    wb.save(dst)
    print(f"已写出：{dst}")
    print()
    print("=== 前 3 条示例（看看材料够不够写题）===")
    for c in picked[:3]:
        print(f"  [{c['path']} > {c.get('heading','')}]")
        print(f"    {c['text'].strip()[:110]}…")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
