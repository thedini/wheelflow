"""
Database module for WheelFlow job persistence.

Uses SQLite for simplicity - jobs survive server restarts.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database file location
DB_PATH = Path(__file__).parent.parent / "data" / "wheelflow.db"


def ensure_db_dir():
    """Ensure the data directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                config TEXT,
                results TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                batch_id TEXT,
                batch_yaw_angles TEXT,
                yaw_angle REAL
            )
        ''')
        conn.commit()


def job_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a database row to a job dictionary."""
    job = dict(row)
    # Parse JSON fields
    if job.get('config'):
        job['config'] = json.loads(job['config'])
    if job.get('results'):
        job['results'] = json.loads(job['results'])
    if job.get('batch_yaw_angles'):
        job['batch_yaw_angles'] = json.loads(job['batch_yaw_angles'])
    return job


def create_job(job_id: str, config: Dict[str, Any], batch_id: Optional[str] = None,
               batch_yaw_angles: Optional[List[float]] = None, yaw_angle: Optional[float] = None) -> Dict[str, Any]:
    """Create a new job in the database."""
    now = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO jobs (id, status, config, created_at, updated_at, batch_id, batch_yaw_angles, yaw_angle)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id,
            'pending',
            json.dumps(config),
            now,
            now,
            batch_id,
            json.dumps(batch_yaw_angles) if batch_yaw_angles else None,
            yaw_angle
        ))
        conn.commit()

    return get_job(job_id)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
        row = cursor.fetchone()
        if row:
            return job_to_dict(row)
    return None


def get_all_jobs() -> List[Dict[str, Any]]:
    """Get all jobs."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC')
        return [job_to_dict(row) for row in cursor.fetchall()]


def update_job(job_id: str, **updates) -> Optional[Dict[str, Any]]:
    """Update a job with the given fields."""
    now = datetime.utcnow().isoformat()

    # Build update query
    fields = ['updated_at = ?']
    values = [now]

    for key, value in updates.items():
        if key in ('config', 'results', 'batch_yaw_angles'):
            value = json.dumps(value) if value is not None else None
        fields.append(f'{key} = ?')
        values.append(value)

    values.append(job_id)

    with get_db_connection() as conn:
        conn.execute(
            f'UPDATE jobs SET {", ".join(fields)} WHERE id = ?',
            values
        )
        conn.commit()

    return get_job(job_id)


def update_job_status(job_id: str, status: str, **extra_fields) -> Optional[Dict[str, Any]]:
    """Update job status with optional additional fields."""
    updates = {'status': status}

    if status == 'running' and 'started_at' not in extra_fields:
        extra_fields['started_at'] = datetime.utcnow().isoformat()
    elif status in ('complete', 'failed') and 'completed_at' not in extra_fields:
        extra_fields['completed_at'] = datetime.utcnow().isoformat()

    updates.update(extra_fields)
    return update_job(job_id, **updates)


def set_job_results(job_id: str, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Set job results and mark as complete."""
    return update_job_status(job_id, 'complete', results=results)


def set_job_error(job_id: str, error: str) -> Optional[Dict[str, Any]]:
    """Set job error and mark as failed."""
    return update_job_status(job_id, 'failed', error=error)


def delete_job(job_id: str) -> bool:
    """Delete a job from the database."""
    with get_db_connection() as conn:
        cursor = conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        conn.commit()
        return cursor.rowcount > 0


def job_exists(job_id: str) -> bool:
    """Check if a job exists."""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT 1 FROM jobs WHERE id = ?', (job_id,))
        return cursor.fetchone() is not None


# Initialize database on module import
init_db()
