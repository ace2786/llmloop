#!/usr/bin/env python3
"""用便宜的免费模型给 120 条候选做「可回答性预判」。

为什么需要：
  BM25 只测词面重合，挑出来的文档段落经常和问题无关（实测 #1 问多模态数据格式，
  命中的却是 DPO 数据格式）。人工核对时看到无关摘录，没法判断「答案在不在」。
  所以先用免费模型过一遍：给它问题 + 检索到的 3 段文档，让它判断能不能回答。

注意：
  · 这只是**预判**，供人工参考，不能替代人工确认（第 8.1 ⑤ 要求人工确认）
  · 用的是智谱免费模型，不花钱

输出：data/prejudge.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from week1 import Retriever  # noqa: E402

DATA = ROOT / "data"
BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

SYSTEM = """你是严格的技术文档审校员。我会给你一条用户提问，以及从 LlamaFactory 中文文档/示例配置里检索到的若干段落。

你的任务：判断这些段落里**有没有能直接回答该问题的信息**。

只输出一行 JSON，不要任何解释、不要 markdown 代码块：
{"verdict":"能用|部分|不能用","best":1,"reason":"一句话理由"}

判定标准：
- 能用：段落里明确写了答案（参数默认值、具体配置项、明确的支持/不支持说明）
- 部分：段落提到了相关内容，但缺少关键信息（比如只出现参数名没有解释）
- 不能用：段落和问题无关，或者只是目录/参考文献/赞助商

best 填最有用的那段资料的序号（1/2/3），如果都不能用填 0。
reason 不超过 40 字，说明关键依据。"""


def ask(key: str, question: str, ctxs: list[dict], model: str, retries: int = 3) -> dict:
    ctx_text = "\n\n".join(
        f"[资料{i + 1}] {c['path']} | {c['heading']}\n{c['text'][:900]}"
        for i, c in enumerate(ctxs)
    )
    user = f"【提问】\n{question}\n\n【检索到的段落】\n{ctx_text}"

    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 200,
        }
    ).encode()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                BASE,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                d = json.loads(resp.read())
            txt = d["choices"][0]["message"]["content"].strip()
            txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
            m = re.search(r"\{.*\}", txt, re.S)
            if not m:
                raise ValueError(f"无法解析输出：{txt[:80]}")
            obj = json.loads(m.group(0))
            return {
                "verdict": obj.get("verdict", "不能用"),
                "best": int(obj.get("best", 0) or 0),
                "reason": str(obj.get("reason", ""))[:80],
                "usage": (d.get("usage") or {}),
            }
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if attempt == retries:
                return {"verdict": "ERROR", "best": 0, "reason": f"HTTP {e.code}", "usage": {}}
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                return {"verdict": "ERROR", "best": 0, "reason": str(e)[:80], "usage": {}}
            time.sleep(2)
    return {"verdict": "ERROR", "best": 0, "reason": "未知", "usage": {}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm-4-flash",
                    help="预判用的模型，默认 glm-4-flash（快且免费）")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        print("环境变量 ZHIPU_API_KEY 未设置", file=sys.stderr)
        return 1

    draft = json.loads((DATA / "questions_draft.json").read_text(encoding="utf-8"))
    if args.limit:
        draft = draft[: args.limit]

    retriever = Retriever(DATA / "chunks.jsonl")

    out_path = DATA / "prejudge.json"
    results = {}
    if out_path.exists():
        results = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"已有 {len(results)} 条预判，跳过已完成")

    t0 = time.time()
    for i, q in enumerate(draft, 1):
        qid = str(q["id"])
        if qid in results and results[qid].get("verdict") not in ("ERROR", None):
            continue
        ctxs = retriever.top_k(q["question"], k=3)
        r = ask(key, q["question"], ctxs, args.model)
        results[qid] = {
            "verdict": r["verdict"],
            "best": r["best"],
            "reason": r["reason"],
            "top_paths": [c["path"] for c in ctxs],
            "top_heads": [c["heading"] for c in ctxs],
            "top_texts": [c["text"][:900] for c in ctxs],
            "top_scores": [c["score"] for c in ctxs],
        }
        print(f"  [{i}/{len(draft)}] #{qid} {r['verdict']:<4} {r['reason'][:40]}")
        if i % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.3)

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter

    c = Counter(v.get("verdict") for v in results.values())
    print()
    print("=" * 50)
    print("预判汇总")
    for k, v in c.most_common():
        print(f"  {k:<6} {v}")
    print(f"  耗时 {time.time() - t0:.0f}s")
    print(f"  输出 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
