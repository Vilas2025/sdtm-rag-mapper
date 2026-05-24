"""
Feedback Store
--------------
Logs human-in-the-loop decisions on SDTM mapping suggestions.
This is the data that, in production, would feed back into:
  - Fine-tuning or retrieval reweighting
  - Accuracy metrics tracked over time
  - Audit trails for regulatory submissions
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "feedback.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    raw_variable_name TEXT NOT NULL,
    raw_variable_description TEXT,
    suggested_domain TEXT,
    suggested_variable TEXT,
    suggested_confidence REAL,
    final_domain TEXT,
    final_variable TEXT,
    decision TEXT NOT NULL CHECK(decision IN ('accept', 'edit', 'reject')),
    reviewer_note TEXT,
    full_suggestion_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_feedback_decision ON feedback(decision);
CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
"""


def init_db() -> None:
    """Create the database and tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def log_feedback(
    raw_variable: Dict[str, Any],
    suggestion: Dict[str, Any],
    decision: str,
    final_domain: Optional[str] = None,
    final_variable: Optional[str] = None,
    reviewer_note: Optional[str] = None,
) -> int:
    """
    Log a reviewer's decision on a mapping suggestion.

    decision: 'accept' (use suggested as-is), 'edit' (corrected to final_*),
              or 'reject' (no good mapping).
    Returns the inserted row id.
    """
    if decision not in ("accept", "edit", "reject"):
        raise ValueError(f"Invalid decision: {decision}")

    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO feedback (
                timestamp, raw_variable_name, raw_variable_description,
                suggested_domain, suggested_variable, suggested_confidence,
                final_domain, final_variable, decision, reviewer_note,
                full_suggestion_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                raw_variable.get("name", ""),
                raw_variable.get("description", ""),
                suggestion.get("domain_code"),
                suggestion.get("variable_name"),
                suggestion.get("confidence"),
                final_domain or suggestion.get("domain_code"),
                final_variable or suggestion.get("variable_name"),
                decision,
                reviewer_note,
                json.dumps(suggestion, default=str),
            ),
        )
        return cursor.lastrowid


def get_all_feedback() -> List[Dict[str, Any]]:
    """Retrieve all logged feedback."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> Dict[str, Any]:
    """Compute summary metrics over logged feedback."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        accepted = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE decision='accept'"
        ).fetchone()[0]
        edited = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE decision='edit'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE decision='reject'"
        ).fetchone()[0]
        avg_conf = conn.execute(
            "SELECT AVG(suggested_confidence) FROM feedback"
        ).fetchone()[0] or 0.0

    acceptance_rate = (accepted / total) if total else 0.0
    return {
        "total_reviews": total,
        "accepted": accepted,
        "edited": edited,
        "rejected": rejected,
        "acceptance_rate": round(acceptance_rate, 3),
        "avg_suggested_confidence": round(float(avg_conf), 3),
    }
