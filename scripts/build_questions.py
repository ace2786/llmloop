#!/usr/bin/env python3
"""题目草稿 → 最终定稿。

两阶段：

  ① 生成草稿（默认）
     python scripts/build_questions.py --draft
     读 data/review_sheet.json，输出 data/questions_draft.json（120 条，答案与勾选留空）

  ② 定稿（人工填完 selected / answer / doc_location 之后）
     python scripts/build_questions.py --finalize
     校验：勾选必须正好 60 条、每条都有标准答案和文档位置
     按固定随机种子切成 30 条「优化用」+ 30 条「测试用」
     输出 data/questions.json

随机种子写在脚本里（第 11 节要求），换机器重跑得到同样切分。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# ★ 第 11 节要求：随机种子写进脚本
SEED = 20261020
N_OPTIMIZE = 30
N_TEST = 30
N_TOTAL = N_OPTIMIZE + N_TEST


def do_draft(limit: int = 0) -> int:
    """生成草稿。

    顺序规则（关键）：
      1. 先放 review_sheet.json 里的 120 条，**保持原顺序** → id 1-120
         这样已有的人工勾选和 AI 预判（按 id 索引）不会失效
      2. 再追加 question_candidates.json 里没出现过的候选 → id 121+
    """
    sheet = DATA / "review_sheet.json"
    cand = DATA / "question_candidates.json"

    if not sheet.exists():
        print(f"找不到 {sheet}，请先运行 scripts/make_review_sheet.py", file=sys.stderr)
        return 1

    rows = json.loads(sheet.read_text(encoding="utf-8"))
    print(f"基础池：review_sheet.json（{len(rows)} 条，保持原顺序）")

    if cand.exists():
        pool = json.loads(cand.read_text(encoding="utf-8"))
        seen = {r["number"] for r in rows}
        extras = []
        for r in pool:
            if r["number"] in seen:
                continue
            seen.add(r["number"])
            top = (r.get("top3") or [{}])[0]
            extras.append(
                {
                    "number": r["number"],
                    "url": r.get("url"),
                    "title": r["title"],
                    "doc_path": top.get("path", ""),
                    "doc_heading": top.get("heading", ""),
                    "doc_text": top.get("text", ""),
                }
            )
        print(f"追加池：question_candidates.json 里新增 {len(extras)} 条")
        rows = rows + extras
    else:
        print("⚠ 没有 question_candidates.json，只能用 120 条")

    if limit:
        rows = rows[:limit]

    print(f"合计：{len(rows)} 条")
    draft = []
    for i, r in enumerate(rows, 1):
        draft.append(
            {
                "id": i,
                "issue": r["number"],
                "issue_url": r.get("url"),
                "question": r["title"],
                "answer": "",
                "doc_location": "",
                "doc_path_hint": r.get("doc_path"),
                "doc_heading_hint": r.get("doc_heading"),
                "doc_excerpt_hint": (r.get("doc_text") or "")[:500],
                "selected": "",
                "split": "",
                "note": "",
            }
        )

    out = DATA / "questions_draft.json"
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成草稿：{out}")
    print(f"  条数：{len(draft)}")
    print()
    print("下一步（人工）：")
    print("  1. 打开 data/questions_draft.json")
    print("  2. 逐条看 question / doc_path_hint / doc_excerpt_hint")
    print("  3. 能用的填 \"selected\": true，并在 answer 写标准答案、doc_location 写位置")
    print("     例：\"doc_location\": \"docs/zh/configuration/training.md > TrainingArguments > Checkpoint 与日志配置\"")
    print("  4. 用不了的填 \"selected\": false（或直接留空）")
    print("  5. 勾满 60 条后运行：python scripts/build_questions.py --finalize")
    return 0


def do_finalize() -> int:
    src = DATA / "questions_draft.json"
    if not src.exists():
        print(f"找不到 {src}，请先运行 --draft", file=sys.stderr)
        return 1
    draft = json.loads(src.read_text(encoding="utf-8"))

    picked = [q for q in draft if q.get("selected") in (True, "true", "True", 1, "1", "✓")]
    print(f"勾选条数：{len(picked)}")

    if len(picked) != N_TOTAL:
        print(
            f"\n✗ 勾选数必须正好 {N_TOTAL} 条（现在 {len(picked)} 条）",
            file=sys.stderr,
        )
        return 1

    # 校验答案与文档位置
    bad = [
        q
        for q in picked
        if not str(q.get("answer", "")).strip()
        or not str(q.get("doc_location", "")).strip()
    ]
    if bad:
        print(f"\n✗ 有 {len(bad)} 条缺标准答案或文档位置：", file=sys.stderr)
        for q in bad[:10]:
            print(f"   #{q['id']} {q['question'][:50]}", file=sys.stderr)
        return 1

    # ★ 固定种子切分
    rng = random.Random(SEED)
    order = list(range(len(picked)))
    rng.shuffle(order)
    optimize_idx = set(order[:N_OPTIMIZE])

    final = []
    for i, q in enumerate(picked):
        final.append(
            {
                "id": i + 1,
                "issue": q["issue"],
                "issue_url": q.get("issue_url"),
                "question": q["question"],
                "answer": q["answer"].strip(),
                "doc_location": q["doc_location"].strip(),
                "split": "optimize" if i in optimize_idx else "test",
            }
        )

    final.sort(key=lambda x: x["id"])
    out = DATA / "questions.json"
    out.write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")

    n_opt = sum(1 for q in final if q["split"] == "optimize")
    n_test = len(final) - n_opt
    print(f"\n✓ 已生成 {out}")
    print(f"  优化用：{n_opt} 条")
    print(f"  测试用：{n_test} 条")
    print(f"  随机种子：{SEED}（写在 scripts/build_questions.py 里，可复算）")
    print("\n★ 测试集已封存：改进阶段只允许跑 --split optimize")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draft", action="store_true", help="生成候选草稿")
    g.add_argument("--finalize", action="store_true", help="校验并切分成 30/30")
    ap.add_argument("--limit", type=int, default=0, help="草稿只取前 N 条（0=全部）")
    args = ap.parse_args()
    return do_draft(args.limit) if args.draft else do_finalize()


if __name__ == "__main__":
    sys.exit(main())
