#!/usr/bin/env python3
"""把 WorkBuddy 分享页复制出来的文本整理成 md。

这个脚本针对分享页的实际格式：
    用户的问题
    11月4日 21:20
    WorkBuddy AI
    AI 的回答（可能很长，带表格）

处理：
  1. 去掉标题行和「内容由 AI 生成」免责声明
  2. 日期行改成 `### 11月4日 21:20`（三级标题）
  3. 去掉重复的「WorkBuddy AI」标记
  4. 连续空行压成一个
  5. 在文件头写清来源和说明

用法：
    python scripts/format_session.py 输入.txt -o agent-sessions/2026-11-11/01_xxx.md --title "第三周开发记录"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"^\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}$")
NOISE_EXACT = {
    "WorkBuddy AI",
    "内容由 AI 生成，请核实重要信息",
    "复制链接",
    "分享",
}
NOISE_PREFIX = ("内容由 AI 生成",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--title", default="会话记录")
    ap.add_argument("--project", default="llmloop")
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"找不到：{src}")
        return 1

    raw = src.read_text(encoding="utf-8", errors="replace").splitlines()

    # 第一行是会话标题（分享页顶部），不是对话内容，去掉
    if raw and raw[0].strip() and not DATE_RE.match(raw[0].strip()):
        raw = raw[1:]

    out: list[str] = []
    prev_blank = False
    turns = 0

    for line in raw:
        s = line.rstrip()

        if s in NOISE_EXACT or s.startswith(NOISE_PREFIX):
            continue

        if DATE_RE.match(s.strip()):
            out.append("")
            out.append(f"### {s.strip()}")
            out.append("")
            turns += 1
            prev_blank = False
            continue

        blank = not s.strip()
        if blank and prev_blank:
            continue
        out.append(s)
        prev_blank = blank

    body = "\n".join(out).strip()

    head = (
        f"# {a.title}\n\n"
        f"> 项目：{a.project}　日期：2026-11-04 ～ 2026-11-11\n\n"
        "> **来源**：WorkBuddy 分享页复制整理。工具没有「保存到本地」按钮，"
        "分享页又是动态渲染的（脚本抓不到正文），所以由人工在浏览器里全选复制，再用本脚本去噪。\n"
        "> **这是整理后的文本，不是工具的原始导出文件。**\n\n"
        f"> 共 {turns} 轮对话，{len(body.splitlines())} 行。\n\n---\n\n"
    )

    dst = Path(a.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(head + body + "\n", encoding="utf-8")
    print(f"已写出：{dst}")
    print(f"  轮次 {turns}，行数 {len(body.splitlines())}，字符 {len(body)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
