#!/usr/bin/env python3
"""评测接口冒烟测试：登录 → 发起 → 轮询 → 查概览 → 查逐题。

用途：接口改完后跑一遍，确认整条链路通。
     不依赖前端，纯 HTTP 调用，适合在服务器上验证。

用法：
    python scripts/smoke_eval_api.py                  # 默认测 app 11 的 test 集
    python scripts/smoke_eval_api.py --app 11 --model qwen3-4b-local
    python scripts/smoke_eval_api.py --no-wait        # 只发起，不等结果
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8020"


def q(**kwargs) -> str:
    """拼查询串，自动做 URL 编码（中文参数必须编码，否则 urllib 会崩）。"""
    items = [(k, str(v)) for k, v in kwargs.items() if v not in ("", None)]
    return ("?" + urllib.parse.urlencode(items)) if items else ""


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:  # noqa: BLE001
            return e.code, {"detail": e.reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=int, default=11)
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--split", default="test")
    ap.add_argument("--email", default="smoke@test.local")
    ap.add_argument("--password", default="demo12345")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    ok = True

    # 1. 登录
    st, d = call("POST", "/auth/login", {"email": a.email, "password": a.password})
    if st != 200:
        print(f"✗ 登录失败 {st}: {d}")
        return 1
    tok = d["token"]
    print(f"✓ 登录（{a.email}）")

    # 2. 应用列表，确认 app 存在
    st, d = call("GET", "/apps", token=tok)
    apps = d if isinstance(d, list) else d.get("items", [])
    if not any(x["id"] == a.app for x in apps):
        print(f"✗ 应用 {a.app} 不存在，现有：{[x['id'] for x in apps]}")
        return 1
    print(f"✓ 应用 {a.app} 存在")

    # 3. 发起评测
    st, d = call("POST", f"/apps/{a.app}/eval",
                 {"model": a.model, "split": a.split, "topk": 3}, tok)
    if st == 409:
        print(f"! 已有评测在跑：{d.get('detail')}（等它结束再试，或换应用）")
        return 1
    if st != 200:
        print(f"✗ 发起失败 {st}: {d}")
        return 1
    run_id = d["run_id"]
    print(f"✓ 发起评测 run_id={run_id}")

    # 4. 重复发起应被拒
    st2, _ = call("POST", f"/apps/{a.app}/eval",
                  {"model": a.model, "split": a.split, "topk": 3}, tok)
    if st2 == 409:
        print("✓ 重复发起被拒（409）")
    else:
        print(f"✗ 重复发起没被拒，返回 {st2}")
        ok = False

    if a.no_wait:
        print("\n（--no-wait，不等结果）")
        return 0 if ok else 2

    # 5. 轮询
    t0 = time.time()
    status = "pending"
    while time.time() - t0 < a.timeout:
        st, d = call("GET", f"/evals/{run_id}", token=tok)
        status = d.get("status")
        if status in ("done", "failed", "canceled"):
            break
        print(f"  … {status} {d.get('total', 0)} 题")
        time.sleep(3)

    if status != "done":
        print(f"✗ 评测没成功结束：{status} {d.get('error')}")
        return 1
    print(f"✓ 评测完成：{d['total']} 题，严格 {d['strict_acc']:.1%}，宽松 {d['loose_acc']:.1%}")
    print(f"  分来源：{d['by_source']}")

    # 6. 列表
    st, d = call("GET", f"/apps/{a.app}/evals", token=tok)
    print(f"✓ 列表返回 {len(d['items'])} 条，最新 run_id={d['items'][0]['run_id']}")

    # 7. 逐题（按判定筛选）
    st, d = call("GET", f"/evals/{run_id}/cases" + q(verdict="错", page=1, page_size=3), token=tok)
    print(f"✓ 逐题筛选「错」：共 {d['total']} 条，返回 {len(d['items'])} 条")
    for it in d["items"]:
        print(f"    · {it['question'][:34]}  →  {it['reason'][:36]}")

    # 8. 分页边界
    st, d = call("GET", f"/evals/{run_id}/cases" + q(page=999), token=tok)
    if st == 200 and d["items"] == []:
        print("✓ 超范围分页返回空列表（不报错）")
    else:
        print(f"✗ 超范围分页异常：{st}")
        ok = False

    print()
    print("✓ 全部通过" if ok else "✗ 有失败项")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
