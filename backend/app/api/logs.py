from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas, database

router = APIRouter()

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
