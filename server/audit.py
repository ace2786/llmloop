"""审计日志：记录关键操作，谁在什么时候做了什么。

任务书第 4 节「谁在什么时候启动了哪个实验、批准了哪次发布、改了哪道题的标准答案」
和第 16 节都要求。这里只做「记录 + 查询」，不做拦截。

写日志一律不抛异常——审计失败不能把正常业务搞挂。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from .auth import current_user
from .db import connect, execute

router = APIRouter(tags=["audit"])


def log_action(
    user_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict | None = None,
) -> None:
    """写一条审计记录。任何异常都吞掉，只打印，不影响调用方。"""
    try:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO audit_logs (user_id, action, target_type, target_id, detail) "
                "VALUES (?,?,?,?,?)",
                (user_id, action, target_type, target_id,
                 json.dumps(detail, ensure_ascii=False) if detail else None),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"[audit] 写日志失败 {action}: {type(e).__name__} {e}")


@router.get("/audit-logs")
def list_audit_logs(limit: int = 50, action: str | None = None, user=Depends(current_user)):
    """当前用户自己的操作记录，最新的在前。"""
    limit = max(1, min(limit, 200))
    if action:
        rows = execute(
            "SELECT * FROM audit_logs WHERE user_id=? AND action=? ORDER BY id DESC LIMIT ?",
            (user["id"], action, limit), True,
        )
    else:
        rows = execute(
            "SELECT * FROM audit_logs WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user["id"], limit), True,
        )
    items = []
    for r in rows:
        d = dict(r)
        try:
            d["detail"] = json.loads(d["detail"]) if d["detail"] else None
        except (json.JSONDecodeError, TypeError):
            pass
        items.append(d)
    return {"items": items}
