# Egyptian ASR Dataset Builder

A web application for creating large-scale Egyptian Arabic ASR datasets from YouTube videos.

## Features
- **Channel Monitoring**: Automatically fetch all videos from specified YouTube channels.
- **Audio Extraction**: Download high-quality audio using `pytubefix`.
- **AI Transcription**: High-accuracy Egyptian Arabic transcription using **Google Gemini 2.0 Flash**.
- **VAD Filtering**: Intelligent **Voice Activity Detection** to remove non-speech chunks.
- **Transcript Alignment**: Fetch existing Arabic captions (manual or auto-generated) as a fallback.
- **Intelligent Splitting**: Silence-based audio splitting using `pydub` and VAD.
- **Slack Notifications**: Real-time alerts for system status, errors, and daily summaries.
- **Dataset Export**: Create HuggingFace-compatible datasets (Arrow/Parquet).
- **Modern UI**: Dark-themed dashboard with real-time progress tracking.

## Technical Stack
- **Backend**: FastAPI, SQLAlchemy (**MySQL**), Celery, Redis.
- **Frontend**: React, TypeScript, Vite, Vanilla CSS.
- **Processing**: Pydub, Librosa, Pytubefix, Google Gemini API.

## Setup

### Prerequisites
- Docker and Docker Compose
- HuggingFace Token (optional, for Hub export)
- Google Gemini API Key (for transcription)
- Slack Webhook URL (optional, for notifications)

### Installation
1. Clone the repository.
2. Create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with your credentials:
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `SLACK_WEBHOOK_URL`: Your Slack webhook URL.
   - `DATABASE_URL`: Your MySQL connection string (e.g., `mysql+pymysql://user:password@localhost/dbname`).
4. Start the application:
   ```bash
   docker-compose up --build
   ```

### Usage
- Access the UI at `http://localhost:5173`.
- Upload a `.txt` file with channel URLs in the "Channels" tab.
- Monitor progress in the "Videos" tab.
- Browse and preview chunks in the "Chunks" tab.
- Use the "Transcribe" feature to generate accurate text for your chunks.
- Export your dataset in the "Export" tab.

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
5. Start the FastAPI server:
   ```bash
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
- `backend/`: FastAPI application, Celery tasks, and Gemini integration.
- `frontend/`: React application.
- `data/`: Local storage for audio and transcripts (ignored by git).
- `logs/`: Error logs (ignored by git).

## Database Migration
To use MySQL, ensure `DATABASE_URL` in `.env` is set to a MySQL connection string (e.g., `mysql+pymysql://...`). The application will verify the connection on startup.
