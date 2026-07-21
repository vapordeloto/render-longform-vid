"""Longform video processor - creates videos from audio + background images/videos."""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, unquote
import httpx
import time

from utils.storage import BUCKET, ENDPOINT, get_client

MAX_LONGFORM_DURATION_SECONDS = 7200  # 2 hours
DOWNLOAD_TIMEOUT = 300  # 5 min per file

# --- Title overlay (drawtext) config ---
# Text is only shown for the first few seconds of the video; the rest of the
# video shows just the plain background image/video, per product requirement.
TITLE_OVERLAY_DURATION_SECONDS = 6
TITLE_FADE_SECONDS = 0.6
TITLE_FONT_SIZE = 64
# Resolved via fontconfig at render time (requires "fontconfig" + "dejavu_fonts"
# nix packages in nixpacks.toml). DejaVu Sans covers Spanish accented characters
# (Ã¡ Ã© Ã­ Ã³ Ãº Ã± Â¿ Â¡).
TITLE_FONT_FAMILY = "DejaVu Sans Bold"


def _escape_drawtext(text: str) -> str:
    """
    Escape a raw string for safe use as ffmpeg drawtext's text= value.
    Order matters: backslash first, then the other special characters.
    """
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def _title_overlay_filter(src_label: str, dst_label: str, title_text: Optional[str]) -> str:
    """
    Build the filter_complex segment that overlays `title_text` on top of
    `src_label`, fading in/out, visible only during the first
    TITLE_OVERLAY_DURATION_SECONDS seconds, and outputs it as `dst_label`.

    If title_text is empty/None, just passes the video through unchanged.
    """
    if not title_text:
        return f"[{src_label}]null[{dst_label}]"

    escaped = _escape_drawtext(title_text)
    fade_expr = (
        f"if(lt(t,{TITLE_FADE_SECONDS}),t/{TITLE_FADE_SECONDS},"
        f"if(lt(t,{TITLE_OVERLAY_DURATION_SECONDS - TITLE_FADE_SECONDS}),1,"
        f"if(lt(t,{TITLE_OVERLAY_DURATION_SECONDS}),"
        f"({TITLE_OVERLAY_DURATION_SECONDS}-t)/{TITLE_FADE_SECONDS},0)))"
    )
    return (
        f"[{src_label}]drawtext=font='{TITLE_FONT_FAMILY}':text='{escaped}':"
        f"fontcolor=white:fontsize={TITLE_FONT_SIZE}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"box=1:boxcolor=black@0.35:boxborderw=24:"
        f"alpha='{fade_expr}':"
        f"enable='between(t,0,{TITLE_OVERLAY_DURATION_SECONDS})'[{dst_label}]"
    )


def _bucket_key_from_url(url: str) -> Optional[str]:
    """
    If url points at our own private storage bucket/endpoint, return the
    object key inside the bucket. Otherwise return None.

    Our Railway bucket is never publicly readable, so plain HTTP GETs to it
    come back 403. When we recognize one of our own bucket URLs we fetch it
    via a presigned S3 URL instead (signed using the storage credentials
    already configured as Railway env vars) rather than a public GET.
    """
    if not ENDPOINT or not BUCKET:
        return None
    endpoint_host = urlparse(ENDPOINT).netloc
    parsed = urlparse(url)
    if not endpoint_host or parsed.netloc != endpoint_host:
        return None
    prefix = f"/{BUCKET}/"
    if not parsed.path.startswith(prefix):
        return None
    return unquote(parsed.path[len(prefix):])


