# Changelog

All notable changes to the Video Merge API project.

---

## [2.1.0] - 2026-07-21

### Added
- **NEW:** Optional `title_text` field on `/api/v1/longform/render`. When provided, it is overlaid on the video (fading in/out) only during the first 6 seconds; the rest of the video shows just the plain background image/video. Implemented via an ffmpeg `drawtext` filter (not baked into the AI-generated background image), so text timing is fully deterministic and legible.
- `title_text` is now included in job records (SQLite) and in `/api/v1/longform/result/{id}` responses.
- Nixpacks build now installs `fontconfig` + `dejavu_fonts` so the drawtext overlay has a reliable font (with Spanish accented character support) at runtime.

---

## [2.0.0] - 2026-02-11

### Major Release: Longform Video Rendering

This release introduces asynchronous longform video rendering capabilities with significant new features.

### Added

#### Longform Video Rendering
- **NEW:** Async processing system for longform videos (up to 2 hours)
- **NEW:** SQLite database for job tracking and persistence
- **NEW:** Background worker for processing video jobs
- **NEW:** Support for audio-driven video creation with background media
- **NEW:** Three new API endpoints:
  - `POST /api/v1/longform/render` - Queue render job
  - `GET /api/v1/longform/status/{request_id}` - Check job status
  - `GET /api/v1/longform/result/{request_id}` - Get completed result

#### Features
- Support for 1-30 audio URLs (concatenated automatically)
- Two background source types:
  - **Images:** 1-15 URLs supported
  - **Videos:** 1-5 URLs supported (automatically muted)
- Fixed 16:9 aspect ratio for longform videos
- Quality options: 720p (1280x720) or 1080p (1920x1080)
- Automatic background media looping to match audio duration
- Maximum video duration: 2 hours (7200 seconds)
- Final video length always matches total audio length (capped at 2h)

#### Technical Infrastructure
- SQLite database with migration system
- Database schema for job tracking (pending, processing, completed, failed)
- Async database operations using `aiosqlite`
- Background worker with automatic startup
- Request ID system for job tracking
- Comprehensive error handling and logging

#### Documentation
- **NEW:** `API-DOCUMENTATION.md` - Complete API reference with examples
- **NEW:** `SETUP.md` - Detailed setup and deployment guide
- **NEW:** `CHANGELOG.md` - This file
- Expanded README with new features
- cURL examples for all endpoints (images and videos)

#### Code Organization
- New `routers/` package for endpoint organization
- New `utils/db.py` - Database utilities
- New `utils/longform_processor.py` - Longform video processing
- New `utils/worker.py` - Background job worker
- New `migrations/` directory with database schema

### Changed

#### Breaking Changes
- API version updated to 2.0.0
- Application description updated to include longform capabilities
- Root endpoint (`/`) now includes all available endpoints

#### Enhancements
- Enhanced logging configuration with timestamps
- Better error messages and validation
- Improved startup sequence with database initialization

#### Dependencies
- Added `aiosqlite>=0.19.0` for async SQLite operations
- Added `pillow>=10.0.0` for image processing

### Fixed
- N/A (new features, no fixes in this release)

### Deprecated
- None

### Removed
- None

### Security
- API key authentication required for all new endpoints
- Database file protection via file system permissions
- No sensitive data logged in errors

---

## [1.0.0] - 2025-XX-XX

### Initial Release

#### Features
- Video merge endpoint (`POST /api/v1/merge`)
- Support for 2-10 video URLs
- Configurable quality: 720p or 1080p
- Configurable aspect ratio: 16:9, 9:16, or 1:1
- Maximum duration: 2 hours (7200 seconds)
- FFmpeg-based video processing
- Railway/S3 storage integration
- API key authentication
- Health check endpoint

#### Technical
- FastAPI framework
- Synchronous video processing
- In-memory temporary file handling
- Video scaling, padding, and crossfade transitions
- Audio crossfade for smooth merging

---

## Migration Guide: v1.x to v2.0

### No Breaking Changes for Existing Endpoints

The v2.0 release is **fully backward compatible** with v1.x for the video merge endpoint. Existing integrations will continue to work without changes.

### What's New

If you want to use the new longform rendering features:

1. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Update environment variables:**
   Add `DATABASE_PATH` to your `.env` file (optional, defaults to `jobs.db`)

3. **Use new endpoints:**
   - See `API-DOCUMENTATION.md` for complete examples
   - Use `/api/v1/longform/render` for async video creation
   - Poll `/api/v1/longform/status/{request_id}` for job status
   - Fetch result from `/api/v1/longform/result/{request_id}`

### Database

- SQLite database is created automatically on first startup
- No manual migration required
- Database file location: `DATABASE_PATH` env var (default: `jobs.db`)

### Worker

- Background worker starts automatically with the application
- No additional configuration needed
- Processes one job at a time (sequential)

---

## Roadmap

Future planned features (not yet implemented):

### v2.1 (Potential)
- Multiple concurrent workers
- PostgreSQL support for production
- Redis queue for better scalability
- Webhook notifications for job completion
- Progress percentage during processing
- Job cancellation endpoint
- Job history cleanup/archival

### v2.2 (Potential)
- Video preview/thumbnail generation
- Subtitle/caption support
- Watermark support
- Multiple output formats (WebM, etc.)
- Custom transition effects
- Audio normalization options

### v3.0 (Potential)
- User accounts and quotas
- Dashboard UI for job management
- Analytics and usage tracking
- Batch job submission
- Template system for common video types
- AI-generated transitions and effects

---

## Support

- **Issues:** Report bugs or request features via GitHub issues
- **Documentation:** See `API-DOCUMENTATION.md` and `SETUP.md`
- **Contact:** [Your contact information]

---

## Contributors

- [Your name/team]

---

## License

This project is provided as-is for your use.
