#!/usr/bin/env python3
"""最终题库 v4：49 条去重后 + 11 条新主题补充 = 60 条。

分层切分保证两份主题分布接近：按 source 分组各取一半，再微调使每份正好 30。
种子固定 20261020。
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 20261020


def main() -> int:
    base = json.loads((DATA / "questions_dedup.json").read_text(encoding="utf-8"))
    sup = json.loads((DATA / "supplement_questions.json").read_text(encoding="utf-8"))
    allq_raw = base + sup
    print(f"合并 {len(base)} + {len(sup)} = {len(allq_raw)} 条")

    # 去重
    seen, merged = set(), []
    for q in allq_raw:
        if q["issue"] in seen:
            continue
        seen.add(q["issue"])
        merged.append(q)
    if len(merged) != 60:
        print(f"✗ 去重后 {len(merged)} 条，不是 60")
        return 1
    print("构成:", dict(Counter(q["source"] for q in merged)))

    random.seed(SEED)
    groups: dict[str, list] = {}
    for q in merged:
        groups.setdefault(q["source"], []).append(q)
    for g in groups.values():
        random.shuffle(g)

    # 每组一半进 optimize，凑不满/超了从最大的组调整
    opt, test = [], []
    for src, lst in groups.items():
        k = (len(lst) + 1) // 2
        opt += lst[:k]
        test += lst[k:]

    # 调整到 30/30
    while len(opt) > 30:
        test.append(opt.pop())
    while len(opt) < 30:
        opt.append(test.pop())

    random.shuffle(opt)
    random.shuffle(test)

    allq, qid = [], 1
    for q in opt:
        q["id"] = qid
        q["split"] = "optimize"
        allq.append(q)
        qid += 1
    for q in test:
        q["id"] = qid
        q["split"] = "test"
        allq.append(q)
        qid += 1

    print(f"\n优化用 {len(opt)} ｜ 测试用 {len(test)}")
    print("优化用:", dict(Counter(q["source"] for q in opt)))
    print("测试用:", dict(Counter(q["source"] for q in test)))

    bad = [q["id"] for q in allq if not (q.get("question") and q.get("answer") and q.get("doc_location"))]
    if bad:
        print("✗ 字段缺失:", bad)
        return 1

    p = DATA / "questions_v4.json"
    p.write_text(json.dumps(allq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {p}（60 条，种子 {SEED}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
