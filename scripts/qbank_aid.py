#!/usr/bin/env python3
"""题库核对辅助工具：把 140 条候选摊成一屏一条，键盘过，导出 CSV 回填。

★ 这个工具不代替人写题。它只做三件事：
  1. 把 140 条候选摊成一屏一条，省掉 Excel 里左右横跳的时间
  2. 键盘 1/2/3 判定 + Ctrl+Enter 下一条，进度自动存浏览器，关掉不丢
  3. 导出 CSV，再由 apply 子命令回填到 select_140.csv

「问题」仍然由人来写——issue 是 bug 报告，不是提问，机器改不出来。

用法：
    python scripts/qbank_aid.py make                    # 生成 out/qbank.html
    python scripts/qbank_aid.py apply <导出的csv>        # 回填 select_140.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SRC = OUT / "select_140.csv"
DATA = ROOT / "data"

COLS = [
    "序号", "优先级", "issue", "issue链接", "草稿答案（待核对）", "文档原文",
    "所在段落上下文", "出处（文件#块号）", "问题（你来写）", "核对结果",
]

# 从原文里抽「这条讲的是哪个参数/配置项」
TABLE_CELL = re.compile(r"^\s*\|?\s*`?([a-zA-Z_][a-zA-Z0-9_.]{2,})`?\s*\|", re.M)
YAML_KEY = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_.]{2,})\s*:", re.M)
BACKTICK = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_.]{2,})`")
# 答案开头的「支持 X」「使用 X」也能提示主题
CJK_HEAD = re.compile(r"^(支持|使用|设置|通过|可以)")
# 模型名/产品名：Qwen3-4B-Instruct-2507、Meta-Llama-3-8B 这种
MODEL_NAME = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+){1,}")

# issue 标题里的噪音前缀：[Feature] [Help] [Question] 【Help】 等
TAG_PREFIX = re.compile(r"^\s*[\[【][^\]】]{1,14}[\]】]\s*")


def draft_question(title: str) -> str:
    """把 issue 标题收拾成一句能用的提问，作为输入框的预填内容。

    只做机械清理，不改写语义：去掉 [Feature]/【Help】 这类标签前缀、压掉多余空格。
    人可以在这个基础上改，也可以直接采用。
    """
    s = (title or "").strip()
    for _ in range(3):
        s2 = TAG_PREFIX.sub("", s)
        if s2 == s:
            break
        s = s2
    return re.sub(r"\s+", " ", s).strip()


CN = re.compile(r"[\u4e00-\u9fff]")
ASK_WORD = re.compile(r"如何|怎么|怎样|是否|能否|可以|什么|哪个|为什么|多少|哪些|吗|呢")


def qtype(title: str) -> tuple[str, int]:
    """判断原提问能不能直接当题目用。返回 (类型, 排序权重)。

    0 = 中文问句，直接可用
    1 = 中文但非问句，改几个字
    2 = 纯英文，需要翻译
    """
    t = (title or "").strip()
    if not t:
        return "无提问", 3
    if not CN.search(t):
        return "英文·需翻译", 2
    if "？" in t or "?" in t or ASK_WORD.search(t):
        return "中文问句·可直接用", 0
    return "中文陈述·需改写", 1


def topic_of(quote: str, answer: str) -> str:
    """猜这条原文讲的是什么（参数名/配置项/模型名）。机械提取，不编。"""
    for pat in (TABLE_CELL, YAML_KEY, BACKTICK):
        m = pat.search(quote or "")
        if m:
            return m.group(1)
    # 原文没有标识符，就从答案里找
    m = BACKTICK.search(answer or "")
    if m:
        return m.group(1)
    m = MODEL_NAME.search(answer or "")
    return m.group(0) if m else ""


def load_reasons() -> dict[str, str]:
    """从 located.json 取「当初为什么选这段」，里面常含 issue 问什么。"""
    p = DATA / "located.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v.get("reason") or "") for k, v in d.items()}


def load_flags() -> dict[str, list[str]]:
    """读审计结果，序号 → 命中的问题类型列表。没有就返回空。

    只保留「需要人动手」的类别；「原文偏短·多半可用」是误报（完整配置项），
    标红只会干扰，直接丢掉。
    """
    p = OUT / "audit_flagged.csv"
    if not p.exists():
        return {}
    SKIP = {"原文偏短·多半可用"}
    m: dict[str, list[str]] = {}
    with p.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            kind = r["问题类型"]
            if kind in SKIP:
                continue
            m.setdefault(r["序号"].strip(), []).append(kind)
    return m


def do_make() -> int:
    if not SRC.exists():
        print(f"找不到 {SRC}，先跑：python scripts/select_140.py", file=sys.stderr)
        return 1

    with SRC.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    flags = load_flags()
    reasons = load_reasons()
    items = [
        {
            "i": r["序号"],
            "issue": r["issue"],
            "pri": r["优先级"],
            "ans": r["草稿答案（待核对）"],
            "quote": r["文档原文"],
            "ctx": r["所在段落上下文"],
            "seg": r["出处（文件#块号）"],
            "url": r["issue链接"],
            "flag": flags.get(r["序号"].strip(), []),
            "topic": topic_of(r["文档原文"], r["草稿答案（待核对）"]),
            "reason": reasons.get(r["issue"].strip(), "")[:200],
            "qtitle": r.get("用户原提问（标题）", ""),
            "qbody": r.get("用户原提问（正文）", ""),
            "qdefault": draft_question(r.get("用户原提问（标题）", "")),
            "qtype": qtype(r.get("用户原提问（标题）", ""))[0],
            "qrank": qtype(r.get("用户原提问（标题）", ""))[1],
        }
        for r in rows
    ]
    n_flagged = sum(1 for it in items if it["flag"])

    # 按「能直接用的排前面」重排：中文问句 → 中文陈述 → 英文
    # 序号保持不变（导出时按序号回填，不能重编）
    items.sort(key=lambda x: (x["qrank"], int(x["i"])))
    from collections import Counter as _C
    dist = _C(it["qtype"] for it in items)
    print("  类型分布：" + "　".join(f"{k} {v}" for k, v in dist.most_common()))

    tpl = (Path(__file__).resolve().parent / "qbank_aid_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False))
    dst = OUT / "qbank.html"
    dst.write_text(html, encoding="utf-8")

    print(f"已生成：{dst}（{len(items)} 条，其中 {n_flagged} 条被审计标红）")
    print()
    print("Windows 路径：")
    print("  \\\\wsl.localhost\\Ubuntu\\home\\ace\\llmloop\\out\\qbank.html")
    print()
    print("  快捷键：1=对  2=要改  3=砍掉  Ctrl+Enter=保存并下一条  ←/→=翻条")
    print("  进度自动存浏览器，关掉再打开还在。做完点「导出 CSV」。")
    return 0


def do_apply(csv_path: Path) -> int:
    with csv_path.open(encoding="utf-8-sig") as f:
        res = {r["序号"].strip(): r for r in csv.DictReader(f)}
    print(f"读到核对结果 {len(res)} 条")

    with SRC.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    n_q = n_v = 0
    for r in rows:
        g = res.get(r["序号"].strip())
        if not g:
            continue
        q = (g.get("问题") or "").strip()
        v = (g.get("核对结果") or "").strip()
        if q:
            r["问题（你来写）"] = q
            n_q += 1
        if v:
            r["核对结果"] = v
            n_v += 1

    dst = OUT / "select_140_filled.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    keep = [r for r in rows if r["核对结果"] == "对" and r["问题（你来写）"].strip()]
    print(f"填了问题 {n_q} 条，标了结果 {n_v} 条")
    print(f"可直接入库（结果=对 且 有问题）：{len(keep)} 条")
    print()
    print(f"已写出：{dst.relative_to(ROOT)}")
    print()
    print("下一步：把「对」的条目并进 data/questions.json，再重跑切分。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "apply"])
    ap.add_argument("csv", nargs="?", help="apply 时要回填的 CSV")
    a = ap.parse_args()

    if a.cmd == "make":
        return do_make()
    if not a.csv:
        print("apply 需要指定 CSV 路径", file=sys.stderr)
        return 1
    return do_apply(Path(a.csv))


if __name__ == "__main__":
    sys.exit(main())
