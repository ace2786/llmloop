"""审计日志查询接口。

写入逻辑在 lib/audit.py（那边不依赖 fastapi，优化循环脚本也能用）；
这里只做路由和查询。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from lib.audit import log_action  # noqa: F401  对外仍可从 server.audit 导入

from .auth import current_user
from .db import execute

router = APIRouter(tags=["audit"])


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
