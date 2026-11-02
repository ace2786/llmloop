#!/usr/bin/env python3
"""生成 60 条核对表的 Excel 版（.xlsx），带重复标记。

为什么是 xlsx：CSV 在这台机器的 Excel 上打开会报错，xlsx 一定能开。

给每行加三样东西帮人快速判断：
  1. 类型（问句/陈述/功能请求/报错求助）——不是问句的可以直接打错
  2. 文档原文（150 字）——没有原文没法判断「答没答上」
  3. 重复组——同一主题出现多次时标出组号，同组只留 1-2 条

用法：
    python scripts/make_review_60_xlsx.py
输出：
    D:/llmloop/60条核对表.xlsx
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CN = re.compile(r"[\u4e00-\u9fff]")
ASK = re.compile(r"如何|怎么|怎样|是否|能否|可以|什么|哪个|为什么|多少|哪些|吗|呢|么")
ERR_WORD = re.compile(r"报错|出错|失败|FAILED|Error|error|异常|不生效|无效|崩溃")
FEAT_WORD = re.compile(r"希望|建议|增加功能|支持一下|Support|Add support|feature")

# 主题分组：同一主题超过 1 条就标组号，提醒「同组只留 1-2 条」
TOPICS = [
    ("多模态/视觉模型支持", r"多模态|video|image|vl|VL|OmniVinci|HunyuanOCR|视觉|图片"),
    ("部署/vllm", r"vllm|部署|API|接口|推理服务"),
    ("数据格式", r"数据格式|数据集格式|json|converter|模板"),
    ("并行/多卡", r"并行|多卡|多机|dp|DDP|npu|deepspeed|ring attention"),
    ("量化/显存", r"量化|显存|int4|awq|gptq|显卡"),
]


def qtype_of(t: str) -> str:
    t = t or ""
    if not CN.search(t):
        return "英文"
    if ERR_WORD.search(t):
        return "报错求助"
    if FEAT_WORD.search(t):
        return "功能请求"
    if "？" in t or "?" in t or ASK.search(t):
        return "问句"
    return "陈述"


def topic_of(t: str) -> str:
    for name, pat in TOPICS:
        if re.search(pat, t or ""):
            return name
    return ""


def main() -> int:
    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    items = [q for q in qs if q.get("source") == "real-issue"]
    print(f"待核对：{len(items)} 条")

    # 主题分组：同组内按 id 排序，标「组N·第k/共m」
    groups: dict[str, list[dict]] = {}
    for q in items:
        g = topic_of(q.get("question", ""))
        if g:
            groups.setdefault(g, []).append(q)
    dup_note: dict[int, str] = {}
    for g, members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda x: x.get("id", 0))
        for k, q in enumerate(members, 1):
            dup_note[q.get("id", 0)] = f"{g} 第{k}/{len(members)} 条"

    # 排序：可疑度高的在前（先看风险高的），可疑度相同按 id
    def susp(q: dict) -> int:
        title = q.get("question", "")
        ans = q.get("answer", "")
        ev = q.get("evidence", "")
        s = 0
        tt = {w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_\-]{2,}\b", title)
              if w.lower() not in {"the", "and", "for", "how", "what", "why", "can", "you",
                                   "with", "use", "model", "train", "data", "error", "issue",
                                   "help", "please", "when", "does", "not", "but", "from",
                                   "this", "that", "have", "get", "set", "run", "load"}
              and len(w) >= 4}
        if tt and not (tt & {w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_]{2,}\b", ans)}):
            s += 3
        if qtype_of(title) != "问句":
            s += 2
        if len(ans) < 20:
            s += 2
        if len(ev) < 30:
            s += 1
        return s

    items.sort(key=lambda q: (-susp(q), q.get("id", 0)))

    wb = Workbook()
    ws = wb.active
    ws.title = "60条核对"

    headers = ["#", "判定（对/错/查）", "类型", "问题", "文档原文（答案的依据）", "出处", "重复提示", "Issue"]
    widths = [5, 14, 10, 46, 60, 42, 22, 9]
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, size=10)
        cell.fill = PatternFill("solid", fgColor="F1EFE8")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30

    for i, q in enumerate(items, 1):
        ev = (q.get("evidence") or "").replace("¶", " ").strip()
        vals = [
            i,
            "",
            qtype_of(q.get("question", "")),
            q.get("question", ""),
            ev[:150] + ("…" if len(ev) > 150 else ""),
            (q.get("doc_location") or "").replace("¶", "").strip(),
            dup_note.get(q.get("id", 0), ""),
            f"#{q.get('issue','')}",
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i + 1, column=c, value=v)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.font = Font(size=10)
        ws.row_dimensions[i + 1].height = 46
        # 判定列留浅黄底，提示「填这里」
        ws.cell(row=i + 1, column=2).fill = PatternFill("solid", fgColor="FFF9E6")

    dst = Path("/mnt/d/llmloop/60条核对表.xlsx")
    if not dst.parent.is_dir():
        dst = ROOT / "out" / "60条核对表.xlsx"
    try:
        wb.save(dst)
    except PermissionError:
        dst = dst.with_name("60条核对表_最终版.xlsx")
        wb.save(dst)
        print("（原文件被 Excel 占用，已写到新文件）")

    from collections import Counter
    print(f"已写出：{dst}")
    print("类型分布：", dict(Counter(qtype_of(q.get("question", "")) for q in items)))
    print("重复组：")
    for g, m in groups.items():
        if len(m) > 1:
            print(f"  {g}：{len(m)} 条")
    print()
    print("=== 前 5 行 ===")
    for i, q in enumerate(items[:5], 1):
        print(f"  {i}. [{qtype_of(q.get('question',''))}] {q.get('question','')[:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
