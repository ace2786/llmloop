"""抽查：detailed 提示词涨了 26 点，到底是真答对了，还是靠堆词刷分。

抽几道优化集的题，同一个配置跑两遍（concise / detailed），把问题和两种回答并排放出来，
人眼判断 detailed 是不是「答非所问但列了一堆参数名」。

用法：
    /home/ace/comfyvenv/bin/python scripts/check_answer_quality.py --n 3
    /home/ace/comfyvenv/bin/python scripts/check_answer_quality.py --n 5 --only-wrong
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rank_bm25 import BM25Okapi  # noqa: E402

from lib.judge import judge  # noqa: E402
from lib.llm import ask, build_prompt  # noqa: E402
from lib.text import tokenize  # noqa: E402

DATA = ROOT / "data"
MODEL_DIR = Path("/home/ace/models/bge-reranker-v2-m3")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="optimize")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--start", type=int, default=0, help="从第几道开始取")
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--topk", type=int, default=3)
    a = ap.parse_args()

    chunks = [json.loads(l) for l in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])

    from rerank_eval import Reranker

    ranker = Reranker(MODEL_DIR, device=a.device)

    qs = [q for q in json.loads((DATA / "questions.json").read_text(encoding="utf-8")) if q["split"] == a.split]
    qs = qs[a.start:a.start + a.n]

    for i, q in enumerate(qs, 1):
        scores = bm25.get_scores(tokenize(q["question"]))
        cand = sorted(range(len(scores)), key=lambda j: -scores[j])[:20]
        rs = ranker.score(q["question"], [chunks[j]["text"] for j in cand])
        order = sorted(range(len(cand)), key=lambda k: -rs[k])
        ctx = [chunks[cand[k]]["text"] for k in order[:a.topk]]

        print("=" * 72)
        print(f"[{i}] {q['question']}")
        print(f"    标准答案：{q['answer'][:220]}")
        print()
        for style in ("concise", "detailed"):
            got, dt = ask(a.model, build_prompt(q["question"], ctx, style))
            tag, why = judge(q["answer"], got)
            print(f"  【{style}】判定 {tag}（{why}）{dt:.1f}s")
            print(f"    {got[:420]}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