def download_media(url: str, dest: Path) -> None:
    """Download a single media file (audio, image, or video) from URL to dest.

    Files that live in our own Railway storage bucket are downloaded via a
    presigned S3 URL (signed with our existing storage credentials) instead
    of a direct boto3 get_object() call. Direct get_object() proved
    unreliable against the Tigris-backed bucket (spurious NoSuchKey on
    objects confirmed to exist via the bucket's own file browser); a
    presigned URL takes a different path through the storage gateway.
    Anything else falls back to a plain HTTP GET.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    bucket_key = _bucket_key_from_url(url)
    if bucket_key:
        client = get_client()
        for attempt in range(180):
            presigned_url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": bucket_key},
                ExpiresIn=3600,
            )
            with httpx.stream("GET", presigned_url, timeout=DOWNLOAD_TIMEOUT) as r:
                if r.status_code == 404:
                    if attempt == 179:
                        r.raise_for_status()
                    time.sleep(5)
                    continue
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
                return
        return

    with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def get_media_duration(path: Path) -> float:
    """
    Get duration of an audio or video file in seconds using ffprobe.
    Raises ValueError if duration cannot be determined.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise ValueError(f"Invalid media file: {result.stderr or result.stdout}")

    raw = (result.stdout or "").strip()
    # ffprobe can return "N/A" or an empty string for some inputs
    if not raw or raw.upper() == "N/A":
        raise ValueError("Could not determine media duration (ffprobe returned N/A).")

    try:
        duration = float(raw)
    except ValueError as exc:
        raise ValueError(f"Could not parse media duration from ffprobe output: {raw!r}") from exc

    return duration


def concatenate_audio(audio_paths: List[Path], output_path: Path) -> float:
    """
    Concatenate multiple audio files into one.
    Returns the total duration in seconds.
    """
    # Create a file list for FFmpeg concat demuxer
    list_file = output_path.parent / "audio_list.txt"
    with open(list_file, "w") as f:
        for p in audio_paths:
            f.write(f"file '{p.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Audio concatenation failed: {result.stderr[-1000:]}")

    # Get final duration
    total_duration = get_media_duration(output_path)
    list_file.unlink()

    return total_duration


def create_video_from_images(
    image_paths: List[Path],
    audio_path: Path,
    output_path: Path,
    quality: str,
    audio_duration: float,
    title_text: Optional[str] = None,
) -> float:
    """
    Create a video from images and audio.
    Images are looped/cycled to match audio duration.
    Fixed aspect ratio: 16:9
    Resolution: 720p or 1080p
    If title_text is provided, it is overlaid (fading in/out) only during the
    first TITLE_OVERLAY_DURATION_SECONDS seconds; the rest of the video shows
    just the plain background image(s).
    Returns final video duration (capped at 2 hours).
    """
    width, height = (1280, 720) if quality == "720" else (1920, 1080)

    # Calculate how long each image should be displayed
    num_images = len(image_paths)
    duration_per_image = audio_duration / num_images

    # Cap total duration at 2 hours
    final_duration = min(audio_duration, MAX_LONGFORM_DURATION_SECONDS)

    # Create input list with duration for each image
    inputs = []
    filter_parts = []

    for i, img_path in enumerate(image_paths):
        inputs.extend(["-loop", "1", "-t", str(duration_per_image), "-i", str(img_path)])
        # Scale and pad each image to target resolution
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
        )

    # Add audio input
    inputs.extend(["-i", str(audio_path)])
    audio_idx = num_images

    # Concatenate all scaled images
    filter_parts.append(
        "".join([f"[v{i}]" for i in range(num_images)]) +
        f"concat=n={num_images}:v=1:a=0[vraw]"
    )

    # Overlay title text only at the start of the video (or pass through untouched)
    filter_parts.append(_title_overlay_filter("vraw", "v", title_text))

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-threads", "2",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(final_duration),  # Cap duration
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        print("FFMPEG_CMD: " + " ".join(cmd), flush=True); print("FFMPEG_STDOUT: " + result.stdout, flush=True); print("FFMPEG_STDERR: " + result.stderr, flush=True); raise RuntimeError(f"Video creation failed (rc={result.returncode}): {result.stderr[-3000:]}")

    return final_duration


