#!/usr/bin/env python3
"""对「真实 Issue 候选」做严格判断：文档能否明确回答？答案原文是什么？

和 locate_answer.py 的区别：
  locate_answer 只输出「挑中了哪几段」，答案还得另抽一次（draft_answers.py），
  中间会引入新的编造风险。
  本脚本一次到位：判断能否回答 + 直接抄出答案原文 + 给出依据行。

  ★ 关键是 prompt 里强制「答案必须逐字来自候选段落」，不许改写不许推断。

输出：data/real_judged.json
  {"<issue>": {"ok": true, "answer": "...", "quote": "...", "path": "...", "heading": "..."}}
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from week1 import Retriever  # noqa: E402

DATA = ROOT / "data"
BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

SYSTEM = """你是严格的技术文档检索员。给你一条用户提问，以及从 LlamaFactory 文档里粗筛出的候选段落（带编号）。

任务：判断**这些段落里是否真的写明了答案**。如果有，把答案逐字抄出来。

规则：
1. 答案必须能在候选段落里**逐字找到**。找不到就判 ok=false，绝不许用自己的知识补。
2. 只提到关键词、但没回答问题 → ok=false。
3. 只答了问题的一部分 → ok=false（考题要求完整答案）。
4. 目录、参考文献、赞助商、报错日志 → ok=false。
5. 答案是「文档里没写/建议去别处查」→ ok=false。

只输出 JSON，不要 markdown 代码块：
{"ok":true,"pick":段落编号,"answer":"一句话答案（尽量逐字抄原文）","quote":"支撑这句话的原文片段（逐字，20-120字）","reason":"一句话理由"}

判否时输出：{"ok":false,"reason":"..."}"""


def call(key: str, model: str, question: str, cands: list[dict], retries: int = 3) -> dict:
    blocks = []
    for i, c in enumerate(cands, 1):
        body = c["text"][:1100]
        blocks.append(f"[{i}] {c['path']} > {c['heading']}\n{body}")
    user = "【候选段落】\n" + "\n\n".join(blocks) + f"\n\n【用户提问】\n{question}"

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 900,
    }).encode()

    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE, data=payload, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            })
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            txt = d["choices"][0]["message"].get("content") or ""
            txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
            m = re.search(r"\{.*\}", txt, re.S)
            if m:
                return json.loads(m.group(0))
            return {"ok": False, "reason": "输出无法解析"}
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 + attempt * 3)
    return {"ok": False, "reason": "调用失败 " + last}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/real_title_hits.json")
    ap.add_argument("--out", default="data/real_judged.json")
    ap.add_argument("--pool", type=int, default=25)
    ap.add_argument("--model", default="glm-4-flash")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        print("环境变量 ZHIPU_API_KEY 未设置", file=sys.stderr)
        return 1

    cands = json.loads((ROOT / args.src).read_text(encoding="utf-8"))
    if args.limit:
        cands = cands[: args.limit]
    print(f"待判断: {len(cands)} 条")

    out_path = ROOT / args.out
    done = {}
    if out_path.exists():
        done = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"已有结果: {len(done)} 条，跳过")

    retriever = Retriever(DATA / "chunks.jsonl")
    todo = [c for c in cands if str(c["issue"]) not in done]
    print(f"本次处理: {len(todo)} 条\n")

    def work(c: dict) -> tuple[str, dict]:
        issue = str(c["issue"])
        q = c["ask"][:600]
        ctxs = retriever.top_k(q, k=args.pool)
        if not ctxs:
            return issue, {"ok": False, "reason": "检索无结果"}
        r = call(key, args.model, q, ctxs)
        if r.get("ok"):
            idx = r.get("pick")
            if isinstance(idx, int) and 1 <= idx <= len(ctxs):
                ch = ctxs[idx - 1]
                r["path"] = ch["path"]
                r["heading"] = ch["heading"]
                r["text"] = ch["text"][:1500]
            else:
                r["ok"] = False
                r["reason"] = "pick 编号越界"
        return issue, r

    ok_n = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, c): c for c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            c = futs[fut]
            try:
                issue, r = fut.result()
            except Exception as e:  # noqa: BLE001
                issue, r = str(c["issue"]), {"ok": False, "reason": str(e)}
            done[issue] = r
            if r.get("ok"):
                ok_n += 1
            mark = "✓" if r.get("ok") else "·"
            print(f"  [{i}/{len(todo)}] {mark} #{issue} {c['title'][:44]}")
            if i % 10 == 0 or i == len(todo):
                out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")

    out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    total_ok = sum(1 for v in done.values() if v.get("ok"))
    print(f"\n完成：{len(done)} 条，能明确回答 {total_ok} 条（{total_ok*100//max(len(done),1)}%），用时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
