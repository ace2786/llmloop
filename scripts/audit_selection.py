#!/usr/bin/env python3
"""审计 select_140.csv：找出「选题本身有问题」的条目。

为什么需要：140 条是从 188 条候选里自动挑的，草稿答案是 AI 生成的，
它会自信地编。人工核对 140 条之前，先用机器把明显的坑标出来，
人只需要重点看被标红的，不用平均用力。

检查项：
  1. 实体缺失  —— 草稿答案里的参数名/数字/模型名，原文里找不到 → 答案缺依据
  2. 原文过短  —— quote 少于 25 字，撑不起一道题
  3. 答案过短  —— 答案少于 8 字，等于没说
  4. issue 重复 —— 同一个 issue 被选了多条，可能出成高度相似的题
  5. 答案重复  —— 两条答案一模一样
  6. 段落超限  —— 同一段落超过 3 条
  7. 原文像目录 —— quote 里几乎没有实质内容（纯标题、纯符号）

用法：
    python scripts/audit_selection.py
    python scripts/audit_selection.py --csv out/select_140.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 反引号里的标识符（参数名、命令、文件名）
BACKTICK = re.compile(r"`([^`]{1,40})`")
# 英文标识符：下划线或驼峰，至少 3 个字符
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b")
# 数字（含小数、版本号）
NUM = re.compile(r"\b\d+(?:\.\d+)*\b")


def norm(s: str) -> str:
    return (s or "").lower()


def hard_entities(answer: str) -> list[str]:
    """从答案里抽「必须在原文出现」的硬实体。"""
    out: list[str] = []
    out += [m.strip() for m in BACKTICK.findall(answer) if m.strip()]
    # 下划线标识符（参数名、字段名）最可靠
    out += [w for w in IDENT.findall(answer) if "_" in w]
    # 版本号式数字
    out += [n for n in NUM.findall(answer) if "." in n]
    # 去重保序
    seen, uniq = set(), []
    for e in out:
        k = norm(e)
        if k and k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def looks_like_toc(quote: str) -> bool:
    """原文像目录/导航。

    注意：不能简单用「英文多」判断——YAML 配置片段（如 `report_to: none # choices: [...]`）
    几乎全是英文，但它恰恰是这类题最好的证据。真正的目录特征是：
    大量 markdown 链接，或者一堆短行且没有任何赋值符号。
    """
    q = quote.strip()
    if not q:
        return False
    # 3 个以上 markdown 链接 → 多半是目录
    if len(re.findall(r"\[[^\]]*\]\([^)]*\)", q)) >= 3:
        return True
    lines = [ln.strip() for ln in q.splitlines() if ln.strip()]
    if len(lines) >= 5 and all(len(ln) < 25 for ln in lines):
        if ":" not in q and "|" not in q and "=" not in q:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "out" / "select_140.csv"))
    a = ap.parse_args()

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    issues = Counter(r["issue"] for r in rows)
    answers = Counter(r["草稿答案（待核对）"].strip() for r in rows)
    segs = Counter(r["出处（文件#块号）"] for r in rows)

    flags: dict[str, list[dict]] = defaultdict(list)

    for r in rows:
        ans = r["草稿答案（待核对）"].strip()
        quote = r["文档原文"].strip()
        nq = norm(quote)

        # 1a. 原文无效（空 / None / 极短）—— 直接砍
        if len(quote) < 6 or nq in ("none", "null", "-", "无", "n/a"):
            flags["原文无效·必砍"].append({**r, "_note": f"原文只有 {len(quote)} 字：{quote!r}"})
            continue

        # 1b. 实体缺失 —— 答案里有、原文里没有
        ents = hard_entities(ans)
        missing = [e for e in ents if norm(e) not in nq]
        if ents and missing:
            flags["答案超出原文·要改或砍"].append(
                {**r, "_note": "这些在原文找不到：" + "、".join(missing[:4])}
            )

        # 1c. 原文偏短但含赋值（key: value / 表格行）—— 通常可用，仅提示
        if 6 <= len(quote) < 25:
            if any(ch in quote for ch in ":|=|"):
                flags["原文偏短·多半可用"].append({**r, "_note": f"原文 {len(quote)} 字，但是完整配置项"})
            else:
                flags["原文偏短·需确认"].append({**r, "_note": f"原文 {len(quote)} 字且不含赋值：{quote[:30]!r}"})

        # 2. 答案过短
        if len(ans) < 8:
            flags["答案过短"].append({**r, "_note": f"答案仅 {len(ans)} 字"})

        # 3. 原文像目录
        if looks_like_toc(quote):
            flags["原文像目录"].append({**r, "_note": "原文像链接列表或目录，出题价值低"})

    for i, c in issues.items():
        if c > 1:
            flags["issue 重复"].append(
                {"序号": "-", "issue": i, "_note": f"同一个 issue 选了 {c} 条"}
            )
    for t, c in answers.items():
        if c > 1 and t:
            flags["答案重复"].append({"序号": "-", "issue": "-", "_note": f"重复 {c} 次：{t[:40]}"})
    for s, c in segs.items():
        if c > 3:
            flags["段落超限"].append({"序号": "-", "issue": "-", "_note": f"{s} 选了 {c} 条"})

    # ---- 输出 ----
    print(f"审计 {len(rows)} 条")
    print("=" * 60)
    if not flags:
        print("✓ 没发现问题")
        return 0

    total_flagged = len({r.get("序号") for lst in flags.values() for r in lst if r.get("序号") != "-"})
    print(f"⚠ 命中 {sum(len(v) for v in flags.values())} 处问题，涉及 {total_flagged} 条（去重后）")
    print()
    for kind, lst in sorted(flags.items(), key=lambda x: -len(x[1])):
        print(f"【{kind}】{len(lst)} 处")
        for r in lst[:8]:
            if r.get("序号") == "-":
                print(f"    · {r['_note']}")
            else:
                print(f"    #{r['序号']:>3}  {r['_note']}")
                print(f"          答案：{r['草稿答案（待核对）'][:60]}")
        if len(lst) > 8:
            print(f"    …还有 {len(lst) - 8} 处")
        print()

    # 建议直接砍的：多个问题同时命中
    bad = Counter()
    for lst in flags.values():
        for r in lst:
            if r.get("序号") != "-":
                bad[r["序号"]] += 1
    worst = [(k, v) for k, v in bad.most_common() if v >= 2]
    if worst:
        print("建议优先砍掉（命中 2 项以上）：")
        for k, v in worst:
            row = next(x for x in rows if x["序号"] == k)
            print(f"    #{k}  命中 {v} 项  {row['草稿答案（待核对）'][:50]}")

    # 写一份清单，方便照着处理
    out = ROOT / "out" / "audit_flagged.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "问题类型", "说明", "草稿答案", "文档原文"])
        for kind, lst in flags.items():
            for r in lst:
                if r.get("序号") == "-":
                    continue
                w.writerow([r["序号"], kind, r["_note"],
                            r["草稿答案（待核对）"][:120], r["文档原文"][:120]])
    print()
    print(f"问题清单已写出：{out.relative_to(ROOT)}")
    print("（按「必砍 → 要改 → 可接受」的顺序处理，可接受的直接放过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
