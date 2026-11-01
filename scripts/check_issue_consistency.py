#!/usr/bin/env python3
"""不耗 API 额度的本地一致性检查。

验三件事：
  1. CSV 里的「用户原提问」和本地数据源（缓存 / 抓取结果）是否逐字一致
  2. issue 编号和 URL 是否自洽（URL 里的号必须等于 issue 列）
  3. 有没有 PR 混进来、有没有空标题、有没有重复 issue

注意：这只能证明「CSV 忠实反映了我们手里的数据」，
不能证明「我们手里的数据真的是 GitHub 上的原 issue」——
后者需要重新请求 API，用 verify_issue_text.py（耗额度）。

用法：
    python scripts/check_issue_consistency.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def load_sources() -> dict[str, dict]:
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
        m.update(json.loads(detail.read_text(encoding="utf-8")))
    return m


def main() -> int:
    src = load_sources()
    with (ROOT / "out" / "select_140.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"检查 {len(rows)} 行")
    print("=" * 60)

    problems: dict[str, list[str]] = {
        "编号与链接不一致": [],
        "CSV 标题与数据源不一致": [],
        "CSV 正文与数据源不一致": [],
        "数据源是 PR": [],
        "标题为空": [],
        "找不到数据源": [],
    }

    for r in rows:
        num = r["issue"].strip()
        url = r["issue链接"].strip()
        title = r["用户原提问（标题）"].strip()
        body = r["用户原提问（正文）"].strip()

        if not url.endswith(f"/issues/{num}"):
            problems["编号与链接不一致"].append(f"#{num} → {url}")

        it = src.get(num)
        if it is None:
            problems["找不到数据源"].append(f"#{num}")
            continue

        if it.get("is_pr") or ("pull_request" in it and it.get("pull_request")):
            problems["数据源是 PR"].append(f"#{num} {title[:40]}")

        api_title = (it.get("title") or "").strip()
        api_body = (it.get("body") or "").strip()

        if norm(api_title) != norm(title):
            problems["CSV 标题与数据源不一致"].append(
                f"#{num} CSV={title[:40]!r} 源={api_title[:40]!r}"
            )
        # body 在 CSV 里被截断到 400 字并压过空白
        if api_body and not norm(api_body).startswith(norm(body)[:380]):
            problems["CSV 正文与数据源不一致"].append(
                f"#{num} CSV={norm(body)[:50]!r} 源={norm(api_body)[:50]!r}"
            )
        if not title:
            problems["标题为空"].append(f"#{num}")

    dup = [k for k, v in Counter(r["issue"] for r in rows).items() if v > 1]

    total = 0
    for kind, lst in problems.items():
        total += len(lst)
        if lst:
            print(f"【{kind}】{len(lst)} 处")
            for x in lst[:6]:
                print(f"    · {x}")
            if len(lst) > 6:
                print(f"    …还有 {len(lst) - 6} 处")
    if dup:
        total += len(dup)
        print(f"【同一 issue 出现多次】{len(dup)} 个：{dup[:10]}")

    print()
    if total == 0:
        print("✓ CSV 与本地数据源完全一致，编号/链接自洽，无 PR、无空标题")
        print()
        print("  注意：这只证明 CSV 忠实反映了本地数据。")
        print("  要证明本地数据就是 GitHub 原 issue，等额度恢复后跑：")
        print("    python scripts/verify_issue_text.py --all")
        return 0
    print(f"✗ 共 {total} 处问题")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
