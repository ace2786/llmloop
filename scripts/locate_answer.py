#!/usr/bin/env python3
"""为每条候选提问精确定位「能回答它的文档段落」（BM25 粗筛 + LLM 精选）。

为什么需要：
  单靠 BM25 抓 top-1 经常抓错（词面重合 ≠ 能回答问题）。
  实测用户核对 97 条只有 11 条可用（11%），主因就是摘录里根本没有答案。

做法：
  ① BM25 粗筛 top-N（默认 20）
  ② 把这些候选的「标题 + 前 300 字」交给免费 LLM，让它挑出真正能回答问题的 1-3 个
  ③ 都挑不出来 → 标记 NONE（这条题确实不可用）

★ 这不会削弱 v0 的缺陷：
  测试集构建用「好检索」，v0 评测用「BM25 top-3」，
  两者脱钩，v0 该错还是错——那正是第 1 周要诊断的东西。

输出：data/located.json
  {"3": {"picks": [0, 2], "paths": [...], "heads": [...], "texts": [...], "ok": true}, ...}
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

SYSTEM = """你是严格的技术文档检索员。我会给你一条用户提问，以及从 LlamaFactory 文档里粗筛出的若干候选段落（带编号）。

任务：挑出**真正能回答该提问**的段落编号。

判定标准：
- 段落里必须明确写出了答案（具体参数名+默认值 / 具体配置项 / 明确的步骤 / 明确的支持与否）
- 只是出现相同关键词但讲的不是同一件事 → 不算
- 只是目录、参考文献、赞助商、项目列表 → 不算
- 只是参数表里列了名字但没有说明 → 视情况，若能看出默认值和含义则算

只输出 JSON，不要 markdown 代码块：
{"picks":[编号,...],"reason":"一句话理由"}

挑不出来就输出 {"picks":[],"reason":"..."}。
最多挑 3 个，按相关性从高到低排。"""


def call(key: str, model: str, question: str, cands: list[dict], retries: int = 3) -> dict:
    blocks = []
    for i, c in enumerate(cands, 1):
        blocks.append(
            f"[{i}] {c['path']} | {c['heading']}\n{c['text'][:300]}"
        )
    user = f"【提问】\n{question}\n\n【候选段落】\n" + "\n\n".join(blocks)

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
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read())
            txt = d["choices"][0]["message"]["content"].strip()
            txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
            m = re.search(r"\{.*\}", txt, re.S)
            if not m:
                raise ValueError(f"无法解析：{txt[:80]}")
            obj = json.loads(m.group(0))
            picks = obj.get("picks") or []
            picks = [int(p) for p in picks if isinstance(p, (int, float, str)) and str(p).isdigit()]
            picks = [p for p in picks if 1 <= p <= len(cands)][:3]
            return {"picks": picks, "reason": str(obj.get("reason", ""))[:100]}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if attempt == retries:
                return {"picks": [], "reason": f"HTTP {e.code}"}
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                return {"picks": [], "reason": str(e)[:80]}
            time.sleep(2)
    return {"picks": [], "reason": "未知"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm-4-flash")
    ap.add_argument("--pool", type=int, default=20, help="BM25 粗筛候选数")
    ap.add_argument("--skip-marked", action="store_true",
                    help="跳过 Excel 里已判 ✗ 的条目（省时间）")
    ap.add_argument("--xlsx", default="/mnt/d/llmloop/待核对_265题.xlsx")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        print("环境变量 ZHIPU_API_KEY 未设置", file=sys.stderr)
        return 1

    draft = json.loads((DATA / "questions_draft.json").read_text(encoding="utf-8"))

    skip = set()
    if args.skip_marked:
        try:
            from openpyxl import load_workbook

            wb = load_workbook(args.xlsx, data_only=True)
            ws = wb["待核对"]
            for r in range(2, ws.max_row + 1):
                v = ws.cell(row=r, column=2).value
                if v and str(v).strip() in ("✗", "×", "x"):
                    skip.add(int(ws.cell(row=r, column=1).value))
            print(f"跳过已判 ✗ 的 {len(skip)} 条")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ 读 Excel 失败（{e}），不跳过")

    targets = [q for q in draft if q["id"] not in skip]
    if args.limit:
        targets = targets[: args.limit]
    print(f"待定位：{len(targets)} 条（粗筛池 {args.pool}）")

    retriever = Retriever(DATA / "chunks.jsonl")

    out_path = DATA / "located.json"
    results = {}
    if out_path.exists():
        results = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"已有 {len(results)} 条，跳过已完成")

    t0 = time.time()
    ok_n = 0
    for i, q in enumerate(targets, 1):
        qid = str(q["id"])
        if qid in results:
            if results[qid].get("ok"):
                ok_n += 1
            continue

        cands = retriever.top_k(q["question"], k=args.pool)
        r = call(key, args.model, q["question"], cands)
        picks = r["picks"]

        entry = {"picks": picks, "reason": r["reason"], "ok": bool(picks)}
        if picks:
            entry["paths"] = [cands[p - 1]["path"] for p in picks]
            entry["heads"] = [cands[p - 1]["heading"] for p in picks]
            entry["texts"] = [cands[p - 1]["text"] for p in picks]
            ok_n += 1
        results[qid] = entry

        mark = "✓" if picks else "✗"
        print(f"  [{i}/{len(targets)}] #{qid} {mark} {r['reason'][:46]}")
        if i % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.3)

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("=" * 54)
    print(f"可定位 {ok_n} / {len(results)}  （{ok_n / max(len(results), 1):.0%}）")
    print(f"耗时 {time.time() - t0:.0f}s")
    print(f"输出 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
