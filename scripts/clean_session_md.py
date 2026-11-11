#!/usr/bin/env python3
"""把从分享页复制下来的文本清理成可读的 md。

为什么需要：
  WorkBuddy/CodeBuddy 只有「分享链接」，没有「保存到本地」。
  分享页是动态渲染的，脚本抓不到正文，只能人工在浏览器里全选复制。
  但复制出来会带一堆网页噪音（导航、按钮文字、重复的标题）。

这个脚本做三件事：
  1. 删掉已知的噪音行（按钮文字、导航、页脚）
  2. 把连续空行压成一个
  3. 给文件加一个标题头

用法：
    # 先把复制的内容存成 raw.txt，然后
    python scripts/clean_session_md.py raw.txt -o agent-sessions/2026-11-11/01_xxx.md --title "重排序实验"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 分享页里常见的噪音行（整行匹配就删）
NOISE = [
    r"^复制链接$", r"^分享$", r"^复制$", r"^返回$", r"^收起$", r"^展开$",
    r"^WorkBuddy", r"^CodeBuddy", r"^Powered by", r"^©",
    r"^\s*$", r"^[·•\-—]{3,}$", r"^\d+\.\d+k? ?(次|浏览|查看)$",
]
NOISE_RE = [re.compile(p) for p in NOISE]


def clean(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.rstrip()
        if any(p.search(s) for p in NOISE_RE):
            continue
        lines.append(s)

    # 连续空行压成一个
    out, prev_blank = [], False
    for s in lines:
        blank = not s.strip()
        if blank and prev_blank:
            continue
        out.append(s)
        prev_blank = blank
    return "\n".join(out).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="从分享页复制下来的原始文本")
    ap.add_argument("-o", "--out", help="输出 md 路径（默认同目录 .md）")
    ap.add_argument("--title", default="", help="标题，写进文件头")
    ap.add_argument("--date", default="", help="日期，写进文件头")
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"找不到：{src}")
        return 1

    body = clean(src.read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else src.with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)

    head = f"# {a.title or out.stem}\n\n"
    if a.date:
        head += f"> 日期：{a.date}　项目：llmloop\n\n"
    head += "> 本文件由分享页复制内容整理而成，非工具原始导出。\n\n---\n\n"

    out.write_text(head + body, encoding="utf-8")
    print(f"已写出：{out}（{len(body)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
