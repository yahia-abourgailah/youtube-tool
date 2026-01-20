# Egyptian ASR Dataset Builder

A web application for creating large-scale Egyptian Arabic ASR datasets from YouTube videos.

## Features
- **Channel Monitoring**: Automatically fetch all videos from specified YouTube channels.
- **Audio Extraction**: Download high-quality audio using `pytubefix`.
- **Transcript Alignment**: Fetch Arabic captions (manual or auto-generated).
- **Intelligent Splitting**: Silence-based audio splitting using `pydub`.
- **Dataset Export**: Create HuggingFace-compatible datasets (Arrow/Parquet).
- **Modern UI**: Dark-themed dashboard with real-time progress tracking.

## Technical Stack
- **Backend**: FastAPI, SQLAlchemy (SQLite), Celery, Redis.
- **Frontend**: React, TypeScript, Vite, Vanilla CSS.
- **Processing**: Pydub, Librosa, Pytubefix.

## Setup

### Prerequisites
- Docker and Docker Compose
- HuggingFace Token (optional, for Hub export)

### Installation
1. Clone the repository.
2. Create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. Start the application:
   ```bash
   docker-compose up --build
   ```

### Usage
- Access the UI at `http://localhost:5173`.
- Upload a `.txt` file with channel URLs in the "Channels" tab.
- Monitor progress in the "Videos" tab.
- Browse and preview chunks in the "Chunks" tab.
- Export your dataset in the "Export" tab.

### Local Setup (Without Docker)

If you prefer to run the application without Docker, follow these steps:

#### 1. Prerequisites
- **Python 3.10+**: Install from [python.org](https://www.python.org/).
- **Node.js 20+**: Install from [nodejs.org](https://nodejs.org/).
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
   uv run celery -A app.celery_app worker --loglevel=info
   ```
5. Start the FastAPI server (ensure REDIS_URL is set):
   ```bash
   export REDIS_URL="redis://localhost:6379/0"
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
- `backend/`: FastAPI application and Celery tasks.
- `frontend/`: React application.
- `data/`: Local storage for audio and transcripts (ignored by git).
- `logs/`: Error logs (ignored by git).

## Database Migration
To migrate from SQLite to PostgreSQL, update the `DATABASE_URL` in `.env` and run migrations if using Alembic.
