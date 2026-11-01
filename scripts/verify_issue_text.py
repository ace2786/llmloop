#!/usr/bin/env python3
"""验证 CSV 里的「用户原提问」是不是真的来自 GitHub 原 issue。

做法：从 CSV 随机抽 N 条，重新请求 GitHub API，把返回的 title/body
和 CSV 里存的逐字比对。不一致就说明抓取环节出过问题。

用法：
    python scripts/verify_issue_text.py            # 抽查 5 条
    python scripts/verify_issue_text.py --n 10
    python scripts/verify_issue_text.py --all      # 全查（注意 API 额度）
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com/repos/hiyouga/LlamaFactory/issues/"


def norm(s: str) -> str:
    """归一化：压掉所有空白，便于逐字比对。"""
    return re.sub(r"\s+", "", s or "")


def fetch(num: str) -> dict | None:
    req = urllib.request.Request(
        API + num,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "llmloop-verify"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    with (ROOT / "out" / "select_140.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    picks = rows if a.all else random.Random(20261101).sample(rows, min(a.n, len(rows)))

    ok = bad = 0
    for r in picks:
        num = r["issue"].strip()
        csv_title = r["用户原提问（标题）"].strip()
        csv_body = r["用户原提问（正文）"].strip()

        d = fetch(num)
        if d is None:
            print(f"#{num}  取不到（可能限流或已删除），跳过")
            continue

        api_title = (d.get("title") or "").strip()
        api_body = (d.get("body") or "").strip()
        is_pr = "pull_request" in d

        # CSV 里 body 被截断到 400 字并压过空白，所以只比前 380 字
        body_ok = norm(api_body)[:380].startswith(norm(csv_body)[:380]) or \
                  norm(csv_body)[:380].startswith(norm(api_body)[:380])

        title_ok = norm(api_title) == norm(csv_title)

        tag = "✓" if (title_ok and body_ok and not is_pr) else "✗"
        if tag == "✓":
            ok += 1
        else:
            bad += 1
        print(f"{tag} #{num}  {'[PR!]' if is_pr else ''}")
        print(f"    CSV 标题: {csv_title[:60]}")
        print(f"    API 标题: {api_title[:60]}")
        if not body_ok:
            print(f"    CSV 正文: {norm(csv_body)[:80]}")
            print(f"    API 正文: {norm(api_body)[:80]}")

    print()
    print(f"抽查 {ok + bad} 条：一致 {ok}，有问题 {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
