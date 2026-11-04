#!/usr/bin/env python3
"""把 data/questions.json 同步进某个应用的题库（保留原有切分和来源）。

为什么需要：
  题库在 questions.json 里已经按 3:3:4 切好、标了来源。
  如果导入时让服务端重新随机切，数据库的测试集就和 questions.json 不是同一批，
  报告里的数字和页面上显示的数字会对不上。

用法：
    python scripts/sync_bank_to_db.py --app 11
    python scripts/sync_bank_to_db.py --app 11 --dry-run   # 只看会导入什么
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8020"


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:  # noqa: BLE001
            return e.code, {"detail": e.reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=int, required=True)
    ap.add_argument("--email", default="smoke@test.local")
    ap.add_argument("--password", default="demo12345")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    qs = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
    splits = Counter(q["split"] for q in qs)
    sources = Counter(q.get("source", "?") for q in qs)
    print(f"questions.json：{len(qs)} 道")
    print(f"  切分 {dict(splits)}")
    print(f"  来源 {dict(sources)}")

    if a.dry_run:
        print("\n（--dry-run，不实际导入）")
        return 0

    st, d = call("POST", "/auth/login", {"email": a.email, "password": a.password})
    if st != 200:
        print(f"✗ 登录失败 {st}: {d}")
        return 1
    tok = d["token"]

    st, d = call("POST", f"/apps/{a.app}/questions/import", {
        "items": [
            {"content": q["question"], "reference": q["answer"],
             "split": q["split"], "source": q.get("source", "")}
            for q in qs
        ],
        "replace": True,
    }, tok)
    if st != 200:
        print(f"✗ 导入失败 {st}: {d}")
        return 1
    print(f"\n✓ 导入 {d['imported']} 道，切分 {d['splits']}，切分来源 {d.get('split_source')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
