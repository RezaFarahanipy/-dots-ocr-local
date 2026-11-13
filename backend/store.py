import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "data" / "jobs.sqlite3"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)

def create_job(job_id, filename, source_path):
    with connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, filename, source_path, status, progress, created_at) VALUES (?, ?, ?, 'queued', 0, ?)",
            (job_id, filename, source_path, datetime.now(timezone.utc).isoformat())
        )

def update_job(job_id, **fields):
    allowed = {"status", "progress", "result_json", "error"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    query = ", ".join(f"{key}=?" for key in fields)
    values = list(fields.values()) + [job_id]
    with connect() as conn:
        conn.execute(f"UPDATE jobs SET {query} WHERE id=?", values)

def _serialize(row):
    item = dict(row)
    if item.get("result_json"):
        try:
            item["result"] = json.loads(item["result_json"])
        except Exception:
            item["result"] = None
    return item

def get_job(job_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _serialize(row) if row else None

def list_jobs(limit=30):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_serialize(row) for row in rows]
