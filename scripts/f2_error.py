#!/usr/bin/env python3
"""F2 复现：tinyBenchmarks 在 MMLU 上的估计误差（对照论文 2.4% / 1.6% / 1.6%）

★ 不需要跑模型、不需要联网、不需要 API key。
  数据全部来自官方源码包 `D:\\llmloop\\tb.zip`：
    tutorials/data/lb.pickle   395 个模型 × 14042 道 MMLU 题的逐题对错矩阵
    tinyBenchmarks.pkl         100 道代表题的定义 + IRT 参数

做法：
  1. 按 subscenarios_position 把 57 个科目拼成 14042×395 的对错矩阵
     → 每列就是一个模型的「真实全量成绩」（这就是之前误以为「缺」的那份数据）
  2. 只取 100 道代表题的成绩，喂给官方 tb.evaluate() 得到 IRT / p-IRT / gp-IRT 估计
  3. 误差 = |估计 − 真实|，对 395 个模型取平均与标准差
  4. 对照组：直接拿 100 道代表题算平均（不做 IRT 校正），看 IRT 到底帮了多少

用法：
    python scripts/f2_error.py             # 全量 395 个模型
    python scripts/f2_error.py --check     # 只做数据对齐校验
    python scripts/f2_error.py --limit 50  # 只跑前 50 个模型（调试用）
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
REFS = ROOT / "refs"
ZIP_PATH = Path("/mnt/d/llmloop/tb.zip")
PKG_DIR = Path("/tmp/tbpkg")

# 论文基线（Maia Polo et al., arXiv:2402.14992，MMLU）
PAPER = {"irt": (2.4, 1.7), "pirt": (1.6, 1.5), "gpirt": (1.6, 1.5)}
LABEL = {"irt": "IRT", "pirt": "p-IRT", "gpirt": "gp-IRT"}


def load_pkg():
    """从源码包里抽出 tinyBenchmarks 包，直接挂到 sys.path，不安装进环境。"""
    if not (PKG_DIR / "__init__.py").exists():
        PKG_DIR.mkdir(parents=True, exist_ok=True)
        z = zipfile.ZipFile(ZIP_PATH)
        for n in z.namelist():
            if n.startswith("felipemaiapolo-tinyBenchmarks-e9a8b10/tinyBenchmarks/") and n.endswith(".py"):
                (PKG_DIR / os.path.basename(n)).write_bytes(z.read(n))
    sys.path.insert(0, str(PKG_DIR.parent))
    import tbpkg  # noqa: E402

    return tbpkg


def build_matrix() -> tuple[np.ndarray, list[str], dict]:
    """拼出 (14042, 395) 的对错矩阵，行索引与 IRT 参数一致。"""
    with open(ROOT / "tinyBenchmarks.pkl", "rb") as f:
        tbk = pickle.load(f)["mmlu"]
    ssp = tbk["subscenarios_position"]["mmlu"]
    seen = tbk["seen_examples"]

    z = zipfile.ZipFile(ZIP_PATH)
    lb = pickle.loads(z.read("felipemaiapolo-tinyBenchmarks-e9a8b10/tutorials/data/lb.pickle"))
    models = lb["models"]

    n_items = sum(len(v) for v in ssp.values())
    M = np.full((n_items, len(models)), np.nan, dtype=np.float32)

    for sub, idx in ssp.items():
        corr = np.asarray(lb["data"][sub]["correctness"], dtype=np.float32)
        if corr.shape[0] != len(idx):
            raise SystemExit(f"科目 {sub} 题数对不上：数据 {corr.shape[0]} vs 索引 {len(idx)}")
        M[np.asarray(idx), :] = corr

    if np.isnan(M).any():
        raise SystemExit(f"矩阵有 {int(np.isnan(M).sum())} 个空洞，索引没对齐")

    return M, models, {"seen": list(seen), "tbk": tbk}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只做对齐校验")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    tb = load_pkg()
    M, models, meta = build_matrix()
    seen = meta["seen"]
    B = np.asarray(meta["tbk"]["irt_parameters"]["B"]).reshape(-1)

    print(f"对错矩阵：{M.shape[0]} 题 × {M.shape[1]} 个模型")
    print(f"整体正确率：{M.mean():.1%}（MMLU 全量，跨全部模型）")

    # 对齐校验：IRT 难度参数应与实测题目正确率负相关。
    # 阈值取 0.5 而非 0.8——B 只是 5 维 IRT 模型里的单维难度项，不会被 1 维难度完全解释。
    # 真正的决定性检验在下面：估计值与真实值的差（--check 会跑 6 个模型看）。
    item_acc = M.mean(axis=1)
    r = float(np.corrcoef(-B, item_acc)[0, 1])
    print(f"对齐校验：−B（难度）与实测正确率的相关系数 r = {r:+.3f}", end="  ")
    print("✓ 对齐正确" if r > 0.5 else "✗ 可能错位！")
    if r <= 0.5:
        print("  预期 r > 0.5（题目越难，答对率越低）。请先排查索引顺序。", file=sys.stderr)
        return 1

    if a.check:
        print("\n决定性检验：估计值应贴住真实值")
        print(f"{'模型':<34} {'真实':>7} {'100题均':>8} {'IRT':>7} {'p-IRT':>7} {'gp-IRT':>7}")
        for m in range(min(6, M.shape[1])):
            y = M[seen, m]
            e = tb.evaluate(y, "mmlu")["mmlu"]
            name = models[m].replace("open-llm-leaderboard/details_", "")[:34]
            print(f"{name:<34} {M[:, m].mean():>7.3f} {y.mean():>8.3f} "
                  f"{e['irt']:>7.3f} {e['pirt']:>7.3f} {e['gpirt']:>7.3f}")
        return 0

    n_models = M.shape[1] if a.limit is None else min(a.limit, M.shape[1])
    print(f"\n开始估计 {n_models} 个模型……")

    # ── 对照组：随机抽 100 题（第 8 节要求的口径，和「选代表题」对比）──
    true_all = M[:, :n_models].mean(axis=0)
    rng = np.random.default_rng(20261028)
    rand_means, rand_stds = [], []
    for _ in range(20):
        idx = rng.choice(M.shape[0], 100, replace=False)
        est = M[idx, :n_models].mean(axis=0)
        err = np.abs(est - true_all) * 100
        rand_means.append(err.mean())
        rand_stds.append(err.std(ddof=1))
    rand_err = float(np.mean(rand_means))
    rand_err_std = float(np.mean(rand_stds))
    print(f"  随机抽 100 题（20 次抽样平均）：误差 {rand_err:.1f}%")

    rows = []
    for m in range(n_models):
        y = M[seen, m]
        true_acc = float(M[:, m].mean())
        est = tb.evaluate(y, "mmlu")["mmlu"]
        rows.append(
            {
                "model": models[m].replace("open-llm-leaderboard/details_", ""),
                "true": true_acc,
                "naive100": float(y.mean()),
                "irt": float(est["irt"]),
                "pirt": float(est["pirt"]),
                "gpirt": float(est["gpirt"]),
            }
        )
        if (m + 1) % 50 == 0:
            print(f"  {m + 1}/{n_models}")

    def stats(key: str) -> tuple[float, float]:
        err = np.abs(np.array([r[key] for r in rows]) - np.array([r["true"] for r in rows])) * 100
        return float(err.mean()), float(err.std(ddof=1))

    print()
    print("=" * 64)
    print(f"F2 复现结果：MMLU 100 道代表题，{len(rows)} 个模型")
    print("=" * 64)
    print()
    print("| 方法 | 平均绝对误差 | 标准差 | 论文 | 差距 |")
    print("|---|---|---|---|---|")
    print(f"| **随机抽 100 题**（20 次抽样平均） | **{rand_err:.1f}%** | {rand_err_std:.1f}% | — | — |")
    n_mean, n_std = stats("naive100")
    print(f"| 直接用 100 道代表题平均（不做 IRT） | **{n_mean:.1f}%** | {n_std:.1f}% | — | — |")
    for k in ("irt", "pirt", "gpirt"):
        mean, std = stats(k)
        pm, ps = PAPER[k]
        print(f"| {LABEL[k]} | **{mean:.1f}%** | {std:.1f}% | {pm}% | {mean - pm:+.1f} 点 |")
    print()
    print(f"（论文标准差：IRT {PAPER['irt'][1]}%、p-IRT {PAPER['pirt'][1]}%、gp-IRT {PAPER['gpirt'][1]}%）")

    # 分组：高估 / 低估
    for k in ("irt", "pirt", "gpirt"):
        diff = np.array([r[k] for r in rows]) - np.array([r["true"] for r in rows])
        print(f"  {LABEL[k]:6s} 平均偏差 {diff.mean() * 100:+.2f} 点"
              f"（高估 {int((diff > 0).sum())} 个 / 低估 {int((diff < 0).sum())} 个）")

    OUT.mkdir(exist_ok=True)
    REFS.mkdir(exist_ok=True)
    payload = {
        "n_models": len(rows),
        "n_items": int(M.shape[0]),
        "n_seen": len(seen),
        "random100": {"mean": rand_err, "std": rand_err_std, "draws": 20},
        "summary": {k: dict(zip(("mean", "std"), stats(k)))
                    for k in ("naive100", "irt", "pirt", "gpirt")},
        "paper": PAPER,
        "rows": rows,
    }
    (REFS / "f2_error_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n明细已存：{REFS / 'f2_error_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
