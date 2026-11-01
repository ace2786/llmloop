#!/usr/bin/env python3
"""生成「60 条新增真实提问」的人工确认表（Excel 可直接打开）。

为什么需要：任务书第 8.1 ⑤ 要求「人工确认答案能在文档或示例配置里找到」。
这 60 条入库时只过了机器审计，没做人工确认。

排序：按「可疑度」从高到低，最可能出问题的排最前面，人先看前 20 条就能覆盖大部分风险。

可疑度怎么算（全部是机械规则，不涉及语义判断）：
  +3  标题里的技术词（含下划线/驼峰/长度≥4 的英文词）在答案里一个都没出现
  +2  标题是纯英文（英文提问的草稿答案历史上质量差）
  +2  标题不是问句（陈述句/功能请求，如「希望增加功能：xxx」）
  +2  答案少于 20 字
  +1  原文依据少于 30 字

用法：
    python scripts/make_review_60.py
输出：
    D:/llmloop/60条人工确认.csv（若 D 盘不可写，则落到 out/）
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

IDENT = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]{2,}\b")
CN = re.compile(r"[\u4e00-\u9fff]")
ASK = re.compile(r"如何|怎么|怎样|是否|能否|可以|什么|哪个|为什么|多少|哪些|吗|呢")
# 常见虚词，不算技术词
STOP = {
    "the", "and", "for", "how", "what", "why", "can", "you", "with", "use", "using",
    "model", "train", "training", "data", "error", "issue", "help", "please", "when",
    "does", "not", "but", "from", "this", "that", "have", "get", "set", "run", "load",
    "any", "are", "was", "were", "will", "would", "should", "could", "support", "about",
}


def tech_terms(s: str) -> set[str]:
    out = set()
    for w in IDENT.findall(s or ""):
        low = w.lower()
        if low in STOP or "." in w or w[0].isdigit():
            continue
        if "_" in w or len(w) >= 4:
            out.add(low)
    return out


def suspicion(q: dict) -> tuple[int, list[str]]:
    title = q.get("question", "")
    ans = q.get("answer", "")
    ev = q.get("evidence", "")
    score, why = 0, []

    tt = tech_terms(title)
    if tt and not (tt & tech_terms(ans)):
        score += 3
        why.append("标题技术词未出现在答案：" + "、".join(sorted(tt)[:3]))

    if not CN.search(title):
        score += 2
        why.append("纯英文标题")

    if CN.search(title) and not ("？" in title or "?" in title or ASK.search(title)):
        score += 2
        why.append("不是问句")

    if len(ans) < 20:
        score += 2
        why.append(f"答案仅 {len(ans)} 字")

    if len(ev) < 30:
        score += 1
        why.append(f"原文仅 {len(ev)} 字")

    return score, why


def main() -> int:
    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    items = [q for q in qs if q.get("source") == "real-issue"]
    print(f"待确认：{len(items)} 条（source=real-issue）")

    scored = []
    for q in items:
        s, why = suspicion(q)
        scored.append((s, q, why))
    scored.sort(key=lambda r: (-r[0], r[1].get("id", 0)))

    from collections import Counter
    dist = Counter(s for s, _, _ in scored)
    print("可疑度分布：", dict(sorted(dist.items(), reverse=True)))

    rows = []
    for i, (s, q, why) in enumerate(scored, 1):
        rows.append({
            "序号": i,
            "可疑分": s,
            "可疑原因": "；".join(why) if why else "无明显问题",
            "问题（用户原提问）": q.get("question", ""),
            "标准答案": q.get("answer", "")[:200],
            "文档原文（答案的依据）": (q.get("evidence") or "")[:200],
            "出处": q.get("doc_location", ""),
            "判定（填 能/不能）": "",
            "备注": "",
            "原 id": q.get("id", ""),
            "issue": q.get("issue", ""),
        })

    dst = Path("/mnt/d/llmloop/60条人工确认.csv")
    if not dst.parent.is_dir():
        dst = ROOT / "out" / "60条人工确认.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"已写出：{dst}")
    print()
    print("=== 前 8 条（最可疑）===")
    for r in rows[:8]:
        print(f"  #{r['序号']} 可疑{r['可疑分']}  {r['可疑原因'][:36]}")
        print(f"      问：{r['问题（用户原提问）'][:46]}")
        print(f"      答：{r['标准答案'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
