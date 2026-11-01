#!/usr/bin/env python3
"""从核验过的候选里挑 140 条，做「最大段落覆盖」选题，并生成人工核对表。

前置：先跑 verify_sources.py --fix，产出 data/candidates_verified.json
      （answer_drafts 的 doc_heading 不可靠，必须用 chunks 反查真实出处）

做法：
  阶段 1 —— 每个真实段落先各挑 1 条（保证覆盖）
  阶段 2 —— 剩余名额按段落轮转，避免某段独大

输出：
  out/select_140.csv   人工核对表（Excel 直接开）
  out/select_140.json  选中清单

用法：
    python scripts/select_140.py
    python scripts/select_140.py --n 80
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"


def load_issues() -> dict[str, dict]:
    """合并所有 issue 来源：本地缓存 + 后来补抓的 issue_detail.json。

    注意：PR 和 issue 共用编号，PR 不是用户提问，必须排除。
    """
    m: dict[str, dict] = {}
    for f in sorted(glob.glob(str(DATA / "issues" / "*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = d.get("items", []) if isinstance(d, dict) else d
        for it in items:
            if isinstance(it, dict) and it.get("number"):
                m[str(it["number"])] = it
    detail = DATA / "issues" / "issue_detail.json"
    if detail.exists():
        try:
            m.update(json.loads(detail.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return m


def issue_text(it: dict | None) -> tuple[str, str] | None:
    """返回 (标题, 正文) ；不可用（PR / 已删除 / 空标题）返回 None。"""
    if not it:
        return None
    if it.get("is_pr") or it.get("gone"):
        return None
    title = (it.get("title") or "").strip()
    if not title:
        return None
    body = " ".join((it.get("body") or "").split())[:400]
    return title, body


def quality(r: dict) -> float:
    """给候选打分：答案长度适中、有原文引用、出处完整。"""
    ans = r.get("answer") or ""
    quote = r.get("quote") or ""
    s = 0.0
    n = len(ans)
    if 15 <= n <= 120:
        s += 2.0
    elif 10 <= n <= 200:
        s += 1.0
    if quote:
        s += 1.5
    if len(quote) >= 20:
        s += 0.5
    if r.get("real_path") and r.get("real_heading"):
        s += 1.0
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=140)
    a = ap.parse_args()

    src = DATA / "candidates_verified.json"
    if not src.exists():
        print("缺少 candidates_verified.json，先跑：python scripts/verify_sources.py --fix")
        return 1

    cands = json.loads(src.read_text(encoding="utf-8"))
    issues = load_issues()

    # 只保留「有真实用户提问」的候选——老师要求题目来自真实 issue
    kept, dropped = [], 0
    for c in cands:
        txt = issue_text(issues.get(str(c["issue"])))
        if txt is None:
            dropped += 1
            continue
        c["title"], c["body"] = txt
        c["score"] = quality(c)
        kept.append(c)
    cands = kept
    print(f"候选 {len(kept) + dropped} 条 → 有真实提问的 {len(kept)} 条（剔除 {dropped} 条：PR/已删除/无原文）")

    print(f"覆盖 {len({c['seg'] for c in cands})} 个真实段落")

    by_seg: dict[str, list[dict]] = defaultdict(list)
    for c in cands:
        by_seg[c["seg"]].append(c)
    for seg in by_seg:
        by_seg[seg].sort(key=lambda x: -x["score"])

    picked: list[dict] = []
    for seg in sorted(by_seg, key=lambda s: -len(by_seg[s])):
        picked.append(by_seg[seg][0])
        if len(picked) >= a.n:
            break

    idx = {seg: 1 for seg in by_seg}
    while len(picked) < a.n:
        progressed = False
        for seg in sorted(by_seg, key=lambda s: (idx[s], -len(by_seg[s]))):
            if idx[seg] < len(by_seg[seg]):
                picked.append(by_seg[seg][idx[seg]])
                idx[seg] += 1
                progressed = True
                if len(picked) >= a.n:
                    break
        if not progressed:
            break

    seg_seen: dict[str, int] = defaultdict(int)
    for p in picked:
        seg_seen[p["seg"]] += 1
        p["priority"] = "必选" if seg_seen[p["seg"]] == 1 else "备选"

    OUT.mkdir(exist_ok=True)
    csv_path = OUT / "select_140.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "序号", "优先级", "issue", "issue链接",
            "用户原提问（标题）", "用户原提问（正文）",
            "草稿答案（待核对）", "文档原文", "所在段落上下文", "出处（文件#块号）",
            "问题（你来写）", "核对结果",
        ])
        for i, p in enumerate(picked, 1):
            w.writerow([
                i, p["priority"], p["issue"],
                f"https://github.com/hiyouga/LlamaFactory/issues/{p['issue']}",
                p.get("title", ""), p.get("body", ""),
                p["answer"], (p["quote"] or "")[:400],
                (p.get("chunk_text") or "")[:300], p["seg"],
                "", "",
            ])

    json_path = OUT / "select_140.json"
    json_path.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")

    segs = {p["seg"] for p in picked}
    print()
    print(f"已选 {len(picked)} 条，覆盖 {len(segs)} 个真实段落")
    print(f"  必选 {sum(1 for p in picked if p['priority'] == '必选')} 条")
    print(f"  备选 {sum(1 for p in picked if p['priority'] == '备选')} 条")
    print()
    print("段落分布 Top 8：")
    cnt: dict[str, int] = defaultdict(int)
    for p in picked:
        cnt[p["seg"]] += 1
    for seg, c in sorted(cnt.items(), key=lambda x: -x[1])[:8]:
        print(f"  {c:>2} 条  {seg[:70]}")
    print()
    print(f"核对表：{csv_path.relative_to(ROOT)}")
    print(f"选中清单：{json_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
