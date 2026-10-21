#!/usr/bin/env python3
"""从 1293 条真实 Issue 里挖「文档能明确回答」的用法类提问。

和 find_param_questions.py 的区别：
  旧版只扫 title，正文完全没看 —— 而真实用户的细节几乎都在正文里。
  新版扫 title + body，并且：
    ① 只过滤「纯报错」：正文里 traceback 占比高、且不含任何参数名
    ② 记录问题原文（标题 + 正文首段），便于人工/LLM 判断语义
    ③ 同时输出命中的参数及其文档答案，供对照

输出：data/real_candidates.json
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 正文里出现这些 → 大概率是报错求助，不是用法提问
TRACE_PAT = re.compile(
    r"(Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|"
    r"\b(ValueError|TypeError|RuntimeError|AssertionError|ImportError|KeyError|"
    r"CUDA out of memory|OOM|Segmentation fault)\b)"
)

# 用法类信号
USAGE_PAT = re.compile(
    r"(怎么|如何|什么|哪些|哪个|是否|能否|可以吗|默认|为什么|为啥|多少|区别|含义|作用|"
    r"设置|配置|要不要|需不需要|支持|啥意思|怎么用|怎么写|how to|what is|default|"
    r"difference|which one|should i|can i)",
    re.I,
)


def parse_all_tables() -> dict[str, dict]:
    """扫全部 chunk 的表格行，凑出参数字典。"""
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
            default = cells[3] if len(cells) >= 4 else ""
            desc = cells[2] if len(cells) >= 3 else ""
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
    """读三种来源：
      data/issues/page_*.json      原始列表接口（list，最新 1000 条）
      data/issues/old/p*.json      原始列表接口（list，since 窗口）
      data/issues/win_*_p*.json    Search API 时间切片（dict，含 items）
    """
    files = (
        glob.glob(str(DATA / "issues/page_*.json"))
        + glob.glob(str(DATA / "issues/old/p*.json"))
        + glob.glob(str(DATA / "issues/win_*_p*.json"))
    )
    items, seen = [], set()
    for p in sorted(files):
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict):
            data = data.get("items") or []
        if not isinstance(data, list):
            continue
        for it in data:
            n = it.get("number")
            if n in seen or "pull_request" in it:
                continue
            seen.add(n)
            items.append(it)
    return items


def clean_body(body: str) -> str:
    """去掉代码块、图片、HTML 标签，留下自然语言部分。"""
    t = body or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\r", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def main() -> int:
    params = parse_all_tables()
    print(f"参数字典: {len(params)} 个")

    issues = load_issues()
    print(f"Issue 总数: {len(issues)}")

    hits = []
    stat = {"no_param": 0, "trace_only": 0, "no_usage": 0, "ok": 0}

    for it in issues:
        title = (it.get("title") or "").strip()
        body = clean_body(it.get("body") or "")
        full = (title + "\n" + body).lower()

        matched = [p for p in params if re.search(r"(?<![a-z0-9_])" + re.escape(p) + r"(?![a-z0-9_])", full)]
        if not matched:
            stat["no_param"] += 1
            continue

        # 纯报错：正文有 traceback 且几乎没有用法类问句
        n_trace = len(TRACE_PAT.findall(body))
        if n_trace >= 2 and not USAGE_PAT.search(title):
            stat["trace_only"] += 1
            continue

        if not USAGE_PAT.search(title + " " + body[:400]):
            stat["no_usage"] += 1
            continue

        stat["ok"] += 1
        # 问题原文：标题 + 正文前 300 字（去掉代码）
        ask = title
        if body:
            head = body[:300].replace("\n", " ").strip()
            if head and head not in title:
                ask = title + " ｜ " + head

        hits.append(
            {
                "issue": it["number"],
                "url": it.get("html_url"),
                "title": title,
                "ask": ask,
                "comments": it.get("comments") or 0,
                "created": (it.get("created_at") or "")[:10],
                "params": matched[:5],
                "answers": {p: params[p] for p in matched[:5]},
                "n_trace": n_trace,
            }
        )

    hits.sort(key=lambda h: (-len(h["params"]), h["n_trace"], -h["comments"]))

    out = DATA / "real_candidates.json"
    out.write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n过滤统计: 无参数名 {stat['no_param']} ｜ 纯报错 {stat['trace_only']} ｜ 非提问 {stat['no_usage']} ｜ 通过 {stat['ok']}")
    print(f"★ 候选 {len(hits)} 条 → {out}\n")

    for h in hits[:15]:
        p0 = h["params"][0]
        a = h["answers"][p0]
        print(f"  #{h['issue']}  参数={h['params'][:2]}  trace={h['n_trace']}")
        print(f"     {h['ask'][:100]}")
        print(f"     文档: {p0} ｜ {a['desc'][:56]} ｜ 默认 {a['default']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
