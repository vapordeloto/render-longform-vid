# Video Merge API â Complete API Documentation

Comprehensive guide for all endpoints in the Video Merge API, including the original video merge endpoint and the new longform video rendering endpoints.

---

## Table of Contents

1. [Base URL](#base-url)
2. [Authentication](#authentication)
3. [Endpoints Overview](#endpoints-overview)
4. [Video Merge Endpoint](#video-merge-endpoint)
5. [Longform Video Rendering Endpoints](#longform-video-rendering-endpoints)
6. [cURL Examples](#curl-examples)
7. [Limits and Notes](#limits-and-notes)

---

## Base URL

- **Local:** `http://localhost:8000`
- **Production:** Your deployed URL (e.g. `https://your-app.up.railway.app`)

Replace `BASE_URL` in the examples below with your actual base URL.

---

## Authentication

All API requests (except health check) require an API key in the header:

| Header        | Required | Description                                |
|---------------|----------|--------------------------------------------|
| `X-API-Key`   | Yes      | Your API key (set in env as `API_KEY`)    |
| `Content-Type`| Yes      | `application/json` for POST requests      |

**Example:**

```bash
-H "X-API-Key: YOUR_API_KEY"
-H "Content-Type: application/json"
```

---

## Endpoints Overview

| Endpoint                                    | Method | Description                                    |
|---------------------------------------------|--------|------------------------------------------------|
| `/health`                                   | GET    | Health check                                   |
| `/api/v1/merge`                             | POST   | Merge 2-10 videos (synchronous)                |
| `/api/v1/longform/render`                   | POST   | Queue longform video render job (async)        |
| `/api/v1/longform/status/{request_id}`      | GET    | Check status of render job                     |
| `/api/v1/longform/result/{request_id}`      | GET    | Get result of completed render job             |

---

## Video Merge Endpoint

### POST `/api/v1/merge`

Merge 2â10 video URLs into one video with configurable quality and aspect ratio. This is a **synchronous** endpoint that processes immediately and returns the merged video URL.

#### Request Body

| Field          | Type     | Required | Values                          | Default  |
|----------------|----------|----------|----------------------------------|----------|
| `video_urls`   | string[] | Yes      | 2â10 valid HTTP(S) URLs          | â        |
| `quality`      | string   | No       | `"720"` or `"1080"`              | `"1080"` |
| `aspect_ratio` | string   | No       | `"9:16"`, `"16:9"`, `"1:1"`      | `"16:9"` |

**Constraints:**
- Total duration of all input videos must not exceed **2 hours (7200 seconds)**
- Each URL must be publicly accessible

#### Success Response (200)

```json
{
  "success": true,
  "merged_url": "https://storage.example.com/merged-abc123.mp4",
  "duration_seconds": 180.5,
  "processing_time": 45.2,
  "clips_merged": 3
}
```

#### Error Response (4xx / 5xx)

```json
{
  "error": "Error message here"
}
```

Common errors:
- `400`: Validation error, duration limit exceeded
- `401`: Invalid or missing API key
- `422`: Failed to download video
- `500`: Processing or upload failed

---

## Longform Video Rendering Endpoints

### POST `/api/v1/longform/render`

Queue a longform video render job. This is an **asynchronous** endpoint that returns immediately with a `request_id`. The video is processed in the background.

#### Request Body

| Field              | Type     | Required | Values                                          | Default  |
|-------------------|----------|----------|-------------------------------------------------|----------|
| `audio_urls`      | string[] | Yes      | 1â30 valid HTTP(S) URLs to audio files          | â        |
| `background_source` | string   | Yes      | `"images"` or `"videos"`                        | â        |
| `background_urls` | string[] | Yes      | 1â15 image URLs OR 1â5 video URLs (depends on `background_source`) | â |
| `quality`         | string   | No       | `"720"` or `"1080"`                             | `"1080"` |
| `title_text`      | string   | No       | Title/tema text, max 200 chars                  | `null`   |

**Constraints:**
- `audio_urls`: Minimum 1, maximum 30 URLs
- `background_urls` for images: Minimum 1, maximum 15 URLs
- `background_urls` for videos: Minimum 1, maximum 5 URLs
- Final video is fixed at **16:9 aspect ratio**
- Final video resolution: **720p (1280x720)** or **1080p (1920x1080)**
- Total audio duration is capped at **2 hours (7200 seconds)**
- `title_text`: if provided, it's overlaid on the video (fading in/out) only during the first 6 seconds; the rest of the video shows just the plain background image/video
- Background videos are automatically **muted**
- Background media is **looped/cycled** to match audio duration

#### Success Response (200)

```json
{
  "success": true,
  "request_id": "req_a1b2c3d4e5f6",
  "message": "Render job queued. Use the request_id to check status."
}
```

Use the `request_id` to poll for status and retrieve the result.

---

### GET `/api/v1/longform/status/{request_id}`

Check the status of a render job.

#### URL Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `request_id` | string | The request ID from `/render`  |

#### Success Response (200)

```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "processing",
  "created_at": "2026-02-11T12:34:56.789012",
  "updated_at": "2026-02-11T12:35:23.456789",
  "error_message": null
}
```

**Status Values:**
- `pending`: Job is queued but not yet started
- `processing`: Job is currently being processed
- `completed`: Job finished successfully (fetch result using `/result` endpoint)
- `failed`: Job failed (check `error_message` field)

#### Error Response

```json
{
  "error": "Job not found"
}
```

---

### GET `/api/v1/longform/result/{request_id}`

Get the result of a completed render job. This endpoint only works for jobs with status `completed`.

#### URL Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `request_id` | string | The request ID from `/render`  |

#### Success Response (200)

```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "completed",
  "result_url": "https://storage.example.com/longform-req_a1b2c3.mp4",
  "duration_seconds": 3600.0,
  "processing_time": 245.8
}
```

#### Error Responses

**Job not found (404):**
```json
{
  "error": "Job not found"
}
```

**Job not completed (400):**
```json
{
  "error": "Job is not completed. Current status: processing"
}
```

---

## cURL Examples

Replace:
- `BASE_URL` â your API base URL (e.g. `https://your-app.up.railway.app` or `http://localhost:8000`)
- `YOUR_API_KEY` â your actual API key
- URLs â real, publicly accessible HTTP(S) URLs

---

### 1. Health Check

```bash
curl -s "https://BASE_URL/health"
```

**Response:**
```json
{"status": "ok"}
```

---

### 2. Merge Videos (Original Endpoint)

#### Merge 2 videos â 1080p, 16:9

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/video1.mp4",
      "https://example.com/video2.mp4"
    ],
    "quality": "1080",
    "aspect_ratio": "16:9"
  }'
```

#### Merge 3 videos â 720p, 9:16 (vertical)

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "quality": "720",
    "aspect_ratio": "9:16"
  }'
```

---

### 3. Longform Video Rendering (New Endpoints)

#### Render longform video with images as background

This example uses:
- **5 audio URLs** (minimum 1, maximum 30)
- **10 image URLs** (minimum 1, maximum 15 when using images)
- **1080p quality**

```bash
curl -X POST "https://BASE_URL/api/v1/longform/render" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_urls": [
      "https://example.com/audio1.mp3",
      "https://example.com/audio2.mp3",
      "https://example.com/audio3.mp3",
      "https://example.com/audio4.mp3",
      "https://example.com/audio5.mp3"
    ],
    "background_source": "images",
    "background_urls": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg",
      "https://example.com/image3.jpg",
      "https://example.com/image4.jpg",
      "https://example.com/image5.jpg",
      "https://example.com/image6.jpg",
      "https://example.com/image7.jpg",
      "https://example.com/image8.jpg",
      "https://example.com/image9.jpg",
      "https://example.com/image10.jpg"
    ],
    "quality": "1080"
  }'
```

**Response:**
```json
{
  "success": true,
  "request_id": "req_a1b2c3d4e5f6",
  "message": "Render job queued. Use the request_id to check status."
}
```

**Important Notes:**
- Background images will be looped/cycled to match the total audio duration
- Each image will be displayed for an equal duration
- Final video will be exactly as long as the combined audio (up to 2 hours max)

---

#### Render longform video with videos as background

This example uses:
- **3 audio URLs** (minimum 1, maximum 30)
- **3 video URLs** (minimum 1, maximum 5 when using videos)
- **720p quality**

```bash
curl -X POST "https://BASE_URL/api/v1/longform/render" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_urls": [
      "https://example.com/audio1.mp3",
      "https://example.com/audio2.mp3",
      "https://example.com/audio3.mp3"
    ],
    "background_source": "videos",
    "background_urls": [
      "https://example.com/background1.mp4",
      "https://example.com/background2.mp4",
      "https://example.com/background3.mp4"
    ],
    "quality": "720"
  }'
```

**Important Notes:**
- Background videos are **automatically muted**
- Background videos will be concatenated and looped to match the total audio duration
- Final video will be exactly as long as the combined audio (up to 2 hours max)

---

#### Check render job status

```bash
curl -X GET "https://BASE_URL/api/v1/longform/status/req_a1b2c3d4e5f6" \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response (processing):**
```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "processing",
  "created_at": "2026-02-11T12:34:56.789012",
  "updated_at": "2026-02-11T12:35:23.456789",
  "error_message": null
}
```

**Response (completed):**
```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "completed",
  "created_at": "2026-02-11T12:34:56.789012",
  "updated_at": "2026-02-11T12:40:15.234567",
  "error_message": null
}
```

**Response (failed):**
```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "failed",
  "created_at": "2026-02-11T12:34:56.789012",
  "updated_at": "2026-02-11T12:36:30.987654",
  "error_message": "Failed to download audio from URL: https://..."
}
```

---

#### Get render job result

Only works for completed jobs:

```bash
curl -X GET "https://BASE_URL/api/v1/longform/result/req_a1b2c3d4e5f6" \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response:**
```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "completed",
  "result_url": "https://storage.example.com/longform-req_a1b2c3.mp4",
  "duration_seconds": 3600.0,
  "processing_time": 245.8
}
```

---

### Complete Workflow Example

**Step 1: Submit a render job**

```bash
REQUEST_ID=$(curl -X POST "https://BASE_URL/api/v1/longform/render" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_urls": ["https://example.com/audio1.mp3"],
    "background_source": "images",
    "background_urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
    "quality": "1080"
  }' | jq -r '.request_id')

echo "Request ID: $REQUEST_ID"
```

**Step 2: Poll for status**

```bash
# Poll every 10 seconds until completed
while true; do
  STATUS=$(curl -s "https://BASE_URL/api/v1/longform/status/$REQUEST_ID" \
    -H "X-API-Key: YOUR_API_KEY" | jq -r '.status')
  
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 10
done
```

**Step 3: Get result**

```bash
curl -X GET "https://BASE_URL/api/v1/longform/result/$REQUEST_ID" \
  -H "X-API-Key: YOUR_API_KEY" | jq
```

---

## Limits and Notes

### Video Merge Endpoint (`/api/v1/merge`)

- **URLs:** Between 2 and 10 per request
- **Duration:** Sum of all input durations must be â¤ 7200 seconds (2 hours)
- **Aspect Ratios:** 16:9, 9:16, or 1:1
- **Quality:** 720p or 1080p
- **Processing:** Synchronous (wait for response)
- **Timeout:** Can take 1-10+ minutes. Use long client timeout (e.g. `curl --max-time 900`)

### Longform Rendering Endpoints (`/api/v1/longform/*`)

- **Audio URLs:** Between 1 and 30 per request
- **Background Images:** Between 1 and 15 per request (when using `background_source: "images"`)
- **Background Videos:** Between 1 and 5 per request (when using `background_source: "videos"`)
- **Aspect Ratio:** Fixed at **16:9**
- **Quality:** 720p (1280x720) or 1080p (1920x1080)
- **Duration:** Final video duration = total audio duration, capped at **2 hours (7200 seconds)**
- **Processing:** Asynchronous (returns immediately with request_id)
- **Background Videos:** Automatically muted
- **Background Media:** Looped/cycled to match audio duration
- **Polling:** Use `/status` endpoint to check progress
- **Result:** Use `/result` endpoint to get final video URL when completed

### General Notes

- All URLs must be publicly accessible HTTP or HTTPS URLs
- Supported audio formats: MP3, WAV, M4A, etc. (any format FFmpeg supports)
- Supported image formats: JPG, PNG, etc.
- Supported video formats: MP4, MOV, etc.
- Output videos are always MP4 format
- Result URLs are typically valid for 7 days (configurable in storage settings)
- Large longform videos can take 5-30+ minutes to process depending on duration and quality

---

## Testing with Sample URLs

For quick tests, you can use publicly available sample media:

**Sample Videos:**
- https://www.w3schools.com/html/mov_bbb.mp4
- https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4

**Sample Audio:**
- Use any publicly accessible MP3/audio file
- For testing: https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3

**Sample Images:**
- https://picsum.photos/1920/1080 (random image, 1920x1080)
- https://via.placeholder.com/1920x1080

---

## Error Handling

All endpoints return errors in this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

**Common HTTP status codes:**
- `200`: Success
- `400`: Bad request (validation error, invalid parameters)
- `401`: Unauthorized (missing or invalid API key)
- `404`: Not found (job doesn't exist)
- `422`: Unprocessable entity (failed to download media)
- `500`: Internal server error (processing failed)

---

## Rate Limiting

Currently there is no rate limiting implemented. However, consider:
- Limiting concurrent longform render jobs per API key
- Implementing request queuing if multiple jobs are submitted simultaneously
- The background worker processes one job at a time

---

## Support

For issues or questions:
1. Check the `/health` endpoint to verify the service is running
2. Review error messages in responses
3. Check server logs for detailed error information
4. Verify all media URLs are publicly accessible
5. Ensure API key is correct and included in headers
