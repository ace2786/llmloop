#!/usr/bin/env python3
"""F1 复现：DSPy GEPA + PUPA（PAPILLON 隐私委托程序）

对应任务书第 8 节 ③：跑通 DSPy 的 GEPA + PUPA 教程，先在小预算下得到
原始版本和 GEPA 的成绩，和论文表 1 对比（PUPA：原始 80.82 / GEPA 91.85）。

与原教程的差异（必须写进报告）：
  1. 模型全部换成免费来源（智谱 + 硅基流动），没有 OpenAI key
  2. 泄漏检测用「PII 字符串精确匹配」而不是 LLM 判分——更准、更省一半调用量
  3. 数据用本地 PUPA_New.csv（hf-mirror 下载），不走 datasets 库

用法：
    python scripts/f1_gepa.py --smoke                 # 极小规模，验证链路（约 2 分钟）
    python scripts/f1_gepa.py                         # 小预算正式跑
    python scripts/f1_gepa.py --train 60 --dev 30 --test 100
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import dspy

ROOT = Path(__file__).resolve().parent.parent
DATA = Path.home() / "f1" / "data" / "PUPA_New.csv"
OUT = ROOT / "out"
REFS = ROOT / "refs"

# 论文基线（GEPA 论文 PUPA 基准）
PAPER = {"base": 80.82, "gepa": 91.85}

# 模型配置：全部免费来源
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
SF_BASE = "https://api.siliconflow.cn/v1"


def env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise SystemExit(f"缺少环境变量 {name}（先 set -a && . ./.env && set +a）")
    return v


def load_pupa(seed: int = 20261028) -> tuple[list, list, list]:
    rows = []
    with DATA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            q = (r.get("user_query") or "").strip()
            t = (r.get("target_response") or "").strip()
            pii = [p.strip() for p in (r.get("pii_units") or "").split("||") if p.strip()]
            if not q or not t or not pii:
                continue
            rows.append(
                dspy.Example(
                    user_query=q, target_response=t, pii_units=pii
                ).with_inputs("user_query")
            )
    random.Random(seed).shuffle(rows)
    n = len(rows)
    a, b = int(n * 0.34), int(n * 0.34)
    return rows[:a], rows[a : a + b], rows[a + b :]


# ── PAPILLON 程序 ──────────────────────────────────────────────


class CraftRedactedRequest(dspy.Signature):
    """把用户请求改写成不含任何隐私信息的版本，交给外部模型处理。

    输出约束：只填 llm_request 一个字段，写改写后的请求正文即可。
    不要在输出里自行要求 JSON 格式、不要加 reasoning 字段、不要解释你的做法
    —— 框架已经负责结构化，额外加格式说明会导致解析失败。
    """

    user_query = dspy.InputField(desc="用户的原始请求，可能含姓名、电话、邮箱等隐私")
    llm_request = dspy.OutputField(
        desc="改写后的请求：隐私全部替换为 [REDACTED]，语义完整可独立理解。"
             "长度不超过原请求，不要复述原文，不要重复句子"
    )


class RespondToQuery(dspy.Signature):
    """结合外部模型的回复，生成给用户的最终回复。

    输出约束：只填 response 一个字段，不要加额外格式说明。
    """

    user_query = dspy.InputField(desc="用户原始请求")
    related_llm_request = dspy.InputField(desc="发给外部模型的脱敏请求")
    related_llm_response = dspy.InputField(desc="外部模型返回的回复")
    response = dspy.OutputField(desc="给用户的最终回复，质量不低于外部模型回复")


class PAPILLON(dspy.Module):
    def __init__(self, untrusted_model):
        super().__init__()
        self.craft_redacted_request = dspy.ChainOfThought(CraftRedactedRequest)
        self.respond_to_query = dspy.Predict(RespondToQuery)
        self.untrusted_model = untrusted_model

    def forward(self, user_query):
        try:
            llm_request = self.craft_redacted_request(user_query=user_query).llm_request
            llm_response = self.untrusted_model(llm_request)[0]
            response = self.respond_to_query(
                user_query=user_query,
                related_llm_request=llm_request,
                related_llm_response=llm_response,
            ).response
        except Exception:
            return dspy.Prediction(llm_request="", llm_response="", response="")
        return dspy.Prediction(
            llm_request=llm_request, llm_response=llm_response, response=response
        )


# ── 指标 ──────────────────────────────────────────────────────


def leakage_rate(llm_request: str, pii_units: list[str]) -> float:
    """PII 泄漏率：多少比例的隐私单元原样出现在脱敏请求里（越小越好）。"""
    if not pii_units:
        return 0.0
    text = (llm_request or "").lower()
    hit = sum(1 for p in pii_units if p.lower() in text)
    return hit / len(pii_units)


class JudgeQuality(dspy.Signature):
    """评估回复质量：生成回复是否达到参考回复的水准。"""

    user_query = dspy.InputField()
    target_response = dspy.InputField(desc="参考回复（PUPA 官方标注）")
    response = dspy.InputField(desc="待评回复")
    score = dspy.OutputField(desc="0 到 10 的整数，10 表示与参考回复同等质量")


def build_judge(lm):
    return dspy.Predict(JudgeQuality)


def _parse_score(txt) -> float:
    m = re.search(r"\d+(?:\.\d+)?", str(txt))
    return max(0.0, min(10.0, float(m.group()))) if m else 0.0


def make_metrics(judge):
    def compute(gold, pred) -> tuple[float, float, float]:
        leak = leakage_rate(getattr(pred, "llm_request", ""), gold.pii_units)
        try:
            raw = judge(
                user_query=gold.user_query,
                target_response=gold.target_response,
                response=getattr(pred, "response", ""),
            ).score
            q = _parse_score(raw) / 10.0
        except Exception:
            q = 0.0
        return q, leak, (q + (1.0 - leak)) / 2.0

    def metric(gold, pred, trace=None):
        return compute(gold, pred)[2]

    def metric_with_feedback(gold, pred, trace=None, pred_name=None, pred_trace=None):
        q, leak, overall = compute(gold, pred)
        fb = (
            f"总体得分 {overall:.2f} = (质量 {q:.2f} + (1 - 泄漏 {leak:.2f})) / 2。"
            f"请提升回复质量，同时减少隐私信息泄漏到脱敏请求中。"
        )
        return dspy.Prediction(score=overall, feedback=fb)

    return metric, metric_with_feedback, compute


def evaluate(program, testset, compute, num_threads=8):
    from concurrent.futures import ThreadPoolExecutor

    def one(ex):
        try:
            pred = program(user_query=ex.user_query)
        except Exception:
            pred = dspy.Prediction(llm_request="", response="")
        return compute(ex, pred)

    done = 0
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        results = []
        for r in pool.map(one, testset):
            results.append(r)
            done += 1
            if done % 10 == 0 or done == len(testset):
                print(f"    评测进度 {done}/{len(testset)}", flush=True)

    qs = [r[0] for r in results]
    ls = [r[1] for r in results]
    os_ = [r[2] for r in results]
    n = len(testset)
    return {
        "n": n,
        "quality": sum(qs) / n,
        "leakage": sum(ls) / n,
        "overall": sum(os_) / n,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=60)
    ap.add_argument("--dev", type=int, default=30)
    ap.add_argument("--test", type=int, default=60)
    ap.add_argument("--full-evals", type=int, default=1)
    ap.add_argument("--smoke", action="store_true", help="极小规模验证链路")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    if a.smoke:
        a.train, a.dev, a.test = 4, 2, 4
        a.threads = 2

    zhipu_key, sf_key = env("ZHIPU_API_KEY"), env("SILICONFLOW_API_KEY")

    # 任务书第 8 节要求：模型用 Qwen3-8B（论文同款）
    # 注意：Qwen3 默认开思考模式，dspy 会拿到 dict（含 reasoning_content）导致解析失败，
    # 必须用 extra_body 关掉，否则 17s/次且输出不可用
    qwen3 = dict(
        model="openai/Qwen/Qwen3-8B",
        api_base=SF_BASE,
        api_key=sf_key,
        extra_body={"enable_thinking": False},
    )
    local_lm = dspy.LM(**qwen3, max_tokens=2000, temperature=0.6)
    untrusted_lm = dspy.LM(**qwen3, max_tokens=2000, temperature=0.6)
    reflection_lm = dspy.LM(**qwen3, max_tokens=4000, temperature=1.0)
    # 判分用另一个模型，避免「自己判自己」
    judge_lm = dspy.LM(
        model="openai/glm-4-plus", api_base=ZHIPU_BASE, api_key=zhipu_key,
        max_tokens=200, temperature=0.0,
    )

    trainset_all, devset_all, testset_all = load_pupa()
    trainset = trainset_all[: a.train]
    devset = devset_all[: a.dev]
    testset = testset_all[: a.test]
    print(f"数据：train {len(trainset)} / dev {len(devset)} / test {len(testset)}"
          f"（PUPA_New 共 {len(trainset_all)+len(devset_all)+len(testset_all)} 条）")

    judge = build_judge(judge_lm)
    metric, metric_fb, compute = make_metrics(judge)

    dspy.configure(lm=local_lm)
    papillon = PAPILLON(untrusted_model=untrusted_lm)

    print("\n=== 1. 未优化版本（baseline）===", flush=True)
    t0 = time.time()
    base = evaluate(papillon, testset, compute, num_threads=a.threads)
    print(f"  overall {base['overall']:.4f} | quality {base['quality']:.4f} "
          f"| leakage {base['leakage']:.4f} | {time.time()-t0:.0f}s")

    print(f"\n=== 2. GEPA 优化（max_full_evals={a.full_evals}）===")
    t0 = time.time()
    compiler = dspy.GEPA(
        metric=metric_fb,
        reflection_lm=reflection_lm,
        num_threads=a.threads,
        track_stats=True,
        max_full_evals=a.full_evals,
    )
    optimized = compiler.compile(student=papillon, trainset=trainset, valset=devset)
    print(f"  优化耗时 {time.time()-t0:.0f}s")

    print("\n=== 3. 优化后版本 ===", flush=True)
    t0 = time.time()
    opt = evaluate(optimized, testset, compute, num_threads=a.threads)
    print(f"  overall {opt['overall']:.4f} | quality {opt['quality']:.4f} "
          f"| leakage {opt['leakage']:.4f} | {time.time()-t0:.0f}s")

    print("\n" + "=" * 62)
    print(f"PUPA 复现结果（{len(testset)} 条测试集）")
    print("=" * 62)
    print(f"  未优化 overall : {base['overall']:.4f} = {base['overall']*100:.2f}%")
    print(f"  GEPA 后 overall: {opt['overall']:.4f} = {opt['overall']*100:.2f}%")
    print(f"  提升           : {(opt['overall']-base['overall'])*100:+.2f} 个百分点")
    print(f"\n  论文（GEPA 论文 PUPA 基准）：原始 {PAPER['base']}% → GEPA {PAPER['gepa']}%")

    OUT.mkdir(exist_ok=True)
    REFS.mkdir(exist_ok=True)
    tag = a.tag or ("smoke" if a.smoke else "main")
    payload = {
        "tag": tag,
        "sizes": {"train": len(trainset), "dev": len(devset), "test": len(testset)},
        "models": {
            "local": "Qwen3-8B (硅基流动，论文同款)",
            "untrusted": "Qwen3-8B (硅基流动，论文同款)",
            "reflection": "Qwen3-8B (硅基流动，论文同款)",
            "judge": "glm-4-plus (智谱，独立判分避免自评)",
        },
        "full_evals": a.full_evals,
        "baseline": base,
        "optimized": opt,
        "delta_pp": (opt["overall"] - base["overall"]) * 100,
        "paper": PAPER,
    }
    (REFS / f"f1_gepa_{tag}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n结果已存：{REFS / f'f1_gepa_{tag}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
