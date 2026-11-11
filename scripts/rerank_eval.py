#!/usr/bin/env python3
"""重排序实验：BM25 粗召回 → bge-reranker 精排 → 取 top-k 喂模型。

为什么要这个脚本：
  诊断发现 top-3 只命中 57.5% 的答案文档，top-10 能命中 82.5%
  —— 说明对的文档被召回了，只是排得太靠后。所以问题在「排序」不在「召回量」。
  上一步试过「加大 topk」（3→5），测试集只涨 1.2 点，判定无效。
  这一步换成「先粗召回 20 条，再用 cross-encoder 精排取 3 条」。

同一个脚本跑两种模式，保证对比公平：
  --no-rerank   BM25 直接取 top-k（复现 v0）
  默认          BM25 取 top-recall，重排后再取 top-k（v1）

依赖：torch + transformers（在 comfyvenv 里），jieba + rank_bm25。
运行：/home/ace/comfyvenv/bin/python scripts/rerank_eval.py --split optimize

输出：out/rerank_<split>_<mode>_<时间>.csv，逐题可查。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.judge import judge  # noqa: E402
from lib.llm import ask, build_prompt  # noqa: E402
from lib.text import tokenize  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "out"
MODEL_DIR = Path("/home/ace/models/bge-reranker-v2-m3")


def load_chunks() -> list[dict]:
    chunks = []
    for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(json.loads(line))
    return chunks


class Reranker:
    """bge-reranker-v2-m3 的薄封装：给 (query, doc) 打分。"""

    def __init__(self, path: Path, device: str = "cuda", batch: int = 10):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.batch = batch
        self.tok = AutoTokenizer.from_pretrained(str(path))
        dtype = torch.float16 if device == "cuda" else torch.float32
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(str(path), torch_dtype=dtype)
            .to(device)
            .eval()
        )
        self.device = device

    def score(self, query: str, docs: list[str]) -> list[float]:
        out: list[float] = []
        with self.torch.no_grad():
            for i in range(0, len(docs), self.batch):
                batch = docs[i:i + self.batch]
                pairs = [[query, d[:1500]] for d in batch]
                inp = self.tok(
                    pairs, padding=True, truncation=True, max_length=512, return_tensors="pt"
                ).to(self.device)
                logits = self.model(**inp).logits.view(-1).float()
                out.extend(logits.cpu().tolist())
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="optimize", choices=["optimize", "valid", "test", "all"])
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--topk", type=int, default=3, help="最终喂给模型的文档块数")
    ap.add_argument("--recall", type=int, default=20, help="BM25 粗召回条数（仅重排模式）")
    ap.add_argument("--no-rerank", action="store_true", help="只用 BM25，不重排（复现 v0）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    if a.split != "all":
        qs = [q for q in qs if q["split"] == a.split]
    if a.limit:
        qs = qs[:a.limit]

    chunks = load_chunks()
    from rank_bm25 import BM25Okapi

    t0 = time.time()
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    print(f"检索库 {len(chunks)} 个块，建索引 {time.time()-t0:.1f}s")

    ranker = None
    mode = "bm25"
    if not a.no_rerank:
        if not MODEL_DIR.exists():
            print(f"!! 找不到重排模型：{MODEL_DIR}")
            return 1
        t0 = time.time()
        ranker = Reranker(MODEL_DIR, device=a.device)
        print(f"重排模型加载完成 {time.time()-t0:.1f}s（{a.device}）")
        mode = f"rerank{a.recall}"

    print(f"模式 {mode}，题数 {len(qs)}，最终 top-{a.topk}，模型 {a.model}")
    print()

    rows = []
    t0 = time.time()
    for i, q in enumerate(qs, 1):
        scores = bm25.get_scores(tokenize(q["question"]))
        recall_n = a.topk if a.no_rerank else max(a.recall, a.topk)
        cand = sorted(range(len(scores)), key=lambda j: -scores[j])[:recall_n]

        if ranker is not None:
            rs = ranker.score(q["question"], [chunks[j]["text"] for j in cand])
            order = sorted(range(len(cand)), key=lambda k: -rs[k])
            top = [cand[k] for k in order[:a.topk]]
        else:
            top = cand[:a.topk]

        ctx = [chunks[j]["text"] for j in top]
        loc = f"{chunks[top[0]]['path']} > {chunks[top[0]]['heading']}" if top else ""

        try:
            got, dt = ask(a.model, build_prompt(q["question"], ctx))
        except Exception as e:  # noqa: BLE001
            got, dt = "", 0.0
            print(f"  [{i}] 调用失败 {type(e).__name__}")

        tag, why = judge(q["answer"], got)
        rows.append({
            "id": q["id"], "source": q.get("source", ""), "split": q["split"],
            "question": q["question"], "标准答案": q["answer"], "模型回答": got,
            "自动判分": tag, "判分依据": why, "命中文档": loc, "耗时s": round(dt, 1),
        })
        if i % 10 == 0 or i == len(qs):
            print(f"  [{i}/{len(qs)}] 累计 {(time.time()-t0)/60:.1f} 分钟")

    stamp = time.strftime("%m%d_%H%M")
    dst = OUT / f"rerank_{a.split}_{mode}_{stamp}.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter

    acc = Counter(r["自动判分"] for r in rows)
    n = len(rows)
    print()
    print(f"总耗时 {(time.time()-t0)/60:.1f} 分钟")
    print(f"结果：对 {acc['对']}　部分对 {acc['部分对']}　错 {acc['错']}　（共 {n}）")
    print(f"严格正确率 {acc['对']/n:.1%}　宽松正确率 {(acc['对']+acc['部分对'])/n:.1%}")
    print()
    print("分来源：")
    for src in sorted({r["source"] for r in rows}):
        g = [r for r in rows if r["source"] == src]
        ok = sum(1 for r in g if r["自动判分"] == "对")
        print(f"  {src:<18} {len(g):>3} 道　对 {ok}　严格 {ok/len(g):.1%}")
    print()
    print(f"已写出：{dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
