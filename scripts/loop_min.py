"""优化循环最小闭环。

跑一轮完整的「评测 → 诊断 → 提议 → 验证 → 决策」，把每一步落进 opt_runs / opt_rounds。

和任务书第 5 节九步的对应关系：
  ① 评测     —— evaluate()，在优化集上逐题跑
  ② 诊断     —— diagnose()，把错题分成「检索没命中」和「命中但没答对」
  ③ 提议     —— propose()，把失败案例喂给模型，让它提一个候选改动并写预期
  ⑤ 验证     —— 候选过了优化集门槛，才在验证集上完整跑
  ⑥ 决策     —— 涨幅超过误差范围才保留，否则退回
  ④⑦⑧⑨ 不做（快速筛选、停止条件、审批发布、经验沉淀）属于阶段 2 后续

用法：
    /home/ace/comfyvenv/bin/python scripts/loop_min.py --app 11 --rounds 2
    /home/ace/comfyvenv/bin/python scripts/loop_min.py --app 11 --dry-run   # 只诊断+提议，不跑评测
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rank_bm25 import BM25Okapi  # noqa: E402

from lib.judge import judge  # noqa: E402
from lib.llm import ask, build_prompt  # noqa: E402
from lib.text import tokenize  # noqa: E402
from server.db import connect  # noqa: E402

DATA = ROOT / "data"
MODEL_DIR = Path("/home/ace/models/bge-reranker-v2-m3")

# 起点配置：就是现在线上在用的那套（重排 + top3 + 简洁提示词）
BASE_CONFIG = {
    "topk": 3,
    "use_rerank": True,
    "recall": 20,
    "prompt_style": "concise",
}

# 允许模型改的范围。不在白名单里的值一律拒绝——防止它提出「换模型」这种没法自动验证的改动。
ALLOWED = {
    "topk": [3, 5],
    "prompt_style": ["concise", "detailed"],
}

# 一道题占多少个百分点：优化集 69 道约 1.45，验证集 70 道约 1.43。
# 要求至少多对 2 道才算「真的变好」，1 道算噪声。
MIN_GAIN_QUESTIONS = 2

_reranker = None


def get_reranker(device: str):
    global _reranker
    if _reranker is None:
        from rerank_eval import Reranker

        t0 = time.time()
        _reranker = Reranker(MODEL_DIR, device=device)
        print(f"  重排模型加载 {time.time() - t0:.1f}s")
    return _reranker


def load_chunks() -> list[dict]:
    p = DATA / "chunks.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_questions(split: str) -> list[dict]:
    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    return [q for q in qs if q["split"] == split]


def retrieve(bm25, chunks, question: str, cfg: dict, ranker) -> list[int]:
    """返回最终喂给模型的文档下标列表。"""
    scores = bm25.get_scores(tokenize(question))
    depth = max(cfg["recall"], cfg["topk"]) if cfg["use_rerank"] else cfg["topk"]
    cand = sorted(range(len(scores)), key=lambda j: -scores[j])[:depth]
    if not cfg["use_rerank"] or ranker is None:
        return cand[: cfg["topk"]]
    rs = ranker.score(question, [chunks[j]["text"] for j in cand])
    order = sorted(range(len(cand)), key=lambda k: -rs[k])
    return [cand[k] for k in order[: cfg["topk"]]]


def evaluate(cfg: dict, split: str, model: str, bm25, chunks, ranker, limit: int = 0) -> dict:
    """跑一遍评测，返回成绩和逐题明细。"""
    qs = load_questions(split)
    if limit:
        qs = qs[:limit]

    rows = []
    t0 = time.time()
    for i, q in enumerate(qs, 1):
        top = retrieve(bm25, chunks, q["question"], cfg, ranker)
        ctx = [chunks[j]["text"] for j in top]

        want = (q.get("doc_location") or "").split(" > ")[0].strip()
        hit = bool(want) and any(chunks[j]["path"] == want for j in top)

        try:
            got, dt = ask(model, build_prompt(q["question"], ctx, cfg["prompt_style"]))
        except Exception as e:  # noqa: BLE001
            got, dt = "", 0.0
            print(f"    [{i}] 调用失败 {type(e).__name__}")

        verdict, reason = judge(q["answer"], got)
        rows.append({
            "id": q["id"],
            "source": q.get("source", ""),
            "question": q["question"],
            "reference": q["answer"],
            "answer": got,
            "verdict": verdict,
            "reason": reason,
            "hit": hit,
            "latency": round(dt, 1),
        })
        if i % 20 == 0:
            print(f"    [{i}/{len(qs)}] {time.time() - t0:.0f}s", end="\r")

    ok = sum(1 for r in rows if r["verdict"] == "对")
    part = sum(1 for r in rows if r["verdict"] == "部分对")
    print(f"    {len(qs)} 道，对 {ok} 部分对 {part}，严格 {ok / len(rows):.1%}，{time.time() - t0:.0f}s")
    return {"score": ok / len(rows) if rows else 0.0, "ok": ok, "n": len(rows), "rows": rows}


def diagnose(rows: list[dict]) -> dict:
    """② 诊断：把错题按「检索问题 / 生成问题」分开。"""
    wrong = [r for r in rows if r["verdict"] != "对"]
    miss = [r for r in wrong if not r["hit"]]
    gen = [r for r in wrong if r["hit"]]
    return {
        "n": len(rows),
        "ok": sum(1 for r in rows if r["verdict"] == "对"),
        "wrong": len(wrong),
        "miss": len(miss),
        "gen": len(gen),
        "hit_rate": sum(1 for r in rows if r["hit"]) / len(rows) if rows else 0.0,
        "miss_examples": miss[:3],
        "gen_examples": gen[:3],
    }


PROPOSE_PROMPT = """/no_think
你是提示词优化助手。下面是一次评测的失败情况，请提出**一个**改动。

