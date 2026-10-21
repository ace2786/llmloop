#!/usr/bin/env python3
"""把 questions_draft.json + prejudge.json 导成 Excel，供人工勾选与填写标准答案。

输出：data/待核对_265题.xlsx
  Sheet「待核对」：按 AI 预判排序（能用→部分→不能用），带下拉框、冻结表头
  Sheet「说明」  ：怎么填、填完干什么

配合 import_review_xlsx.py 使用（勾完导回 JSON）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

HEADERS = [
    ("序号", 6),
    ("能用吗\n(你填)", 10),
    ("问题", 40),
    ("Issue", 9),
    ("AI预判", 9),
    ("AI理由", 30),
    ("命中文档", 32),
    ("文档摘录（看答案在不在这）", 62),
    ("标准答案（你填）", 40),
    ("文档位置（你填）", 32),
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

VERDICT_FILL = {
    "能用": PatternFill("solid", fgColor="E2EFDA"),
    "部分": PatternFill("solid", fgColor="FFF2CC"),
    "不能用": PatternFill("solid", fgColor="F2F2F2"),
    "ERROR": PatternFill("solid", fgColor="FCE4EC"),
}
INPUT_FILL = PatternFill("solid", fgColor="FFF9E6")

ORDER = {"能用": 0, "部分": 1, "不能用": 2, "ERROR": 3, "": 4}

WIN = 700  # 摘录窗口长度


def snippet(text: str, query: str, width: int = WIN) -> str:
    """围绕问题关键词取窗口，而不是从段落开头截。

    为什么要这样：文档里参数表很长，直接截前 900 字经常截不到问题问的那个参数，
    人工看摘录就判断不了「答案在不在」。
    """
    if not text:
        return ""
    if len(text) <= width:
        return text

    # 从问题里挑候选关键词：英文标识符优先，其次中文词
    keys = [k for k in re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]{2,30}", query)]
    keys += [k for k in re.findall(r"[\u4e00-\u9fff]{2,6}", query)]

    best_pos, best_hits = 0, -1
    for k in keys:
        pos = text.lower().find(k.lower())
        if pos < 0:
            continue
        # 统计以 pos 为中心窗口内命中的关键词数
        lo = max(0, pos - width // 2)
        hi = min(len(text), lo + width)
        seg = text[lo:hi].lower()
        hits = sum(1 for kk in keys if kk.lower() in seg)
        if hits > best_hits:
            best_hits, best_pos = hits, lo

    start = best_pos
    end = min(len(text), start + width)
    seg = text[start:end]
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + seg + suffix

NOTE_TEXT = [
    ("这份表怎么用", True),
    ("", False),
    ("目标：从 120 条候选里挑出 60 条「答案能在文档或示例配置里找到」的题，并写出标准答案。", False),
    ("", False),
    ("表已按 AI 预判排序：能用 → 部分 → 不能用。建议从上往下勾，勾满 60 条就停。", True),
    ("", False),
    ("① B 列「能用吗」点下拉选：", True),
    ("     ✓  = 这条能用（答案确实在 F/G 列那段文档里）", False),
    ("     ✗  = 不能用（答案不在文档里 / 问题太模糊 / 不是用法类提问）", False),
    ("     ?  = 拿不准，先空着，最后一起看", False),
    ("", False),
    ("② 打 ✓ 的行，I 列填「标准答案」：", True),
    ("     要简短、可核对。比如「cutoff_len 默认值是 2048」。", False),
    ("     不要写「见文档」这种没信息量的话。", False),
    ("", False),
    ("③ J 列填「文档位置」：", True),
    ("     格式：文件名 > 章节 > 小节", False),
    ("     例：docs/zh/configuration/training.md > TrainingArguments > Checkpoint 与日志配置", False),
    ("     懒得写就把 G 列的内容复制过来。", False),
    ("", False),
    ("④ 勾满 60 条后保存，运行：", True),
    ("     python scripts/import_review_xlsx.py", False),
    ("     脚本会校验数量、检查答案是否填全，然后按固定随机种子切成 30 优化用 + 30 测试用。", False),
    ("", False),
    ("★ AI预判 这一列是什么", True),
    ("     是我用免费的 glm-4-flash 跑的一遍「这段文档能不能回答问题」的判断，", False),
    ("     目的是帮你从 120 条里快速筛出可能能用的，少看无关内容。", False),
    ("     ⚠ 它只是参考，不是结论。最终必须你自己看一眼 G 列摘录再打勾。", False),
    ("     第 8.1 ⑤ 明确要求「人工确认答案能在文档或示例配置里找到」，AI 预判不能替代这一步。", False),
    ("", False),
    ("★ 几条纪律（老师第 8.1 ⑤ 和第 16 节要求）", True),
    ("     · 标准答案必须人工核对过文档，不能凭印象写", False),
    ("     · 不能用 AI 代判/代标", False),
    ("     · 勾不够 60 条不要硬凑，宁可去 Issue 里再找", False),
    ("", False),
    ("★ 判断技巧", True),
    ("     · G 列是命中的文档原文。答案能在里面直接找到 → ✓", False),
    ("     · 只有参数名没有解释、或只有 yaml 没有说明 → 大概率 ✗", False),
    ("     · 问「支不支持 X」而文档里有模型列表 → 通常 ✓", False),
    ("     · 问「报错怎么办」这种 → 一般 ✗（属于 bug 报告，不是用法提问）", False),
    ("     · AI 说「能用」但你看着不像 → 信你自己", False),
]


def main() -> int:
    src = DATA / "questions_draft.json"
    if not src.exists():
        print(f"找不到 {src}，先运行 scripts/build_questions.py --draft")
        return 1

    draft = json.loads(src.read_text(encoding="utf-8"))

    # 加载 chunks 全文（prejudge.json 里只存了前 900 字，摘录需要全文才能截到关键词）
    full_text = {}
    cj = DATA / "chunks.jsonl"
    if cj.exists():
        for line in cj.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            full_text[(c["path"], c["heading"])] = c["text"]
        print(f"已加载 chunks 全文 {len(full_text)} 条")


    prej: dict = {}
    pj = DATA / "prejudge.json"
    if pj.exists():
        prej = json.loads(pj.read_text(encoding="utf-8"))
        print(f"读到 AI 预判 {len(prej)} 条")
    else:
        print("⚠ 没有 prejudge.json，AI预判列会空着")

    # 按 AI 预判排序
    def sort_key(q):
        v = (prej.get(str(q["id"])) or {}).get("verdict", "")
        return (ORDER.get(v, 4), q["id"])

    rows = sorted(draft, key=sort_key)

    wb = Workbook()
    ws = wb.active
    ws.title = "待核对"

    for col, (name, width) in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.row_dimensions[1].height = 36
    ws.freeze_panes = "C2"

    for i, q in enumerate(rows, start=2):
        p = prej.get(str(q["id"])) or {}
        verdict = p.get("verdict", "")
        reason = p.get("reason", "")
        best = p.get("best", 0)

        # 选 AI 认为最好的那段；AI 说都不能用就退回第一段
        paths = p.get("top_paths") or []
        heads = p.get("top_heads") or []
        texts = p.get("top_texts") or []
        idx = (best - 1) if 1 <= best <= len(paths) else 0
        if paths:
            doc = paths[idx] + (" > " + heads[idx] if heads and heads[idx] else "")
            _full = full_text.get((paths[idx], heads[idx] if heads else ""), "")
            excerpt = snippet(_full or (texts[idx] if idx < len(texts) else ""), q["question"])
        else:
            doc = q.get("doc_path_hint") or ""
            excerpt = snippet(q.get("doc_excerpt_hint") or "", q["question"])

        ws.cell(row=i, column=1, value=q["id"]).alignment = Alignment(horizontal="center")
        ws.cell(row=i, column=2, value="")
        ws.cell(row=i, column=3, value=q["question"])
        ws.cell(row=i, column=4, value=q.get("issue"))
        c5 = ws.cell(row=i, column=5, value=verdict)
        ws.cell(row=i, column=6, value=reason)
        ws.cell(row=i, column=7, value=doc)
        ws.cell(row=i, column=8, value=excerpt)
        ws.cell(row=i, column=9, value="")
        ws.cell(row=i, column=10, value="")

        if verdict in VERDICT_FILL:
            c5.fill = VERDICT_FILL[verdict]
        for col in (2, 9, 10):
            ws.cell(row=i, column=col).fill = INPUT_FILL

        for col in range(1, 11):
            c = ws.cell(row=i, column=col)
            c.border = BORDER
            if col in (3, 6, 7, 8, 9, 10):
                c.alignment = Alignment(vertical="top", wrap_text=True)
            else:
                c.alignment = Alignment(horizontal="center", vertical="top")

        ws.row_dimensions[i].height = 84

    dv = DataValidation(type="list", formula1='"✓,✗,?"', allow_blank=True)
    dv.error = "只能选 ✓ / ✗ / ?"
    dv.errorTitle = "输入无效"
    dv.prompt = "✓ 能用  ✗ 不能用  ? 拿不准"
    dv.promptTitle = "这条能用吗"
    ws.add_data_validation(dv)
    dv.add(f"B2:B{len(rows) + 1}")

    ws.auto_filter.ref = f"A1:J{len(rows) + 1}"

    ws2 = wb.create_sheet("说明")
    ws2.column_dimensions["A"].width = 104
    for r, (text, bold) in enumerate(NOTE_TEXT, start=1):
        c = ws2.cell(row=r, column=1, value=text)
        c.alignment = Alignment(vertical="top")
        if bold:
            c.font = Font(bold=True, size=11, color="1F4E79")

    out = DATA / "待核对_265题.xlsx"
    wb.save(out)

    # 自检
    wb2 = load_workbook(out, data_only=True)
    ws3 = wb2["待核对"]
    empty_q = empty_doc = empty_ex = 0
    for r in range(2, len(rows) + 2):
        if not ws3.cell(row=r, column=3).value:
            empty_q += 1
        if not ws3.cell(row=r, column=7).value:
            empty_doc += 1
        if not ws3.cell(row=r, column=8).value:
            empty_ex += 1

    from collections import Counter

    dist = Counter((prej.get(str(q["id"])) or {}).get("verdict", "无预判") for q in rows)

    print(f"已生成：{out}")
    print(f"  行数：{len(rows)}")
    print()
    print("AI 预判分布：")
    for k in ("能用", "部分", "不能用", "ERROR", "无预判"):
        if dist.get(k):
            print(f"  {k:<6} {dist[k]}")
    print()
    print("自检：")
    print(f"  问题为空     : {empty_q}")
    print(f"  命中文档为空 : {empty_doc}")
    print(f"  文档摘录为空 : {empty_ex}")
    print()
    print("前 3 行预览：")
    for r in range(2, min(5, len(rows) + 2)):
        print(f"  #{ws3.cell(row=r, column=1).value}  [{ws3.cell(row=r, column=5).value}] "
              f"{str(ws3.cell(row=r, column=3).value or '')[:34]}")
        print(f"      文档：{str(ws3.cell(row=r, column=7).value or '(空)')[:52]}")
        print(f"      摘录：{str(ws3.cell(row=r, column=8).value or '(空)')[:64]}")
    print()
    print("打开方式：D:\\llmloop\\待核对_265题.xlsx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
