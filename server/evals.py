"""评测接口：发起 / 列表 / 概览 / 逐题。

设计要点：
  - 发起评测立刻返回 run_id，真正跑在后台线程里（不阻塞请求）
  - 结果落库（eval_runs / eval_cases），页面从库里查，不读 CSV
  - 判分和提示词都调 lib/ 下的共用实现，不在这里另写一份
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib.audit import log_action
from lib.judge import judge
from lib.llm import ask, build_prompt
from lib.text import tokenize

from .auth import current_user
from .db import connect, execute

router = APIRouter(tags=["evals"])

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# BM25 索引只建一次（363 个块，建一次约 1 秒）
_index_lock = threading.Lock()
_chunks: list[dict] | None = None
_bm25 = None


def _get_index():
    global _chunks, _bm25
    with _index_lock:
        if _chunks is None:
            from rank_bm25 import BM25Okapi

            chunks = []
            for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
                if line.strip():
                    chunks.append(json.loads(line))
            _chunks = chunks
            _bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
        return _chunks, _bm25


class EvalStart(BaseModel):
    model: str = "qwen3-4b-local"
    split: str = "test"
    topk: int = 3


def _owned_app(app_id: int, user_id: int) -> dict:
    rows = execute("SELECT * FROM apps WHERE id=? AND user_id=?", (app_id, user_id), True)
    if not rows:
        raise HTTPException(404, "app not found")
    return dict(rows[0])


def _owned_run(run_id: int, user_id: int) -> dict:
    rows = execute(
        """SELECT r.* FROM eval_runs r JOIN apps a ON a.id = r.app_id
           WHERE r.id=? AND a.user_id=?""",
        (run_id, user_id), True,
    )
    if not rows:
        raise HTTPException(404, "eval run not found")
    return dict(rows[0])


# ---------------------------------------------------------------- 后台执行


def _run_eval(run_id: int, app_id: int, model: str, split: str, topk: int) -> None:
    """后台跑一次评测。任何异常都写进 error 字段，状态置 failed。"""
    conn = connect()
    t0 = time.time()
    # 后台线程没有登录态，但审计要归到应用所有者名下
    _o = conn.execute("SELECT user_id FROM apps WHERE id=?", (app_id,)).fetchone()
    owner_id = _o["user_id"] if _o else None
    try:
        conn.execute("UPDATE eval_runs SET status='running' WHERE id=?", (run_id,))
        conn.commit()

        qs = conn.execute(
            "SELECT id, content, reference, split, source FROM questions WHERE app_id=? AND split=?",
            (app_id, split),
        ).fetchall()
        if not qs:
            raise RuntimeError(f"应用 {app_id} 没有 split={split} 的题目")

        chunks, bm25 = _get_index()
        correct = partial = wrong = 0

        for q in qs:
            scores = bm25.get_scores(tokenize(q["content"]))
            top = sorted(range(len(scores)), key=lambda j: -scores[j])[:topk]
            contexts = [chunks[j]["text"] for j in top]
            doc_loc = f"{chunks[top[0]]['path']} > {chunks[top[0]]['heading']}" if top else ""

            try:
                answer, dt = ask(model, build_prompt(q["content"], contexts))
            except Exception as e:  # noqa: BLE001
                answer, dt = "", 0.0
                print(f"[eval {run_id}] 调用失败：{type(e).__name__}")

            verdict, reason = judge(q["reference"] or "", answer)
            if verdict == "对":
                correct += 1
            elif verdict == "部分对":
                partial += 1
            else:
                wrong += 1

            conn.execute(
                """INSERT INTO eval_cases
                   (run_id, question_id, question, reference, answer, verdict, reason,
                    source, doc_location, latency_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (run_id, q["id"], q["content"], q["reference"], answer, verdict, reason,
                 q["source"] or "unknown", doc_loc, int(dt * 1000)),
            )
            conn.execute(
                "UPDATE eval_runs SET total=?, correct=?, partial=?, wrong=? WHERE id=?",
                (correct + partial + wrong, correct, partial, wrong, run_id),
            )
            conn.commit()

        total = correct + partial + wrong
        conn.execute(
            """UPDATE eval_runs SET status='done', strict_acc=?, loose_acc=?,
               duration_sec=?, finished_at=datetime('now') WHERE id=?""",
            (correct / total if total else 0.0,
             (correct + partial) / total if total else 0.0,
             time.time() - t0, run_id),
        )
        conn.commit()
        print(f"[eval {run_id}] 完成：{correct}/{total}")
        log_action(
            owner_id, "eval.finish", "eval_run", run_id,
            {"total": total, "correct": correct,
             "strict": round(correct / total, 4) if total else 0.0},
        )
    except Exception as e:  # noqa: BLE001
        conn.execute(
            "UPDATE eval_runs SET status='failed', error=?, finished_at=datetime('now') WHERE id=?",
            (str(e)[:300], run_id),
        )
        conn.commit()
        print(f"[eval {run_id}] 失败：{e}")
        log_action(owner_id, "eval.failed", "eval_run", run_id, {"error": str(e)[:300]})
    finally:
        conn.close()


