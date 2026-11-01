#!/usr/bin/env python3
"""合并题库：真实提问类 + 文档反推类，按第 6 节 3:3:4 切分。

依据：
  · 第 6 节：题目来源包括中文文档/示例配置 + 真实用户提问；按 3:3:4 切成
    优化用 / 验证用 / 最终测试用
  · 第 13 节退路：真实提问不够时可用文档反推补充，**但要单独标出来源，
    评测结论按来源分开报告**

两个来源分别标注：
  · real-issue  —— GitHub 真实提问（人工确认答案能在文档里找到）
  · doc-synth   —— 从文档参数表反推

切分策略：**每个来源内部各自按 3:3:4 切**，保证优化/验证/测试三份里
两种来源都有，这样才能分来源报告结果。

用法：
    python scripts/merge_questions.py --target 200            # 出报告
    python scripts/merge_questions.py --target 200 --write    # 替换题库
"""
from __future__ import annotations

import argparse
import csv
import json
import re as _re
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"


def load_candidates() -> dict[str, dict]:
    rows = json.loads((DATA / "candidates_verified.json").read_text(encoding="utf-8"))
    return {str(r["issue"]): r for r in rows}


def load_flags() -> set[str]:
    p = OUT / "audit_flagged.csv"
    if not p.exists():
        return set()
    with p.open(encoding="utf-8-sig") as f:
        return {r["序号"].strip() for r in csv.DictReader(f)}


def load_verdicts(csv_path: str | None) -> dict[str, str]:
    """核对页导出的判定；没有就返回空。"""
    if not csv_path:
        return {}
    with open(csv_path, encoding="utf-8-sig") as f:
        return {r["序号"].strip(): (r.get("核对结果") or "").strip() for r in csv.DictReader(f)}


def build_real_issue(verdicts: dict[str, str], cn_only: bool) -> list[dict]:
    """真实提问类。判定优先用人工导出，否则按审计建议（无标记=留）。"""
    cands = load_candidates()
    flags = load_flags()
    with (OUT / "select_140.csv").open(encoding="utf-8-sig") as f:
        sel = list(csv.DictReader(f))

    out = []
    for r in sel:
        sid = r["序号"].strip()
        v = verdicts.get(sid) if verdicts else ("砍" if sid in flags else "对")
        if v != "对":
            continue
        title = r.get("用户原提问（标题）", "")
        if cn_only and not _re.search(r"[\u4e00-\u9fff]", title):
            continue
        issue = r["issue"].strip()
        c = cands.get(issue)
        ans = (r["草稿答案（待核对）"] or "").strip()
        quote = (r["文档原文"] or "").strip()
        if not c or not ans or not quote:
            continue
        loc = c.get("real_path") or ""
        head = c.get("real_heading") or ""
        out.append({
            "issue": int(issue),
            "question": title.strip(),
            "answer": ans,
            "doc_location": f"{loc} > {head}" if head else loc,
            "evidence": quote,
            "source": "real-issue",
            "origin": f"GitHub Issue #{issue}",
            "split": "",
        })
    return out


def split_334(items: list[dict], start_id: int) -> list[dict]:
    """按 3:3:4 切分（优化/验证/测试），并在组内分配 id。"""
    n = len(items)
    n_opt = round(n * 0.3)
    n_val = round(n * 0.3)
    for i, it in enumerate(items):
        it["split"] = "optimize" if i < n_opt else ("valid" if i < n_opt + n_val else "test")
        it["id"] = start_id + i
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="核对页导出的 qbank_result.csv")
    ap.add_argument("--target", type=int, default=200, help="题库总题数（含现有）")
    ap.add_argument("--no-cn-only", action="store_true", help="不限制中文提问")
    ap.add_argument("--write", action="store_true", help="替换 questions.json")
    a = ap.parse_args()

    existing = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    verdicts = load_verdicts(a.csv)

    real = build_real_issue(verdicts, not a.no_cn_only)
    print(f"真实提问类可用：{len(real)} 条")

    doc_path = DATA / "questions_docsynth.json"
    docs = json.loads(doc_path.read_text(encoding="utf-8")) if doc_path.exists() else []
    print(f"文档反推类可用：{len(docs)} 条")

    # 「扩到 200 道」是题库总数，所以新增 = 目标 - 现有
    n_new = max(0, a.target - len(existing))
    # 先保证真实提问全收（更可信），剩下用文档反推补到目标
    real = real[:n_new]
    n_doc = max(0, n_new - len(real))
    docs = docs[:n_doc]
    print(f"目标总数 {a.target} 道，现有 {len(existing)} → 需新增 {n_new}")
    print(f"  真实提问 {len(real)} + 文档反推 {len(docs)} = {len(real) + len(docs)}")

    # 两个来源各自 3:3:4，保证三份里都有两种来源
    next_id = max((q.get("id", 0) for q in existing), default=0) + 1
    for it in real:
        it["id"] = next_id
        next_id += 1
    for it in docs:
        it["id"] = next_id
        next_id += 1

    new = real + docs
    merged = existing + new

    # ★ 对「整个题库」重新按 3:3:4 切分（含现有 60 道），
    #   否则总数不是 60/60/80。按来源分组切，保证每份里两种来源都有。
    def src_group(q: dict) -> str:
        return "doc" if q.get("source") == "doc-synth" else "real"

    for g in ("real", "doc"):
        group = [q for q in merged if src_group(q) == g]
        n = len(group)
        n_opt, n_val = round(n * 0.3), round(n * 0.3)
        for i, q in enumerate(group):
            q["split"] = "optimize" if i < n_opt else ("valid" if i < n_opt + n_val else "test")

    dst = DATA / "questions_merged.json"
    dst.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"现有 {len(existing)} 道 + 新增 {len(new)} 道 = {len(merged)} 道")
    print("  来源：", dict(Counter(src_group(q) for q in merged)))
    print("  切分：", dict(Counter(q["split"] for q in merged)))
    print(f"已写出：{dst.relative_to(ROOT)}")

    if a.write:
        bak = DATA / "questions.before_merge.json"
        shutil.copy2(DATA / "questions.json", bak)
        (DATA / "questions.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已替换 questions.json（备份 {bak.name}）")
    else:
        print("（未替换原文件，确认后加 --write）")

    print()
    print("=== 真实提问类抽样 4 条 ===")
    for q in real[:4]:
        print(f"  #{q['id']} [{q['split']}] 问：{q['question'][:50]}")
        print(f"        答：{q['answer'][:60]}")
    print()
    print("=== 文档反推类抽样 4 条 ===")
    for q in docs[:4]:
        print(f"  #{q['id']} [{q['split']}] 问：{q['question'][:50]}")
        print(f"        答：{q['answer'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
