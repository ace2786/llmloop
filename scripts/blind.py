#!/usr/bin/env python3
"""盲判工具：把多版本的回答打乱、遮掉版本和模型，只留代号。

为什么要盲判（RUBRIC 第三节）：
  知道哪条是「改过之后」的，判分就会不自觉宽容。
  第 1 周测试集只有 30 道题，一个 10% 提升 = 3 道题，任何偏袒都会让结论失效。

两个子命令：

  python scripts/blind.py make [--split test]
      读 out/week1_*.csv → 生成 out/to_grade.csv（遮版本模型、打乱顺序）
      + out/blind_map.json（代号 → 真实版本/模型，判完再解开）

  python scripts/blind.py merge
      读 out/to_grade.csv（你填完判分）→ 按 blind_map.json 写回原 CSV

判分只填三列：人工判分 / 失败原因 / 判断理由。其余列不要动。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

SEED = 20261020  # 固定种子，打乱可复现
BLIND_COLS = [
    "代号",
    "题号",
    "问题",
    "回答",
    "检索到的段落",
    "人工判分",
    "失败原因",
    "判断理由",
]
GRADE_COLS = ["人工判分", "失败原因", "判断理由"]


def load_all(split: str, version: str = "") -> dict[str, list[dict]]:
    """返回 {源文件路径: 行列表}"""
    files = sorted(glob.glob(str(OUT / "week1_*.csv")))
    if version:
        files = [f for f in files if f"_{version}." in f]
        print(f"  只读版本 {version}: {len(files)} 个文件")
    if not files:
        raise SystemExit("out/ 下没有 week1_*.csv，先跑 week1.py")

    result = {}
    for p in files:
        with open(p, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        s = (rows[0].get("所属份") or "").strip()
        if split == "test" and s != "测试用":
            continue
        if split == "optimize" and s != "优化用":
            continue
        result[p] = rows
    if not result:
        raise SystemExit(f"没有匹配 --split {split} 的数据")
    return result


def cmd_make(args) -> int:
    sources = load_all(args.split, args.version)

    flat = []
    for path, rows in sources.items():
        for idx, r in enumerate(rows):
            flat.append({"src": path, "idx": idx, "row": r})

    rng = random.Random(SEED)
    rng.shuffle(flat)

    # 生成代号：字母 + 序号，不含版本信息
    codes = []
    for i, item in enumerate(flat):
        code = f"Q{i + 1:03d}"
        codes.append(code)

    mapping = {}
    out_rows = []
    for code, item in zip(codes, flat):
        r = item["row"]
        mapping[code] = {
            "src": item["src"],
            "idx": item["idx"],
            "版本": r.get("版本"),
            "模型": r.get("模型"),
            "题号": r.get("题号"),
        }
        out_rows.append(
            {
                "代号": code,
                "题号": r.get("题号"),
                "问题": r.get("问题"),
                "回答": r.get("回答"),
                "检索到的段落": r.get("检索到的段落"),
                "人工判分": "",
                "失败原因": "",
                "判断理由": "",
            }
        )

    OUT.mkdir(exist_ok=True)
    to_grade = OUT / "to_grade.csv"
    with open(to_grade, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=BLIND_COLS)
        w.writeheader()
        w.writerows(out_rows)

    map_path = OUT / "blind_map.json"
    map_path.write_text(
        json.dumps({"seed": SEED, "split": args.split, "map": mapping},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print("=" * 58)
    print("盲判表已生成")
    print("=" * 58)
    print(f"  来源文件 : {len(sources)} 个")
    print(f"  总行数   : {len(out_rows)}")
    print(f"  打乱种子 : {SEED}（可复现）")
    print(f"  判分表   : {to_grade}")
    print(f"  对照表   : {map_path}  ← 判完之前别看")
    print()
    print("判分时只填三列：人工判分 / 失败原因 / 判断理由")
    print("  人工判分可选：对 / 部分对 / 错")
    print("  失败原因可选：检索没命中 / 编造内容 / 理解错 / 格式错")
    print()
    print("★ 判分期间不要打开 out/week1_*.csv，也不要看 blind_map.json")
    return 0


def cmd_merge(args) -> int:
    to_grade = OUT / "to_grade.csv"
    map_path = OUT / "blind_map.json"
    if not to_grade.exists() or not map_path.exists():
        raise SystemExit("找不到 to_grade.csv 或 blind_map.json，先跑 blind.py make")

    meta = json.loads(map_path.read_text(encoding="utf-8"))
    mapping = meta["map"]

    with open(to_grade, encoding="utf-8-sig") as f:
        graded = list(csv.DictReader(f))

    # 按源文件分组回填
    by_src: dict[str, dict[int, dict]] = {}
    graded_n = 0
    for g in graded:
        code = g["代号"]
        info = mapping.get(code)
        if not info:
            print(f"⚠ 代号 {code} 不在对照表里，跳过")
            continue
        marks = {k: (g.get(k) or "").strip() for k in GRADE_COLS}
        if not marks["人工判分"]:
            continue
        graded_n += 1
        by_src.setdefault(info["src"], {})[info["idx"]] = marks

    if graded_n == 0:
        raise SystemExit("to_grade.csv 里还没有任何判分（人工判分列全空）")

    print(f"已判分 {graded_n} / {len(graded)} 条")
    print()

    for src, idx_marks in by_src.items():
        p = Path(src)
        with open(p, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            fieldnames = list(rows[0].keys()) if rows else []

        for idx, marks in idx_marks.items():
            if 0 <= idx < len(rows):
                for k in GRADE_COLS:
                    rows[idx][k] = marks[k]

        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"  ✓ 回填 {p.name}：{len(idx_marks)} 条")

    print()
    print("解开盲判完成。现在可以跑：")
    print("  python scripts/report.py --split test")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="盲判工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("make", help="生成盲判表")
    p1.add_argument("--split", default="test", choices=["test", "optimize", "all"])
    p1.add_argument("--version", default="", help="只处理某个版本，如 v1")
    p1.set_defaults(func=cmd_make)

    p2 = sub.add_parser("merge", help="把判分结果回填到原 CSV")
    p2.set_defaults(func=cmd_merge)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
