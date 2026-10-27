import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import current_user
from .db import execute

router = APIRouter(prefix="/apps", tags=["apps"])


class AppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    base_url: str = ""
    model: str = ""
    description: str = ""


def _owned(app_id: int, user_id: int) -> dict:
    rows = execute("SELECT * FROM apps WHERE id=? AND user_id=?", (app_id, user_id), True)
    if not rows:
        raise HTTPException(404, "app not found")
    return dict(rows[0])


def _counts(app_id: int) -> dict:
    rows = execute(
        "SELECT split, COUNT(*) AS n FROM questions WHERE app_id=? GROUP BY split", (app_id,), True
    )
    out = {"optimize": 0, "valid": 0, "test": 0, "total": 0}
    for r in rows:
        out[r["split"]] = r["n"]
        out["total"] += r["n"]
    return out


def _detail(app_id: int, user_id: int) -> dict:
    return {**_owned(app_id, user_id), "questions": _counts(app_id)}


@router.post("")
def create_app(body: AppCreate, user: dict = Depends(current_user)):
    app_key = "sk-" + secrets.token_urlsafe(24)
    app_id = execute(
        "INSERT INTO apps (user_id,name,app_key,base_url,model,description) VALUES (?,?,?,?,?,?)",
        (
            user["id"],
            body.name.strip(),
            app_key,
            body.base_url.strip(),
            body.model.strip(),
            body.description.strip(),
        ),
    )
    return _detail(app_id, user["id"])


@router.get("")
def list_apps(user: dict = Depends(current_user)):
    rows = execute("SELECT * FROM apps WHERE user_id=? ORDER BY id DESC", (user["id"],), True)
    return [{**dict(r), "questions": _counts(r["id"])} for r in rows]


@router.get("/{app_id}")
def get_app(app_id: int, user: dict = Depends(current_user)):
    return _detail(app_id, user["id"])


@router.delete("/{app_id}")
def delete_app(app_id: int, user: dict = Depends(current_user)):
    _owned(app_id, user["id"])
    execute("DELETE FROM apps WHERE id=?", (app_id,))
    return {"deleted": app_id}
