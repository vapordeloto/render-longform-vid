"""SQLite database utilities for async job tracking."""
import json
import os
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = os.getenv("DATABASE_PATH", "jobs.db")


async def init_db():
    """Initialize database and run migrations."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Run migration
        migration_file = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"
        if migration_file.exists():
            with open(migration_file, "r") as f:
                await db.executescript(f.read())

        # Migration 002: add title_text column if it isn't there yet.
        # Done in Python (rather than a raw .sql migration) so it stays
        # idempotent across restarts without relying on "ADD COLUMN IF NOT
        # EXISTS" SQLite version support.
        async with db.execute("PRAGMA table_info(jobs)") as cursor:
            existing_columns = [row[1] async for row in cursor]
        if "title_text" not in existing_columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN title_text TEXT")

        await db.commit()


async def create_job(
    job_id: str,
    audio_urls: List[str],
    background_source: str,
    background_urls: List[str],
    quality: str,
    title_text: Optional[str] = None,
) -> None:
    """Create a new job with pending status."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            INSERT INTO jobs (id, status, created_at, updated_at, audio_urls, background_source, background_urls, quality, title_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                "pending",
                now,
                now,
                json.dumps(audio_urls),
                background_source,
                json.dumps(background_urls),
                quality,
                title_text,
            ),
        )
        await db.commit()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a job by ID. Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            
            job = dict(row)
            # Parse JSON fields
            job["audio_urls"] = json.loads(job["audio_urls"])
            job["background_urls"] = json.loads(job["background_urls"])
            return job


async def update_job_status(job_id: str, status: str, error_message: Optional[str] = None) -> None:
    """Update job status and optionally set error message."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE jobs SET status = ?, updated_at = ?, error_message = ? WHERE id = ?",
            (status, now, error_message, job_id),
        )
        await db.commit()


async def update_job_result(
    job_id: str,
    result_url: str,
    duration_seconds: float,
    processing_time: float,
) -> None:
    """Mark job as completed and store result."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            UPDATE jobs 
            SET status = ?, updated_at = ?, result_url = ?, duration_seconds = ?, processing_time = ?
            WHERE id = ?
            """,
            ("completed", now, result_url, duration_seconds, processing_time, job_id),
        )
        await db.commit()


async def get_pending_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """Get pending jobs for processing."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            jobs = []
            for row in rows:
                job = dict(row)
                job["audio_urls"] = json.loads(job["audio_urls"])
                job["background_urls"] = json.loads(job["background_urls"])
                jobs.append(job)
            return jobs
"""SQLite database utilities for async job tracking."""
import json
import os
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = os.getenv("DATABASE_PATH", "jobs.db")


async def init_db():
    """Initialize database and run migrations."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Run migration
        migration_file = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"
        if migration_file.exists():
            with open(migration_file, "r") as f:
                await db.executescript(f.read())
        await db.commit()


async def create_job(
    job_id: str,
    audio_urls: List[str],
    background_source: str,
    background_urls: List[str],
    quality: str,
) -> None:
    """Create a new job with pending status."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            INSERT INTO jobs (id, status, created_at, updated_at, audio_urls, background_source, background_urls, quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                "pending",
                now,
                now,
                json.dumps(audio_urls),
                background_source,
                json.dumps(background_urls),
                quality,
            ),
        )
        await db.commit()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a job by ID. Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            
            job = dict(row)
            # Parse JSON fields
            job["audio_urls"] = json.loads(job["audio_urls"])
            job["background_urls"] = json.loads(job["background_urls"])
            return job


async def update_job_status(job_id: str, status: str, error_message: Optional[str] = None) -> None:
    """Update job status and optionally set error message."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE jobs SET status = ?, updated_at = ?, error_message = ? WHERE id = ?",
            (status, now, error_message, job_id),
        )
        await db.commit()


async def update_job_result(
    job_id: str,
    result_url: str,
    duration_seconds: float,
    processing_time: float,
) -> None:
    """Mark job as completed and store result."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            UPDATE jobs 
            SET status = ?, updated_at = ?, result_url = ?, duration_seconds = ?, processing_time = ?
            WHERE id = ?
            """,
            ("completed", now, result_url, duration_seconds, processing_time, job_id),
        )
        await db.commit()


async def get_pending_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """Get pending jobs for processing."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            jobs = []
            for row in rows:
                job = dict(row)
                job["audio_urls"] = json.loads(job["audio_urls"])
                job["background_urls"] = json.loads(job["background_urls"])
                jobs.append(job)
            return jobs
