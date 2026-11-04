#!/usr/bin/env python3
"""跑一次真实评测：BM25 检索 + 本地 Qwen3-4B 回答 + 自动判分。

对应检查点第 5 条「发起一次评测并看到真实结果」。
不是 mock：每次回答都由本地模型真实生成，检索由 BM25 真实打分。

流程（每题）：
  1. 用问题做 BM25 检索，取 top-k 文档块
  2. 拼「文档 + 问题」喂给模型（/no_think，temperature=0）
  3. 剥掉 <think> 块
  4. 自动判分：标准答案里的硬实体在模型回答里命中多少
       全中 → 对；≥40% → 部分对；否则 → 错
  5. 落 CSV，人工可复核（RUBRIC 要求人工判分，自动判分只作参考列）

用法：
    python scripts/run_eval.py --split test --limit 20     # 先试 20 条
    python scripts/run_eval.py --split test                # 跑完整测试集
    python scripts/run_eval.py --split test --no-rag       # 不用检索（对照组）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.text import tokenize  # noqa: E402
from lib.judge import hard_entities, judge  # noqa: E402,F401

from rank_bm25 import BM25Okapi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
OLLAMA = "http://127.0.0.1:11434/api/generate"
ZHIPU = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

THINK = re.compile(r"<think>.*?</think>", re.S)
BACKTICK = re.compile(r"`([^`]{1,40})`")
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b")
NUM = re.compile(r"\b\d+(?:\.\d+)*\b")


def _load_env() -> None:
    """读 .env 里的 key（不覆盖已有环境变量）。"""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ask_glm(prompt: str, model: str, num_predict: int = 220) -> tuple[str, float]:
    """调智谱免费模型。被测助手用云端免费模型是任务书第 7 节允许的。"""
    _load_env()
    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        raise RuntimeError("ZHIPU_API_KEY 未设置，无法调用 " + model)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": num_predict,
    }).encode()
    req = urllib.request.Request(
        ZHIPU, data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    ans = THINK.sub("", d["choices"][0]["message"]["content"]).strip()
    return ans, time.time() - t0


def ask(model: str, prompt: str, num_predict: int = 220) -> tuple[str, float]:
    # glm / 云端模型走智谱接口，其余走本地 Ollama
    if model.startswith("glm"):
        return ask_glm(prompt, model, num_predict)

    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0, "top_p": 0.9},
    }).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    ans = THINK.sub("", d.get("response", "")).strip()
    return ans, time.time() - t0


def load_chunks() -> tuple[list[dict], BM25Okapi]:
    chunks = []
    for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(json.loads(line))
    corpus = [tokenize(c["text"]) for c in chunks]
    return chunks, BM25Okapi(corpus)


# 判分逻辑已抽到 lib/judge.py，脚本和接口共用同一份。
# 不要在这里再写一份——两套判分 = 两套结论。


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["optimize", "valid", "test", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--no-rag", action="store_true", help="不检索，直接问（对照组）")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    if a.split != "all":
        qs = [q for q in qs if q.get("split") == a.split]
    if a.limit:
        qs = qs[: a.limit]
    print(f"待评测 {len(qs)} 道（split={a.split}，topk={a.topk}，rag={'off' if a.no_rag else 'on'}）")

    chunks, bm25 = load_chunks() if not a.no_rag else ([], None)
    if chunks:
        print(f"检索库 {len(chunks)} 个文档块")

    rows, t0 = [], time.time()
    for i, q in enumerate(qs, 1):
        ctx = ""
        if not a.no_rag:
            scores = bm25.get_scores(tokenize(q["question"]))
            top = sorted(range(len(scores)), key=lambda j: -scores[j])[: a.topk]
            ctx = "\n\n".join(f"[文档{i+1}] {chunks[j]['text'][:900]}" for i, j in enumerate(top))

        prompt = "/no_think\n"
        if ctx:
            prompt += f"根据下面的文档回答问题，只答文档里明确写的内容，不要编造。\n\n{ctx}\n\n"
        prompt += f"问题：{q['question']}\n回答："

        try:
            got, dt = ask(a.model, prompt)
        except Exception as e:  # noqa: BLE001
            got, dt = "", 0.0
            detail = getattr(e, "reason", "") or str(e)
            print(f"  [{i}/{len(qs)}] 失败：{type(e).__name__} {str(detail)[:120]}")

        tag, why = judge(q["answer"], got)
        rows.append({
            "id": q["id"], "issue": q.get("issue", ""), "source": q.get("source", ""),
            "split": q.get("split", ""), "question": q["question"],
            "标准答案": q["answer"], "模型回答": got,
            "自动判分": tag, "判分依据": why, "人工判分": "", "耗时s": round(dt, 1),
        })
        if i % 10 == 0 or i == len(qs):
            print(f"  [{i}/{len(qs)}] 累计 {(time.time()-t0)/60:.1f} 分钟")

    stamp = time.strftime("%m%d_%H%M")
    mtag = a.model.replace(":", "-").replace("/", "-")
    dst = Path(a.out) if a.out else OUT / f"eval_{a.split}_{mtag}_{stamp}{'_norag' if a.no_rag else ''}.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    empty = sum(1 for r in rows if not r["模型回答"].strip())
    if empty > total * 0.5:
        print()
        print(f"!! 中止：{empty}/{total} 道题没有拿到回答。")
        print(f"!! 这多半是模型服务没起来（Ollama 挂了，或 {a.model} 不可用），")
        print("!! 不是模型答错。这份结果不能用来报指标。")
        print(f"!! 结果文件仍保留以便排查：{dst}")
        return 2

    acc = Counter(r["自动判分"] for r in rows)
    print()
    print(f"总耗时 {(time.time()-t0)/60:.1f} 分钟，平均 {sum(r['耗时s'] for r in rows)/max(total,1):.1f}s/题")
    print(f"结果：对 {acc['对']}　部分对 {acc['部分对']}　错 {acc['错']}　（共 {total}）")
    print(f"严格正确率 {acc['对']/total:.1%}　宽松正确率 {(acc['对']+acc['部分对'])/total:.1%}")
    print()
    print("分来源：")
    for src in sorted({r["source"] for r in rows}):
        g = [r for r in rows if r["source"] == src]
        ok = sum(1 for r in g if r["自动判分"] == "对")
        half = sum(1 for r in g if r["自动判分"] == "部分对")
        print(f"  {src:<18} {len(g):>3} 道　对 {ok}　部分对 {half}　严格 {ok/len(g):.1%}")
    print()
    print(f"已写出：{dst}")

    # 顺手复制一份到 Windows 侧，方便现场直接双击打开（录屏时不用去 WSL 里找）
    win_dir = Path("/mnt/d/llmloop")
    if win_dir.is_dir():
        wname = f"评测结果_{stamp}{'_norag' if a.no_rag else ''}.csv"
        wdst = win_dir / wname
        try:
            shutil.copy2(dst, wdst)
            print(f"Windows 路径：D:\\llmloop\\{wname}")
            print("（现场演示：直接双击这个文件就能看到逐题结果）")
        except OSError as e:
            print(f"（复制到 D 盘失败：{e}，不影响结果）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
