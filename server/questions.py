import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import current_user
from .db import connect, execute

router = APIRouter(prefix="/apps/{app_id}/questions", tags=["questions"])

SPLITS = ("optimize", "valid", "test")
RATIO = (0.6, 0.2, 0.2)


class ImportPayload(BaseModel):
    items: list = Field(default_factory=list)
    raw_text: str = ""
    replace: bool = True
    seed: int | None = None


def _app_or_404(app_id: int, user_id: int) -> None:
    if not execute("SELECT 1 FROM apps WHERE id=? AND user_id=?", (app_id, user_id), True):
        raise HTTPException(404, "app not found")


def _counts(app_id: int) -> dict:
    rows = execute(
        "SELECT split, COUNT(*) AS n FROM questions WHERE app_id=? GROUP BY split", (app_id,), True
    )
    out = {"optimize": 0, "valid": 0, "test": 0, "total": 0}
    for r in rows:
        out[r["split"]] = r["n"]
        out["total"] += r["n"]
    return out


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _where(app_id: int, split: str, q: str) -> tuple[str, list]:
    sql = "FROM questions WHERE app_id = ?"
    params = [app_id]
    if split:
        sql += " AND split = ?"
        params.append(split)
    if q:
        sql += (
            " AND (lower(content) LIKE ? ESCAPE '\\'"
            " OR lower(COALESCE(reference, '')) LIKE ? ESCAPE '\\')"
        )
        kw = f"%{_escape_like(q.strip().lower())}%"
        params += [kw, kw]
    return sql, params


def _sizes(n: int) -> tuple[int, int, int]:
    if n < 3:
        return n, 0, 0
    a = max(1, round(n * RATIO[0]))
    b = max(1, round(n * RATIO[1]))
    c = n - a - b
    if c < 1:
        a, c = n - 2, 1
    return a, b, c


def _normalize(payload: ImportPayload) -> list[tuple[str, str]]:
    out, seen = [], set()
    for it in payload.items:
        if isinstance(it, str):
            content, ref = it, ""
        elif isinstance(it, dict):
            content, ref = it.get("content", ""), it.get("reference", "")
        else:
            content, ref = getattr(it, "content", ""), getattr(it, "reference", "")
        content = (content or "").strip()
        if not content or content in seen:
            continue
        seen.add(content)
        out.append((content, (ref or "").strip()))
    for line in payload.raw_text.splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            out.append((line, ""))
    return out


@router.post("/import")
def import_questions(app_id: int, payload: ImportPayload, user: dict = Depends(current_user)):
    _app_or_404(app_id, user["id"])
    rows = _normalize(payload)
    if not rows:
        raise HTTPException(400, "no valid questions")
    seed = payload.seed if payload.seed is not None else app_id * 1000 + len(rows)
    rng = random.Random(seed)
    rng.shuffle(rows)
    a, b, _ = _sizes(len(rows))
    labels = ["optimize"] * a + ["valid"] * b + ["test"] * (len(rows) - a - b)
    conn = connect()
    try:
        with conn:
            if payload.replace:
                conn.execute("DELETE FROM questions WHERE app_id=?", (app_id,))
            conn.executemany(
                "INSERT INTO questions (app_id,split,content,reference) VALUES (?,?,?,?)",
                [(app_id, s, c, r) for (c, r), s in zip(rows, labels)],
            )
    finally:
        conn.close()
    return {"imported": len(rows), "seed": seed, "splits": _counts(app_id)}


@router.get("")
def list_questions(
    app_id: int,
    split: str = Query(default=""),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(current_user),
):
    _app_or_404(app_id, user["id"])
    if split and split not in SPLITS:
        raise HTTPException(400, "split must be optimize/valid/test")
    where, params = _where(app_id, split, q)
    rows = execute(
        f"SELECT * {where} ORDER BY id LIMIT ? OFFSET ?", (*params, limit, offset), True
    )
    matched = execute(f"SELECT COUNT(*) AS n {where}", tuple(params), True)[0]["n"]
    counts = _counts(app_id)
    return {
        "total": counts["total"],
        "splits": counts,
        "matched": matched,
        "items": [dict(r) for r in rows],
    }


@router.get("/stats")
def question_stats(app_id: int, user: dict = Depends(current_user)):
    _app_or_404(app_id, user["id"])
    return _counts(app_id)


@router.delete("")
def clear_questions(app_id: int, split: str = "", user: dict = Depends(current_user)):
    _app_or_404(app_id, user["id"])
    if split:
        if split not in SPLITS:
            raise HTTPException(400, "split must be optimize/valid/test")
        execute("DELETE FROM questions WHERE app_id=? AND split=?", (app_id, split))
    else:
        execute("DELETE FROM questions WHERE app_id=?", (app_id,))
    return _counts(app_id)


@router.delete("/{question_id}")
def delete_question(app_id: int, question_id: int, user: dict = Depends(current_user)):
    _app_or_404(app_id, user["id"])
    if not execute(
        "SELECT 1 FROM questions WHERE id=? AND app_id=?", (question_id, app_id), True
    ):
        raise HTTPException(404, "question not found")
    execute("DELETE FROM questions WHERE id=?", (question_id,))
    return {"deleted": question_id, "splits": _counts(app_id)}
