#!/usr/bin/env python3
"""助手接口冒烟测试：问一句 → 看回答和引用 → 打反馈 → 查历史。

用法：
    python scripts/smoke_chat_api.py
    python scripts/smoke_chat_api.py --app 11 --question "save_epochs 设成 null 会怎样"
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8020"


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:  # noqa: BLE001
            return e.code, {"detail": e.reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=int, default=11)
    ap.add_argument("--question", default="训练时 save_epochs 这个参数是干什么的？")
    ap.add_argument("--email", default="smoke@test.local")
    ap.add_argument("--password", default="demo12345")
    a = ap.parse_args()

    st, d = call("POST", "/auth/login", {"email": a.email, "password": a.password})
    if st != 200:
        print(f"✗ 登录失败 {st}: {d}")
        return 1
    tok = d["token"]
    print(f"✓ 登录")

    st, d = call("POST", f"/apps/{a.app}/chat", {"question": a.question, "topk": 3}, tok)
    if st != 200:
        print(f"✗ 问答失败 {st}: {d}")
        return 1
    print(f"✓ 问答成功（{d['latency_ms']} ms，message_id={d['message_id']}）")
    print(f"  问：{a.question}")
    print(f"  答：{d['answer'][:120]}")
    print(f"  引用 {len(d['references'])} 段：")
    for r in d["references"]:
        print(f"    · [{r['score']}] {r['path']} > {r['heading']}")

    mid = d["message_id"]
    st, d2 = call("POST", f"/chat/{mid}/feedback", {"rating": "useful", "comment": "测试"}, tok)
    if st != 200:
        print(f"✗ 反馈失败 {st}: {d2}")
        return 1
    print(f"✓ 反馈成功：{d2['rating']}")

    st, d3 = call("GET", f"/apps/{a.app}/chat/history?limit=5", token=tok)
    if st != 200:
        print(f"✗ 历史失败 {st}: {d3}")
        return 1
    print(f"✓ 历史返回 {len(d3['items'])} 条，最后一条 rating={d3['items'][-1]['rating']}")

    print()
    print("✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