【当前配置】
topk={topk}（喂给模型的文档段数）
prompt_style={style}（concise=只答文档明确写的内容；detailed=要求把相关要点都列全，含默认值和参数关系）

【失败统计】
共 {n} 道，严格答对 {ok} 道。
- 检索没命中正确答案所在文档：{miss} 道
- 检索命中了、但模型没答对：{gen} 道

【失败案例】
{cases}

请只从下面两项里改，**只能改一个**：
- topk：可选 3 或 5
- prompt_style：可选 concise 或 detailed

输出严格 JSON，不要任何解释和代码块：
{{"topk": 3, "prompt_style": "detailed", "reason": "一句话理由", "expect": "预期修好哪类失败"}}"""


def _fmt_cases(rows: list[dict]) -> str:
    out = []
    for i, r in enumerate(rows, 1):
        out.append(
            f"{i}. 问题：{r['question'][:60]}\n"
            f"   标准答案：{r['reference'][:100]}\n"
            f"   模型回答：{(r['answer'] or '(空)')[:100]}\n"
            f"   检索是否命中：{'是' if r['hit'] else '否'}"
        )
    return "\n".join(out)


def propose(cfg: dict, diag: dict, model: str) -> dict:
    """③ 提议：让模型提一个候选改动。解析失败就退回默认候选。"""
    cases = diag["gen_examples"] + diag["miss_examples"]
    prompt = PROPOSE_PROMPT.format(
        topk=cfg["topk"],
        style=cfg["prompt_style"],
        n=diag["n"],
        ok=diag["ok"],
        miss=diag["miss"],
        gen=diag["gen"],
        cases=_fmt_cases(cases) if cases else "（无）",
    )
    raw, dt = ask(model, prompt, num_predict=260)
    print(f"    模型提议（{dt:.1f}s）：{raw[:160]}")

    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"config": None, "reason": "模型没输出 JSON", "expect": "", "raw": raw}

    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"config": None, "reason": "JSON 解析失败", "expect": "", "raw": raw}

    cand = dict(cfg)
    changes = []
    for k, allowed in ALLOWED.items():
        if k in d:
            v = d[k]
            if k == "topk":
                v = int(v) if str(v).isdigit() else v
            if v in allowed and v != cfg[k]:
                changes.append((k, v))
    if not changes:
        return {"config": None, "reason": "模型给的改动不在白名单内或没改动",
                "expect": str(d.get("expect", "")), "raw": raw}

    # 一次只改一项：否则涨了分不清是哪项起的作用。
    # 模型如果提了多项，按诊断出的主要矛盾挑一个——生成问题多就优先改提示词，检索问题多就优先改 topk。
    if len(changes) > 1:
        prefer = "prompt_style" if diag["gen"] >= diag["miss"] else "topk"
        picked = [c for c in changes if c[0] == prefer]
        changes = picked or changes[:1]
        print(f"    （模型提了 {len(picked) or 1} 项里的多项，按诊断只取「{changes[0][0]}」，保证单变量）")
    k, v = changes[0]
    cand[k] = v
    return {
        "config": cand,
        "reason": str(d.get("reason", ""))[:200],
        "expect": str(d.get("expect", ""))[:200],
        "raw": raw,
    }


def cfg_str(c: dict) -> str:
    return f"topk={c['topk']} rerank={c['use_rerank']} style={c['prompt_style']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=int, default=11)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--limit", type=int, default=0, help="每题只跑前 N 道（调试用）")
    ap.add_argument("--dry-run", action="store_true", help="只诊断+提议，不跑候选评测")
    ap.add_argument("--base-style", default="detailed", choices=["concise", "detailed"],
                    help="起点提示词风格。默认 detailed（第一轮优化后的当前最佳）")
    a = ap.parse_args()

    # 起点跟着当前最佳走：第一轮之后最佳已经是 detailed，再跑就该从 detailed 继续往上找
    BASE_CONFIG["prompt_style"] = a.base_style

    chunks = load_chunks()
    t0 = time.time()
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    print(f"检索库 {len(chunks)} 块，索引 {time.time() - t0:.1f}s")

    ranker = None
    if BASE_CONFIG["use_rerank"]:
        ranker = get_reranker(a.device)

    conn = connect()
    cur = conn.execute(
        "INSERT INTO opt_runs (app_id, base_config, best_config, rounds_planned) VALUES (?,?,?,?)",
        (a.app, json.dumps(BASE_CONFIG, ensure_ascii=False),
         json.dumps(BASE_CONFIG, ensure_ascii=False), a.rounds),
    )
    opt_run_id = cur.lastrowid
    conn.commit()
    print(f"\n=== 优化实验 #{opt_run_id} 开始（{a.rounds} 轮）===\n")

    # ① 基线
    print("① 基线评测（优化集）")
    base = evaluate(BASE_CONFIG, "optimize", a.model, bm25, chunks, ranker, a.limit)
    best_cfg, best_score, best_rows = dict(BASE_CONFIG), base["score"], base["rows"]
    best_valid = None
    conn.execute(
        "UPDATE opt_runs SET base_score=?, best_score=? WHERE id=?",
        (base["score"], best_score, opt_run_id),
    )
    conn.commit()

    stop_reason = "轮数用完"

    for rnd in range(1, a.rounds + 1):
        print(f"\n=== 第 {rnd} 轮 ===")

        # ② 诊断
        diag = diagnose(best_rows)
        print(
            f"② 诊断：{diag['n']} 道里错 {diag['wrong']} 道 —— "
            f"检索没命中 {diag['miss']}，命中但没答对 {diag['gen']}（命中率 {diag['hit_rate']:.1%}）"
        )

        # ③ 提议
        print("③ 提议")
        prop = propose(best_cfg, diag, a.model)
        if prop["config"] is None:
            print(f"    × 没拿到合法候选：{prop['reason']}")
            conn.execute(
                "INSERT INTO opt_rounds (opt_run_id, round_no, config, reason, expect, diag_json, decision, decision_note) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (opt_run_id, rnd, json.dumps(best_cfg, ensure_ascii=False), prop["reason"],
                 prop["expect"], json.dumps(diag, ensure_ascii=False), "skipped", prop["reason"]),
            )
            conn.commit()
            continue

        cand = prop["config"]
        print(f"    候选：{cfg_str(cand)}")
        print(f"    理由：{prop['reason']}")
        print(f"    预期：{prop['expect']}")

        if a.dry_run:
            print("    （dry-run，不跑候选）")
            conn.execute(
                "INSERT INTO opt_rounds (opt_run_id, round_no, config, reason, expect, diag_json, decision, decision_note) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (opt_run_id, rnd, json.dumps(cand, ensure_ascii=False), prop["reason"],
                 prop["expect"], json.dumps(diag, ensure_ascii=False), "skipped", "dry-run"),
            )
            conn.commit()
            continue

        # ① 候选评测（优化集）
        print("① 候选评测（优化集）")
        cand_res = evaluate(cand, "optimize", a.model, bm25, chunks, ranker, a.limit)
        gain_q = cand_res["ok"] - base["ok"]
        opt_delta = cand_res["score"] - best_score
        print(f"    {cfg_str(cand)} → 严格 {cand_res['score']:.1%}（{cand_res['ok']}/{cand_res['n']}），"
              f"相对当前最佳 {opt_delta:+.1%}（{gain_q:+d} 道）")

        decision, note = "reverted", ""
        valid_score = valid_delta = None

        if gain_q < MIN_GAIN_QUESTIONS:
            note = f"优化集只多对 {gain_q} 道，不到 {MIN_GAIN_QUESTIONS} 道的门槛，判为噪声"
            print(f"⑥ 决策：退回 —— {note}")
        else:
            # ⑤ 验证集
            print("⑤ 验证集验证（候选）")
            v_cand = evaluate(cand, "valid", a.model, bm25, chunks, ranker, a.limit)
            if best_valid is None:
                print("⑤ 验证集验证（当前最佳，只需跑一次）")
                v_best = evaluate(best_cfg, "valid", a.model, bm25, chunks, ranker, a.limit)
                best_valid = v_best["score"]
            valid_score = v_cand["score"]
            valid_delta = valid_score - best_valid
            v_gain_q = v_cand["ok"] - round(best_valid * v_cand["n"])
            print(f"    验证集 {valid_score:.1%} vs 当前最佳 {best_valid:.1%}（{valid_delta:+.1%}）")

            if v_gain_q >= 1:
                decision = "kept"
                note = f"优化集 +{gain_q} 道、验证集 {valid_delta:+.1%}，保留"
                best_cfg, best_score, best_rows = cand, cand_res["score"], cand_res["rows"]
                best_valid = valid_score  # 新最佳在验证集的成绩，下一轮拿它当基准
            else:
                note = f"优化集涨了 {gain_q} 道，但验证集没跟上（{valid_delta:+.1%}），判为过拟合，退回"
            print(f"⑥ 决策：{decision} —— {note}")

        conn.execute(
            "INSERT INTO opt_rounds (opt_run_id, round_no, config, reason, expect, diag_json, "
            "opt_score, opt_delta, valid_score, valid_delta, decision, decision_note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (opt_run_id, rnd, json.dumps(cand, ensure_ascii=False), prop["reason"], prop["expect"],
             json.dumps(diag, ensure_ascii=False), cand_res["score"], opt_delta,
             valid_score, valid_delta, decision, note),
        )
        conn.execute(
            "UPDATE opt_runs SET best_config=?, best_score=?, best_valid=?, rounds_done=? WHERE id=?",
            (json.dumps(best_cfg, ensure_ascii=False), best_score, best_valid, rnd, opt_run_id),
        )
        conn.commit()

    conn.execute(
        "UPDATE opt_runs SET status='done', stop_reason=?, rounds_done=?, finished_at=datetime('now') WHERE id=?",
        (stop_reason, a.rounds, opt_run_id),
    )
    conn.commit()

    print(f"\n=== 实验 #{opt_run_id} 结束 ===")
    print(f"起点：{cfg_str(BASE_CONFIG)} → 严格 {base['score']:.1%}")
    print(f"终点：{cfg_str(best_cfg)} → 严格 {best_score:.1%}")
    print(f"提升：{best_score - base['score']:+.1%}（{(best_score - base['score']) * base['n']:+.0f} 道）")
    for r in conn.execute(
        "SELECT round_no, config, opt_score, valid_score, decision FROM opt_rounds "
        "WHERE opt_run_id=? ORDER BY round_no", (opt_run_id,)
    ):
        d = dict(r)
        vs = "—" if d["valid_score"] is None else f"{d['valid_score']:.1%}"
        os_ = "—" if d["opt_score"] is None else f"{d['opt_score']:.1%}"
        print(f"  第{d['round_no']}轮 {d['config']} → 优化集 {os_} 验证集 {vs} {d['decision']}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
