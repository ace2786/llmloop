#!/usr/bin/env python3
"""统计 CSV 记录数（CSV 里回答含换行，不能用 wc -l）。

用法：
    python scripts/count_csv.py out/week1_optimize_v0.csv
    python scripts/count_csv.py out/to_grade.csv --graded
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--graded", action="store_true", help="只数已判分的")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print("0")
        return 0

    with p.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if args.graded:
        n = sum(1 for r in rows if (r.get("人工判分") or "").strip())
        print(f"{n}/{len(rows)}")
    else:
        print(len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
