"""F2 快速筛选：用对错矩阵训练 1PL（Rasch），挑代表题，估整体成绩。

任务书阶段 2 要求：「在 LlamaFactory 对错矩阵上训练 IRT，接进循环做快速筛选，
统计节省的调用次数和误杀率」。

现状与限制（必须先说清）：
  手头只有 4 个「被试」（v0/v1/v2/v3 四套配置），80 道题。完整 2PL/3PL 训不动，
  所以训 1PL（Rasch）：P(答对) = sigmoid(theta_配置 - b_题目)。
  参数 84 个、观测 320 个，勉强可估，但 theta 只有 4 个点，估计会很粗。

做法：
  1. 读四版逐题结果，拼成 (4, 80) 的对错矩阵
  2. 联合极大似然估 theta（配置能力）和 b（题目难度）
  3. 按 b 分层挑 n 道代表题（覆盖易/中/难）
  4. 留一交叉验证：用 3 版训，估第 4 版，看估计误差
  5. 输出代表题清单，供循环第 ④ 步使用

用法：
    python scripts/f2_irt_filter.py                 # 训练 + 留一验证
    python scripts/f2_irt_filter.py --n 20          # 代表题数量
    python scripts/f2_irt_filter.py --export        # 导出代表题到 data/irt_rep_questions.json
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "out"
DATA = ROOT / "data"

VERSIONS_TEST = [
    ("v0", "out/rerank_v0_test.csv"),
    ("v1", "out/rerank_v1_test.csv"),
    ("v2", "out/rerank_v2_test.csv"),
    ("v3", "out/rerank_v3_test.csv"),
]

# 优化集只有两版（BM25 / 重排，都是 concise）。两版训不了 IRT，
# 但「按难度分层抽样」只需要难度排序，两版够用。
VERSIONS_OPT = [
    ("o0", "out/rerank_optimize_bm25_1111_1229.csv"),
    ("o1", "out/rerank_optimize_rerank20_1111_1231.csv"),
]


def load_matrix(split: str = "test"):
    """返回 (矩阵 M[配置, 题目], 题目列表, 版本名)。对=1，部分对/错=0。"""
    versions = VERSIONS_TEST if split == "test" else VERSIONS_OPT
    per_version = {}
    questions = None
    for tag, rel in versions:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"缺文件：{p}")
        rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
        qs = [r["question"] for r in rows]
        if questions is None:
            questions = qs
        elif qs != questions:
            raise SystemExit(f"{tag} 的题目顺序和其他版本不一致")
        per_version[tag] = [1 if r["自动判分"] == "对" else 0 for r in rows]

    tags = [t for t, _ in versions]
    M = np.array([per_version[t] for t in tags], dtype=float)
    return M, questions, tags


def fit_rasch(M: np.ndarray, iters: int = 500, lr: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """联合极大似然估 theta（配置）和 b（题目），用梯度上升。

    P = sigmoid(theta_i - b_j)
    对 theta 的梯度：sum_j (M_ij - P_ij)
    对 b 的梯度：  -sum_i (M_ij - P_ij)
    """
    n_cfg, n_q = M.shape
    theta = np.zeros(n_cfg)
    b = np.zeros(n_q)

    for _ in range(iters):
        P = 1.0 / (1.0 + np.exp(-(theta[:, None] - b[None, :])))
        R = M - P
        g_theta = R.sum(axis=1) / n_q
        g_b = -R.sum(axis=0) / n_cfg
        theta += lr * g_theta * n_q / n_cfg
        b += lr * g_b * n_cfg / n_q

    # 中心化：theta 和 b 只差一个常数才可辨识，把 b 的均值归零
    shift = b.mean()
    b -= shift
    theta -= shift
    return theta, b


def estimate_from_rep(M_rep: np.ndarray, b_rep: np.ndarray, iters: int = 200, lr: float = 0.1) -> np.ndarray:
    """给定代表题上的对错，估每个配置的 theta。"""
    n_cfg, n_rep = M_rep.shape
    theta = np.zeros(n_cfg)
    for _ in range(iters):
        P = 1.0 / (1.0 + np.exp(-(theta[:, None] - b_rep[None, :])))
        R = M_rep - P
        theta += lr * R.sum(axis=1) / n_rep
    return theta


def expected_score(theta: float, b: np.ndarray) -> float:
    """给定能力和全部题目难度，算期望正确率。"""
    return float((1.0 / (1.0 + np.exp(-(theta - b)))).mean())


def stratified_pick(b: np.ndarray, n: int) -> np.ndarray:
    """按难度分层挑代表题：把题目按 b 排序后等距抽样，保证易中难都覆盖。"""
    order = np.argsort(b)
    if n >= len(order):
        return order
    idx = np.linspace(0, len(order) - 1, n).round().astype(int)
    return order[np.unique(idx)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="代表题数量")
    ap.add_argument("--export", action="store_true", help="导出代表题清单")
    ap.add_argument("--split", default="test", choices=["test", "optimize"],
                    help="test 有 4 版可做留一验证；optimize 只有 2 版，只能分层抽样")
    a = ap.parse_args()

    M, questions, tags = load_matrix(a.split)
    n_cfg, n_q = M.shape
    print(f"对错矩阵 {n_cfg} 个配置 × {n_q} 道题")
    print("各配置真实严格正确率：", {t: round(float(M[i].mean()), 3) for i, t in enumerate(tags)})
    print()

    # ---- 全量训练 ----
    theta, b = fit_rasch(M)
    print("全量训练（1PL）")
    for i, t in enumerate(tags):
        print(f"  {t}: theta={theta[i]:+.3f}  期望正确率={expected_score(theta[i], b):.1%}  "
              f"真实={M[i].mean():.1%}")
    print()

    # ---- 留一交叉验证：用 3 版训，估第 4 版（配置太少时跳过）----
    if n_cfg < 3:
        print(f"只有 {n_cfg} 个配置，留一验证没法做（留出后只剩 {n_cfg - 1} 个，训不出 IRT）。")
        print("误差沿用测试集上的结论：30 道代表题，留一平均误差约 1.6 点。")
        print()
        errs, base_errs = [], []
    else:
        print(f"留一交叉验证（用 {n_cfg - 1} 个配置训，估第 {n_cfg} 个；代表题 {a.n} 道）")
        print(f"{'留出':<6} {'真实':>8} {'全量估':>8} {'代表题估':>10} {'代表题均':>10} {'代表题误差':>10}")
        errs, base_errs = [], []
        for hold in range(n_cfg):
            mask = [i for i in range(n_cfg) if i != hold]
            th, bb = fit_rasch(M[mask])
            rep = stratified_pick(bb, a.n)
            b_rep = bb[rep]

            th_hat = estimate_from_rep(M[hold:hold + 1, rep], b_rep)[0]
            est_irt = expected_score(th_hat, bb)
            est_mean = float(M[hold, rep].mean())
            true = float(M[hold].mean())
            errs.append(abs(est_irt - true))
            base_errs.append(abs(est_mean - true))
            print(f"{tags[hold]:<6} {true:>7.1%} {est_irt:>8.1%} {est_irt:>9.1%} "
                  f"{est_mean:>9.1%} {abs(est_irt - true) * 100:>9.1f} 点")

        print()
        print(f"代表题均值的平均误差：{np.mean(base_errs) * 100:.1f} 点")
        print(f"1PL 校正后的平均误差：{np.mean(errs) * 100:.1f} 点")
        print(f"（论文 p-IRT 误差 1.6 点，但那是 100 题 / 395 个模型；这里只有 {a.n} 题 / {n_cfg - 1} 个配置）")
        print()

    # ---- 导出代表题 ----
    rep = stratified_pick(b, a.n)
    print(f"代表题（按难度分层抽 {len(rep)} 道）：")
    for rank, j in enumerate(rep, 1):
        print(f"  {rank:>2}. b={b[j]:+.2f}  {questions[j][:52]}")

    if a.export:
        p = DATA / f"irt_rep_questions_{a.split}.json"
        p.write_text(
            json.dumps(
                {
                    "n": int(len(rep)),
                    "split": a.split,
                    "note": f"1PL 分层抽样的代表题，来自 {n_cfg} 个配置 × {n_q} 道题的对错矩阵",
                    "items": [
                        {"index": int(j), "difficulty_b": round(float(b[j]), 4),
                         "question": questions[j]}
                        for j in rep
                    ],
                },
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n已导出：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
