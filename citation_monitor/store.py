"""SQLite run history: every weekly run is stored so the digest can diff
against the previous run and draw a score trend across weeks.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone


def iso_week(dt: datetime | None = None) -> str:
    d = (dt or datetime.now(timezone.utc)).date().isocalendar()
    return f"{d.year}-W{d.week:02d}"


def prev_week_label(weeks_back: int = 1) -> str:
    return iso_week(datetime.now(timezone.utc) - timedelta(days=7 * weeks_back))


def connect(path: str) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            week TEXT NOT NULL,
            mode TEXT NOT NULL,
            brand TEXT NOT NULL,
            engines TEXT NOT NULL,
            tokens_est INTEGER NOT NULL DEFAULT 0,
            citation_rate REAL NOT NULL DEFAULT 0,
            sov REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS results (
            run_id INTEGER NOT NULL,
            engine TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            locale TEXT NOT NULL,
            style TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            brand_mentioned INTEGER NOT NULL,
            brand_pos INTEGER NOT NULL,
            brand_alias TEXT NOT NULL,
            brand_fuzzy INTEGER NOT NULL,
            competitors TEXT NOT NULL,
            tokens_est INTEGER NOT NULL DEFAULT 0,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
        """
    )
    conn.commit()


def save_run(conn, meta: dict, rows: list) -> int:
    cur = conn.execute(
        "INSERT INTO runs (created_at, week, mode, brand, engines, tokens_est, citation_rate, sov)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            meta["created_at"], meta["week"], meta["mode"], meta["brand"],
            json.dumps(meta["engines"]), meta.get("tokens_est", 0),
            meta.get("citation_rate", 0.0), meta.get("sov", 0.0),
        ),
    )
    run_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO results (run_id, engine, model, prompt_id, prompt_text, locale, style,"
        " raw_text, brand_mentioned, brand_pos, brand_alias, brand_fuzzy, competitors,"
        " tokens_est, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                run_id, r["engine"], r["model"], r["prompt_id"], r["prompt_text"],
                r["locale"], r["style"], r["raw_text"], int(r["brand_mentioned"]),
                r["brand_pos"], r["brand_alias"], int(r["brand_fuzzy"]),
                json.dumps(r["competitors"]), r.get("tokens_est", 0), r.get("error"),
            )
            for r in rows
        ],
    )
    conn.commit()
    return run_id


def has_run(conn, week: str, mode: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM runs WHERE week = ? AND mode = ? LIMIT 1", (week, mode)
    ).fetchone()
    return row is not None


def latest_run(conn, mode: str | None = None):
    q = "SELECT * FROM runs"
    args = []
    if mode:
        q += " WHERE mode = ?"
        args.append(mode)
    q += " ORDER BY id DESC LIMIT 1"
    return conn.execute(q, args).fetchone()


def previous_run(conn, run_id: int, mode: str | None = None):
    q = "SELECT * FROM runs WHERE id < ?"
    args = [run_id]
    if mode:
        q += " AND mode = ?"
        args.append(mode)
    q += " ORDER BY id DESC LIMIT 1"
    return conn.execute(q, args).fetchone()


def get_rows(conn, run_id: int) -> list:
    rows = []
    for r in conn.execute("SELECT * FROM results WHERE run_id = ? ORDER BY id", (run_id,)):
        rows.append({
            "engine": r["engine"], "model": r["model"], "prompt_id": r["prompt_id"],
            "prompt_text": r["prompt_text"], "locale": r["locale"], "style": r["style"],
            "raw_text": r["raw_text"], "brand_mentioned": bool(r["brand_mentioned"]),
            "brand_pos": r["brand_pos"], "brand_alias": r["brand_alias"],
            "brand_fuzzy": bool(r["brand_fuzzy"]),
            "competitors": json.loads(r["competitors"]),
            "tokens_est": r["tokens_est"], "error": r["error"],
        })
    return rows


def history(conn, mode: str | None = None, limit: int = 12) -> list:
    q = "SELECT id, week, created_at, mode, citation_rate, sov FROM runs"
    args = []
    if mode:
        q += " WHERE mode = ?"
        args.append(mode)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    out = list(conn.execute(q, args))
    out.reverse()
    return out
