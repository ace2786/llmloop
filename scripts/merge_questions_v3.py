#!/usr/bin/env python3
"""最终题库：27 条参数类 + 33 条操作类 = 60 条全正样本（无负样本）。

为什么去掉负样本：
  老师第 8.1 ⑤ 要求「人工确认答案能在文档或示例配置里找到」。
  负样本的答案是「文档里没有」，字面上不符合。
  补挖操作类问题后正样本已够 60 条，不需要负样本了。

分层切分保证两份难度相当：
  参数类 27 → 14 / 13
  操作类 33 → 16 / 17
  合计     30 / 30

种子固定 20261020。
输出：data/questions_v3.json
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
    param = json.loads((DATA / "positive_questions.json").read_text(encoding="utf-8"))
    op = json.loads((DATA / "op_positive.json").read_text(encoding="utf-8"))
    print(f"参数类 {len(param)} 条 ｜ 操作类 {len(op)} 条")

    for p in param:
        p["source"] = "real-param"
        p["origin"] = f"GitHub Issue #{p['issue']}"
    for o in op:
        o["source"] = "real-operation"
        o["origin"] = f"GitHub Issue #{o['issue']}"

    # 去重（同一 issue 只留一条，参数类优先）
    seen, merged = set(), []
    for q in param + op:
        if q["issue"] in seen:
            continue
        seen.add(q["issue"])
        merged.append(q)
    if len(merged) != 60:
        print(f"⚠ 去重后 {len(merged)} 条，不是 60")
    print(f"去重后 {len(merged)} 条 ｜ 构成 {dict(Counter(q['source'] for q in merged))}")

    random.seed(SEED)
    p_list = [q for q in merged if q["source"] == "real-param"]
    o_list = [q for q in merged if q["source"] == "real-operation"]
    random.shuffle(p_list)
    random.shuffle(o_list)

    # 目标 30/30：参数类 14/13（或按实际），操作类补足
    n_p = min(14, len(p_list))
    n_o = 30 - n_p
    opt = p_list[:n_p] + o_list[:n_o]
    test = p_list[n_p:] + o_list[n_o:]
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
    if len(allq) != 60 or len(opt) != 30 or len(test) != 30:
        print(f"✗ 数量不对: 总 {len(allq)} / 优化 {len(opt)} / 测试 {len(test)}")
        return 1

    p = DATA / "questions_v3.json"
    p.write_text(json.dumps(allq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {p}（60 条全正样本，种子 {SEED}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
