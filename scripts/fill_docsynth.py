#!/usr/bin/env python3
"""从「未使用的文档反推题」里补足题库到目标数。

为什么走这条路：人工核对 60 条真实提问只有 6 条通过（10%）。
按这个通过率，补 54 道要生成 540 条候选——不现实。
而文档反推题（参数表 → 问题）天然「问答对应」，质量稳定，
第 13 节也明确允许「用文档反推题目可以补充，但要单独标来源」。

质量闸门：答案里的默认值必须能在 evidence 里逐字找到，否则不收。

用法：
    python scripts/fill_docsynth.py --need 54            # 只看能补多少
    python scripts/fill_docsynth.py --need 54 --write    # 写回
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BT = chr(96)


def norm(s: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "").lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", type=int, default=54)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    have = {q.get("param") for q in qs if q.get("source") == "doc-synth"}
    print(f"题库现有 {len(qs)} 道，其中 doc-synth {len(have)} 道")

    pool = json.loads((DATA / "questions_docsynth.json").read_text(encoding="utf-8"))
    print(f"反推题池共 {len(pool)} 条")

    fresh, bad = [], []
    for it in pool:
        if it.get("param") in have:
            continue
        # 闸门：答案里的默认值必须出现在 evidence 里
        m = re.search(r"默认值(?:为|是)?\s*([^。]+)。?$", it["answer"].strip())
        if not m:
            bad.append((it["param"], "取不到默认值"))
            continue
        val = m.group(1).strip().rstrip("。")
        if norm(val) not in norm(it.get("evidence", "")):
            bad.append((it["param"], "默认值不在原文"))
            continue
        fresh.append(it)

    print(f"可用新题 {len(fresh)} 条（被闸门挡掉 {len(bad)} 条）")
    if bad[:3]:
        print("  挡掉的样例：", [(p, r) for p, r in bad[:3]])

    take = fresh[: a.need]
    print(f"本次补 {len(take)} 条")

    if len(take) < a.need:
        print(f"⚠ 不够 {a.need} 条，只能补 {len(take)} 条")

    next_id = max((q.get("id", 0) for q in qs), default=0) + 1
    for i, it in enumerate(take):
        qs.append({
            "id": next_id + i,
            "question": it["question"],
            "answer": it["answer"],
            "doc_location": it["doc_location"],
            "evidence": it["evidence"],
            "source": "doc-synth",
            "origin": it.get("origin", "文档参数表反推"),
            "param": it["param"],
            "split": "",
        })

    print()
    from collections import Counter
    print(f"补后总数 {len(qs)} 道")
    print("  来源：", dict(Counter(q.get("source", "?") for q in qs)))

    if a.write:
        (DATA / "questions.json").write_text(
            json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\n已写回 questions.json")
        print("下一步：python scripts/resplit.py --write")
    else:
        print("\n（未写回，确认后加 --write）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
