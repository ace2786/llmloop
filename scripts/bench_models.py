#!/usr/bin/env python3
"""对比几个免费模型在真实 RAG 场景下的表现（耗时 / token / 回答质量）。

用法：
    python scripts/bench_models.py
    python scripts/bench_models.py --models glm-4-flash glm-5.3-flash
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from week1 import Retriever  # noqa: E402

BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 三道有代表性的题：一道参数含义、一道配置方法、一道「资料里没有」
QUESTIONS = [
    "请问--cutoff_len这个参数如果不想让文本被截断的话应该如何设置比较好",
    "How to set save_steps? I set a 15,000, and mine has more than that",
    "LlamaFactory 支持昇腾 NPU 吗",
]

SYSTEM = (
    "你是 LlamaFactory 中文技术支持助手。"
    "只根据资料回答；资料里没有就说「资料里没有找到」。回答简洁准确。"
)


def call(model: str, key: str, messages: list[dict], max_tokens: int = 500) -> dict:
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    ).encode()
    req = urllib.request.Request(
        BASE,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        d = json.loads(resp.read())
    el = time.time() - t0
    u = d.get("usage") or {}
    return {
        "text": d["choices"][0]["message"]["content"].strip(),
        "elapsed": round(el, 2),
        "in_tokens": u.get("prompt_tokens", 0),
        "out_tokens": u.get("completion_tokens", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+",
                    default=["glm-4-flash", "glm-4.7-flash", "glm-5.3-flash"])
    ap.add_argument("--max-tokens", type=int, default=500,
                    help="输出上限。推理模型（glm-5.x）需要 2000+ 才出得来内容")
    ap.add_argument("--questions", type=int, default=0,
                    help="只跑前 N 道（0=全部）")
    args = ap.parse_args()

    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        print("环境变量 ZHIPU_API_KEY 未设置", file=sys.stderr)
        return 1

    retriever = Retriever(ROOT / "data" / "chunks.jsonl")

    questions = QUESTIONS[: args.questions] if args.questions else QUESTIONS

    summary = []
    for qi, q in enumerate(questions, 1):
        ctxs = retriever.top_k(q, k=3)
        ctx = "\n\n".join(
            f"[资料{i + 1}] {c['path']} | {c['heading']}\n{c['text']}"
            for i, c in enumerate(ctxs)
        )
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"【资料】\n{ctx}\n\n【问题】\n{q}"},
        ]

        print("=" * 70)
        print(f"题 {qi}：{q[:60]}")
        print("检索命中：")
        for c in ctxs:
            print(f"   [{c['score']:6.1f}] {c['path']} | {c['heading'][:52]}")
        print()

        for m in args.models:
            try:
                r = call(m, key, messages, max_tokens=args.max_tokens)
                print(f"── {m} ──  {r['elapsed']}s  in={r['in_tokens']} out={r['out_tokens']}")
                print("   " + (r["text"][:320].replace("\n", " ") if r["text"] else "(空回答，可能 token 被推理耗尽)"))
                summary.append(
                    {"q": qi, "model": m, "elapsed": r["elapsed"],
                     "in": r["in_tokens"], "out": r["out_tokens"]}
                )
            except Exception as e:  # noqa: BLE001
                print(f"── {m} ──  ✗ {type(e).__name__}: {e}")
            print()

    if summary:
        print("=" * 70)
        print("汇总（平均）")
        for m in args.models:
            rows = [s for s in summary if s["model"] == m]
            if not rows:
                continue
            n = len(rows)
            print(
                f"  {m:<18} 平均耗时 {sum(r['elapsed'] for r in rows) / n:5.2f}s"
                f"   平均输出 {sum(r['out'] for r in rows) / n:5.0f} token"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
