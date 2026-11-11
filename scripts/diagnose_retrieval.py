"""诊断检索质量：重排后的 top-3 到底命中没命中，错题归因到检索还是生成。

不调用大模型，只跑 BM25 + 重排，所以 80 道题几十秒能跑完。

输出三件事：
1. BM25 top-3 命中率 vs 重排 top-3 命中率（重排有没有把对的往前挪）
2. 正确文档在重排后的排名分布（还差几名能进 top-3）
3. 答错的题里，检索没命中 vs 检索命中但答错 各多少
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rank_bm25 import BM25Okapi  # noqa: E402

from lib.text import tokenize  # noqa: E402

MODEL_DIR = Path("/home/ace/models/bge-reranker-v2-m3")


def load_chunks() -> list[dict]:
    p = ROOT / "data/chunks.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_verdicts(csv_path: Path) -> dict[str, str]:
    if not csv_path.exists():
        return {}
    return {
        r["question"]: r["自动判分"]
        for r in csv.DictReader(open(csv_path, encoding="utf-8-sig"))
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--recall", type=int, default=20)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--csv", default="out/rerank_v1_test.csv", help="重排版的评测结果，用于归因")
    ap.add_argument("--rank-depth", type=int, default=10, help="统计正确文档排到第几")
    a = ap.parse_args()

    chunks = load_chunks()
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])

    from rerank_eval import Reranker  # noqa: E402

    ranker = Reranker(MODEL_DIR, device=a.device)

    qs = [
        q for q in json.load(open(ROOT / "data/questions.json", encoding="utf-8"))
        if q["split"] == a.split
    ]
    verdicts = load_verdicts(ROOT / a.csv)

    hit_bm25 = hit_rr = 0
    no_loc = 0
    gen_fail = ret_fail = 0
    rank_hist: Counter = Counter()
    rescued = worsened = 0
    examples = []

    for q in qs:
        loc = (q.get("doc_location") or "").strip()
        if not loc:
            no_loc += 1
            continue
        want = loc.split(" > ")[0].strip()

        scores = bm25.get_scores(tokenize(q["question"]))
        depth = max(a.recall, a.topk)
        cand = sorted(range(len(scores)), key=lambda j: -scores[j])[:depth]

        ok_bm25 = any(chunks[j]["path"] == want for j in cand[:a.topk])
        if ok_bm25:
            hit_bm25 += 1

        rs = ranker.score(q["question"], [chunks[j]["text"] for j in cand])
        order = sorted(range(len(cand)), key=lambda k: -rs[k])
        ranked = [cand[k] for k in order]

        # 正确文档在重排后的名次（1 起）；不在候选里则记为 99
        pos = 99
        for i, j in enumerate(ranked, 1):
            if chunks[j]["path"] == want:
                pos = i
                break
        if pos <= a.topk:
            hit_rr += 1
        rank_hist[min(pos, a.rank_depth + 1)] += 1

        if ok_bm25 and pos > a.topk:
            worsened += 1
        if not ok_bm25 and pos <= a.topk:
            rescued += 1

        v = verdicts.get(q["question"])
        if v and v != "对":
            if pos <= a.topk:
                gen_fail += 1
            else:
                ret_fail += 1
            if len(examples) < 6 and pos > a.topk:
                examples.append((q["question"], pos, v))

    n = len(qs) - no_loc
    print(f"题数 {len(qs)}，其中有标注出处 {n}（{no_loc} 道无出处，跳过）")
    print()
    print(f"BM25 top-{a.topk} 命中率      {hit_bm25}/{n} = {hit_bm25 / n:.1%}")
    print(f"重排 top-{a.topk} 命中率      {hit_rr}/{n} = {hit_rr / n:.1%}")
    print(f"  重排救回来（BM25 没进、重排进了） {rescued} 道")
    print(f"  重排弄丢了（BM25 进了、重排没进） {worsened} 道")
    print()
    print(f"正确文档在重排后的名次分布（候选 {a.recall} 条内）：")
    for k in sorted(rank_hist):
        label = f"第 {k} 名" if k <= a.rank_depth else f">{a.rank_depth} 名或不在候选"
        bar = "█" * rank_hist[k]
        print(f"  {label:16} {rank_hist[k]:>3}  {bar}")
    print()
    if gen_fail + ret_fail:
        tot = gen_fail + ret_fail
        print(f"答错的 {tot} 道题归因：")
        print(f"  检索已命中、模型没答出来   {gen_fail} 道（{gen_fail / tot:.0%}）← 生成/读取问题")
        print(f"  检索就没命中              {ret_fail} 道（{ret_fail / tot:.0%}）← 检索问题")
    if examples:
        print()
        print("检索没命中的例子（问题 / 正确文档名次 / 判定）：")
        for q, pos, v in examples:
            print(f"  [{pos:>2}] {v:4} {q[:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
