import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from .db import execute

router = APIRouter(prefix="/auth", tags=["auth"])
TOKEN_TTL = timedelta(days=7)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _hash(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 120000).hex()}"


def _verify(pw, stored):
    return secrets.compare_digest(_hash(pw, stored.split("$", 1)[0]), stored)


def _token(user_id):
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + TOKEN_TTL).isoformat(timespec="seconds")
    execute("UPDATE users SET token=?, token_expires_at=? WHERE id=?", (token, expires, user_id))
    return token


class Credentials(BaseModel):
    email: str
    password: str


def current_user(authorization: str = Header(default="")) -> dict:
    raw = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    token = raw.strip()
    if not token:
        raise HTTPException(401, "missing token")
    rows = execute(
        "SELECT * FROM users WHERE token=? AND token_expires_at>?", (token, _now()), True
    )
    if not rows:
        raise HTTPException(401, "invalid or expired token")
    return dict(rows[0])


@router.post("/register")
def register(body: Credentials):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "invalid email")
    if len(body.password) < 8:
        raise HTTPException(400, "password must be >= 8 chars")
    try:
        uid = execute(
            "INSERT INTO users (email,password_hash) VALUES (?,?)",
            (email, _hash(body.password)),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "email already registered")
    return {"user_id": uid, "token": _token(uid)}


@router.post("/login")
def login(body: Credentials):
    rows = execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),), True)
    if not rows or not _verify(body.password, rows[0]["password_hash"]):
        raise HTTPException(401, "wrong email or password")
    uid = rows[0]["id"]
    return {"user_id": uid, "token": _token(uid)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


@router.post("/logout")
def logout(user: dict = Depends(current_user)):
    execute("UPDATE users SET token=NULL, token_expires_at=NULL WHERE id=?", (user["id"],))
    return {"ok": True}
