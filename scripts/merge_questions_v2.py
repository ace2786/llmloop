#!/usr/bin/env python3
"""合并正负样本 → 60 题，分层切分 30/30。

分层切分（关键）：
  随机切分可能让某一份全是负样本，导致两份难度不等。
  这里按 source 分别切，保证每份都是 13-14 正 + 16-17 负。

种子固定 SEED = 20261020，别人重跑得到完全相同的切分（第 11 节要求）。

输出：data/questions_v2.json
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 20261020


def main() -> int:
    pos = json.loads((DATA / "positive_questions.json").read_text(encoding="utf-8"))
    neg = json.loads((DATA / "negative_questions.json").read_text(encoding="utf-8"))
    print(f"正样本 {len(pos)} 条 ｜ 负样本 {len(neg)} 条")

    for p in pos:
        p["source"] = "real-positive"
        p["origin"] = f"GitHub Issue #{p['issue']}"
    for n in neg:
        n["source"] = "real-negative"
        n["origin"] = f"GitHub Issue #{n['issue']}"

    random.seed(SEED)
    pos_sorted = sorted(pos, key=lambda x: x["issue"])
    neg_sorted = sorted(neg, key=lambda x: x["issue"])
    random.shuffle(pos_sorted)
    random.shuffle(neg_sorted)

    # 分层：每份必须正好 30 条
    #   正 27 → 14 / 13      负 33 → 16 / 17
    #   合起来 14+16=30、13+17=30
    n_pos_opt = (len(pos_sorted) + 1) // 2      # 14
    n_neg_opt = 30 - n_pos_opt                  # 16
    opt = pos_sorted[:n_pos_opt] + neg_sorted[:n_neg_opt]
    test = pos_sorted[n_pos_opt:] + neg_sorted[n_neg_opt:]

    random.shuffle(opt)
    random.shuffle(test)

    allq = []
    qid = 1
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

    # 检查
    from collections import Counter
    print(f"\n优化用 {len(opt)} 条 ｜ 测试用 {len(test)} 条")
    print("优化用构成:", dict(Counter(q["source"] for q in opt)))
    print("测试用构成:", dict(Counter(q["source"] for q in test)))

    # 校验：每条必须有 question / answer / doc_location
    bad = [q["id"] for q in allq if not (q.get("question") and q.get("answer") and q.get("doc_location"))]
    if bad:
        print("✗ 字段缺失:", bad)
        return 1
    if len(allq) != 60:
        print(f"✗ 题数不是 60，而是 {len(allq)}")
        return 1

    p = DATA / "questions_v2.json"
    p.write_text(json.dumps(allq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ 已生成 {p}（{len(allq)} 条，种子 {SEED}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
