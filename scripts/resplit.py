#!/usr/bin/env python3
"""把题库重新按 3:3:4 切分（剔除题目后用）。

规则与 merge_questions.py 一致：**按来源分组各自切**，
保证优化/验证/测试三份里真实提问和文档反推都有，方便分来源报告。

用法：
    python scripts/resplit.py            # 只看结果
    python scripts/resplit.py --write    # 写回
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def group_of(q: dict) -> str:
    return "doc" if q.get("source") == "doc-synth" else "real"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    print(f"当前 {len(qs)} 道")

    for g in ("real", "doc"):
        group = [q for q in qs if group_of(q) == g]
        n = len(group)
        if not n:
            continue
        n_opt, n_val = round(n * 0.3), round(n * 0.3)
        for i, q in enumerate(group):
            q["split"] = "optimize" if i < n_opt else ("valid" if i < n_opt + n_val else "test")

    c = Counter(q.get("split") for q in qs)
    total = len(qs)
    print(f"切分：优化 {c['optimize']}　验证 {c['valid']}　测试 {c['test']}")
    print(f"比例：{c['optimize']/total:.1%} : {c['valid']/total:.1%} : {c['test']/total:.1%}")

    print()
    for s in ("optimize", "valid", "test"):
        g = [q for q in qs if q.get("split") == s]
        real = sum(1 for q in g if group_of(q) == "real")
        print(f"  {s:<9} {len(g):>3} 道（真实 {real} / 反推 {len(g)-real}）")

    if a.write:
        (DATA / "questions.json").write_text(
            json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\n已写回 questions.json")
    else:
        print("\n（未写回，确认后加 --write）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
