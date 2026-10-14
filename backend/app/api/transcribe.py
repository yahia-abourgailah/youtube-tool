from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from .. import database, models, schemas
from ..tasks import transcribe
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=dict)
def trigger_transcription(
    request: schemas.TranscribeRequest,
    db: Session = Depends(database.get_db),
):
    """
    Trigger transcription for specific channels or videos.
    """
    if not request.channel_ids and not request.video_ids:
        raise HTTPException(status_code=400, detail="No channel IDs or video IDs provided")

    task_ids = []

    # Handle video-based transcription
    if request.video_ids:
        videos = db.query(models.Video).filter(models.Video.id.in_(request.video_ids)).all()
        if len(videos) != len(request.video_ids):
            found_ids = [v.id for v in videos]
            missing = set(request.video_ids) - set(found_ids)
            raise HTTPException(status_code=404, detail=f"Videos not found: {missing}")

        job = models.Job(
            job_type="transcription",
            entity_id=f"videos_{len(request.video_ids)}",
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        task = transcribe.transcribe_videos_task.delay(request.video_ids, request.force_retranscribe)
        job.celery_task_id = task.id
        db.commit()
        task_ids.append(task.id)

        return {
            "message": f"Started transcription for {len(request.video_ids)} video(s)",
            "task_ids": task_ids,
        }

    # Handle channel-based transcription
    channels = db.query(models.Channel).filter(models.Channel.id.in_(request.channel_ids)).all()
    if len(channels) != len(request.channel_ids):
        found_ids = [c.id for c in channels]
        missing = set(request.channel_ids) - set(found_ids)
        raise HTTPException(status_code=404, detail=f"Channels not found: {missing}")

    for channel in channels:
        job = models.Job(job_type="transcription", entity_id=f"channel_{channel.id}", status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)

        task = transcribe.transcribe_channel_task.delay(channel.id, request.force_retranscribe)
        job.celery_task_id = task.id
        db.commit()
        task_ids.append(task.id)

    return {
        "message": f"Started {len(channels)} transcription tasks",
        "task_ids": task_ids
    }


@router.post("/all-untranscribed", response_model=dict)
def transcribe_all_untranscribed(db: Session = Depends(database.get_db)):
    """
    Transcribe all chunks that have no transcript, regardless of video/channel.
    """
    untranscribed_count = db.query(models.AudioChunk).filter(
        (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
    ).count()

    if untranscribed_count == 0:
        return {"message": "No untranscribed chunks found", "task_ids": []}

    job = models.Job(
        job_type="transcription",
        entity_id="all_untranscribed",
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = transcribe.transcribe_all_untranscribed_task.delay()
    job.celery_task_id = task.id
    db.commit()

    return {
        "message": f"Started transcription for {untranscribed_count} untranscribed chunks",
        "task_ids": [task.id],
    }
