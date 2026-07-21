"""Longform video rendering endpoints - async processing with status polling."""
import logging
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from utils.auth import get_api_key
from utils.db import create_job, get_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/longform", tags=["longform"])


# --- Request / Response models ---


class LongformRenderRequest(BaseModel):
    audio_urls: List[str] = Field(..., min_length=1, max_length=30)
    background_source: str = Field(..., pattern="^(images|videos)$")
    background_urls: List[str] = Field(...)
    quality: str = Field(default="1080", pattern="^(720|1080)$")
    title_text: Optional[str] = Field(
        default=None,
        max_length=200,
        description=(
            "Optional title/tema text. If provided, it is overlaid on the "
            "video only during the first few seconds (fading in/out); the "
            "rest of the video shows just the plain background."
        ),
    )

    @field_validator("audio_urls")
    @classmethod
    def validate_audio_urls(cls, v: List[str]) -> List[str]:
        if not v or len(v) < 1 or len(v) > 30:
            raise ValueError("Provide between 1 and 30 audio URLs")
        
        url_re = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
        for i, u in enumerate(v):
            u = (u or "").strip()
            if not u or not url_re.match(u):
                raise ValueError(f"Invalid audio URL at index {i}: {u!r}")
        return [u.strip() for u in v]

    @field_validator("background_urls")
    @classmethod
    def validate_background_urls(cls, v: List[str], info) -> List[str]:
        # Get background_source from the context
        data = info.data
        background_source = data.get("background_source")
        
        if background_source == "images":
            if len(v) < 1 or len(v) > 15:
                raise ValueError("For images: provide between 1 and 15 URLs")
        elif background_source == "videos":
            if len(v) < 1 or len(v) > 5:
                raise ValueError("For videos: provide between 1 and 5 URLs")
        
        url_re = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
        for i, u in enumerate(v):
            u = (u or "").strip()
            if not u or not url_re.match(u):
                raise ValueError(f"Invalid background URL at index {i}: {u!r}")
        
        return [u.strip() for u in v]


class LongformRenderResponse(BaseModel):
    success: bool = True
    request_id: str
    message: str = "Render job queued. Use the request_id to check status."


class JobStatusResponse(BaseModel):
    request_id: str
    status: str
    created_at: str
    updated_at: str
    error_message: Optional[str] = None


class JobResultResponse(BaseModel):
    request_id: str
    status: str
    result_url: str
    duration_seconds: float
    processing_time: float
    # Original request data
    audio_urls: List[str]
    background_source: str
    background_urls: List[str]
    quality: str
    title_text: Optional[str] = None


# --- Endpoints ---


@router.post("/render", response_model=LongformRenderResponse)
async def render_longform_video(
    body: LongformRenderRequest,
    _api_key: str = Depends(get_api_key),
) -> LongformRenderResponse:
    """
    Queue a longform video render job.
    
    - **audio_urls**: 1-30 audio file URLs (will be concatenated)
    - **background_source**: Either 'images' or 'videos'
    - **background_urls**: 1-15 image URLs or 1-5 video URLs (depending on background_source)
    - **quality**: '720' or '1080' (default: '1080')
    
    The final video will:
    - Have a fixed 16:9 aspect ratio
    - Match the total length of the combined audio (capped at 2 hours)
    - Loop/cycle background media to match audio duration
    - Mute any background videos
    
    Returns a request_id to poll for status and retrieve the result.
    """
    request_id = f"req_{uuid.uuid4().hex}"
    
    try:
        await create_job(
            job_id=request_id,
            audio_urls=body.audio_urls,
            background_source=body.background_source,
            background_urls=body.background_urls,
            quality=body.quality,
            title_text=body.title_text,
        )
    except Exception as e:
        logger.exception(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue render job: {str(e)}",
        )
    
    return LongformRenderResponse(request_id=request_id)


@router.get("/status/{request_id}", response_model=JobStatusResponse)
async def get_render_status(
    request_id: str,
    _api_key: str = Depends(get_api_key),
) -> JobStatusResponse:
    """
    Check the status of a render job.
    
    Status values:
    - **pending**: Job is queued but not yet started
    - **processing**: Job is currently being processed
    - **completed**: Job finished successfully (use /result endpoint to get the video)
    - **failed**: Job failed (check error_message)
    """
    job = await get_job(request_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        request_id=job["id"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        error_message=job.get("error_message"),
    )


@router.get("/result/{request_id}", response_model=JobResultResponse)
async def get_render_result(
    request_id: str,
    _api_key: str = Depends(get_api_key),
) -> JobResultResponse:
    """
    Get the result of a completed render job.
    
    This endpoint only returns data for completed jobs.
    Use /status endpoint first to check if the job is completed.
    """
    job = await get_job(request_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}",
        )
    
    return JobResultResponse(
        request_id=job["id"],
        status=job["status"],
        result_url=job["result_url"],
        duration_seconds=job["duration_seconds"],
        processing_time=job["processing_time"],
        # Include original request data
        audio_urls=job["audio_urls"],
        background_source=job["background_source"],
        background_urls=job["background_urls"],
        quality=job["quality"],
        title_text=job.get("title_text"),
    )
