#!/usr/bin/env python3
"""读取人工核对表的判定，按结果重新生成题库。

判定列兼容多种写法（不用管表头写的是什么）：
  T / t / 对 / ✓ / 1 / true   → 通过
  F / f / 错 / ✗ / 0 / false  → 剔除
  ? / 查 / u / U / 空          → 待查（默认也剔除，但单独统计）

用法：
    python scripts/apply_review.py                    # 只看统计，不改题库
    python scripts/apply_review.py --write            # 真的写回 questions.json
    python scripts/apply_review.py --keep-unknown     # 「查」的也保留（默认剔除）
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

OK = {"t", "对", "✓", "√", "1", "true", "y", "yes", "能"}
NO = {"f", "错", "✗", "×", "x", "0", "false", "n", "no", "不能"}
UNK = {"?", "？", "查", "u", "unknown", ""}


def norm(v) -> str:
    return str(v if v is not None else "").strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="/mnt/d/llmloop/60条核对表_最终版.xlsx")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--keep-unknown", action="store_true")
    a = ap.parse_args()

    p = Path(a.xlsx)
    if not p.exists():
        print(f"找不到核对表：{p}")
        return 1

    ws = load_workbook(p, data_only=True).active
    head = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    # 定位列（不依赖固定序号，防止列顺序变过）
    def col(name: str) -> int:
        for c, h in enumerate(head, 1):
            if h and name in str(h):
                return c
        return 0

    c_verdict = col("判定")
    c_q = col("问题")
    c_issue = col("Issue")
    if not c_verdict or not c_q:
        print("表头里找不到「判定」或「问题」列，实际表头：", head)
        return 1

    rows = []
    for r in range(2, ws.max_row + 1):
        v = norm(ws.cell(row=r, column=c_verdict).value)
        q = ws.cell(row=r, column=c_q).value
        if not q:
            continue
        issue = str(ws.cell(row=r, column=c_issue).value or "").lstrip("#")
        if v in OK:
            tag = "通过"
        elif v in NO:
            tag = "剔除"
        else:
            tag = "待查"
        rows.append({"row": r, "issue": issue, "question": q, "verdict": v, "tag": tag})

    from collections import Counter
    c = Counter(r["tag"] for r in rows)
    print(f"读入 {len(rows)} 条")
    print(f"  通过 {c['通过']}　剔除 {c['剔除']}　待查/未填 {c['待查']}")

    unfilled = [r for r in rows if r["verdict"] == ""]
    if unfilled:
        print(f"  还有 {len(unfilled)} 条完全没填（第 {unfilled[0]['row']} 行起）")
    unknown = [r for r in rows if r["tag"] == "待查" and r["verdict"] != ""]
    if unknown:
        print(f"  填了「查」的 {len(unknown)} 条：")
        for r in unknown[:8]:
            print(f"    #{r['issue']} {r['question'][:44]}")

    keep_issues = {r["issue"] for r in rows if r["tag"] == "通过"}
    if a.keep_unknown:
        keep_issues |= {r["issue"] for r in rows if r["tag"] == "待查"}

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    before = len(qs)
    kept, dropped = [], []
    for q in qs:
        if q.get("source") == "real-issue":
            if str(q.get("issue", "")) in keep_issues:
                kept.append(q)
            else:
                dropped.append(q)
        else:
            kept.append(q)

    print()
    print(f"题库 {before} 道 → 保留 {len(kept)} 道（剔除 {len(dropped)} 道 real-issue）")

    from collections import Counter as C2
    print("  保留后的来源：", dict(C2(q.get("source", "?") for q in kept)))

    if not a.write:
        print()
        print("（未写回，确认后加 --write）")
        if dropped:
            print(f"将被剔除的前 5 条：")
            for q in dropped[:5]:
                print(f"  #{q.get('issue')} {q.get('question','')[:46]}")
        return 0

    bak = DATA / "questions.before_review.json"
    shutil.copy2(DATA / "questions.json", bak)
    (DATA / "questions.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写回 questions.json（备份 {bak.name}）")
    print("下一步：重新切分 3:3:4 → python scripts/resplit.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
