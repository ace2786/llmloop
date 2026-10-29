#!/usr/bin/env python3
"""Bug 数据库的命令行工具。

用法：
    python scripts/bug.py list                 # 全部
    python scripts/bug.py list --days 3        # 最近 3 天
    python scripts/bug.py list --area F3       # 按模块
    python scripts/bug.py list --tag 环境      # 按标签
    python scripts/bug.py stats                # 统计 + 找出重复犯错
    python scripts/bug.py check                # 校验格式，有问题返回 1（给 CI 用）
    python scripts/bug.py export               # 导出 eval case 给回归套件
    python scripts/bug.py add --json '{...}'   # 追加一条

设计原则：只依赖标准库，不联网，不做花活。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "bugs" / "index.jsonl"

REQUIRED = [
    "id", "date", "area", "title", "symptom", "root_cause",
    "fix", "minimal_repro", "eval_case", "negative_case", "tags", "seen_days",
]


def load() -> list[dict]:
    if not INDEX.exists():
        return []
    out = []
    for i, line in enumerate(INDEX.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"✗ 第 {i} 行 JSON 解析失败：{e}", file=sys.stderr)
            raise SystemExit(1)
    return out


def validate(rows: list[dict]) -> list[str]:
    """返回错误列表，空列表表示通过。"""
    errs: list[str] = []
    ids = Counter()
    for i, r in enumerate(rows, 1):
        rid = r.get("id", f"第{i}行")
        for f in REQUIRED:
            if f not in r or (isinstance(r[f], str) and not r[f].strip()):
                errs.append(f"{rid}: 缺字段 {f}")
        ids[r.get("id", "")] += 1
        if not re.fullmatch(r"B\d{3}", str(r.get("id", ""))):
            errs.append(f"{rid}: id 应为 B + 三位数字")
        try:
            datetime.strptime(str(r.get("date", "")), "%Y-%m-%d")
        except ValueError:
            errs.append(f"{rid}: date 应为 YYYY-MM-DD")
        seen = r.get("seen_days")
        if not isinstance(seen, list) or not seen:
            errs.append(f"{rid}: seen_days 应为非空列表")
        elif str(r.get("date")) not in [str(d) for d in seen]:
            errs.append(f"{rid}: seen_days 必须包含 date 本身")
        if not isinstance(r.get("tags"), list):
            errs.append(f"{rid}: tags 应为列表")
        if len(str(r.get("eval_case", ""))) < 10:
            errs.append(f"{rid}: eval_case 太短，写不出可执行的检查")
        if len(str(r.get("negative_case", ""))) < 5:
            errs.append(f"{rid}: negative_case 缺失，eval 会误杀")
    for k, c in ids.items():
        if c > 1:
            errs.append(f"id 重复：{k} 出现 {c} 次")
    return errs


def cmd_list(a) -> int:
    rows = load()
    if a.days:
        cutoff = date.today() - timedelta(days=a.days)
        rows = [r for r in rows if datetime.strptime(r["date"], "%Y-%m-%d").date() >= cutoff]
    if a.area:
        rows = [r for r in rows if a.area.lower() in r["area"].lower()]
    if a.tag:
        rows = [r for r in rows if any(a.tag.lower() in t.lower() for t in r["tags"])]
    if not rows:
        print("（没有匹配的记录）")
        return 0
    for r in rows:
        flag = f"  ⚠ 重复 {len(r['seen_days'])} 次" if len(r["seen_days"]) >= 2 else ""
        print(f"{r['id']}  {r['date']}  [{r['area']}]  {r['title']}{flag}")
        print(f"      根因：{r['root_cause'][:70]}")
    print(f"\n共 {len(rows)} 条")
    return 0


def cmd_stats(a) -> int:
    rows = load()
    if not rows:
        print("（库是空的）")
        return 0
    print(f"总条数：{len(rows)}")
    print(f"日期范围：{min(r['date'] for r in rows)} ~ {max(r['date'] for r in rows)}")
    print()
    print("按模块：")
    for k, c in Counter(r["area"] for r in rows).most_common():
        print(f"  {k:<10} {c:>3}")
    print()
    print("按标签（前 10）：")
    for k, c in Counter(t for r in rows for t in r["tags"]).most_common(10):
        print(f"  {k:<18} {c:>3}")
    print()
    repeat = [r for r in rows if len(r["seen_days"]) >= 2]
    if repeat:
        print("⚠ 重复犯错（seen_days ≥ 2）：")
        for r in repeat:
            days = ", ".join(r["seen_days"])
            print(f"  {r['id']}  {r['title']}")
            print(f"       出现过：{days}")
            if len(r["seen_days"]) >= 3:
                print("       → 已达 3 次，必须升级成硬规则")
    else:
        print("✓ 没有重复犯错")
    return 0


def cmd_check(a) -> int:
    rows = load()
    errs = validate(rows)
    if errs:
        print(f"✗ {len(errs)} 个问题：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"✓ {len(rows)} 条记录格式正确")
    return 0


def cmd_export(a) -> int:
    rows = load()
    cases = [
        {
            "id": r["id"],
            "area": r["area"],
            "title": r["title"],
            "minimal_repro": r["minimal_repro"],
            "eval_case": r["eval_case"],
            "negative_case": r["negative_case"],
            "tags": r["tags"],
        }
        for r in rows
    ]
    print(json.dumps(cases, ensure_ascii=False, indent=2))
    return 0


def cmd_add(a) -> int:
    try:
        rec = json.loads(a.json)
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败：{e}", file=sys.stderr)
        return 1
    rows = load()
    errs = validate(rows + [rec])
    if errs:
        print("✗ 新记录有问题，未写入：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    with INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"✓ 已追加 {rec['id']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Bug 数据库工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出记录")
    p.add_argument("--days", type=int)
    p.add_argument("--area")
    p.add_argument("--tag")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("stats", help="统计与重复犯错")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("check", help="校验格式（CI 用）")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("export", help="导出 eval case")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("add", help="追加一条")
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_add)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
