# Egyptian ASR Dataset Builder

A web application for creating large-scale Egyptian Arabic ASR datasets from YouTube videos.

## Features
- **Channel Monitoring**: Automatically fetch all videos from specified YouTube channels.
- **Audio Extraction**: Download high-quality audio using `pytubefix`.
- **AI Transcription**: High-accuracy Egyptian Arabic transcription using a configurable external ASR service.
- **Automatic Pipeline**: Download → split → transcribe runs without manual steps. Newly split videos are queued automatically, missed/failed chunks are swept up, and failed or orphaned downloads are retried with safeguards.
- **VAD Filtering**: Intelligent **Voice Activity Detection** to remove non-speech chunks.
- **Transcript Alignment**: Optional download of existing Arabic YouTube captions for reference (disabled by default; the ASR service is the source of transcripts).
- **Intelligent Splitting**: Silence-based audio splitting using `pydub` and VAD.
- **Slack Notifications**: Real-time alerts for system status, errors, and daily summaries.
- **Dataset Export**: Create HuggingFace-compatible datasets (Arrow/Parquet), optionally with train/validation/test splits, a JSON manifest, and a one-click zip download. Exports run fully locally and only push to the Hub when a repo and token are provided.
- **Dataset QA**: Read-only quality report that flags missing audio, empty/short/non-Arabic transcripts, implausible speech rates and duplicate transcripts.
- **Safe Cleanup**: Delete individual videos or whole channels (database rows, chunks, transcripts and files) and prune raw source audio without touching processed chunks.
- **Provenance & Retention**: Store ASR model/version/language/confidence per chunk, keep `.txt` transcript sidecars, and automatically prune old activity logs.
- **Modern UI**: Dark-themed dashboard with real-time progress tracking.

## Technical Stack
- **Backend**: FastAPI, SQLAlchemy (**MySQL**), Celery, Redis.
- **Frontend**: React, TypeScript, Vite, Vanilla CSS.
- **Processing**: Pydub, Librosa, Pytubefix, external ASR API.

## Setup

### Prerequisites
- Docker and Docker Compose
- A reachable external ASR service (see `ASR_ENDPOINT`)
- HuggingFace Token (optional, only for Hub export)
- Slack Webhook URL (optional, for notifications)

### Installation
1. Clone the repository.
2. Create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with your credentials:
   - `DATABASE_URL` / `MYSQL_*`: MySQL connection settings.
   - `ASR_ENDPOINT`, `ASR_API_KEY`, `ASR_API_SECRET`: external transcription service.
   - `HF_TOKEN`: only needed to push exports to the Hub.
   - `SLACK_WEBHOOK_URL`: optional notifications.
   - `API_KEY`: optional; when set, every API call must send `X-API-Key`.
   - `CORS_ORIGINS`: comma-separated frontend origins.
4. Start the application:
   ```bash
   docker-compose up --build
   ```
   The `app` container runs `alembic upgrade head` before starting, so schema
   changes are applied automatically. Set `RUN_MIGRATIONS=false` to skip this.

### Usage
- Access the UI at `http://localhost:5173`.
- Upload a `.txt` file with channel URLs in the "Channels" tab.
- Monitor progress in the "Videos" tab.
- Browse and preview chunks in the "Chunks" tab.
- Use the "Transcribe" feature to generate accurate text for your chunks.
  Transcription is automatic by default (toggle it in Settings); the Transcribe
  page is still available for manual or forced re-runs.
- Failed downloads and orphaned pending videos are retried automatically
  (toggle it in Settings). User-stopped videos and bot-detection pauses are
  never retried, and each video is capped at a few automatic rounds.
- Export your dataset in the "Export" tab. You can optionally split each channel
  subset into train/validation/test files; the download bundles all Parquet
  files with `hf_dataset_manifest.json`.
- Review dataset quality in the "QA" tab before exporting.

### Local Setup (Without Docker)

If you prefer to run the application without Docker, follow these steps:

#### 1. Prerequisites
- **Python 3.10+**: Install from [python.org](https://www.python.org/).
- **Node.js 20+**: Install from [nodejs.org](https://nodejs.org/).
- **MySQL Server**: Recommended for production/large datasets.
- **Redis Server**: Required for Celery. 
  - Mac: `brew install redis`
  - Linux: `sudo apt install redis-server`
  - Windows: Use [Redis on WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-database#install-redis).

#### 2. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Setup environment and install dependencies using **uv**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```
3. Start Redis (in a separate terminal):
   ```bash
   redis-server
   ```
4. Start the Celery worker (in a separate terminal, ensure REDIS_URL is set):
   ```bash
   export REDIS_URL="redis://localhost:6379/0"
   # Make sure your .env is loaded or variables are set
   uv run celery -A app.celery_app worker --loglevel=info
   ```
   For the periodic auto-transcription sweep, also start Celery Beat:
   ```bash
   uv run celery -A app.celery_app beat --loglevel=info
   ```
   (Docker Compose starts a `celery-beat` service automatically.)
5. Apply database migrations, then start the FastAPI server:
   ```bash
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```

#### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## Project Structure
- `backend/`: FastAPI application, Celery tasks, Alembic migrations and the external ASR client.
- `frontend/`: React application.
- `data/`: Local storage for audio, transcript sidecars, settings and exports (ignored by git).
- `logs/`: Error logs (ignored by git).

Chunk audio is stored under
`data/channels/<channel_id>/videos/<youtube_id>/`, with a matching `.txt`
transcript sidecar written whenever a chunk is transcribed or edited.

## Database Migrations
Alembic is the schema authority; the app no longer calls `create_all()`.
Migrations are idempotent, so they also work on databases created before
Alembic was introduced (the existing tables/columns are detected and skipped).

```bash
cd backend
alembic upgrade head          # apply
alembic current               # show current revision
alembic revision --autogenerate -m "describe change"
```

Docker Compose runs `alembic upgrade head` automatically before the API starts.
For a local setup, run it manually before `uvicorn` (see above).

### MySQL authentication error
MySQL 8 defaults to `caching_sha2_password`. PyMySQL needs the `cryptography`
package for that auth method, so it is included in `backend/requirements.txt`.
If an older image reports `cryptography package is required for
sha256_password or caching_sha2_password`, rebuild the backend services:

```bash
docker compose build app celery-worker celery-beat
docker compose up -d
```

## Tests
Backend unit tests cover path resolution, CSV formula neutralization and QA
classification. They only need `pytest` (no database or ASR service):

```bash
pip install pytest
pytest backend/tests -q
```

The optional ASR smoke script is configured with environment variables:

```bash
ASR_TEST_AUDIO_DIR=/path/to/chunks python test_endpoints.py
```
