"""审计日志的写入函数。

**为什么单独放 lib/ 而不是 server/：**
优化循环脚本跑在 comfyvenv（有 torch，用于重排），那里没有 fastapi；
而 server/audit.py 要 import fastapi 才能定义路由。所以把纯写入逻辑抽到这里，
server 和脚本都从这里导入，谁也不用迁就谁。

写日志一律不抛异常——审计失败不能把正常业务搞挂。
"""
from __future__ import annotations

import json

from server.db import connect


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
