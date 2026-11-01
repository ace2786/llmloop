#!/usr/bin/env python3
"""补齐 issue 原文：从 GitHub API 抓缺失的 issue 标题与正文。

为什么需要：老师要求题目来自「仓库里真实的用户提问」，但本地缓存只覆盖 5720 条，
候选里有一批早期 issue 没抓到。没有原文，人没法把 issue 改写成提问。

限流：未认证 60 次/小时。脚本会自动读 rate_limit，抓满就停，下次再跑会接着抓。

用法：
    python scripts/fetch_issue_text.py            # 抓当前 140 条里缺的
    python scripts/fetch_issue_text.py --all      # 抓 188 条候选里缺的
    python scripts/fetch_issue_text.py --limit 20 # 只抓 20 条
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "issues" / "issue_detail.json"
API = "https://api.github.com/repos/hiyouga/LlamaFactory/issues/"


def load_cached() -> dict[str, dict]:
    """本地已有的 issue（来自 data/issues/*.json 的各种抓取结果）。"""
    m: dict[str, dict] = {}
    for f in sorted(glob.glob(str(DATA / "issues" / "*.json"))):
        if f.endswith("issue_detail.json"):
            continue
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = d.get("items", []) if isinstance(d, dict) else d
        for it in items:
            if isinstance(it, dict) and it.get("number"):
                m[str(it["number"])] = it
    return m


def load_detail() -> dict[str, dict]:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def wanted(all_mode: bool) -> list[str]:
    src = DATA / ("candidates_verified.json" if all_mode else "") 
    if all_mode:
        rows = json.loads((DATA / "candidates_verified.json").read_text(encoding="utf-8"))
        nums = [str(r["issue"]) for r in rows]
    else:
        with (ROOT / "out" / "select_140.csv").open(encoding="utf-8-sig") as f:
            nums = [r["issue"].strip() for r in csv.DictReader(f)]
    # 去重保序
    seen, out = set(), []
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def rate_left() -> int:
    try:
        with urllib.request.urlopen("https://api.github.com/rate_limit", timeout=15) as r:
            return int(json.load(r)["rate"]["remaining"])
    except Exception:  # noqa: BLE001
        return 0


def fetch(num: str) -> tuple[dict | None, str]:
    """返回 (数据, 失败原因)。原因用于决定要不要中断。"""
    req = urllib.request.Request(
        API + num,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "llmloop-qbank"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            return None, "rate"
        if e.code == 404:
            return None, "gone"
        return None, f"http{e.code}"
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__

    return {
        "number": d.get("number"),
        "title": (d.get("title") or "").strip(),
        "body": (d.get("body") or "").strip(),
        "url": d.get("html_url") or "",
        "state": d.get("state") or "",
        "created_at": d.get("created_at") or "",
        # 关键：PR 和 issue 共用编号，PR 不是用户提问，不能用来出题
        "is_pr": "pull_request" in d,
    }, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="抓 188 条候选，而不是 140 条选中")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cached = load_cached()
    detail = load_detail()
    nums = wanted(a.all)

    have = [n for n in nums if n in cached or n in detail]
    miss = [n for n in nums if n not in cached and n not in detail]
    print(f"需要 {len(nums)} 条 issue，已有 {len(have)}，缺 {len(miss)}")

    left = rate_left()
    print(f"API 剩余额度：{left}")
    todo = miss[: min(left, a.limit or len(miss))]
    if not todo:
        print("没有可抓的（额度用完或缺额为 0），稍后再跑")
        return 0

    print(f"本次抓 {len(todo)} 条…")
    ok = gone = pr = 0
    for i, n in enumerate(todo, 1):
        d, why = fetch(n)
        if d:
            detail[n] = d
            ok += 1
            tag = " [PR，不能出题]" if d.get("is_pr") else ""
            if d.get("is_pr"):
                pr += 1
            print(f"  [{i}/{len(todo)}] #{n} {d['title'][:44]}{tag}")
        elif why == "rate":
            print(f"  [{i}/{len(todo)}] #{n} 限流，停止")
            break
        elif why == "gone":
            # 已删除的 issue：记下来跳过，不要中断整批
            detail[n] = {"number": int(n), "title": "", "body": "", "gone": True}
            gone += 1
            print(f"  [{i}/{len(todo)}] #{n} 已删除（404），跳过")
        else:
            print(f"  [{i}/{len(todo)}] #{n} 失败：{why}")
        time.sleep(1.0)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print(f"成功 {ok} 条（其中 PR {pr} 条）、已删除 {gone} 条，累计 {len(detail)} 条")
    print(f"→ {CACHE.relative_to(ROOT)}")
    rest = len(miss) - ok - gone
    if rest > 0:
        print(f"还剩 {rest} 条没抓（额度限制），约 1 小时后重跑本脚本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
