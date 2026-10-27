#!/usr/bin/env python3
"""F2 复现：用 100 道 MMLU 代表题估计模型成绩，并与全量成绩对比。

流程：
  1. 读 tinyMMLU 的 100 道代表题（parquet）
  2. 让模型逐题作答，判对错，得到 y 向量（0/1）
  3. 用 tinyBenchmarks.evaluate(y, "mmlu") 估计成绩
  4. 输出估计值，供与公开全量成绩对比

用法：
  python refs/f2_run_mmlu.py --model glm --limit 5      # 试跑 5 题
  python refs/f2_run_mmlu.py --model glm                # 全跑 100 题
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from week1 import call_model, load_model_config  # noqa: E402

PARQUET = ROOT / "data" / "tinyMMLU" / "test-00000-of-00001.parquet"
OUT = ROOT / "refs" / "f2_results.json"

LETTERS = ["A", "B", "C", "D"]

PROMPT = """请回答下面的单选题。只输出选项字母（A/B/C/D），不要解释。

{question}

{choices}

答案："""


def load_questions(limit: int = 0) -> list[dict]:
    con = duckdb.connect()
    rows = con.execute(
        f'SELECT question, subject, choices, answer FROM "{PARQUET}"'
    ).fetchall()
    out = []
    for q, subj, choices, ans in rows:
        out.append(
            {
                "question": q,
                "subject": subj,
                "choices": list(choices),
                "answer": int(ans),
            }
        )
    return out[:limit] if limit else out


def format_choices(choices: list[str]) -> str:
    return "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices))


def extract_letter(text: str) -> int | None:
    """从模型输出里提取选项下标（0-3），失败返回 None。"""
    t = (text or "").strip()
    # 优先匹配开头的单个字母
    m = re.match(r"^[\s\*\(\（]*([ABCD])[\s\*\)\）\.。,，:：]?", t, re.I)
    if m:
        return LETTERS.index(m.group(1).upper())
    # 退而求其次：全文里第一个独立的 A/B/C/D
    m = re.search(r"\b([ABCD])\b", t)
    if m:
        return LETTERS.index(m.group(1))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm", help="glm 或 qwen")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfgs = load_model_config(ROOT / "configs" / "models.json")
    cfg = next(c for c in cfgs if args.model in c.name.lower())
    print(f"[模型] {cfg.name}")

    qs = load_questions(args.limit)
    print(f"[题目] {len(qs)} 道")

    y = []
    details = []
    for i, q in enumerate(qs, 1):
        prompt = PROMPT.format(
            question=q["question"], choices=format_choices(q["choices"])
        )
        try:
            res = call_model(cfg, [{"role": "user", "content": prompt}])
            text = res.get("text") or ""
        except Exception as e:
            print(f"  [{i}/{len(qs)}] 调用失败: {e}")
            y.append(0)
            details.append({"idx": i, "pred": None, "gold": q["answer"], "ok": False})
            continue

        pred = extract_letter(text)
        ok = pred == q["answer"]
        y.append(1 if ok else 0)
        details.append(
            {
                "idx": i,
                "subject": q["subject"],
                "pred": pred,
                "gold": q["answer"],
                "ok": ok,
                "raw": text[:60],
            }
        )
        mark = "✓" if ok else "✗"
        print(f"  [{i}/{len(qs)}] {mark} pred={pred} gold={q['answer']}  {q['subject'][:20]}")

    acc = sum(y) / len(y) if y else 0
    print(f"\n[准确率] {sum(y)}/{len(y)} = {acc*100:.1f}%")

    # 估计成绩
    if len(y) == 100:
        import numpy as np
        import tinyBenchmarks as tb

        est = tb.evaluate(np.array(y), "mmlu")
        print(f"[估计成绩] {est}")
    else:
        est = None
        print(f"[估计成绩] 跳过（需要正好 100 题，当前 {len(y)}）")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "model": cfg.name,
                "n": len(y),
                "accuracy": acc,
                "estimate": {k: float(v) for k, v in (est or {}).get("mmlu", {}).items()},
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[已保存] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
