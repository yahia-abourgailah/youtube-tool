"""Database + filesystem deletion helpers used by the API delete endpoints."""

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from . import storage

logger = logging.getLogger(__name__)


def _revoke(task_id: str) -> None:
    if not task_id:
        return
    try:
        from ..celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True)
    except Exception as exc:  # pragma: no cover - broker may be unavailable
        logger.warning(f"Could not revoke task {task_id}: {exc}")


def delete_video(db: Session, video: models.Video) -> None:
    """Delete a video, its chunks, related jobs and files."""
    video_pk = video.id
    channel_id = video.channel_id
    youtube_id = video.video_id
    task_ids = [video.celery_task_id]

    chunks = db.query(models.AudioChunk).filter(models.AudioChunk.video_id == video_pk).all()
    for chunk in chunks:
        storage.delete_chunk_files(chunk)

    # Keep the audit trail but detach it so the FK does not block deletion.
    db.query(models.ActivityLog).filter(models.ActivityLog.video_id == video_pk).update(
        {models.ActivityLog.video_id: None}, synchronize_session=False
    )
    db.query(models.Job).filter(
        or_(
            models.Job.entity_id == str(video_pk),
            models.Job.entity_id == f"video_{video_pk}",
        )
    ).delete(synchronize_session=False)
    db.query(models.AudioChunk).filter(models.AudioChunk.video_id == video_pk).delete(
        synchronize_session=False
    )
    db.delete(video)
    db.commit()

    storage.delete_video_dir(channel_id, youtube_id)
    for task_id in task_ids:
        _revoke(task_id)


def delete_channel(db: Session, channel: models.Channel) -> None:
    """Delete a channel, all of its videos and their files."""
    channel_pk = channel.id
    task_ids = [channel.celery_task_id]

    videos = db.query(models.Video).filter(models.Video.channel_id == channel_pk).all()
    for video in videos:
        task_ids.append(video.celery_task_id)
        delete_video(db, video)

    db.query(models.ActivityLog).filter(models.ActivityLog.channel_id == channel_pk).update(
        {models.ActivityLog.channel_id: None}, synchronize_session=False
    )
    db.query(models.Job).filter(
        or_(
            models.Job.entity_id == str(channel_pk),
            models.Job.entity_id == f"channel_{channel_pk}",
        )
    ).delete(synchronize_session=False)
    db.delete(channel)
    db.commit()

    storage.delete_channel_dir(channel_pk)
    for task_id in task_ids:
        _revoke(task_id)
