import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    token TEXT UNIQUE,
    token_expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    app_key TEXT NOT NULL UNIQUE,
    base_url TEXT,
    model TEXT,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    split TEXT NOT NULL CHECK (split IN ('optimize', 'valid', 'test')),
    content TEXT NOT NULL,
    reference TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_apps_user ON apps(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_app_split ON questions(app_id, split);

-- 评测任务：一次评测 = 一行。status 五态：pending/running/done/failed/canceled
CREATE TABLE IF NOT EXISTS eval_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id       INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    model        TEXT NOT NULL,
    split        TEXT NOT NULL DEFAULT 'test',
    topk         INTEGER NOT NULL DEFAULT 3,
    status       TEXT NOT NULL DEFAULT 'pending',
    total        INTEGER NOT NULL DEFAULT 0,
    correct      INTEGER NOT NULL DEFAULT 0,
    partial      INTEGER NOT NULL DEFAULT 0,
    wrong        INTEGER NOT NULL DEFAULT 0,
    strict_acc   REAL,
    loose_acc    REAL,
    duration_sec REAL,
    error        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT
);

-- 逐题结果：一次评测 = 多行。verdict 三态：对/部分对/错
CREATE TABLE IF NOT EXISTS eval_cases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question_id  INTEGER,
    question     TEXT NOT NULL,
    reference    TEXT,
    answer       TEXT,
    verdict      TEXT,
    reason       TEXT,
    source       TEXT,
    doc_location TEXT,
    latency_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_runs_app ON eval_runs(app_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_run ON eval_cases(run_id);

-- 助手对话记录：被测应用的问答，带用户反馈（有用/没用/有错误）
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    answer          TEXT,
    references_json TEXT,
    rating          TEXT,
    comment         TEXT,
    latency_ms      INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_app ON chat_messages(app_id, created_at DESC);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute(sql, params=(), fetch=False):
    conn = connect()
    try:
        cur = conn.execute(sql, params)
        out = cur.fetchall() if fetch else cur.lastrowid
        conn.commit()
        return out
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # 迁移：老库的 questions 表没有 source 列，补上（题目来源：real-issue / doc-synth 等）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)")]
        if "source" not in cols:
            conn.execute("ALTER TABLE questions ADD COLUMN source TEXT")
        conn.commit()
    finally:
        conn.close()
