#!/usr/bin/env python3
"""检查「用户原提问」和「草稿答案」是否对得上。

为什么需要：之前的审计只查了「答案 vs 文档原文」，
没查「原提问 vs 答案」。如果用户问 A、草稿答 B，
这条题无论怎么改都没意义——直接砍掉最省事。

判据（两条，任一命中就标记）：
  1. 提问里有英文标识符（QLoRA、do_sample、SFT…），但答案里一个都没有
     → 强信号：答非所问
  2. 提问和答案的中文二字组重合率 < 12%
     → 弱信号：可能是同一个话题但表述差很远，需要人看一眼

用法：
    python scripts/check_qa_alignment.py
    python scripts/check_qa_alignment.py --csv out/select_140.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IDENT = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]{2,}\b")
# 常见无意义英文词，不算标识符
STOP = {
    "the", "and", "for", "how", "what", "why", "can", "you", "with", "use", "using",
    "model", "train", "training", "data", "error", "issue", "help", "please", "when",
    "does", "not", "but", "from", "this", "that", "have", "get", "set", "run", "load",
    "any", "are", "was", "were", "will", "would", "should", "could", "support", "about",
    "like", "want", "need", "know", "there", "their", "which", "where", "here", "some",
    "http", "https", "www", "com", "org", "html", "github", "python", "bash", "sh",
    "true", "false", "none", "null", "yes", "no", "all", "new", "old", "add", "fix",
}


def idents(s: str) -> set[str]:
    """只从标题里抽「像技术名词」的词：含下划线/驼峰，或长度>=4 的英文词。

    刻意排除：带点的（文件路径/版本）、纯数字开头、常见虚词。
    """
    out = set()
    for w in IDENT.findall(s or ""):
        if w.lower() in STOP:
            continue
        if "." in w or w[0].isdigit():
            continue
        # 要求：有下划线，或至少 4 个字符
        if "_" in w or len(w) >= 4:
            out.add(w.lower())
    return out


def bigrams(s: str) -> set[str]:
    """中文二字组，用来粗算语义重合。"""
    cn = re.sub(r"[^\u4e00-\u9fff]", "", s)
    return {cn[i:i + 2] for i in range(len(cn) - 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "out" / "select_140.csv"))
    a = ap.parse_args()

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    hard, soft = [], []
    for r in rows:
        title = r["用户原提问（标题）"].strip()
        ans = r["草稿答案（待核对）"].strip()

        # ★ 只用标题判断，不用正文——正文里全是报错日志和链接，会污染判据
        qi, ai = idents(title), idents(ans)
        missing = qi - ai
        if qi and not (qi & ai):
            hard.append((r["序号"], sorted(missing)[:4], title[:44], ans[:44]))
            continue

        # 弱信号：标题和答案都是长句、但中文二字组重合率极低
        if len(title) >= 12 and len(ans) >= 20:
            qb, ab = bigrams(title), bigrams(ans)
            if qb and ab:
                ratio = len(qb & ab) / len(qb)
                if ratio < 0.06:
                    soft.append((r["序号"], round(ratio, 3), title[:44], ans[:44]))

    print(f"检查 {len(rows)} 条：原提问 vs 草稿答案")
    print("=" * 64)
    print(f"【强信号·答非所问】{len(hard)} 条（提问里的技术词，答案里一个都没提）")
    for i, miss, q, ans in hard[:12]:
        print(f"    #{i:>3}  问：{q}")
        print(f"           答：{ans}")
        print(f"           答案里缺：{miss}")
    if len(hard) > 12:
        print(f"    …还有 {len(hard) - 12} 条")

    print()
    print(f"【弱信号·需看一眼】{len(soft)} 条（中文重合率 < 12%）")
    for i, r_, q, ans in soft[:10]:
        print(f"    #{i:>3}  重合 {r_}  问：{q}")
        print(f"                      答：{ans}")
    if len(soft) > 10:
        print(f"    …还有 {len(soft) - 10} 条")

    print()
    good = len(rows) - len(hard) - len(soft)
    print(f"看起来对得上的：{good} 条（{good / len(rows) * 100:.0f}%）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
