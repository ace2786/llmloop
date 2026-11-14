"""离线模拟 F2 快速筛选：不同淘汰余量下，能拦下多少、误杀多少。

为什么不用跑真实循环：
  跑 10 轮真实实验要 100 分钟，而且模型会反复提同样的改动，样本并不独立。
  现有 4 版 × 69 道的对错矩阵是「全量真值」，可以直接拿来做对照——
  对每一对（当前最佳, 候选），算「30 道代表题估分」和「全量真实成绩」的差，
  就能知道某个余量下会拦下谁、误杀谁。

另外做 bootstrap：对每个配置反复随机抽 30 道，看估分的分布有多宽。

用法：
    python scripts/f2_screen_sim.py
    python scripts/f2_screen_sim.py --boot 500
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.f2_irt_filter import VERSIONS_OPT, load_matrix  # noqa: E402

DATA = ROOT / "data"


def load_rep_idx(questions: list[str]) -> np.ndarray:
    """把导出的代表题文本映射回矩阵的列下标。"""
    p = DATA / "irt_rep_questions_optimize.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    want = {x["question"] for x in d["items"]}
    idx = [i for i, q in enumerate(questions) if q in want]
    if len(idx) != len(want):
        raise SystemExit(f"代表题对不上：导出 {len(want)} 道，匹配到 {len(idx)} 道")
    return np.array(idx)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=300, help="bootstrap 次数")
    ap.add_argument("--margins", default="0.01,0.02,0.03,0.05",
                    help="要扫的淘汰余量（点，逗号分隔）")
    a = ap.parse_args()

    M, questions, tags = load_matrix("optimize")
    n_cfg, n_q = M.shape
    rep = load_rep_idx(questions)
    n_rep = len(rep)

    rates = M.mean(axis=1)
    print(f"矩阵 {n_cfg} 版 × {n_q} 道，代表题 {n_rep} 道")
    for i, t in enumerate(tags):
        print(f"  {t}: 全量 {rates[i]:.1%}")
    print()

    # ---------- 1. bootstrap：同一配置反复抽 30 道，估分有多飘 ----------
    print(f"① 估分稳定性（每版随机抽 {n_rep} 道，重复 {a.boot} 次）")
    print(f"{'版本':<6} {'全量真值':>9} {'估分均值':>9} {'偏差':>8} {'标准差':>8} {'95% 区间':>16}")
    rng = np.random.default_rng(42)
    for i, t in enumerate(tags):
        est = []
        for _ in range(a.boot):
            sub = rng.choice(n_q, size=n_rep, replace=False)
            est.append(M[i, sub].mean())
        est = np.array(est)
        lo, hi = np.percentile(est, [2.5, 97.5])
        print(f"{t:<6} {rates[i]:>8.1%} {est.mean():>9.1%} "
              f"{(est.mean() - rates[i]) * 100:>+7.1f} {est.std() * 100:>7.1f} "
              f"{lo:.0%}–{hi:.0%}")
    print()

    # ---------- 2. 固定代表题：两两配对，看不同余量拦谁 ----------
    print(f"② 固定代表题（导出的那 {n_rep} 道）下，不同淘汰余量的拦下 / 误杀")
    est_rep = M[:, rep].mean(axis=1)
    print(f"{'版本':<6} {'全量':>7} {'代表题估分':>10} {'偏差':>7}")
    for i, t in enumerate(tags):
        print(f"{t:<6} {rates[i]:>6.1%} {est_rep[i]:>9.1%} {(est_rep[i] - rates[i]) * 100:>+6.1f}")
    print()

    margins = [float(x) for x in a.margins.split(",")]
    print(f"{'余量':<6} {'拦下':>6} {'其中该拦':>9} {'误杀':>6} {'该拦没拦':>9} {'净省调用':>9}")
    for m in margins:
        killed = correct_kill = false_kill = missed = 0
        saved = 0
        for base in range(n_cfg):
            for cand in range(n_cfg):
                if base == cand:
                    continue
                true_delta = rates[cand] - rates[base]
                est_delta = est_rep[cand] - est_rep[base]
                should_kill = true_delta < 0  # 全量确实更差，该拦
                did_kill = est_delta < -m
                if did_kill:
                    killed += 1
                    saved += n_q - n_rep
                    if should_kill:
                        correct_kill += 1
                    else:
                        false_kill += 1
                else:
                    saved -= n_rep
                    if should_kill:
                        missed += 1
        print(f"{m:.0%}    {killed:>6} {correct_kill:>9} {false_kill:>6} "
              f"{missed:>9} {saved:>+9}")
    print()
    print("说明：净省调用 = 拦下 × (全量-代表题) - 放行 × 代表题。")
    print("      余量越小拦得越多，但误杀也越多；余量 0 等于「只要估分不涨就拦」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
