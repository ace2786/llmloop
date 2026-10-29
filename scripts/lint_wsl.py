#!/usr/bin/env python3
"""扫描仓库里的 .sh 文件，找出「wsl.exe 命令里带 $变量」这种写法。

为什么需要它：同一个坑在 2026-10-27、10-28、10-29 三个不同日子各踩一次（bug B002/B003），
按第 14 节规则必须机械化拦截，不能再靠记性。

原理：wsl.exe 的命令字符串要穿过 Windows 参数解析，$VAR 和 $(...) 会在
到达 WSL 的 bash 之前被展开或吞掉（单双引号都拦不住）。
正确做法是把逻辑写进 .sh 脚本文件，再 `bash ~/xxx.sh` 执行——脚本内部的变量是安全的。

用法：
    python scripts/lint_wsl.py          # 扫描，有问题返回 1
    python scripts/lint_wsl.py -v       # 同时列出扫描了哪些文件
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "node_modules", "data", "models", "out"}

# 匹配调用 wsl / wsl.exe 的行
WSL_CALL = re.compile(r"\bwsl(\.exe)?\b", re.IGNORECASE)
# 行内出现的变量引用
VAR_USE = re.compile(r"\$[A-Za-z_{(]")


def iter_scripts():
    for p in ROOT.rglob("*.sh"):
        if any(part in SKIP_DIRS or part.startswith(".venv") for part in p.parts):
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    problems = []
    scanned = 0
    for p in iter_scripts():
        scanned += 1
        if a.verbose:
            print(f"  扫描 {p.relative_to(ROOT)}")
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if WSL_CALL.search(line) and VAR_USE.search(line):
                problems.append((p.relative_to(ROOT), n, stripped[:110]))

    if problems:
        print(f"✗ 发现 {len(problems)} 处「wsl.exe + $变量」，会静默失败：", file=sys.stderr)
        for path, n, text in problems:
            print(f"  {path}:{n}", file=sys.stderr)
            print(f"    {text}", file=sys.stderr)
        print(file=sys.stderr)
        print("  改法：把逻辑写进独立的 .sh 文件，再 bash 执行；", file=sys.stderr)
        print("        或把变量在调用前展开成字面量。", file=sys.stderr)
        return 1

    print(f"✓ 扫描 {scanned} 个 .sh 文件，没有「wsl.exe + $变量」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
