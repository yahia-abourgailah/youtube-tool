from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from . import models, database
from .api import channels, videos, chunks, jobs, export, logs, settings, transcribe, qa
from .security import APIKeyMiddleware
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Egyptian ASR Dataset Builder")

# Schema changes are managed by Alembic (see backend/migrations and README).
# The app no longer calls create_all(), which silently skipped new columns on
# existing databases.

_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
_allow_all_origins = "*" in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all_origins else _origins,
    # Credentials cannot be combined with a wildcard origin.
    allow_credentials=not _allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)

# Include routers
app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(chunks.router, prefix="/api/chunks", tags=["chunks"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(transcribe.router, prefix="/api/transcribe", tags=["transcribe"])
app.include_router(qa.router, prefix="/api/qa", tags=["qa"])

@app.get("/")
async def root():
    return {"message": "Egyptian ASR Dataset Builder API"}

@app.get("/health")
def health(db: Session = Depends(database.get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/api/stats")
async def get_stats(db: Session = Depends(database.get_db)):
    total_videos = db.query(models.Video).count()
    processed_videos = db.query(models.Video).filter(models.Video.status == "completed").count()
    failed_videos = db.query(models.Video).filter(models.Video.status == "failed").count()
    total_chunks = db.query(models.AudioChunk).count()
    
    # Calculate total duration
    total_duration = db.query(models.func.sum(models.AudioChunk.duration)).scalar() or 0
    
    return {
        "total_videos": total_videos,
        "processed_videos": processed_videos,
        "failed_videos": failed_videos,
        "total_chunks": total_chunks,
        "total_duration_hours": total_duration / 3600
    }
