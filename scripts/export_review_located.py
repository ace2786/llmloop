#!/usr/bin/env python3
"""重建核对表：只保留「LLM 定位到答案」的候选，并保留用户已勾的标记。

相对上一版的改进：
  1. 摘录来自 LLM 精选的段落（不是 BM25 乱抓的 top-1）
  2. 只保留可定位的条目（66%），去掉明显没答案的，减少人工负担
  3. 保留用户在原表里已经打的 ✓ / ✗ / ?

输出：data/待核对_精筛.xlsx
"""
from __future__ import annotations

import argparse
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
    ("问题", 38),
    ("Issue", 9),
    ("关键词核对", 20),
    ("命中文档", 28),
    ("文档摘录（答案在这）", 58),
    ("答案草稿 + 依据\n(AI 抽取，供参考)", 40),
    ("标准答案\n(已预填，可改)", 34),
    ("文档位置\n(已预填，可改)", 26),
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
INPUT_FILL = PatternFill("solid", fgColor="FFF9E6")
DONE_FILL = PatternFill("solid", fgColor="E2EFDA")

WIN = 800

CHECK = {"✓", "√", "v", "V", "Y", "y"}
CROSS = {"✗", "×", "x", "X", "N", "n"}


def snippet(text: str, query: str, width: int = WIN) -> str:
    """围绕问题关键词取窗口。"""
    if not text:
        return ""
    if len(text) <= width:
        return text
    keys = re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]{2,30}", query)
    keys += re.findall(r"[\u4e00-\u9fff]{2,6}", query)
    best_pos, best_hits = 0, -1
    for k in keys:
        pos = text.lower().find(k.lower())
        if pos < 0:
            continue
        lo = max(0, pos - width // 3)
        hi = min(len(text), lo + width)
        hits = sum(1 for kk in keys if kk.lower() in text[lo:hi].lower())
        if hits > best_hits:
            best_hits, best_pos = hits, lo
    start = best_pos
    end = min(len(text), start + width)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


GENERIC_EN = {
    "yaml", "json", "yml", "api", "cli", "webui", "http", "https", "url", "file",
    "path", "name", "type", "value", "list", "true", "false", "none", "null",
    "config", "token", "data", "test", "code", "demo", "example", "user",
    "model", "dataset", "template", "packing", "gpu", "cpu", "npu", "ram", "vram",
}

ZH_STOP = {
    "怎么", "如何", "什么", "哪些", "哪个", "是否", "能否", "可以", "能不能",
    "有没有", "请问", "请教", "求助", "一下", "这个", "那个", "现在", "还是",
    "但是", "因为", "所以", "如果", "已经", "可能", "需要", "应该", "我们",
    "时候", "问题", "情况", "地方", "东西", "方法", "方式", "步骤", "使用",
    "进行", "支持", "参数", "配置", "设置", "默认", "区别", "含义", "作用",
    "用法", "文件", "命令", "行参", "同时", "目前", "新版", "代码", "作者",
}


def key_terms(question: str) -> list[str]:
    """从问题里挑出「必须在摘录里出现」的关键词。

    改进（v2）：
      · 英文加通用技术词黑名单（yaml/api/config 这类词到处都有，不能当判据）
      · 中文用 jieba 抽 2-4 字实词，去停用词
      · 英文标识符优先（含下划线或长度>=5）
    """
    import jieba

    en = re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]{2,30}", question)
    en = [
        w for w in en
        if w.lower() not in GENERIC_EN
        and w.lower() not in {"the", "and", "for", "with", "that", "this", "you", "how", "what",
                              "does", "can", "why", "when", "which", "please", "help", "issue"}
        and ("_" in w or len(w) >= 5)
    ]

    zh = [
        w for w in jieba.cut(question)
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", w) and w not in ZH_STOP
    ]

    merged = list(dict.fromkeys(en + zh))
    return merged[:6]


def keycheck(question: str, excerpt: str) -> tuple[str, list[str]]:
    """返回 (状态文本, 未命中的词)。命中率 >= 60% 算通过。"""
    terms = key_terms(question)
    if not terms:
        return "（无可校验关键词）", []
    low = excerpt.lower()
    miss = [t for t in terms if t.lower() not in low]
    hit_rate = 1 - len(miss) / len(terms)
    if not miss:
        return "✓ 全部命中", []
    if hit_rate >= 0.6:
        return f"◐ 部分命中({len(terms) - len(miss)}/{len(terms)})", miss
    return "⚠ 未命中: " + ", ".join(miss[:3]), miss


