from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import logging
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database
from ..tasks.download import process_channel_task

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=schemas.Channel)
def create_channel(channel: schemas.ChannelCreate, db: Session = Depends(database.get_db)):
    db_channel = models.Channel(url=str(channel.url), name=channel.name)
    db.add(db_channel)
    try:
        db.commit()
    except:
        db.rollback()
        raise HTTPException(status_code=400, detail="Channel already exists")
    db.refresh(db_channel)
    task = process_channel_task.delay(db_channel.id)
    db_channel.celery_task_id = task.id
    # Create a job record for activity log
    job = models.Job(job_type="channel_process", entity_id=str(db_channel.id), status="pending", celery_task_id=task.id)
    db.add(job)
    db.commit()
    return db_channel

@router.post("/upload", response_model=List[schemas.Channel])
async def upload_channels(file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    content = await file.read()
    urls = content.decode("utf-8").splitlines()
    created_channels = []
    for url in urls:
        if not url.strip():
            continue
        db_channel = models.Channel(url=url.strip())
        db.add(db_channel)
        try:
            db.commit()
            db.refresh(db_channel)
            task = process_channel_task.delay(db_channel.id)
            db_channel.celery_task_id = task.id
            # Create a job record for activity log
            job = models.Job(job_type="channel_process", entity_id=str(db_channel.id), status="pending", celery_task_id=task.id)
            db.add(job)
            db.commit()
            created_channels.append(db_channel)
        except:
            db.rollback()
    return created_channels

@router.get("/", response_model=List[schemas.Channel])
def read_channels(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Channel).offset(skip).limit(limit).all()

@router.post("/{channel_id}/process")
def trigger_process_channel(channel_id: int, db: Session = Depends(database.get_db)):
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    task = process_channel_task.delay(channel_id)
    channel.celery_task_id = task.id
    # Create a job record for activity log
    job = models.Job(job_type="channel_process", entity_id=str(channel_id), status="pending", celery_task_id=task.id)
    db.add(job)
    db.commit()
    return {"message": "Processing triggered", "task_id": task.id}

@router.post("/{channel_id}/stop")
def stop_process_channel(channel_id: int, db: Session = Depends(database.get_db)):
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.celery_task_id:
        from ..celery_app import celery_app
        try:
            celery_app.control.revoke(channel.celery_task_id, terminate=True)
        except Exception as e:
            logger.warning(f"Could not revoke task {channel.celery_task_id}: {e}")
    
    channel.celery_task_id = None
    channel.status = "failed"
    db.commit()
    return {"message": "Processing stopped (force cleared)"}

@router.post("/{channel_id}/reset")
def reset_channel(channel_id: int, db: Session = Depends(database.get_db)):
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel.status = "pending"
    channel.celery_task_id = None
    db.commit()
    return {"message": "Channel reset"}