def create_video_from_videos(
    video_paths: List[Path],
    audio_path: Path,
    output_path: Path,
    quality: str,
    audio_duration: float,
    title_text: Optional[str] = None,
) -> float:
    """
    Create a video from background videos and audio.
    Videos are looped/concatenated and muted to match audio duration.
    Fixed aspect ratio: 16:9
    Resolution: 720p or 1080p
    If title_text is provided, it is overlaid (fading in/out) only during the
    first TITLE_OVERLAY_DURATION_SECONDS seconds; the rest of the video shows
    just the plain background video.
    Returns final video duration (capped at 2 hours).
    """
    width, height = (1280, 720) if quality == "720" else (1920, 1080)

    # Cap total duration at 2 hours
    final_duration = min(audio_duration, MAX_LONGFORM_DURATION_SECONDS)

    # Get durations of all background videos
    bg_durations = []
    for vp in video_paths:
        dur = get_media_duration(vp)
        bg_durations.append(dur)

    total_bg_duration = sum(bg_durations)

    # Calculate how many times we need to loop the videos
    num_loops = int(final_duration / total_bg_duration) + 1

    # Build filter_complex
    # Step 1: Scale and pad each background video
    filter_parts = []
    for i in range(len(video_paths)):
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
        )

    # Step 2: Concatenate background videos
    concat_inputs = "".join([f"[v{i}]" for i in range(len(video_paths))])
    filter_parts.append(f"{concat_inputs}concat=n={len(video_paths)}:v=1:a=0[vbg]")

    # Step 3: Loop the video to match audio duration
    # Use loop filter: loop=-1 means infinite loop, we'll cut it with -t
    filter_parts.append(f"[vbg]loop=loop={num_loops}:size=32767:start=0[vraw]")

    # Overlay title text only at the start of the video (or pass through untouched)
    filter_parts.append(_title_overlay_filter("vraw", "vloop", title_text))

    filter_complex = ";".join(filter_parts)

    # Audio input index
    audio_idx = len(video_paths)

    cmd = [
        "ffmpeg", "-y",
    ]

    # Add all background videos as inputs
    for vp in video_paths:
        cmd.extend(["-i", str(vp)])

    # Add audio input
    cmd.extend(["-i", str(audio_path)])

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vloop]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-threads", "2",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(final_duration),  # Cap at exact duration
        str(output_path),
    ])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        raise RuntimeError(f"Video creation from videos failed: {result.stderr[-2000:]}")

    return final_duration


def process_longform_video(
    audio_urls: List[str],
    background_source: str,
    background_urls: List[str],
    quality: str,
    temp_dir: Path,
    title_text: Optional[str] = None,
) -> Tuple[Path, float]:
    """
    Main processing function for longform videos.

    Args:
        audio_urls: List of audio file URLs (1-30)
        background_source: Either 'images' or 'videos'
        background_urls: List of background media URLs (1-15 for images, 1-5 for videos)
        quality: '720' or '1080'
        temp_dir: Temporary directory for processing
        title_text: Optional title/tema text shown only during the first
            seconds of the video (see TITLE_OVERLAY_DURATION_SECONDS); the
            rest of the video shows just the plain background.

    Returns:
        (output_path, duration_seconds)
    """
    # Download all audio files
    audio_paths = []
    for i, url in enumerate(audio_urls):
        dest = temp_dir / f"audio_{i}.mp3"
        download_media(url, dest)
        audio_paths.append(dest)

    # Concatenate audio files
    combined_audio = temp_dir / "combined_audio.mp3"
    total_audio_duration = concatenate_audio(audio_paths, combined_audio)

    # Cap audio duration at 2 hours
    if total_audio_duration > MAX_LONGFORM_DURATION_SECONDS:
        total_audio_duration = MAX_LONGFORM_DURATION_SECONDS

    # Download background media
    bg_paths = []
    for i, url in enumerate(background_urls):
        if background_source == "images":
            ext = "jpg"  # Could be improved by detecting from URL
            dest = temp_dir / f"bg_{i}.{ext}"
        else:
            dest = temp_dir / f"bg_video_{i}.mp4"
        download_media(url, dest)
        bg_paths.append(dest)

    # Create final video
    output_path = temp_dir / "longform_output.mp4"

    if background_source == "images":
        final_duration = create_video_from_images(
            bg_paths,
            combined_audio,
            output_path,
            quality,
            total_audio_duration,
            title_text,
        )
    else:  # videos
        final_duration = create_video_from_videos(
            bg_paths,
            combined_audio,
            output_path,
            quality,
            total_audio_duration,
            title_text,
        )

    return output_path, final_duration
