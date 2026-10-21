#!/usr/bin/env python3
"""为每条候选从文档原文里抽取「标准答案草稿」。

为什么需要：
  人工核对时，让用户「自己想出标准答案」是不现实的——他不一定熟悉 LlamaFactory。
  但让用户「核对 AI 从原文里抽的答案对不对」是现实的：只要比对两段短文本。

  这是合法的：第 8.1 ⑤ 要求「人工确认答案能在文档或示例配置里找到」，
  人工确认 ≠ 人工创作。AI 抽取 + 人工确认，符合要求。

严格约束：
  · 只能用原文里明确写的内容，不许补充、不许推断
  · 原文里没有明确答案 → 输出 NONE，该条标记为「抽取失败」

输出：data/answer_drafts.json
  { "3": {"answer": "...", "quote": "原文依据片段", "ok": true}, ... }
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
DATA = ROOT / "data"
BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

SYSTEM = """你是严格的技术文档摘录员。我会给你一条用户提问，以及从 LlamaFactory 文档里检索到的原文。

任务：从原文中**摘出**能回答该问题的最小充分信息，写成一句简洁中文答案（不超过 70 字）。

铁律：
1. 只能用原文里**明确写出**的内容。原文没写的，一个字都不许补。
2. 不许用自己的知识补充、不许推断、不许「一般来说」。
3. 原文只是提到概念但没有具体答案 → 输出 NONE。
4. 原文是目录、参考文献、赞助商、项目列表 → 输出 NONE。
5. 答案里要带上具体的参数名、默认值、配置项或步骤。

只输出 JSON，不要 markdown 代码块：
{"answer":"答案或 NONE","quote":"原文里最关键的 1-2 句（原文照抄，不改写）"}"""


def call(key: str, model: str, question: str, excerpt: str, retries: int = 3) -> dict:
    user = f"【提问】\n{question}\n\n【原文】\n{excerpt[:2500]}"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 500,
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
                raise ValueError(f"无法解析：{txt[:80]}")
            obj = json.loads(m.group(0))
            ans = str(obj.get("answer", "")).strip()
            return {
                "answer": ans,
                "quote": str(obj.get("quote", "")).strip()[:300],
                "ok": bool(ans) and ans.upper() != "NONE",
            }
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if attempt == retries:
                return {"answer": "", "quote": f"HTTP {e.code}", "ok": False}
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                return {"answer": "", "quote": str(e)[:80], "ok": False}
            time.sleep(2)
    return {"answer": "", "quote": "未知错误", "ok": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm-4-flash")
    ap.add_argument("--verdicts", nargs="+", default=["能用", "部分"],
                    help="只给这些预判的条目抽答案")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        print("环境变量 ZHIPU_API_KEY 未设置", file=sys.stderr)
        return 1

    draft = json.loads((DATA / "questions_draft.json").read_text(encoding="utf-8"))
    prej = json.loads((DATA / "prejudge.json").read_text(encoding="utf-8"))

    # 优先用 located.json（两阶段定位，比 prejudge 的 BM25 top-1 准得多）
    located = {}
    lp = DATA / "located.json"
    if lp.exists():
        located = json.loads(lp.read_text(encoding="utf-8"))
        print(f"使用 located.json（{len(located)} 条）作为定位来源")

    # chunks 全文索引（prejudge 里只存了前 900 字）
    full = {}
    for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            full[(c["path"], c["heading"])] = c["text"]

    targets = []
    for q in draft:
        p = located.get(str(q["id"])) or prej.get(str(q["id"])) or {}
        if located:
            if p.get("ok"):
                targets.append((q, p))
        elif p.get("verdict") in args.verdicts:
            targets.append((q, p))
    if args.limit:
        targets = targets[: args.limit]

    print(f"待抽答案：{len(targets)} 条（预判={args.verdicts}）")

    out_path = DATA / "answer_drafts.json"
    results = {}
    if out_path.exists():
        results = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"已有 {len(results)} 条，跳过已完成")

    t0 = time.time()
    for i, (q, p) in enumerate(targets, 1):
        qid = str(q["id"])
        if qid in results and results[qid].get("answer"):
            continue

        # 兼容两种数据形状：
        #   located.json  → paths / heads / texts（picks 已按相关性排序，取第 1 个）
        #   prejudge.json → top_paths / top_heads / top_texts（best 是 1-based 序号）
        if "paths" in p:
            paths, heads = p.get("paths") or [], p.get("heads") or []
            idx = 0
        else:
            paths, heads = p.get("top_paths") or [], p.get("top_heads") or []
            best = p.get("best", 0)
            idx = (best - 1) if 1 <= best <= len(paths) else 0

        if not paths:
            continue

        excerpt = full.get((paths[idx], heads[idx] if heads else ""), "")
        if not excerpt:
            continue

        r = call(key, args.model, q["question"], excerpt)
        results[qid] = {
            "answer": r["answer"],
            "quote": r["quote"],
            "ok": r["ok"],
            "doc_path": paths[idx],
            "doc_heading": heads[idx] if heads else "",
        }
        mark = "✓" if r["ok"] else "✗"
        print(f"  [{i}/{len(targets)}] #{qid} {mark} {r['answer'][:52]}")

        if i % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.3)

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for v in results.values() if v.get("ok"))
    print()
    print("=" * 50)
    print(f"抽取成功 {ok} / {len(results)}")
    print(f"耗时 {time.time() - t0:.0f}s")
    print(f"输出 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
