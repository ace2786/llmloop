#!/usr/bin/env python3
"""补拉 GitHub Issue（匿名 API，60 次/小时，每次 100 条）。

为什么要补：
  原来只拉了 2000 条（去重 1293），而 LlamaFactory 有 1 万多条 Issue。
  1293 条里能对应到文档答案的用法提问只有 13 条 —— 池子太小，
  不是筛法问题。

用法：
  python scripts/fetch_more_issues.py --start 11 --end 60
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "issues"
API = "https://api.github.com/repos/hiyouga/LlamaFactory/issues"


def fetch_page(page: int, token: str = "") -> list[dict] | None:
    url = f"{API}?state=all&per_page=100&page={page}&sort=created&direction=desc"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "llmloop-research",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            remaining = r.headers.get("X-RateLimit-Remaining")
            data = json.loads(r.read())
        return data, remaining
    except urllib.error.HTTPError as e:
        print(f"  page {page}: HTTP {e.code} {e.reason}")
        return None, None
    except Exception as e:  # noqa: BLE001
        print(f"  page {page}: {type(e).__name__} {e}")
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=11)
    ap.add_argument("--end", type=int, default=60)
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("GITHUB_TOKEN", "")

    got = 0
    for page in range(args.start, args.end + 1):
        path = OUT / f"page_{page:03d}.json"
        if path.exists():
            print(f"  page {page}: 已存在，跳过")
            continue
        data, remaining = fetch_page(page, token)
        if data is None:
            print("  配额用完或出错，停止")
            break
        if not data:
            print(f"  page {page}: 空（已到末尾）")
            break
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        issues = [x for x in data if "pull_request" not in x]
        got += len(issues)
        print(f"  page {page}: {len(data)} 条（issue {len(issues)}）｜ 剩余配额 {remaining}")
        if remaining is not None and int(remaining) <= 1:
            print("  配额即将耗尽，停止")
            break
        time.sleep(args.sleep)

    print(f"\n本次新增 issue: {got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
