"""优化循环的查询接口：实验列表 + 单次实验详情（含每一轮）。

设计要点：
  - 只读。跑循环现在由 scripts/loop_min.py 触发，接口不负责启动——
    循环要加载重排模型、跑几百次模型调用，塞进 HTTP 请求里不合适。
  - 配置和诊断都存成 JSON 字符串，接口返回时解析成对象，前端不用再解一层。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from .auth import current_user
from .db import execute

router = APIRouter(tags=["optimization"])


def _owned_app(app_id: int, user_id: int) -> dict:
    rows = execute(
        "SELECT * FROM apps WHERE id=? AND user_id=?", (app_id, user_id), True
    )
    if not rows:
        raise HTTPException(404, "app not found")
    return dict(rows[0])


def _owned_run(run_id: int, user_id: int) -> dict:
    rows = execute(
        """SELECT r.* FROM opt_runs r JOIN apps a ON a.id = r.app_id
           WHERE r.id=? AND a.user_id=?""",
        (run_id, user_id), True,
    )
    if not rows:
        raise HTTPException(404, "optimization run not found")
    return dict(rows[0])


def _loads(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


@router.get("/apps/{app_id}/opt-runs")
def list_opt_runs(app_id: int, limit: int = 20, user=Depends(current_user)):
    """某应用的优化实验列表，最新的在前。"""
    _owned_app(app_id, user["id"])
    limit = max(1, min(limit, 100))
    rows = execute(
        "SELECT * FROM opt_runs WHERE app_id=? ORDER BY id DESC LIMIT ?",
        (app_id, limit), True,
    )
    items = []
    for r in rows:
        d = dict(r)
        items.append({
            "run_id": d["id"],
            "status": d["status"],
            "base_config": _loads(d["base_config"]),
            "best_config": _loads(d["best_config"]),
            "base_score": d["base_score"],
            "best_score": d["best_score"],
            "best_valid": d["best_valid"],
            "rounds_done": d["rounds_done"],
            "rounds_planned": d["rounds_planned"],
            "stop_reason": d["stop_reason"],
            "created_at": d["created_at"],
            "finished_at": d["finished_at"],
        })
    return {"items": items}


@router.get("/opt-runs/{run_id}")
def opt_run_detail(run_id: int, user=Depends(current_user)):
    """单次实验详情：概览 + 每一轮的候选、理由、成绩、决策。"""
    run = _owned_run(run_id, user["id"])
    rows = execute(
        "SELECT * FROM opt_rounds WHERE opt_run_id=? ORDER BY round_no", (run_id,), True
    )
    rounds = []
    for r in rows:
        d = dict(r)
        rounds.append({
            "round_no": d["round_no"],
            "config": _loads(d["config"]),
            "reason": d["reason"],
            "expect": d["expect"],
            "diagnosis": _loads(d["diag_json"]),
            "opt_score": d["opt_score"],
            "opt_delta": d["opt_delta"],
            "valid_score": d["valid_score"],
            "valid_delta": d["valid_delta"],
            "decision": d["decision"],
            "decision_note": d["decision_note"],
            "created_at": d["created_at"],
        })
    return {
        "run_id": run["id"],
        "app_id": run["app_id"],
        "status": run["status"],
        "base_config": _loads(run["base_config"]),
        "best_config": _loads(run["best_config"]),
        "base_score": run["base_score"],
        "best_score": run["best_score"],
        "best_valid": run["best_valid"],
        "rounds_done": run["rounds_done"],
        "rounds_planned": run["rounds_planned"],
        "stop_reason": run["stop_reason"],
        "created_at": run["created_at"],
        "finished_at": run["finished_at"],
        "rounds": rounds,
    }
