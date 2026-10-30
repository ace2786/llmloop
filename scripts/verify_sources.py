#!/usr/bin/env python3
"""用 chunks.jsonl 反查每条候选的真实出处，修正 answer_drafts 里不可靠的 doc_heading。

背景：answer_drafts.json 的 doc_heading 字段不可靠——有时是文件路径，有时干脆是错的。
实测样例：草稿答案讲 lora_target，出处却写成「eval_steps: 500」，两者毫无关系。
如果照它分组，会得到假的「段落覆盖数」。

做法：拿每条候选的 quote（文档原文片段），在 chunks.jsonl 里做包含匹配，
命中的 chunk 的 path + heading 才是真实出处。

用法：
    python scripts/verify_sources.py          # 只报告
    python scripts/verify_sources.py --fix    # 写出修正后的 data/candidates_verified.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def norm(s: str) -> str:
    """归一化：去掉多余空白，便于包含匹配。"""
    return " ".join((s or "").split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()

    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    located = json.loads((DATA / "located.json").read_text(encoding="utf-8"))
    drafts = json.loads((DATA / "answer_drafts.json").read_text(encoding="utf-8"))
    chunks = [
        json.loads(line)
        for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    used = {str(q["issue"]) for q in questions}

    # 预先把 chunk 文本归一化，避免重复计算
    normed = [(i, norm(c["text"]), c) for i, c in enumerate(chunks)]

    rows = []
    stat = Counter()
    for k, d in drafts.items():
        if k in used or k not in located or not d.get("ok"):
            continue
        quote = norm(d.get("quote") or "")
        claimed_path = d.get("doc_path") or ""
        claimed_head = d.get("doc_heading") or ""

        hit = None
        if quote:
            # 优先找完整包含；找不到再用前 60 字试一次（防止 quote 被截断）
            for _, text, c in normed:
                if quote and quote in text:
                    hit = c
                    break
            if hit is None and len(quote) >= 60:
                frag = quote[:60]
                for _, text, c in normed:
                    if frag in text:
                        hit = c
                        break

        if hit is None:
            stat["找不到出处"] += 1
            real_path, real_head, status = claimed_path, claimed_head, "找不到"
            chunk_id, chunk_text = -1, ""
        else:
            real_path, real_head = hit["path"], hit["heading"]
            same = (real_path == claimed_path)
            stat["出处一致" if same else "出处被修正"] += 1
            status = "一致" if same else "已修正"
            chunk_id = hit.get("id", -1)
            chunk_text = " ".join((hit.get("text") or "").split())[:300]

        rows.append(
            {
                "issue": k,
                "answer": (d.get("answer") or "").strip(),
                "quote": (d.get("quote") or "").strip(),
                "claimed": f"{claimed_path} > {claimed_head}",
                "real_path": real_path,
                "real_heading": real_head,
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "seg": f"{real_path}#{chunk_id}",
                "status": status,
                "score": 0,
            }
        )

    total = len(rows)
    print(f"检查 {total} 条候选的出处")
    print()
    for k, v in stat.most_common():
        print(f"  {k:<8} {v:>4} 条  ({v / total * 100:.0f}%)")
    print()

    usable = [r for r in rows if r["status"] != "找不到"]
    print(f"可用（出处能在 chunks 里找到）：{len(usable)} 条")
    print(f"覆盖的真实段落：{len({r['seg'] for r in usable})} 个")

    # 对比：如果照 answer_drafts 的 doc_heading 分组会得到多少个「假段落」
    fake_segs = {r["claimed"] for r in rows}
    print(f"（若照原始 doc_heading 分组会得到 {len(fake_segs)} 个段落——这个数是虚的）")

    if a.fix:
        out = DATA / "candidates_verified.json"
        out.write_text(json.dumps(usable, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"已写出：{out.relative_to(ROOT)}")
    else:
        print()
        print("加 --fix 可写出修正后的候选清单")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
