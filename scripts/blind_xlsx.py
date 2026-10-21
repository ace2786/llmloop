#!/usr/bin/env python3
"""盲判表的 Excel 版（比 CSV 好打开、带下拉框、自动换行）。

用法：
    python scripts/blind_xlsx.py make     # 从 out/to_grade.csv 生成 Excel
    python scripts/blind_xlsx.py merge    # 从 Excel 读回判分，写进原 CSV
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
D_DIR = Path("/mnt/d/llmloop")
XLSX_NAME = "待判分_60条.xlsx"

HEADERS = [
    ("代号", 8),
    ("题号", 7),
    ("问题", 42),
    ("回答", 92),
    ("检索到的段落", 30),
    ("人工判分\n(你填)", 12),
    ("失败原因\n(你填)", 14),
    ("判断理由\n(你填)", 30),
    ("类型", 11),
    ("标准答案（判分依据）", 56),
]

HFILL = PatternFill("solid", fgColor="1F4E79")
HFONT = Font(color="FFFFFF", bold=True, size=11)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
INPUT = PatternFill("solid", fgColor="FFF2CC")

GRADE_COLS = ["人工判分", "失败原因", "判断理由"]


def do_make() -> int:
    src = OUT / "to_grade.csv"
    if not src.exists():
        print(f"找不到 {src}，先跑 python scripts/blind.py make", file=sys.stderr)
        return 1

    # 题号 → 题目（拿类型和标准答案）
    qfile = ROOT / "data" / "questions.json"
    QMAP = {}
    if qfile.exists():
        for q in json.loads(qfile.read_text(encoding="utf-8")):
            QMAP[str(q["id"])] = q
        print(f"题库 {len(QMAP)} 条")

    with src.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"读到 {len(rows)} 条")

    wb = Workbook()
    ws = wb.active
    ws.title = "判分"

    for c, (name, w) in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=c, value=name)
        cell.fill = HFILL
        cell.font = HFONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "D2"

    for i, r in enumerate(rows, start=2):
        qid = str(r.get("题号", "")).strip()
        q = QMAP.get(qid) or {}
        src = q.get("source", "")
        kind = {"real-param": "参数类", "real-operation": "操作类",
                "real-supplement": "补充类",
                "real-positive": "正样本", "real-negative": "负样本"}.get(src, "")
        ans = q.get("answer", "")
        vals = [
            r.get("代号", ""),
            r.get("题号", ""),
            r.get("问题", ""),
            r.get("回答", ""),
            r.get("检索到的段落", ""),
            "",
            "",
            "",
            kind,
            ans,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=c, value=v)
            cell.border = BORDER
            if c >= 3:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="center", vertical="top")
        for c in (6, 7, 8):
            ws.cell(row=i, column=c).fill = INPUT
        # 类型列上色：正样本浅蓝、负样本浅橙
        kc = ws.cell(row=i, column=9)
        if kind == "正样本":
            kc.fill = PatternFill("solid", fgColor="DDEBF7")
        elif kind == "负样本":
            kc.fill = PatternFill("solid", fgColor="FCE4D6")
        kc.alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=i, column=10).font = Font(size=9)
        _n = max(len(str(ans)), len(str(vals[3])))
        ws.row_dimensions[i].height = min(max(120, _n // 3), 420)

    dv1 = DataValidation(type="list", formula1='"对,部分对,错"', allow_blank=True)
    dv1.error = "只能选 对 / 部分对 / 错"
    dv1.errorTitle = "输入无效"
    dv1.prompt = "对 / 部分对 / 错"
    dv1.promptTitle = "人工判分"
    ws.add_data_validation(dv1)
    dv1.add(f"F2:F{len(rows) + 1}")

    dv2 = DataValidation(
        type="list", formula1='"检索没命中,编造内容,理解错,格式错"', allow_blank=True
    )
    dv2.error = "只能选四类之一"
    dv2.errorTitle = "输入无效"
    dv2.prompt = "检索没命中 / 编造内容 / 理解错 / 格式错"
    dv2.promptTitle = "失败原因（判「对」时留空）"
    ws.add_data_validation(dv2)
    dv2.add(f"G2:G{len(rows) + 1}")

    ws.auto_filter.ref = f"A1:J{len(rows) + 1}"

    # 说明页
    ws2 = wb.create_sheet("说明")
    ws2.column_dimensions["A"].width = 100
    notes = [
        ("怎么判这 60 条", True),
        ("", False),
        ("① 先看 I 列「类型」：参数类（浅蓝）还是操作类（浅橙）", False),
        ("② 读 C 列（问题）和 D 列（模型回答）", False),
        ("③ 对照 J 列「标准答案」——它就是从文档原文摘的，不是模型生成的", False),
        ("④ 在 F 列选：对 / 部分对 / 错", False),
        ("⑤ 判「错」或「部分对」的，在 G 列选失败原因，H 列写一句话理由", False),
        ("⑥ 判「对」的，G/H 两列留空", False),
        ("", False),
        ("两类题分别考什么", True),
        ("  参数类（27 条）：考能不能定位到参数表、读出准确取值。", False),
        ("    典型题：「cutoff_len 设 1024 是指 1024 个字还是 1024 个 token？」", False),
        ("  操作类（33 条）：考能不能定位到功能章节、给出可执行步骤。", False),
        ("    典型题：「命令行如何中断训练及其恢复训练？」", False),
        ("", False),
        ("判「对」的门槛", True),
        ("  模型答出同样的意思就算对，表述不同不影响。", False),
        ("  只看：参数名、默认值、配置项、结论方向 对不对。", False),
        ("", False),
        ("四类失败原因", True),
        ("  检索没命中：检索到的段落里没有回答所需的信息", False),
        ("  编造内容　：回答里出现检索段落中不存在的事实", False),
        ("  理解错　　：检索到了正确段落，但模型理解偏差", False),
        ("  格式错　　：内容基本对，但输出格式不符合要求", False),
        ("", False),
        ("为什么要盲判", True),
        ("  表里的「代号」是打乱后的编号，你不知道哪条是哪个模型答的。", False),
        ("  知道之后判分就会不自觉宽容，30 道题的规模上一个 10% 提升只有 3 道题，", False),
        ("  任何偏袒都会让结论失效。判完我再把版本解开。", False),
        ("", False),
        ("判完之后", True),
        ("  保存文件，然后跑：", False),
        ("    python scripts/blind_xlsx.py merge", False),
        ("  脚本会把判分写回原 CSV，然后就能出报告了。", False),
        ("", False),
        ("★ 判分期间不要打开 out/week1_optimize_v0.csv，也不要看 out/blind_map.json", True),
    ]
    for r, (text, bold) in enumerate(notes, start=1):
        cell = ws2.cell(row=r, column=1, value=text)
        if bold:
            cell.font = Font(bold=True, size=11, color="1F4E79")

    out = OUT / XLSX_NAME
    wb.save(out)
    print(f"已生成：{out}")

    if D_DIR.exists():
        d_out = D_DIR / XLSX_NAME
        wb.save(d_out)
        print(f"已同步：{d_out}")

    print()
    print(f"  {len(rows)} 行，F/G 列有下拉框，表头已冻结")
    print("  判完保存，然后跑：python scripts/blind_xlsx.py merge")
    return 0


def do_merge() -> int:
    # 优先读 D 盘那份（用户实际在编辑的），本地 out/ 里的是生成时的副本
    candidates = [D_DIR / XLSX_NAME, OUT / XLSX_NAME]
    p = next((x for x in candidates if x.exists()), None)
    if p is None:
        print("找不到判分 Excel，先跑 make", file=sys.stderr)
        return 1
    print(f"读取：{p}")

    map_path = OUT / "blind_map.json"
    if not map_path.exists():
        print("找不到 blind_map.json", file=sys.stderr)
        return 1

    mapping = json.loads(map_path.read_text(encoding="utf-8"))["map"]

    wb = load_workbook(p, data_only=True)
    ws = wb["判分"]

    by_src: dict[str, dict[int, dict]] = {}
    graded = 0
    total = 0
    no_reason: list[str] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        total += 1
        code = str(row[0]).strip()
        marks = {
            "人工判分": str(row[5] or "").strip(),
            "失败原因": str(row[6] or "").strip(),
            "判断理由": str(row[7] or "").strip(),
        }
        if not marks["人工判分"]:
            continue
        # 判「对」但没写理由 → 自动补默认理由（省用户力气，保证数据完整）
        if marks["人工判分"] == "对" and not marks["判断理由"]:
            marks["判断理由"] = "与标准答案一致"
        # 判「错」+「检索没命中」但没写理由 → 理由同质化，自动补
        elif (marks["人工判分"] == "错"
              and marks["失败原因"] == "检索没命中"
              and not marks["判断理由"]):
            marks["判断理由"] = "文档中有答案，检索到的段落未命中"
        # 其余（编造内容 / 理解错 / 部分对）必须手写，因为每条缺的东西不一样
        if marks["人工判分"] in ("错", "部分对") and not marks["判断理由"]:
            no_reason.append(code)
        info = mapping.get(code)
        if not info:
            print(f"⚠ 代号 {code} 不在对照表里，跳过")
            continue
        graded += 1
        by_src.setdefault(info["src"], {})[info["idx"]] = marks

    print(f"已判 {graded} / {total} 条")
    if no_reason:
        print(f"⚠ {len(no_reason)} 条判了「错/部分对」但没写理由: {', '.join(no_reason[:10])}")
        print("  （不阻断，但报告里这几条会缺依据，建议补上）")
    if graded == 0:
        print("F 列还没填任何判分", file=sys.stderr)
        return 1

    for src, idx_marks in by_src.items():
        path = Path(src)
        with path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            fields = list(rows[0].keys()) if rows else []
        for idx, marks in idx_marks.items():
            if 0 <= idx < len(rows):
                for k in GRADE_COLS:
                    rows[idx][k] = marks[k]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"  ✓ 回填 {path.name}：{len(idx_marks)} 条")

    print()
    print("解开盲判完成。下一步：python scripts/report.py --split optimize")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "merge"])
    args = ap.parse_args()
    return do_make() if args.cmd == "make" else do_merge()


if __name__ == "__main__":
    sys.exit(main())
