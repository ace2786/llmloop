#!/usr/bin/env python3
"""v3（查询改写）统计：正确率、与 v0/v1/v2 对比、配对检验，写进 out/report.md。

用法：
    python scripts/v3_report.py              # 只打印
    python scripts/v3_report.py --write      # 追加到 out/report.md

口径说明：
  A 口径 = 沿用第 1 周报告的剔除（优化集 {2,19,24}，测试集 {39,44,45,47,49,58}）
  B 口径 = A + 剔除题 55（标准答案有问题，见 v3 收尾说明）

四个版本一律用同一口径比较，否则数字不可比。
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# 第 1 周报告用的剔除（已反推验证：能精确复现 30/54 与 37/48）
EXCL_A = {
    "optimize": {"2", "19", "24"},
    "test": {"39", "44", "45", "47", "49", "58"},
}
# 本次新增：题 55（lora_target 问 MoE 场景，标准答案只给了通用表述）
EXCL_B_EXTRA = {"55"}

VERSIONS = ["v0", "v1", "v2", "v3"]
SPLITS = [("optimize", "优化集", "优化用"), ("test", "测试集", "测试用")]


def load(split_key: str, ver: str) -> list[dict]:
    p = OUT / f"week1_{split_key}_{ver}.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score(r: dict) -> str:
    return (r.get("人工判分") or "").strip()


def acc(rows: list[dict]) -> tuple[int, int]:
    """返回 (对, 已判总数)。空回答按「错」计。"""
    graded = [r for r in rows if score(r)]
    return sum(1 for r in graded if score(r) == "对"), len(graded)


def mcnemar(a: list[dict], b: list[dict]) -> tuple[int, int, float]:
    """配对精确二项检验（双侧），返回 (改善, 回归, p)。"""
    def key(r):
        return (r.get("题号"), r.get("模型"))
    ma = {key(r): score(r) for r in a if score(r)}
    mb = {key(r): score(r) for r in b if score(r)}
    up = down = 0
    for k, sa in ma.items():
        sb = mb.get(k)
        if sb is None:
            continue
        if sa != "对" and sb == "对":
            up += 1
        elif sa == "对" and sb != "对":
            down += 1
    n = up + down
    if n == 0:
        return up, down, 1.0
    k = min(up, down)
    p = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n) * 2
    return up, down, min(1.0, p)


def table(rows_by_split: dict, excl: dict, label: str) -> str:
    lines = [f"### {label}", "", "| 版本 | 优化集 | 测试集 |", "|---|---|---|"]
    for ver in VERSIONS:
        cells = []
        for skey, _, _ in SPLITS:
            rows = [r for r in rows_by_split[skey][ver] if r.get("题号") not in excl[skey]]
            c, n = acc(rows)
            cells.append(f"{c}/{n} = **{c / n:.1%}**" if n else "—")
        lines.append(f"| {ver} | {cells[0]} | {cells[1]} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="追加到 out/report.md")
    a = ap.parse_args()

    rows_by_split = {skey: {v: load(skey, v) for v in VERSIONS} for skey, _, _ in SPLITS}

    missing = [f"{sk}_{v}" for sk in rows_by_split for v in VERSIONS if not rows_by_split[sk][v]]
    if missing:
        print(f"⚠ 缺文件：{', '.join(missing)}（对应版本按缺失处理）")

    for skey, sname, _ in SPLITS:
        un = sum(1 for v in VERSIONS for r in rows_by_split[skey][v] if not score(r))
        print(f"{sname}：未判 {un} 条")

    excl_a = {k: set(v) for k, v in EXCL_A.items()}
    excl_b = {k: set(v) | EXCL_B_EXTRA for k, v in EXCL_A.items()}

    out = []
    out.append("## 十一、延伸实验 v3：查询改写")
    out.append("")
    out.append("> 不属于任务书要求，是在第 1 周闭环之外多做的一轮。")
    out.append("> 改动：检索前用 GLM 把问题改写成「含参数名 + 同义词」的形式，"
               "回答仍用原问题；保留 v1 的参数名加权 + top-k 6。")
    out.append("> 预期写在跑之前：`out/prediction_v3.md`。")
    out.append("")
    out.append(table(rows_by_split, excl_a, "口径 A：沿用第 1 周的剔除（与报告前文一致）"))
    out.append("")
    out.append(table(rows_by_split, excl_b, "口径 B：再剔除题 55（标准答案有争议）"))
    out.append("")

    for skey, sname, _ in SPLITS:
        for base in ("v0", "v1"):
            x = [r for r in rows_by_split[skey][base] if r.get("题号") not in excl_b[skey]]
            y = [r for r in rows_by_split[skey]["v3"] if r.get("题号") not in excl_b[skey]]
            c1, n1 = acc(x)
            c2, n2 = acc(y)
            if not n1 or not n2:
                continue
            up, down, p = mcnemar(x, y)
            out.append(f"- **{sname} v3 vs {base}**：{c1}/{n1} → {c2}/{n2}"
                       f"（{(c2 / n2 - c1 / n1) * 100:+.1f} 个百分点）；"
                       f"改善 {up} 条、回归 {down} 条，p = {p:.3f}"
                       + ("（显著）" if p < 0.05 else "（不显著）"))
    out.append("")

    for skey, sname, _ in SPLITS:
        rs = Counter(
            (r.get("失败原因") or "").strip()
            for r in rows_by_split[skey]["v3"]
            if score(r) in ("错", "部分对") and (r.get("失败原因") or "").strip()
        )
        if rs:
            out.append(f"**{sname} v3 失败原因**：" +
                       "、".join(f"{k} {v} 条" for k, v in rs.most_common()))
    out.append("")

    text = "\n".join(out)
    print(text)

    if a.write:
        rp = OUT / "report.md"
        old = rp.read_text(encoding="utf-8")
        if "延伸实验 v3" in old:
            print("\n⚠ report.md 里已有 v3 小节，请手动替换（不自动覆盖）", file=sys.stderr)
            return 1
        rp.write_text(old.rstrip() + "\n\n---\n\n" + text + "\n", encoding="utf-8")
        print(f"\n已追加到 {rp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
