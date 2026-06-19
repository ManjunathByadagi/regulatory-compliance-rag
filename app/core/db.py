import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from app.core.config import settings


class QueryAuditDB:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.query_log_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    review_flag INTEGER NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs(created_at)")

    def log_query(
        self,
        user_id: str,
        question: str,
        answer: str,
        confidence: float,
        latency_ms: int,
        status: str,
        review_flag: bool,
        sources: list[dict],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO query_logs
                (user_id, question, answer, confidence, latency_ms, status, review_flag, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    question,
                    answer,
                    confidence,
                    latency_ms,
                    status,
                    int(review_flag),
                    json.dumps(sources, ensure_ascii=True),
                    datetime.utcnow().isoformat(),
                ),
            )

    def get_recent_queries(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, question, answer, confidence, latency_ms, status, created_at FROM query_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def purge_old_logs(self, years: int = 7) -> int:
        cutoff = datetime.utcnow() - timedelta(days=years * 365)
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM query_logs WHERE created_at < ?", (cutoff.isoformat(),))
            return cursor.rowcount


class EvaluationDB:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.evaluation_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    context_precision REAL NOT NULL,
                    faithfulness REAL NOT NULL,
                    answer_relevance REAL NOT NULL,
                    context_recall REAL NOT NULL,
                    p50_latency REAL NOT NULL,
                    p95_latency REAL NOT NULL,
                    p99_latency REAL NOT NULL,
                    overall_score REAL NOT NULL,
                    failed_queries INTEGER NOT NULL,
                    notes_json TEXT NOT NULL
                )
                """
            )

    def add_run(self, payload: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_runs
                (run_date, context_precision, faithfulness, answer_relevance, context_recall,
                 p50_latency, p95_latency, p99_latency, overall_score, failed_queries, notes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_date"],
                    payload["context_precision"],
                    payload["faithfulness"],
                    payload["answer_relevance"],
                    payload["context_recall"],
                    payload["p50_latency"],
                    payload["p95_latency"],
                    payload["p99_latency"],
                    payload["overall_score"],
                    payload["failed_queries"],
                    json.dumps(payload.get("notes", {}), ensure_ascii=True),
                ),
            )

    def get_latest_runs(self, days: int = 7) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluation_runs ORDER BY id DESC LIMIT ?",
                (days,),
            ).fetchall()
        return [dict(row) for row in rows]
