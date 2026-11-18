#!/bin/bash

# Egyptian ASR Dataset Builder - Local Start Script

echo "Checking prerequisites..."

# Check Redis
#if ! command -v redis-cli &> /dev/null; then
#    echo "Error: redis-server is not installed. Please install it first."
#    exit 1
#fi

# Check uv
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install it first (https://github.com/astral-sh/uv)."
    exit 1
fi

if ! redis-cli ping &> /dev/null; then
    echo "Starting Redis server in background..."
    redis-server --daemonize yes
fi

# Create data and logs directories if they don't exist
mkdir -p data logs

# Set Redis URL and an absolute data path for local setup (override Docker defaults)
export REDIS_URL="redis://localhost:6379/0"
export DATA_PATH="$(pwd)/data"

# Start Backend
echo "Starting Backend..."
cd backend
#if [ ! -d ".venv" ]; then
#    uv venv
#fi
#source .venv/bin/activate
#uv pip install -r requirements.txt
echo "Applying database migrations..."
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start Celery
echo "Starting Celery Worker..."
uv run celery -A app.celery_app worker --loglevel=info &
CELERY_PID=$!

# Start Celery Beat (periodic auto-transcription safety net)
echo "Starting Celery Beat..."
uv run celery -A app.celery_app beat --loglevel=info --schedule=../logs/celerybeat-schedule &
BEAT_PID=$!

# Start Frontend
echo "Starting Frontend..."
cd ../frontend
export VITE_API_URL="http://localhost:8000"
npm install
npm run dev -- --host &
FRONTEND_PID=$!

echo "Application started!"
echo "Backend/API: http://localhost:8000"
echo "Frontend: http://localhost:5173"

# Trap exit to kill background processes
trap "kill $BACKEND_PID $CELERY_PID $BEAT_PID $FRONTEND_PID; exit" INT TERM EXIT

wait
