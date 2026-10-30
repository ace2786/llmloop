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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SRC = OUT / "select_140.csv"

COLS = [
    "序号", "优先级", "issue", "issue链接", "草稿答案（待核对）", "文档原文",
    "所在段落上下文", "出处（文件#块号）", "问题（你来写）", "核对结果",
]


def do_make() -> int:
    if not SRC.exists():
        print(f"找不到 {SRC}，先跑：python scripts/select_140.py", file=sys.stderr)
        return 1

    with SRC.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

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
        }
        for r in rows
    ]

    tpl = (Path(__file__).resolve().parent / "qbank_aid_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False))
    dst = OUT / "qbank.html"
    dst.write_text(html, encoding="utf-8")

    print(f"已生成：{dst}（{len(items)} 条）")
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
