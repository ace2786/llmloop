"""助手接口：给最终用户用的问答，带引用和反馈。

这是任务书第 4 节列的第 11 个页面「LlamaFactory 助手（被测应用）」的后端：
  给最终用户用的问答和配置生成页面，带「有用 / 没用 / 有错误」反馈按钮。

注意：这个助手是「被测对象」，它的检索和回答不算本系统的三个 AI 功能。
     评测循环优化的是它，不是评测它自己。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.judge import hard_entities  # noqa: F401  （保留：以后做答案自检用）
from lib.llm import ask, build_prompt

from .auth import current_user
from .db import connect, execute
from .evals import _get_index, _owned_app

router = APIRouter(tags=["chat"])

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    topk: int = Field(default=3, ge=1, le=10)


class FeedbackIn(BaseModel):
    rating: str = Field(pattern="^(useful|useless|wrong)$")
    comment: str = ""


@router.post("/apps/{app_id}/chat")
def chat(app_id: int, body: ChatIn, user=Depends(current_user)):
    """问一句，返回回答 + 引用到的文档段落。"""
    _owned_app(app_id, user["id"])

    chunks, bm25 = _get_index()
    from lib.text import tokenize

    scores = bm25.get_scores(tokenize(body.question))
    top = sorted(range(len(scores)), key=lambda j: -scores[j])[: body.topk]
    contexts = [chunks[j]["text"] for j in top]

    t0 = time.time()
    try:
        # 2026-11-12 优化循环第一轮的结论：提示词用 detailed（要求把相关要点列全、
        # 带上默认值和参数间关系），测试集严格正确率 37.5% → 60.0%（升级 29 / 降级 3）。
        # 依据见 scripts/loop_min.py 与 out/rerank_v2_test.csv。
        answer, dt = ask("qwen3-4b-local", build_prompt(body.question, contexts, "detailed"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"模型服务不可用：{type(e).__name__}") from e

    refs = [
        {
            "path": chunks[j]["path"],
            "heading": chunks[j]["heading"],
            "snippet": chunks[j]["text"][:240],
            "score": round(float(scores[j]), 3),
        }
        for j in top
    ]

    msg_id = execute(
        """INSERT INTO chat_messages (app_id, question, answer, references_json, latency_ms)
           VALUES (?,?,?,?,?)""",
        (app_id, body.question, answer, json.dumps(refs, ensure_ascii=False), int(dt * 1000)),
    )

    return {
        "message_id": msg_id,
        "answer": answer,
        "references": refs,
        "latency_ms": int(dt * 1000),
    }


@router.post("/chat/{message_id}/feedback")
def feedback(message_id: int, body: FeedbackIn, user=Depends(current_user)):
    """给一条回答打反馈：有用 / 没用 / 有错误。

    任务书第 4 节的「反馈值守」要靠这个入口收集真实用户反馈。
    """
    rows = execute(
        """SELECT m.id FROM chat_messages m JOIN apps a ON a.id = m.app_id
           WHERE m.id=? AND a.user_id=?""",
        (message_id, user["id"]), True,
    )
    if not rows:
        raise HTTPException(404, "message not found")
    execute(
        "UPDATE chat_messages SET rating=?, comment=? WHERE id=?",
        (body.rating, body.comment, message_id),
    )
    return {"ok": True, "message_id": message_id, "rating": body.rating}


@router.get("/apps/{app_id}/chat/history")
def history(app_id: int, limit: int = 20, user=Depends(current_user)):
    """最近的对话记录（给页面刷新后恢复用）。"""
    _owned_app(app_id, user["id"])
    rows = execute(
        """SELECT id, question, answer, references_json, rating, latency_ms, created_at
           FROM chat_messages WHERE app_id=? ORDER BY id DESC LIMIT ?""",
        (app_id, limit), True,
    )
    return {"items": [
        {
            "message_id": r["id"],
            "question": r["question"],
            "answer": r["answer"],
            "references": json.loads(r["references_json"] or "[]"),
            "rating": r["rating"],
            "latency_ms": r["latency_ms"],
            "created_at": r["created_at"],
        }
        for r in rows
    ][::-1]}
