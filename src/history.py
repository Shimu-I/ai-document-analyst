"""Record of every conversion made through the web page (SQLite, one local file).

The file lives in ``~/.ai_document_analyst/history.db`` (override with the ``HISTORY_DB`` environment
variable). Only metadata is stored: file name, type, size, word and token counts, time taken, success or
error. Document text is never stored.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

COLUMNS = ["id", "ts", "filename", "ext", "kind", "doc_type", "size_bytes", "pages", "words", "tokens",
           "tables", "figures", "formulas", "warnings", "seconds", "ok", "error"]
SCHEMA = """CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,              -- local time, YYYY-MM-DD HH:MM:SS
    filename TEXT NOT NULL,
    ext TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    pages INTEGER,
    words INTEGER NOT NULL DEFAULT 0,
    tokens INTEGER NOT NULL DEFAULT 0,
    tables INTEGER NOT NULL DEFAULT 0,
    figures INTEGER NOT NULL DEFAULT 0,
    formulas INTEGER NOT NULL DEFAULT 0,
    warnings INTEGER NOT NULL DEFAULT 0,
    seconds REAL NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 1,
    error TEXT NOT NULL DEFAULT ''
)"""


def db_path() -> Path:
    env = os.getenv("HISTORY_DB")
    if env:
        return Path(env)
    home = Path.home() / ".ai_document_analyst"
    try:
        home.mkdir(parents=True, exist_ok=True)
        return home / "history.db"
    except OSError:                       # read-only home (some hosted environments)
        return Path(tempfile.gettempdir()) / "ai_document_analyst_history.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_success(result: dict[str, Any], size_bytes: int | None = None) -> None:
    """Store one finished conversion (the dict returned by ``service.process``)."""
    s, an = result["stats"], result["analysis"]
    name = result["filename"]
    row = (_now(), name, Path(name).suffix.lower().lstrip("."), s.get("kind", ""), an.get("doc_type", ""),
           int(size_bytes if size_bytes is not None else s.get("size_bytes") or 0), s.get("pages"),
           int(s.get("words") or 0), int(s.get("estimated_tokens") or 0), int(s.get("tables") or 0),
           int(s.get("figures") or 0), int(s.get("formulas") or 0), len(result.get("warnings") or []),
           float(result.get("elapsed") or s.get("seconds") or 0), 1, "")
    with _connect() as c:
        c.execute("INSERT INTO runs (ts, filename, ext, kind, doc_type, size_bytes, pages, words, tokens, tables,"
                  " figures, formulas, warnings, seconds, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)


def record_error(filename: str, message: str, size_bytes: int = 0, seconds: float = 0.0) -> None:
    with _connect() as c:
        c.execute("INSERT INTO runs (ts, filename, ext, size_bytes, seconds, ok, error) VALUES (?,?,?,?,?,0,?)",
                  (_now(), filename, Path(filename).suffix.lower().lstrip("."), int(size_bytes), float(seconds),
                   message[:500]))


def fetch() -> list[dict[str, Any]]:
    """All runs, newest first."""
    with _connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY id DESC")]


def count() -> int:
    with _connect() as c:
        return c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def clear() -> int:
    with _connect() as c:
        n = c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        c.execute("DELETE FROM runs")
        return n


def to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
