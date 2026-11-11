#!/usr/bin/env python3
"""扩挖真实提问：从已抓的 issue 里按「文档可答性」重新筛，比原来的 156 条宽得多。

为什么原来的路子产出低：
  select_questions.py 用的是 doc_score + 主题词 + 有评论 的加权排序，只取了前 156 条。
  5720 条 issue 里只筛出 156 条（2.7%），池子被人为收窄了。

这个脚本改成：
  1. 全部 5720 条都算 BM25 对文档的分数
  2. 取 doc_score 最高的一批（默认 300 条）
  3. 逐条用 top-3 文档生成答案
  4. 机械校验：答案里的硬实体必须出现在文档里（防编造）
  5. 输出候选 + 人工核对表

用法：
    python scripts/expand_real_questions.py --n 300 --dry-run
    python scripts/expand_real_questions.py --n 300
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.judge import hard_entities  # noqa: E402
from lib.llm import ask  # noqa: E402
from lib.text import tokenize  # noqa: E402

DATA = ROOT / "data"
CJK = re.compile(r"[\u4e00-\u9fff]")

# 「像提问」的标志：疑问词或问号
QUESTION_HINT = re.compile(
    r"(如何|怎么|怎样|为什么|为啥|是否|能不能|可不可以|有没有|报错|错误|失败|无法|"
    r"how (to|do|can|does)|why|what is|error|failed|cannot|unable|\?|？)",
    re.I,
)
# 明显不是「文档可答」的类型
NOT_ANSWERABLE = re.compile(
    r"(feature request|\[feature\]|^support .* for |proposal|roadmap|wishlist)", re.I
)
BAD_LABELS = {"enhancement", "feature request", "feature-request", "proposal", "discussion"}

# Qwen3 默认开思考模式，必须 /no_think，否则 num_predict 全被思考吃掉
PROMPT = """/no_think
根据下面几段文档，回答用户的问题。

要求：
1. 只答文档里明确写的内容，不要补充文档里没有的知识
2. 文档里没写答案就回答「文档里没有提到」
3. 回答控制在 80 字以内，直接给结论

【文档】
{ctx}

【问题】
{question}

【回答】"""


def load_issues() -> dict[int, dict]:
    seen: dict[int, dict] = {}
    for p in glob.glob(str(DATA / "issues" / "*.json")):
        if "/old/" in p:
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        items = d.get("items") if isinstance(d, dict) else d
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("number"):
                seen[it["number"]] = it
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="取 doc_score 最高的多少条")
    ap.add_argument("--min-body", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from rank_bm25 import BM25Okapi

    chunks = [json.loads(l) for l in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    print(f"文档块 {len(chunks)}")

    issues = load_issues()
    print(f"issue 去重后 {len(issues)}")

    bank = {q["question"] for q in json.loads((DATA / "questions.json").read_text(encoding="utf-8"))}
    print(f"题库已有 {len(bank)} 道（会去重）")

    # 只留「像提问」且有正文的
    pool = []
    skipped_kind = 0
    for num, it in issues.items():
        title = (it.get("title") or "").strip()
        body = (it.get("body") or "").strip()
        if len(body) < a.min_body or not title:
            continue

        # 排除「功能请求」这类文档里必然没有答案的
        labels = {str(l.get("name", "")).lower() for l in (it.get("labels") or []) if isinstance(l, dict)}
        if labels & BAD_LABELS or NOT_ANSWERABLE.search(title):
            skipped_kind += 1
            continue
        # 只留像提问的
        if not QUESTION_HINT.search(title):
            skipped_kind += 1
            continue

        q = title if len(title) > 12 else f"{title}\n{body[:300]}"
        if q in bank:
            continue
        scores = bm25.get_scores(tokenize(f"{title} {body[:600]}"))
        top = sorted(range(len(scores)), key=lambda j: -scores[j])[:3]
        pool.append({
            "number": num,
            "question": q,
            "url": it.get("html_url", ""),
            "doc_score": round(float(scores[top[0]]), 2),
            "top": top,
        })

    print(f"排除「不像提问/功能请求」{skipped_kind} 条，剩下 {len(pool)} 条可排")

    pool.sort(key=lambda x: -x["doc_score"])
    picked = pool[: a.n]
    print(f"按文档相关度取前 {len(picked)} 条（最高分 {picked[0]['doc_score'] if picked else 0}）")
    print()

    out = []
    for i, item in enumerate(picked, 1):
        ctx = "\n\n".join(f"[文档{j+1}] {chunks[k]['text'][:700]}" for j, k in enumerate(item["top"]))
        try:
            ans, _ = ask("qwen3-4b-local", PROMPT.format(ctx=ctx, question=item["question"]))
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] 失败 {type(e).__name__}")
            continue

        ans = ans.strip()
        if not ans or "没有提到" in ans:
            continue

        # 校验：答案里的硬实体必须出现在文档里
        docs_text = " ".join(chunks[k]["text"] for k in item["top"])
        ents = hard_entities(ans)
        if any(e.lower() not in docs_text.lower() for e in ents):
            continue

        cn = "".join(CJK.findall(ans))
        if len(cn) >= 6:
            grams = {cn[j:j + 2] for j in range(len(cn) - 1)}
            ratio = sum(1 for g in grams if g in docs_text) / len(grams)
            if ratio < 0.35:
                continue

        out.append({
            "issue": item["number"],
            "question": item["question"],
            "answer": ans,
            "source": "real-issue",
            "doc_location": f"{chunks[item['top'][0]]['path']} > {chunks[item['top'][0]]['heading']}",
            "evidence": chunks[item["top"][0]]["text"][:400],
            "url": item["url"],
            "doc_score": item["doc_score"],
        })
        if len(out) % 10 == 0:
            print(f"  通过 {len(out)} 条（已处理 {i}/{len(picked)}）")
            sys.stdout.flush()

    print()
    print(f"可用 {len(out)} 条（处理 {len(picked)} 条）")
    dst = DATA / "expanded_real.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出：{dst}")

    if a.dry_run:
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
            "id": f"issue-{item['issue']}",
            "question": item["question"],
            "answer": item["answer"],
            "source": "real-issue",
            "split": "optimize",
            "doc_location": item["doc_location"],
            "evidence": item["evidence"],
            "url": item["url"],
        })
        added += 1
    qp.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")
    real = sum(1 for q in qs if q.get("source", "").startswith("real"))
    print(f"并入 {added} 条；题库 {len(qs)} 道，真实 {real} 道 = {real/len(qs):.1%}")
    print("下一步：python scripts/resplit.py 重切分")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
