#!/usr/bin/env python3
"""读「人写出题表」，为每道题从**指定文档段落**生成标准答案，然后并入题库。

为什么答案能保证有出处：
  每道题都绑定了一个文档段落（表格 C 列），生成答案时只喂那一段，
  提示词里明确要求「只答这段文字里写的内容」。所以答案一定可回溯。

和之前失败的那条路的区别：
  之前是「先有 GitHub 问题，再用 BM25 去猜该看哪段文档」——猜错就答非所问（通过率 10%）。
  现在是「先定死文档段落，再让人对着它提问」——源头不会错。

用法：
    python scripts/import_human_questions.py --dry-run   # 只看生成结果，不入库
    python scripts/import_human_questions.py             # 生成并入库
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.llm import ask  # noqa: E402
from lib.judge import hard_entities  # noqa: E402

DATA = ROOT / "data"
CJK = re.compile(r"[\u4e00-\u9fff]")

# 注意：Qwen3 默认开思考模式，会把 num_predict 全用在 <think> 上导致答案被截断。
# 所以提示词必须以 /no_think 开头（lib/llm.py 的 build_prompt 也是这么做的）。
PROMPT = """/no_think
根据下面这段文档，回答用户的问题。

要求：
1. 只答这段文档里明确写的内容，不要补充文档里没有的知识
2. 如果文档里没写答案，就回答「文档里没有提到」
3. 回答控制在 60 字以内，直接给结论，不要复述问题

【文档】
{chunk}

【问题】
{question}

【回答】"""


def load_sheet(path: Path) -> list[dict]:
    from openpyxl import load_workbook

    ws = load_workbook(path, data_only=True).active
    rows = []
    for r in range(5, ws.max_row + 1):
        loc = ws.cell(row=r, column=2).value
        chunk = ws.cell(row=r, column=3).value
        q = ws.cell(row=r, column=4).value
        if not chunk:
            continue
        rows.append({
            "row": r,
            "loc": (loc or "").strip(),
            "chunk": str(chunk).strip(),
            "question": str(q or "").strip(),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="/mnt/d/llmloop/人写出题表.xlsx")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    p = Path(a.sheet)
    if not p.exists():
        p = ROOT / "out" / "人写出题表.xlsx"
    if not p.exists():
        print("找不到出题表")
        return 1

    rows = load_sheet(p)
    filled = [r for r in rows if r["question"]]
    print(f"表里 {len(rows)} 行，填了问题的 {len(filled)} 行")
    if not filled:
        print("D 列还空着——先对着文档原文写问题")
        return 1
    if a.limit:
        filled = filled[: a.limit]

    out: list[dict] = []
    bad = 0
    for i, r in enumerate(filled, 1):
        try:
            ans, _ = ask("qwen3-4b-local", PROMPT.format(chunk=r["chunk"], question=r["question"]))
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] 生成失败 {type(e).__name__}")
            bad += 1
            continue

        ans = ans.strip()
        if not ans or "没有提到" in ans:
            print(f"  [{i}] 跳过（文档里没答案）：{r['question'][:30]}")
            bad += 1
            continue

        # 校验一：答案里的硬实体（参数名、反引号内容、数字）必须出现在原文里。
        # 纯英文参数名没有中文，只靠中文重合会误杀（additional_target 就是这种）。
        ents = hard_entities(ans)
        missing = [e for e in ents if e.lower() not in r["chunk"].lower()]
        if missing:
            print(f"  [{i}] 跳过（答案含原文没有的实体 {missing[:3]}）：{r['question'][:26]}")
            bad += 1
            continue

        # 校验二：中文部分要和原文有重合（没有中文就不算）
        cn = "".join(CJK.findall(ans))
        if len(cn) >= 6:
            grams = {cn[j:j + 2] for j in range(len(cn) - 1)}
            hit = sum(1 for g in grams if g in r["chunk"])
            ratio = hit / len(grams) if grams else 0
            if ratio < 0.35:
                print(f"  [{i}] 跳过（中文重合 {ratio:.0%} 偏低）：{r['question'][:26]}")
                bad += 1
                continue
        else:
            ratio = 1.0  # 纯英文答案，靠实体校验就够了

        out.append({
            "question": r["question"],
            "answer": ans,
            "source": "human-written",
            "doc_location": r["loc"],
            "evidence": r["chunk"][:400],
            "overlap": round(ratio, 2),
        })
        if i <= 5 or i % 10 == 0:
            print(f"  [{i}] {r['question'][:34]}")
            print(f"      → {ans[:60]}  （重合 {ratio:.0%}）")

    print()
    print(f"可用 {len(out)} 条，跳过 {bad} 条")

    dst = DATA / "human_questions.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出：{dst}")

    if a.dry_run:
        print("（--dry-run，没有并入题库）")
        return 0

    # 并入题库
    qp = DATA / "questions.json"
    qs = json.loads(qp.read_text(encoding="utf-8"))
    exist = {q["question"] for q in qs}
    added = 0
    for item in out:
        if item["question"] in exist:
            continue
        qs.append({
            "id": f"human-{added + 1:03d}",
            "question": item["question"],
            "answer": item["answer"],
            "source": "human-written",
            "split": "optimize",   # 先放优化集，之后统一重切
            "doc_location": item["doc_location"],
            "evidence": item["evidence"],
        })
        added += 1
    qp.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"并入题库 {added} 条，题库现在 {len(qs)} 道")
    print("下一步：python scripts/resplit.py 重新切分，再同步到数据库")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
