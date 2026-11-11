#!/usr/bin/env python3
"""重新切分：让**最终测试集**里真实提问占到指定比例。

为什么和原来不同：
  原来的 resplit.py 按来源分层，三份里真实/合成的比例和题库一致（约 39%）。
  但老师的要求是「**测评里**提高真实提问的比例」——测评指的就是最终测试集。
  所以这里对测试集单独指定真实题数量，优化集和验证集用剩下的按 1:1 分。

用法：
    python scripts/resplit_v2.py                          # 只看结果（测试集 80 道，真实 40 道）
    python scripts/resplit_v2.py --write                  # 写回 questions.json
    python scripts/resplit_v2.py --test-n 80 --test-real 48
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def is_real(q: dict) -> bool:
    return q.get("source", "").startswith("real")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-n", type=int, default=80)
    ap.add_argument("--test-real", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261111)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    real = [q for q in qs if is_real(q)]
    synth = [q for q in qs if not is_real(q)]
    print(f"题库 {len(qs)} 道：真实 {len(real)} / 合成 {len(synth)}")

    if a.test_real > len(real):
        print(f"!! 真实题只有 {len(real)} 道，不够 {a.test_real} 道")
        return 1
    if a.test_n - a.test_real > len(synth):
        print(f"!! 合成题只有 {len(synth)} 道，不够 {a.test_n - a.test_real} 道")
        return 1

    rng = random.Random(a.seed)
    rng.shuffle(real)
    rng.shuffle(synth)

    # 测试集：真实 a.test_real 道 + 合成 (test_n - test_real) 道
    test = real[: a.test_real] + synth[: a.test_n - a.test_real]
    rest_real = real[a.test_real:]
    rest_synth = synth[a.test_n - a.test_real:]

    # 剩下按 1:1 分优化 / 验证，各自内部再按真实/合成比例分
    n_opt_real = round(len(rest_real) / 2)
    n_opt_synth = round(len(rest_synth) / 2)
    opt = rest_real[:n_opt_real] + rest_synth[:n_opt_synth]
    val = rest_real[n_opt_real:] + rest_synth[n_opt_synth:]

    for name, group in (("optimize", opt), ("valid", val), ("test", test)):
        for q in group:
            q["split"] = name

    rng.shuffle(test)
    rng.shuffle(opt)
    rng.shuffle(val)

    print()
    print(f"{'':10}{'总':>5}{'真实':>6}{'合成':>6}{'真实占比':>10}")
    for name, group in (("优化集", opt), ("验证集", val), ("测试集", test)):
        r = sum(1 for q in group if is_real(q))
        print(f"{name:10}{len(group):>5}{r:>6}{len(group)-r:>6}{r/len(group):>10.1%}")
    print(f"{'合计':10}{len(opt)+len(val)+len(test):>5}"
          f"{len(real):>6}{len(synth):>6}{len(real)/len(qs):>10.1%}")

    if not a.write:
        print()
        print("（没写回。确认后加 --write）")
        return 0

    DATA.joinpath("questions.json").write_text(
        json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print("已写回 data/questions.json")
    print("下一步：python scripts/sync_bank_to_db.py --app 11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
