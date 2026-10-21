#!/usr/bin/env python3
"""反向找题：用文档里的参数名，去 2000 条真实 Issue 里搜。

为什么换这个思路：
  正向筛（先筛题再找答案）命中率只有 6%——因为 Issue 里大多是报错和功能请求。
  反向查（先拿参数名，再找问这个参数的提问）命中率高得多：
  只要提问里出现某个参数名，而文档里有这个参数的「类型/说明/默认值」，
  这道题就一定有确定答案。

做法：
  ① 从 arguments.md 解析参数表 → {参数名: (类型, 说明, 默认值)}
  ② 扫 2000 条 Issue 标题，找出现参数名的
  ③ 要求标题同时是「提问」（含 怎么/如何/什么/是否/默认/为什么/多少 等）
  ④ 输出候选：问题 + 标准答案（就是表格那一行）

输出：data/param_questions.json
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

Q_PAT = re.compile(
    r"(怎么|如何|什么|哪些|哪个|是否|能否|可以吗|默认|为什么|为啥|多少|区别|含义|作用|"
    r"设置|配置|要不要|需不需要|支持|啥意思|怎么用|怎么写)",
    re.I,
)
BUG_PAT = re.compile(
    r"(报错|错误|失败|OOM|crash|Traceback|Error|Exception|AssertionError|ValueError|"
    r"TypeError|RuntimeError|ImportError|无法|不能用|没有效果|乱码|异常|崩)",
    re.I,
)


def parse_param_table(md: Path) -> dict[str, dict]:
    """从 arguments.md 解析参数表。行格式：| 参数名 | 类型 | 说明 | 默认值 |"""
    params: dict[str, dict] = {}
    heading = ""
    if not md.exists():
        return params

    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            continue
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        name = cells[0].strip("`* ")
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", name):
            continue  # 表头或非参数行
        params[name] = {
            "type": cells[1].strip(),
            "desc": cells[2].strip(),
            "default": cells[3].strip(),
            "section": heading,
        }
    return params


def parse_all_tables() -> dict[str, dict]:
    """扫全部 chunk 里的表格行，凑出最全的参数字典。

    为什么不能只看 arguments.md：
      arguments.md 只覆盖 FinetuningArguments 一类；
      save_steps / save_total_limit 这类 TrainingArguments 在
      docs/zh/configuration/training.md 里，需要一起收。
    """
    params: dict[str, dict] = {}
    cj = DATA / "chunks.jsonl"
    if not cj.exists():
        return params

    for line in cj.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        for row in c["text"].split("\n"):
            if not row.startswith("| "):
                continue
            cells = [x.strip() for x in row.strip("|").split("|")]
            if len(cells) < 3:
                continue
            name = cells[0].strip("`* ")
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", name):
                continue
            if name in ("字段", "参数名称", "参数", "name"):
                continue
            # 默认值通常在第 4 列；只有 3 列时留空
            default = cells[3] if len(cells) >= 4 else ""
            desc = cells[2] if len(cells) >= 3 else ""
            # 同一参数可能在多处出现，保留信息最全的一条
            old = params.get(name)
            if old and len(old["desc"]) >= len(desc):
                continue
            params[name] = {
                "type": cells[1].strip(),
                "desc": desc,
                "default": default,
                "source": c["path"] + " | " + c["heading"],
            }
    return params


def load_issues() -> list[dict]:
    files = glob.glob(str(DATA / "issues/page_*.json")) + glob.glob(str(DATA / "issues/old/p*.json"))
    items, seen = [], set()
    for p in sorted(files):
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, list):
            continue
        for it in data:
            n = it.get("number")
            if n in seen or "pull_request" in it:
                continue
            seen.add(n)
            items.append(it)
    return items


def main() -> int:
    params = parse_all_tables()
    print(f"从 arguments.md 解析出 {len(params)} 个参数")
    if not params:
        print("✗ 没解析到参数，检查文件是否存在")
        return 1

    issues = load_issues()
    print(f"Issue 总数 {len(issues)}")

    hits = []
    for it in issues:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        if BUG_PAT.search(title):
            continue
        if not Q_PAT.search(title):
            continue
        low = title.lower()
        matched = [p for p in params if re.search(r"\b" + re.escape(p) + r"\b", low)]
        if not matched:
            continue
        hits.append(
            {
                "issue": it["number"],
                "url": it.get("html_url"),
                "title": title,
                "comments": it.get("comments") or 0,
                "created": (it.get("created_at") or "")[:10],
                "params": matched,
                "answers": {p: params[p] for p in matched},
            }
        )

    hits.sort(key=lambda h: (-len(h["params"]), -h["comments"]))

    out = DATA / "param_questions.json"
    out.write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n★ 命中 {len(hits)} 条（提问里出现文档参数名）")
    print(f"输出 {out}\n")
    for h in hits[:25]:
        p0 = h["params"][0]
        a = h["answers"][p0]
        print(f"  #{h['issue']}  参数={h['params'][:2]}")
        print(f"     {h['title'][:78]}")
        print(f"     答案：{p0} = {a['default']} ｜ {a['desc'][:50]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
