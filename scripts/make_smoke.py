#!/usr/bin/env python3
"""从核对表取前 N 条，生成「冒烟测试」用的 questions.json。

用途：在真正的 60 道题定稿之前，先用几条跑通链路、验证脚本、调试检索。

注意：**这不是正式题目**。正式题目必须走 build_questions.py --finalize，
      且每条的标准答案要人工核对过（第 8.1 ⑤）。

用法：
    python scripts/make_smoke.py              # 默认 3 条，输出 data/questions_smoke.json
    python scripts/make_smoke.py -n 5 --out /tmp/q.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--num", type=int, default=3)
    ap.add_argument("--out", default=str(DATA / "questions_smoke.json"))
    args = ap.parse_args()

    src = DATA / "review_sheet.json"
    if not src.exists():
        print(f"找不到 {src}，先运行 scripts/make_review_sheet.py")
        return 1

    rows = json.loads(src.read_text(encoding="utf-8"))
    qs = []
    for i, r in enumerate(rows[: args.num], 1):
        qs.append(
            {
                "id": i,
                "issue": r["number"],
                "issue_url": r.get("url"),
                "question": r["title"],
                "answer": "（冒烟测试，未填标准答案）",
                "doc_location": r.get("doc_path") or "",
                "split": "optimize",
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"已生成 {out}（{len(qs)} 条，仅供冒烟测试）")
    for q in qs:
        print(f"  #{q['id']} {q['question'][:64]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