# ---------------------------------------------------------------- 接口


@router.post("/apps/{app_id}/eval")
def start_eval(app_id: int, body: EvalStart, user=Depends(current_user)):
    _owned_app(app_id, user["id"])

    running = execute(
        "SELECT id FROM eval_runs WHERE app_id=? AND status IN ('pending','running')",
        (app_id,), True,
    )
    if running:
        raise HTTPException(409, f"该应用已有评测在跑（run_id={running[0]['id']}），请等它结束")

    run_id = execute(
        "INSERT INTO eval_runs (app_id, model, split, topk, status) VALUES (?,?,?,?,'pending')",
        (app_id, body.model, body.split, body.topk),
    )
    log_action(
        user["id"], "eval.start", "eval_run", run_id,
        {"app_id": app_id, "model": body.model, "split": body.split, "topk": body.topk},
    )
    threading.Thread(
        target=_run_eval,
        args=(run_id, app_id, body.model, body.split, body.topk),
        daemon=True,
    ).start()
    return {"run_id": run_id, "status": "running"}


@router.get("/apps/{app_id}/evals")
def list_evals(app_id: int, limit: int = 20, user=Depends(current_user)):
    _owned_app(app_id, user["id"])
    rows = execute(
        """SELECT id, model, split, status, total, strict_acc, loose_acc,
                  duration_sec, created_at, error
           FROM eval_runs WHERE app_id=? ORDER BY id DESC LIMIT ?""",
        (app_id, limit), True,
    )
    return {"items": [
        {
            "run_id": r["id"],
            "model": r["model"],
            "split": r["split"],
            "status": r["status"],
            "total": r["total"],
            "strict_acc": r["strict_acc"],
            "loose_acc": r["loose_acc"],
            "duration_sec": r["duration_sec"],
            "created_at": r["created_at"],
            "error": r["error"],
        }
        for r in rows
    ]}


@router.get("/evals/{run_id}")
def get_eval(run_id: int, user=Depends(current_user)):
    run = _owned_run(run_id, user["id"])

    # 分来源统计：按 eval_cases.source 分组
    rows = execute(
        """SELECT source, COUNT(*) AS n,
                  SUM(CASE WHEN verdict='对' THEN 1 ELSE 0 END) AS ok
           FROM eval_cases WHERE run_id=? GROUP BY source""",
        (run_id,), True,
    )
    by_source = {r["source"] or "unknown": {"total": r["n"], "correct": r["ok"]} for r in rows}

    return {
        "run_id": run["id"],
        "app_id": run["app_id"],
        "model": run["model"],
        "split": run["split"],
        "topk": run["topk"],
        "status": run["status"],
        "total": run["total"],
        "correct": run["correct"],
        "partial": run["partial"],
        "wrong": run["wrong"],
        "strict_acc": run["strict_acc"],
        "loose_acc": run["loose_acc"],
        "duration_sec": run["duration_sec"],
        "created_at": run["created_at"],
        "finished_at": run["finished_at"],
        "error": run["error"],
        "by_source": by_source,
    }


@router.get("/evals/{run_id}/cases")
def get_cases(
    run_id: int,
    verdict: str = "",
    source: str = "",
    page: int = 1,
    page_size: int = 50,
    user=Depends(current_user),
):
    _owned_run(run_id, user["id"])
    page = max(1, page)
    page_size = min(max(1, page_size), 200)

    where, params = ["run_id=?"], [run_id]
    if verdict:
        where.append("verdict=?")
        params.append(verdict)
    if source:
        where.append("source=?")
        params.append(source)
    clause = " AND ".join(where)

    total = execute(f"SELECT COUNT(*) AS n FROM eval_cases WHERE {clause}", tuple(params), True)[0]["n"]
    rows = execute(
        f"""SELECT id, question, reference, answer, verdict, reason, source, doc_location, latency_ms
            FROM eval_cases WHERE {clause} ORDER BY id LIMIT ? OFFSET ?""",
        tuple(params) + (page_size, (page - 1) * page_size), True,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "case_id": r["id"],
                "question": r["question"],
                "reference": r["reference"],
                "answer": r["answer"],
                "verdict": r["verdict"],
                "reason": r["reason"],
                "source": r["source"],
                "doc_location": r["doc_location"],
                "latency_ms": r["latency_ms"],
            }
            for r in rows
        ],
    }
