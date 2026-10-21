#!/usr/bin/env python3
"""把勾好的 Excel 导回 questions_draft.json，并校验。

读取：data/待核对_265题.xlsx
更新：data/questions_draft.json（selected / answer / doc_location）

列位置按**表头名字**识别，不按固定列号，这样以后调整列顺序也不会错。

校验规则（不通过就报错，不静默跳过）：
  · 勾 ✓ 的必须正好 60 条
  · 每条勾 ✓ 的必须有标准答案和文档位置

用法：
    python scripts/import_review_xlsx.py
    python scripts/import_review_xlsx.py --allow-incomplete   # 只看进度，不强制 60 条
    python scripts/import_review_xlsx.py --xlsx /mnt/d/llmloop/待核对_265题.xlsx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
N_TOTAL = 60

CHECK = {"✓", "√", "v", "V", "Y", "y", "是", "1", "TRUE", "True", "true"}
CROSS = {"✗", "×", "x", "X", "N", "n", "否", "0", "FALSE", "False", "false"}

# 表头关键字 → 内部字段
COLMAP = {
    "序号": "id",
    "能用吗": "flag",
    "标准答案": "answer",
    "文档位置": "location",
}


def norm(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def find_cols(header_row) -> dict[str, int]:
    cols: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        name = norm(cell).replace("\n", "")
        for key, field in COLMAP.items():
            if key in name and field not in cols:
                cols[field] = idx
    return cols


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(DATA / "待核对_265题.xlsx"))
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="不强制 60 条，只报告进度")
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        print(f"找不到 {xlsx}，先运行 scripts/export_review_xlsx.py")
        return 1

    draft_path = DATA / "questions_draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in draft}

    wb = load_workbook(xlsx, data_only=True)
    ws = wb["待核对"]

    cols = find_cols([c.value for c in ws[1]])
    need = {"id", "flag", "answer", "location"}
    if not need.issubset(cols):
        print(f"✗ 表头识别失败，找到的列：{cols}")
        print(f"  需要：{need}")
        return 1
    print(f"列位置：{ {k: v + 1 for k, v in cols.items()} }")
    print()

    picked, marked_no, unclear, blank = [], [], [], []
    missing = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[cols["id"]] is None:
            continue
        try:
            qid = int(row[cols["id"]])
        except (TypeError, ValueError):
            continue
        if qid not in by_id:
            continue

        flag = norm(row[cols["flag"]])
        answer = norm(row[cols["answer"]]) if cols["answer"] < len(row) else ""
        location = norm(row[cols["location"]]) if cols["location"] < len(row) else ""

        q = by_id[qid]
        if flag in CHECK:
            q["selected"] = True
            q["answer"] = answer
            q["doc_location"] = location
            picked.append(q)
            if not answer or not location:
                missing.append((qid, q["question"][:40], bool(answer), bool(location)))
        elif flag in CROSS:
            q["selected"] = False
            marked_no.append(qid)
        elif flag == "?":
            q["selected"] = ""
            unclear.append(qid)
        else:
            q["selected"] = ""
            blank.append(qid)

    total = len(by_id)
    print("=" * 58)
    print("核对进度")
    print("=" * 58)
    print(f"  总条数     : {total}")
    print(f"  ✓ 能用     : {len(picked)}")
    print(f"  ✗ 不能用   : {len(marked_no)}")
    print(f"  ? 拿不准   : {len(unclear)}")
    print(f"  未填       : {len(blank)}")
    print(f"  还需勾选   : {max(0, N_TOTAL - len(picked))} 条")
    print()

    if missing:
        print(f"⚠ 有 {len(missing)} 条勾了 ✓ 但信息不全：")
        for qid, q, has_a, has_l in missing[:15]:
            lack = []
            if not has_a:
                lack.append("缺标准答案")
            if not has_l:
                lack.append("缺文档位置")
            print(f"    #{qid} {'/'.join(lack)}  {q}")
        if len(missing) > 15:
            print(f"    …… 还有 {len(missing) - 15} 条")
        print()

    if args.allow_incomplete:
        draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回（进度模式，不校验 60 条）")
        return 0

    if len(picked) != N_TOTAL:
        print(f"✗ 勾选数必须正好 {N_TOTAL} 条（现在 {len(picked)} 条）")
        print("  补够了再跑一次；或加 --allow-incomplete 只保存进度")
        return 1

    if missing:
        print("✗ 有勾了 ✓ 但缺标准答案或文档位置的，补齐再跑")
        return 1

    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ 已写回 {draft_path}")
    print()
    print("下一步：python scripts/build_questions.py --finalize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
