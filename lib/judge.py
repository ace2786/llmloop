"""判分逻辑：脚本和接口共用同一份。

为什么要单独抽出来：
  `scripts/run_eval.py` 和未来的评测接口（`POST /apps/{id}/eval`）必须用同一套判分。
  写两套 = 两套结论 = 项目废掉。

判分规则（不要改，改了等于改尺子）：
  1. 从标准答案里抽「硬实体」：反引号内容 + 含下划线的标识符 + 带小数点的数字
  2. 硬实体在模型回答里出现的比例 ≥ 100% → 对；≥ 40% → 部分对；否则 → 错
  3. 标准答案没有硬实体时，退化成中文二元组重合率：≥ 60% → 对；≥ 30% → 部分对；否则 → 错
"""
from __future__ import annotations

import re

BACKTICK = re.compile(r"`([^`]{1,40})`")
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b")
NUM = re.compile(r"\b\d+(?:\.\d+)*\b")

# 阈值（改动要记录理由）
HIT_ALL = 0.999      # 硬实体全中才算「对」
HIT_PARTIAL = 0.4    # 硬实体命中 40% 以上算「部分对」
CN_ALL = 0.6         # 中文重合 60% 以上算「对」
CN_PARTIAL = 0.3     # 中文重合 30% 以上算「部分对」


def hard_entities(s: str) -> list[str]:
    """抽标准答案里的硬实体：反引号内容、含下划线的标识符、带小数的数字。"""
    out = [m.strip() for m in BACKTICK.findall(s) if m.strip()]
    out += [w for w in IDENT.findall(s) if "_" in w]
    out += [n for n in NUM.findall(s) if "." in n]
    seen, uniq = set(), []
    for e in out:
        k = e.lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def judge(std: str, got: str) -> tuple[str, str]:
    """返回 (判定, 依据)。判定只作参考，人工可改。

    判定取值固定三个：对 / 部分对 / 错
    """
    if not got.strip():
        return "错", "模型没输出"

    ents = hard_entities(std)
    if not ents:
        # 没有硬实体，退化成中文关键词重合
        cn = re.sub(r"[^\u4e00-\u9fff]", "", std)
        grams = {cn[i:i + 2] for i in range(len(cn) - 1)}
        hit = sum(1 for g in grams if g in got)
        ratio = hit / len(grams) if grams else 0
        tag = "对" if ratio >= CN_ALL else ("部分对" if ratio >= CN_PARTIAL else "错")
        return tag, f"中文重合 {ratio:.0%}（{hit}/{len(grams)}）"

    hit = [e for e in ents if e.lower() in got.lower()]
    ratio = len(hit) / len(ents)
    tag = "对" if ratio >= HIT_ALL else ("部分对" if ratio >= HIT_PARTIAL else "错")
    return tag, f"实体命中 {len(hit)}/{len(ents)}：{'、'.join(hit[:4]) or '无'}"
