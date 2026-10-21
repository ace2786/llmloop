#!/usr/bin/env python3
"""按时间窗口切片，把 LlamaFactory 的 issue 尽量拉全。

背景：
  /repos/{owner}/{repo}/issues 接口最多只能翻到第 10 页（1000 条），第 11 页 422。
  要用 Search API 按 created 时间窗口切片，每个窗口控制在 1000 条以内。

限额：
  Search API 未认证 10 次/分钟 → 每次请求间隔 7 秒。

输出：data/issues/win_<label>_p<NN>.json
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "issues"
API = "https://api.github.com/search/issues"

# 按半年切片（2023 年项目刚起，量小；2024-2026 是活跃期）
WINDOWS = [
    ("2023H1", "2023-01-01", "2023-06-30"),
    ("2023H2", "2023-07-01", "2023-12-31"),
    ("2024H1", "2024-01-01", "2024-06-30"),
    ("2024H2", "2024-07-01", "2024-12-31"),
    ("2025H1", "2025-01-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026H1", "2026-01-01", "2026-06-30"),
    ("2026H2", "2026-07-01", "2026-12-31"),
]


def search(q: str, page: int) -> tuple[dict | None, str]:
    url = API + "?" + urllib.parse.urlencode({"q": q, "per_page": 100, "page": page})
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "llmloop-research",
    })
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read()), r.headers.get("X-RateLimit-Remaining", "?")
    except urllib.error.HTTPError as e:
        return None, f"HTTP{e.code}"
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=7.0)
    ap.add_argument("--windows", nargs="*", default=None)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    wins = [w for w in WINDOWS if not args.windows or w[0] in args.windows]

    total_new = 0
    for label, start, end in wins:
        q = f"repo:hiyouga/LlamaFactory is:issue created:{start}..{end}"
        got = 0
        for page in range(1, 11):
            path = OUT / f"win_{label}_p{page:02d}.json"
            if path.exists():
                try:
                    old = json.load(open(path, encoding="utf-8"))
                    got += len(old.get("items", []))
                    continue
                except Exception:  # noqa: BLE001
                    pass
            data, info = search(q, page)
            if data is None:
                print(f"  {label} p{page}: 失败 {info}")
                break
            items = data.get("items", [])
            if not items:
                break
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            got += len(items)
            if len(items) < 100:
                break
            time.sleep(args.sleep)
        print(f"  {label}: 累计 {got} 条")
        total_new += got
        time.sleep(args.sleep)

    print(f"\n本次覆盖 issue: {total_new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