def read_old_marks(path: Path) -> dict:
    """读旧表里用户已填的标记、答案、文档位置。"""
    if not path.exists():
        return {}
    wb = load_workbook(path, data_only=True)
    ws = wb["待核对"]
    cols = {}
    for idx, cell in enumerate(ws[1], 1):
        name = str(cell.value or "").replace("\n", "")
        if "序号" in name:
            cols["id"] = idx
        elif "能用吗" in name:
            cols["flag"] = idx
        elif "标准答案" in name:
            cols["answer"] = idx
        elif "文档位置" in name:
            cols["loc"] = idx
    out = {}
    for r in range(2, ws.max_row + 1):
        qid = ws.cell(row=r, column=cols.get("id", 1)).value
        if qid is None:
            continue
        out[int(qid)] = {
            "flag": str(ws.cell(row=r, column=cols.get("flag", 2)).value or "").strip(),
            "answer": str(ws.cell(row=r, column=cols.get("answer", 9)).value or "").strip(),
            "loc": str(ws.cell(row=r, column=cols.get("loc", 10)).value or "").strip(),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default="/mnt/d/llmloop/待核对_265题.xlsx")
    ap.add_argument("--out", default=str(DATA / "待核对_精筛.xlsx"))
    ap.add_argument("--include-marked", action="store_true", default=True,
                    help="把用户已判 ✓ 的也纳入（即使没定位到）")
    args = ap.parse_args()

    draft = {q["id"]: q for q in json.loads((DATA / "questions_draft.json").read_text(encoding="utf-8"))}
    located = json.loads((DATA / "located.json").read_text(encoding="utf-8"))
    old = read_old_marks(Path(args.old))

    drafts: dict = {}
    dp = DATA / "answer_drafts.json"
    if dp.exists():
        drafts = json.loads(dp.read_text(encoding="utf-8"))
        n_ok = sum(1 for v in drafts.values() if v.get("ok"))
        print(f"读到答案草稿 {len(drafts)} 条（成功 {n_ok} 条）")
    else:
        print("⚠ 没有 answer_drafts.json，答案列会是空的")

    BLACKLIST = {193}  # 已确认误判：问 hf_transfer 下载加速，文档里没有

    # 收录集合：定位成功 或 用户已判 ✓
    keep = []
    for qid, q in draft.items():
        loc = located.get(str(qid)) or {}
        m = old.get(qid) or {}
        already_yes = m.get("flag") in CHECK
        if qid in BLACKLIST:
            continue
        if loc.get("ok") or (args.include_marked and already_yes):
            # ★ 只保留 ✓ 标记；✗ 和 ? 清空重判——因为摘录换成了更好的来源，
            #   之前判 ✗ 是基于旧摘录，结论可能已经不成立
            kept = dict(m)
            if not already_yes:
                kept["flag"] = ""
                kept["answer"] = ""
                kept["loc"] = ""
            keep.append((qid, q, loc, kept))

    # 排序：已判 ✓ 的放最后，其余按序号。
    # （关键词核对只作提示列，不参与排序——实测两版都不够可靠）
    def key(item):
        qid, q, loc, m = item
        done = 1 if m.get("flag") in CHECK else 0
        return (done, qid)

    keep.sort(key=key)

    wb = Workbook()
    ws = wb.active
    ws.title = "待核对"

    for col, (name, width) in enumerate(HEADERS, 1):
        c = ws.cell(row=1, column=col, value=name)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 36
    ws.freeze_panes = "C2"

    for i, (qid, q, loc, m) in enumerate(keep, start=2):
        paths = loc.get("paths") or []
        heads = loc.get("heads") or []
        texts = loc.get("texts") or []

        if paths:
            doc = paths[0] + (" > " + heads[0] if heads and heads[0] else "")
            excerpt = snippet(texts[0] if texts else "", q["question"])
        else:
            doc = q.get("doc_path_hint") or ""
            excerpt = snippet(q.get("doc_excerpt_hint") or "", q["question"])

        status, miss = keycheck(q["question"], excerpt)

        # 答案草稿（AI 从原文抽），预填到「标准答案」列，用户只需改不用打字
        dr = drafts.get(str(qid)) or {}
        draft_txt = dr.get("answer", "") if dr.get("ok") else ""
        quote = dr.get("quote", "")
        draft_cell = ""
        if draft_txt:
            draft_cell = "草稿：" + draft_txt
            if quote:
                draft_cell += "\n依据：" + quote[:160]

        answer_val = m.get("answer", "") or draft_txt
        loc_val = m.get("loc", "") or doc

        ws.cell(row=i, column=1, value=qid).alignment = Alignment(horizontal="center")
        ws.cell(row=i, column=2, value=m.get("flag", ""))
        ws.cell(row=i, column=3, value=q["question"])
        ws.cell(row=i, column=4, value=q.get("issue"))
        c5 = ws.cell(row=i, column=5, value=status)
        ws.cell(row=i, column=6, value=doc)
        ws.cell(row=i, column=7, value=excerpt)
        ws.cell(row=i, column=8, value=draft_cell)
        ws.cell(row=i, column=9, value=answer_val)
        ws.cell(row=i, column=10, value=loc_val)

        if miss:
            c5.fill = PatternFill("solid", fgColor="FCE4EC")
        else:
            c5.fill = PatternFill("solid", fgColor="E2EFDA")

        for col in (2, 9, 10):
            ws.cell(row=i, column=col).fill = INPUT_FILL
        if m.get("flag") in CHECK:
            ws.cell(row=i, column=2).fill = DONE_FILL

        for col in range(1, 11):
            c = ws.cell(row=i, column=col)
            c.border = BORDER
            if col in (3, 5, 6, 7, 8, 9, 10):
                c.alignment = Alignment(vertical="top", wrap_text=True)
            else:
                c.alignment = Alignment(horizontal="center", vertical="top")
        ws.row_dimensions[i].height = 96

    dv = DataValidation(type="list", formula1='"✓,✗,?"', allow_blank=True)
    dv.error = "只能选 ✓ / ✗ / ?"
    dv.errorTitle = "输入无效"
    dv.prompt = "✓ 能用  ✗ 不能用  ? 拿不准"
    dv.promptTitle = "这条能用吗"
    ws.add_data_validation(dv)
    dv.add(f"B2:B{len(keep) + 1}")
    ws.auto_filter.ref = f"A1:J{len(keep) + 1}"

    # 说明页
    ws2 = wb.create_sheet("说明")
    ws2.column_dimensions["A"].width = 104
    notes = [
        ("这一版和上一版有什么区别", True),
        ("", False),
        ("上一版的摘录是 BM25 抓的，经常抓错（你打 ✗ 的 77 条里，大部分是摘录里根本没有答案）。", False),
        ("这一版改了两步：先用 BM25 粗筛 20 段，再让模型从这 20 段里挑真正能回答问题的段落。", False),
        ("所以：这一版的摘录里，答案基本都在。可定位率从 11% 提到了 66%。", False),
        ("", False),
        ("只保留了「定位到答案」的条目", True),
        ("上一版 265 条，这一版只留下能定位的（约 120 条），去掉明显没答案的，你不用再看垃圾。", False),
        ("你之前打的 ✓ 都保留了，排在最后面（绿色）。", False),
        ("", False),
        ("你要做什么", True),
        ("① 从上往下看，读 C 列（问题）和 G 列（文档摘录）", False),
        ("② G 列里能回答 C 列 → B 列选 ✓，H 列写标准答案，I 列抄 F 列", False),
        ("③ 不能 → B 列选 ✗", False),
        ("④ 勾满 60 条就停，剩下的不用管", False),
        ("", False),
        ("判断标准（重要）", True),
        ("· 有具体数字、参数名、配置项、步骤 → 能当考题", False),
        ("· 只有「可以」「支持」「建议」这种模糊说法 → 不能", False),
        ("· 只有目录、参考文献、赞助商 → 不能", False),
        ("· 问「怎么调参最好」「报错怎么办」→ 不能（没有唯一答案）", False),
        ("", False),
        ("F 列是什么", True),
        ("「命中文档」= 答案在哪个文件的哪一节。你不需要看懂，I 列直接抄过去就行。", False),
        ("它的作用是给老师复查用：按这个路径能翻到原文核对。", False),
        ("", False),
        ("勾完怎么办", True),
        ("保存文件，然后跑：", False),
        ("  python scripts/import_review_xlsx.py --xlsx /mnt/d/llmloop/待核对_精筛.xlsx", False),
        ("脚本会校验正好 60 条、答案是否填全，然后切成 30 优化用 + 30 测试用。", False),
    ]
    for r, (text, bold) in enumerate(notes, start=1):
        c = ws2.cell(row=r, column=1, value=text)
        if bold:
            c.font = Font(bold=True, size=11, color="1F4E79")

    out = Path(args.out)
    wb.save(out)

    # 统计
    n_yes = sum(1 for _, _, _, m in keep if m.get("flag") in CHECK)
    n_no = sum(1 for _, _, _, m in keep if m.get("flag") in CROSS)
    n_blank = len(keep) - n_yes - n_no

    print("=" * 56)
    print("精筛表已生成")
    print("=" * 56)
    print(f"  总条数     : {len(keep)}（原 265 条里可定位的 + 已判 ✓ 的）")
    print(f"  已有 ✓     : {n_yes}")
    print(f"  已有 ✗     : {n_no}")
    print(f"  待你判断   : {n_blank}")
    print(f"  还需勾选   : {max(0, 60 - n_yes)} 条")
    print()
    print(f"  输出：{out}")
    print()
    print("前 3 行预览：")
    wb2 = load_workbook(out, data_only=True)
    ws3 = wb2["待核对"]
    for r in range(2, min(5, len(keep) + 2)):
        print(f"  #{ws3.cell(row=r, column=1).value}  {str(ws3.cell(row=r, column=3).value)[:40]}")
        print(f"      关键词：{str(ws3.cell(row=r, column=6).value)[:56]}")
        print(f"      文档　：{str(ws3.cell(row=r, column=7).value)[:56]}")
        print(f"      摘录　：{str(ws3.cell(row=r, column=8).value)[:72]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
