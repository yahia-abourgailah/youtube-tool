from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import models, schemas, database
from ..tasks.download import queue_video_download
from ..utils import storage, deletion
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=schemas.PaginatedVideos)
def read_videos(
    channel_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Video).options(joinedload(models.Video.channel))
    if channel_id:
        query = query.filter(models.Video.channel_id == channel_id)
    if status:
        query = query.filter(models.Video.status == status)
    if search:
        # Search in id, video_id or title
        search_filter = f"%{search}%"
        filters = [
            models.Video.video_id.like(search_filter),
            models.Video.title.like(search_filter)
        ]
        
        # If search is a number, also search by internal ID
        if search.isdigit():
            filters.append(models.Video.id == int(search))
            
        query = query.filter(or_(*filters))
    
    # Dynamic sorting
    if hasattr(models.Video, sort_by):
        column = getattr(models.Video, sort_by)
        if sort_order == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        query = query.order_by(models.Video.created_at.desc())

    total = query.count()
    pages = (total + size - 1) // size
    skip = (page - 1) * size
    items = query.offset(skip).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }

@router.post("/retry-all")
def retry_all_videos(db: Session = Depends(database.get_db)):
    # Only retry failed and pending videos — never re-download completed videos
    # as that would delete their chunks and destroy transcriptions.
    videos = db.query(models.Video).filter(models.Video.status.in_(["failed", "pending"])).all()
    triggered_count = 0
    for video in videos:
        try:
            queue_video_download(db, video)
            triggered_count += 1
        except Exception as exc:
            logger.error(f"Could not queue video {video.id}: {exc}")

    return {"message": f"Retry triggered for {triggered_count} videos"}

@router.post("/retry-failed")
def retry_failed_videos(db: Session = Depends(database.get_db)):
    # Support retrying both failed and pending videos (as promised in the UI)
    videos = db.query(models.Video).filter(models.Video.status.in_(["failed", "pending"])).all()
    logger.info(f"Retry failed/pending: Found {len(videos)} videos in list")

    triggered_count = 0
    for video in videos:
        try:
            queue_video_download(db, video)
            triggered_count += 1
        except Exception as exc:
            logger.error(f"Could not queue video {video.id}: {exc}")

    logger.info(f"Retry triggered for {triggered_count} videos")
    return {"message": f"Retry triggered for {triggered_count} videos"}

@router.post("/{video_id}/retry")
def retry_video(video_id: int, force: bool = False, db: Session = Depends(database.get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status == "completed" and not force:
        raise HTTPException(
            status_code=400,
            detail="Video is already completed. Re-downloading deletes its chunks and transcripts; pass force=true to confirm.",
        )
    job = queue_video_download(db, video)
    return {"message": "Retry triggered", "task_id": job.celery_task_id, "job_id": job.id}

@router.post("/{video_id}/stop")
def stop_video_task(video_id: int, db: Session = Depends(database.get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.celery_task_id:
        from ..celery_app import celery_app
        try:
            celery_app.control.revoke(video.celery_task_id, terminate=True)
        except Exception as e:
            # Task might have already finished or be unknown
            pass
    
    video.celery_task_id = None
    video.status = "failed"
    video.error_message = "Stopped by user"
    db.commit()
    return {"message": "Task stopped (force cleared)"}

@router.post("/{video_id}/reset")
def reset_video(video_id: int, db: Session = Depends(database.get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video.status = "pending"
    video.celery_task_id = None
    video.retry_count = 0
    # Clear the previous error so the auto-retry sweep treats this as a fresh video
    video.error_message = None
    db.commit()
    return {"message": "Video reset"}

@router.post("/{video_id}/refine-vad")
def refine_vad_video(video_id: int, db: Session = Depends(database.get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    from ..tasks.process import refine_vad_task
    task = refine_vad_task.delay(video.id)
    
    return {"message": "VAD refinement triggered", "task_id": task.id}


@router.post("/cleanup")
def cleanup_storage(db: Session = Depends(database.get_db)):
    """Delete raw downloads and legacy transcript files, keeping processed chunks."""
    videos = db.query(models.Video).filter(models.Video.status.in_(["completed", "failed"])).all()
    deleted_count = 0
    for video in videos:
        deleted_count += storage.cleanup_video_sources(video)
    return {"message": f"Cleanup completed. Deleted {deleted_count} source/auxiliary files."}


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(database.get_db)):
    """Delete a video, its chunks, jobs and audio files."""
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    youtube_id = video.video_id
    deletion.delete_video(db, video)
    return {"message": f"Video {youtube_id} deleted"}

@router.get("/{video_id}/logs")
def get_video_logs(video_id: int, db: Session = Depends(database.get_db)):
    logs = db.query(models.ActivityLog).filter(models.ActivityLog.video_id == video_id).order_by(models.ActivityLog.created_at.desc()).all()
    return logs
