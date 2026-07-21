"""Background worker for processing async longform video jobs."""
import asyncio
import logging
import tempfile
import time
import uuid
from pathlib import Path

from utils.db import get_pending_jobs, update_job_status, update_job_result
from utils.longform_processor import process_longform_video
from utils.storage import upload_merged_video

logger = logging.getLogger(__name__)

WORKER_POLL_INTERVAL = 5  # seconds
WORKER_ENABLED = True


async def process_job(job: dict) -> None:
    """Process a single job."""
    job_id = job["id"]
    logger.info(f"Processing job {job_id}")
    
    # Update status to processing
    await update_job_status(job_id, "processing")
    
    start_time = time.perf_counter()
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Process the video in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        output_path, duration = await loop.run_in_executor(
            None,  # Use default thread pool
            process_longform_video,
            job["audio_urls"],
            job["background_source"],
            job["background_urls"],
            job["quality"],
            temp_dir,
            job.get("title_text"),
        )
        
        # Upload result (also blocking, run in thread pool)
        result_url = await loop.run_in_executor(
            None,
            upload_merged_video,
            output_path,
            f"longform-{job_id[:12]}",
        )
        
        processing_time = time.perf_counter() - start_time
        
        # Update job with result
        await update_job_result(
            job_id=job_id,
            result_url=result_url,
            duration_seconds=duration,
            processing_time=processing_time,
        )
        
        logger.info(f"Job {job_id} completed successfully in {processing_time:.2f}s")
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        await update_job_status(
            job_id=job_id,
            status="failed",
            error_message=str(e)[:500],
        )
    finally:
        # Cleanup temp files
        for f in (temp_dir.iterdir() if temp_dir.exists() else []):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


async def worker_loop():
    """Main worker loop - polls for pending jobs and processes them."""
    logger.info("Background worker started")
    
    while WORKER_ENABLED:
        try:
            # Get pending jobs
            jobs = await get_pending_jobs(limit=1)
            
            if jobs:
                for job in jobs:
                    await process_job(job)
            else:
                # No jobs, wait before polling again
                await asyncio.sleep(WORKER_POLL_INTERVAL)
                
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(WORKER_POLL_INTERVAL)


def start_worker_background():
    """Start the worker in the background as an asyncio task."""
    asyncio.create_task(worker_loop())
    logger.info("Worker task created")
