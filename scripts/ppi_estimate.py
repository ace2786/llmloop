#!/usr/bin/env python3
"""读抽样校验结果，算通过率和 Wilson 95% 置信区间，外推题库可用量。

方法参照 ARES 的 PPI 思路：人工只标注少量样本，用统计区间外推到全体，
而不是假装「每一道都人工看过」。

为什么用 Wilson 而不是正态近似：
  样本量小（30 条）、通过率可能接近 1，正态近似会给出超过 100% 的荒谬上界。
  Wilson 区间在小样本和极端比例下都稳定。

用法：
    python scripts/ppi_estimate.py
"""
from __future__ import annotations

import math
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

OK = {"t", "对", "✓", "√", "1", "true", "y"}
NO = {"f", "错", "✗", "×", "x", "0", "false", "n"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval。"""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, center - half), min(1.0, center + half)


def main() -> int:
    p = Path("/mnt/d/llmloop/抽样校验.xlsx")
    if not p.exists():
        p = ROOT / "out" / "抽样校验.xlsx"
    if not p.exists():
        print("找不到抽样校验表")
        return 1

    ws = load_workbook(p, data_only=True).active
    head = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

    def col(name: str) -> int:
        for c, h in enumerate(head, 1):
            if h and name in str(h):
                return c
        return 0

    c_v, c_src = col("判定"), col("来源")
    rows = []
    for r in range(2, ws.max_row + 1):
        v = str(ws.cell(row=r, column=c_v).value or "").strip().lower()
        src = str(ws.cell(row=r, column=c_src).value or "")
        if not src:
            continue
        rows.append({"v": v, "src": "doc" if "合成" in src else "real"})

    def tally(sub: list[dict]) -> tuple[int, int, int]:
        ok = sum(1 for r in sub if r["v"] in OK)
        no = sum(1 for r in sub if r["v"] in NO)
        unk = len(sub) - ok - no
        return ok, no, unk

    print(f"抽样 {len(rows)} 条\n")
    for name, key in [("全体", None), ("合成题", "doc"), ("真实提问", "real")]:
        sub = rows if key is None else [r for r in rows if r["src"] == key]
        ok, no, unk = tally(sub)
        n = ok + no  # 未填的不算进分母
        if n == 0:
            print(f"{name}: 还没填")
            continue
        lo, hi = wilson(ok, n)
        print(f"{name}：{ok}/{n} 通过 = {ok/n:.1%}　（95% CI: {lo:.1%} – {hi:.1%}）"
              + (f"　未填 {unk} 条" if unk else ""))

    print()
    ok, no, unk = tally(rows)
    n = ok + no
    if n == 0:
        return 0
    lo, hi = wilson(ok, n)

    # 外推题库
    import json
    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    ndoc = sum(1 for q in qs if q.get("source") == "doc-synth")
    nreal = len(qs) - ndoc

    sub_doc = [r for r in rows if r["src"] == "doc"]
    sub_real = [r for r in rows if r["src"] == "real"]
    kd, nd = tally(sub_doc)[0], sum(tally(sub_doc)[:2])
    kr, nr = tally(sub_real)[0], sum(tally(sub_real)[:2])

    print("=== 外推到题库（用点估计）===")
    if nd:
        print(f"  合成题 {ndoc} 道 × {kd/nd:.1%} ≈ {round(ndoc*kd/nd)} 道可用")
    if nr:
        print(f"  真实提问 {nreal} 道 × {kr/nr:.1%} ≈ {round(nreal*kr/nr)} 道可用")
    est = (ndoc * (kd / nd if nd else 1)) + (nreal * (kr / nr if nr else 1))
    print(f"  合计估计可用约 {round(est)} 道（当前 {len(qs)} 道）")

    print()
    print("=== 写进报告的说法 ===")
    print(f"「抽样 {n} 道人工校验，通过 {ok} 道，估计整体通过率 {ok/n:.1%}"
          f"（95% CI {lo:.1%}–{hi:.1%}）。」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
