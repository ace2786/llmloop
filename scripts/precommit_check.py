#!/usr/bin/env python3
"""提交前自检：扫密钥泄露、扫硬编码结果、扫 Mock 痕迹。

对应第 16 节的红线：
  · 「令牌等敏感配置不提交到仓库」
  · 「前端不能写死任何结果，不能用 Mock 冒充真实功能」
  · 「每个数字都必须由后端从真实数据实时算出」

用法：
    python scripts/precommit_check.py
    python scripts/precommit_check.py --strict   # 有 ERROR 就返回非 0
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 疑似密钥
KEY_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "疑似 OpenAI/硅基流动 风格密钥 sk-..."),
    (re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9]{16}\b"), "疑似智谱密钥 32位.16位"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "疑似 GitHub token ghp_..."),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"), "疑似 GitHub token github_pat_..."),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "疑似 AWS Access Key"),
]

# Mock / 假数据痕迹
MOCK_PATTERNS = [
    (re.compile(r"\b(mock|Mock|MOCK|fake|Fake|dummy|Dummy|stub|Stub)\b"), "疑似 Mock/假数据"),
]

# 硬编码的评测结果（在源码里出现准确率数字）
HARDCODE_PATTERNS = [
    (re.compile(r"accuracy\s*=\s*0?\.\d+"), "疑似硬编码准确率"),
    (re.compile(r"\"(正确率|准确率|幻觉率)\"\s*:\s*[\d.]+"), "疑似硬编码指标"),
]

SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules", "data", "models", "out", ".pytest_cache"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".json", ".yaml", ".yml", ".md", ".html", ".vue"}


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in CODE_EXT:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        yield p


def git(*args) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warns: list[str] = []

    print("=" * 62)
    print("提交前自检")
    print("=" * 62)
    print()

    # ── 1. .env 是否被 git 跟踪 ──
    print("① 密钥文件是否被 git 跟踪")
    tracked = git("ls-files", ".env")
    if tracked:
        errors.append(".env 已被 git 跟踪！必须移除：git rm --cached .env")
        print("   ✗ .env 已被跟踪")
    else:
        print("   ✓ .env 未被跟踪")
    if (ROOT / ".env").exists():
        mode = oct((ROOT / ".env").stat().st_mode)[-3:]
        print(f"   .env 存在，权限 {mode}" + ("（建议 600）" if mode != "600" else " ✓"))
    print()

    # ── 2. 扫代码里的密钥 ──
    print("② 扫描代码中的疑似密钥")
    hits = 0
    for p in iter_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for pat, desc in KEY_PATTERNS:
            for m in pat.finditer(text):
                snippet = m.group(0)
                # 排除明显的占位符
                if re.fullmatch(r"[xX\*\.\-]+", snippet):
                    continue
                rel = p.relative_to(ROOT)
                errors.append(f"{rel} 含{desc}：{snippet[:12]}…")
                hits += 1
    if hits:
        print(f"   ✗ 发现 {hits} 处")
    else:
        print("   ✓ 没发现明文密钥")
    print()

    # ── 3. 扫 Mock 痕迹 ──
    print("③ 扫描 Mock / 假数据")
    hits = 0
    for p in iter_files():
        if p.name in ("precommit_check.py", "RUBRIC.md", "README.md", "REPRO.md"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for pat, desc in MOCK_PATTERNS:
            for m in pat.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                warns.append(f"{p.relative_to(ROOT)}:{line_no} {desc}")
                hits += 1
    if hits:
        print(f"   ⚠ 发现 {hits} 处，逐个确认是不是真 Mock")
        for w in warns[:12]:
            print(f"      {w}")
        if len(warns) > 12:
            print(f"      …… 还有 {len(warns) - 12} 处")
    else:
        print("   ✓ 没发现")
    print()

    # ── 4. 扫硬编码指标 ──
    print("④ 扫描硬编码的评测数字")
    hits = 0
    for p in iter_files():
        if p.name in ("precommit_check.py", "RUBRIC.md", "README.md", "REPRO.md"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for pat, desc in HARDCODE_PATTERNS:
            for m in pat.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                warns.append(f"{p.relative_to(ROOT)}:{line_no} {desc}：{m.group(0)[:30]}")
                hits += 1
    if hits:
        print(f"   ⚠ 发现 {hits} 处")
        for w in warns[-min(hits, 10):]:
            print(f"      {w}")
    else:
        print("   ✓ 没发现")
    print()

    # ── 5. 大文件是否会被提交 ──
    print("⑤ 大文件检查（>5MB 不应进仓库）")
    big = []
    staged = git("ls-files")
    for line in staged.splitlines():
        f = ROOT / line
        if f.is_file() and f.stat().st_size > 5 * 1024 * 1024:
            big.append((line, f.stat().st_size))
    if big:
        for name, size in big:
            errors.append(f"大文件将被提交：{name}（{size / 1024 / 1024:.1f} MB）")
            print(f"   ✗ {name}  {size / 1024 / 1024:.1f} MB")
    else:
        print("   ✓ 没有")
    print()

    # ── 6. 关键文件是否齐全 ──
    print("⑥ 关键文件")
    required = {
        "README.md": "第一行要写一句话产品描述",
        "REPRO.md": "可行性五关 + 本机配置",
        "RUBRIC.md": "判分标准",
        ".gitignore": "排除密钥与模型",
    }
    for name, desc in required.items():
        if (ROOT / name).exists():
            print(f"   ✓ {name}")
        else:
            errors.append(f"缺 {name}（{desc}）")
            print(f"   ✗ 缺 {name}（{desc}）")
    print()

    # ── 7. git 状态 ──
    print("⑦ git 状态")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    commits = git("rev-list", "--count", "HEAD") or "0"
    print(f"   分支 {branch or '(未初始化)'}，提交 {commits} 次")
    dirty = git("status", "--porcelain")
    n_dirty = len([l for l in dirty.splitlines() if l.strip()])
    print(f"   未提交变更 {n_dirty} 项")
    if commits == "0":
        warns.append("还没有首次提交，第 11 节要求每天至少 1 次")
    print()

    # ── 汇总 ──
    print("=" * 62)
    if errors:
        print(f"✗ {len(errors)} 个必须修的问题")
        for e in errors:
            print(f"   · {e}")
    else:
        print("✓ 没有必须修的问题")
    if warns:
        print(f"⚠ {len(warns)} 个提醒（自己确认）")
    print("=" * 62)

    if args.strict and errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
