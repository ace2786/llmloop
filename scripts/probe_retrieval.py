#!/usr/bin/env python3
"""用 BM25 索引给每条候选提问做预检索，判断「答案是否在文档里能找到」。

产出：data/candidates_with_retrieval.json
每条候选附：top3 块、最高分、平均分、是否可用（分数阈值）
"""
import json
import os
import re
from collections import Counter

import jieba
import rank_bm25

CJK = re.compile(r"[\u4e00-\u9fff]")
DATA = os.path.expanduser("~/llmloop/data")


def tokenize(text):
    text = text.lower()
    en = re.findall(r"[a-z_][a-z0-9_.\-]{1,30}", text)
    zh = [w for w in jieba.cut(text) if CJK.search(w) and len(w) >= 2]
    return en + zh


def main():
    chunks = []
    with open(os.path.join(DATA, "chunks.jsonl"), encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    corpus = [tokenize(c["heading"] + "\n" + c["text"]) for c in chunks]
    bm25 = rank_bm25.BM25Okapi(corpus)

    with open(os.path.join(DATA, "issue_candidates.json"), encoding="utf-8") as f:
        cands = json.load(f)

    print("块数:", len(chunks), " 候选:", len(cands))

    results = []
    for c in cands:
        query_text = c["title"] + "\n" + (c.get("body") or "")[:800]
        qtok = tokenize(query_text)
        if not qtok:
            continue
        scores = bm25.get_scores(qtok)
        idx = scores.argsort()[::-1][:3]
        top = []
        for i in idx:
            ch = chunks[int(i)]
            top.append(
                {
                    "score": round(float(scores[int(i)]), 2),
                    "source": ch["source"],
                    "path": ch["path"],
                    "heading": ch["heading"][:80],
                    "text": ch["text"][:400],
                }
            )
        mx = top[0]["score"] if top else 0.0
        avg = round(sum(t["score"] for t in top) / len(top), 2) if top else 0.0
        # 检索命中的来源分布
        srcs = Counter(t["source"] for t in top)
        results.append(
            {
                **{k: c[k] for k in ("number", "title", "comments", "url", "state", "score")},
                "bm25_max": mx,
                "bm25_avg": avg,
                "hit_doc": srcs.get("doc", 0),
                "hit_example": srcs.get("example", 0),
                "top3": top,
            }
        )

    results.sort(key=lambda r: -r["bm25_max"])

    out = os.path.join(DATA, "candidates_with_retrieval.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    vals = [r["bm25_max"] for r in results]
    vals.sort(reverse=True)
    print("\n=== BM25 最高分分布 ===")
    for q in (0, 10, 25, 50, 75, 90, 100):
        i = min(int(len(vals) * q / 100), len(vals) - 1)
        print("   P%-3d = %8.2f" % (q, vals[i]))
    print("   均值  = %8.2f" % (sum(vals) / len(vals)))

    for th in (10, 15, 20, 25, 30):
        n = sum(1 for v in vals if v >= th)
        print("   分数 >= %-3d : %3d 条" % (th, n))

    print("\n=== 前 20 条（检索命中最好）===")
    for r in results[:20]:
        print(
            "  [%6.1f] #%-6s doc%d/ex%d  %s"
            % (r["bm25_max"], r["number"], r["hit_doc"], r["hit_example"], r["title"][:52])
        )

    print("\n已写出:", out)


if __name__ == "__main__":
    main()
