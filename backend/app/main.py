from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, schemas, database
from .api import channels, videos, chunks, jobs, export, logs, settings
import os

app = FastAPI(title="Egyptian ASR Dataset Builder")

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(chunks.router, prefix="/api/chunks", tags=["chunks"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

@app.get("/")
async def root():
    return {"message": "Egyptian ASR Dataset Builder API"}

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
