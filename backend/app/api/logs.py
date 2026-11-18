from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas, database
from ..tasks.maintenance import prune_activity_logs_task

router = APIRouter()

@router.post("/prune")
def prune_logs(days: int = 90):
    """Delete activity logs older than the given number of days (0 disables)."""
    if days < 0:
        raise HTTPException(status_code=400, detail="days must be >= 0")
    task = prune_activity_logs_task.delay(days)
    return {"message": "Prune started", "task_id": task.id}

@router.get("/", response_model=List[schemas.ActivityLog])
def read_logs(
    video_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(database.get_db)
):
    query = db.query(models.ActivityLog)
    if video_id:
        query = query.filter(models.ActivityLog.video_id == video_id)
    if channel_id:
        query = query.filter(models.ActivityLog.channel_id == channel_id)
    
    return query.order_by(models.ActivityLog.created_at.desc()).limit(limit).all()
