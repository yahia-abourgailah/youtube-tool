import os
from sqlalchemy.exc import IntegrityError
import uuid
import redis
from sqlalchemy import or_, and_
from ..celery_app import celery_app
from .. import models, database
from ..utils import youtube, logging as activity_log, slack, settings as settings_util, paths
import logging
import urllib.error
from pytubefix.exceptions import VideoUnavailable, BotDetection

logger = logging.getLogger(__name__)

_redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Never auto-retry videos that need a human decision or that would hammer YouTube.
# - "Stopped by user": the user explicitly stopped this video.
# - "System Paused"/bot markers: re-queueing these risks an IP ban.
SKIP_AUTO_RETRY_MARKERS = (
    "stopped by user",
    "system paused",
    "bot detection",
    "botdetection",
    "sign in to confirm you",
    # Permanent YouTube errors: retrying these only burns requests
    "video unavailable",
    "private video",
    "members-only",
    "removed by the uploader",
)

@celery_app.task(bind=True)
def process_channel_task(self, channel_id: int):
    """Fetch all videos for a channel and queue download tasks."""
    db = database.SessionLocal()
    try:
        channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
        if not channel:
            logger.error(f"Channel with ID {channel_id} not found in database.")
            return "Channel not found"
        
        activity_log.log_activity(db, f"Starting to process channel: {channel.url}", channel_id=channel_id)
        channel.status = "processing"
        db.commit()
    
        videos, channel_name = youtube.get_channel_videos(channel.url)
        
        # Update channel name if we got it from YouTube
        if channel_name and not channel.name:
            channel.name = channel_name
            db.commit()
        
        logger.info(f"Channel {channel_id} has {len(videos)} videos total.")
        
        # A video can be in several playlists/channels; it is downloaded and transcribed once,
        # under the first one that adds it (videos.video_id is unique)
        new_videos_count = 0
        duplicate_count = 0
        for v_data in videos:
            existing_video = db.query(models.Video).filter(models.Video.video_id == v_data["video_id"]).first()
            if existing_video:
                duplicate_count += 1
                continue
            video = models.Video(
                video_id=v_data["video_id"],
                channel_id=channel.id,
                title=v_data["title"],
                duration=v_data["duration"],
                upload_date=v_data["upload_date"],
                status="pending"
            )
            db.add(video)
            try:
                db.flush()
            except IntegrityError:
                # Another playlist processed at the same time added this video first.
                # Everything before this point is already committed, so only this insert is undone.
                db.rollback()
                duplicate_count += 1
                continue
            # Queue individual video download (creates its own job record)
            queue_video_download(db, video)
            new_videos_count += 1

        activity_log.log_activity(
            db,
            f"Found {len(videos)} videos, queued {new_videos_count} new, skipped {duplicate_count} already added from another playlist/channel",
            channel_id=channel_id,
        )
        
        logger.info(f"Queued {new_videos_count} new videos for downloading from channel {channel_id}.")
        channel.status = "completed"
        job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Processed channel {channel_id}, found {len(videos)} videos, queued {new_videos_count} new."
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process channel {channel_id}: {str(e)}", exc_info=True)
        if 'channel' in locals() and channel:
            activity_log.log_activity(db, f"Channel processing failed: {str(e)}", channel_id=channel_id, level="error")
            channel.status = "failed"
            job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
            if job:
                job.status = "failed"
            db.commit()
            
            # Send Slack notification for channel processing errors
            slack.notify_slack(
                f"🚨 *Channel Processing Error*\n"
                f"Channel ID: {channel_id}\n"
                f"URL: {channel.url}\n"
                f"Error: {str(e)}"
            )
        return f"Failed: {str(e)}"
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def download_video_task(self, video_id: int):
    """Download audio and transcript for a specific video."""
    db = database.SessionLocal()
    try:
        video = db.query(models.Video).filter(models.Video.id == video_id).first()
        if not video:
            return "Video not found"
        
        activity_log.log_activity(db, f"Downloading video: {video.title}", video_id=video_id)
        video.status = "downloading"
        db.commit()
    
        base_data_dir = paths.data_path()
        data_dir = os.path.join(base_data_dir, "channels", str(video.channel_id), "videos", str(video.video_id))
        os.makedirs(data_dir, exist_ok=True)
        
        # Download audio
        audio_path = youtube.download_audio(video.video_id, data_dir)
        if not audio_path:
            raise Exception("Failed to download audio")
            
        # YouTube captions aren't used (transcripts come from the ASR server), and fetching them
        # costs extra YouTube requests that trigger 429 rate limits, so they are off by default
        if os.getenv("DOWNLOAD_CAPTIONS", "false").lower() == "true":
            transcript_path = youtube.download_transcript(video.video_id, data_dir)
            if not transcript_path:
                activity_log.log_activity(db, f"Audio downloaded, but no Arabic transcript found.", video_id=video_id, level="warning")
                video.error_message = "No Arabic transcript found (audio only)"
            else:
                activity_log.log_activity(db, f"Audio and transcript downloaded successfully.", video_id=video_id)
                video.error_message = None
        else:
            activity_log.log_activity(db, f"Audio downloaded successfully.", video_id=video_id)
            video.error_message = None
            
        # Save metadata
        youtube.save_metadata(video.video_id, {
            "video_id": video.video_id,
            "title": video.title,
            "duration": video.duration,
            "upload_date": video.upload_date
        }, data_dir)
        
        video.status = "processing"
        # Mark download job as processing (split is next)
        job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
        if job:
            job.status = "processing"
        db.commit()

        # Queue audio splitting task
        from .process import split_audio_task
        task = split_audio_task.delay(video.id)
        video.celery_task_id = task.id
        db.commit()

        # The download succeeded, so give this video a fresh retry budget.
        _redis.delete(f"auto_retry:video:{video.id}")
        
    except Exception as e:
        db.rollback()
        
        # Check for critical errors that require system pause
        error_str = str(e)
        critical_error = False
        pause_reason = ""

        # Bot Detection
        if isinstance(e, BotDetection) or "bot" in error_str.lower() and "detected" in error_str.lower():
            critical_error = True
            pause_reason = "YouTube Bot Detection"
        
        # SSL / Network blocking
        elif isinstance(e, urllib.error.URLError) and ("_ssl.c" in error_str or "EOF" in error_str):
            critical_error = True
            pause_reason = "SSL/Network Block (Possible IP Ban)"

        if critical_error:
            logger.critical(f"CRITICAL ERROR DETECTED: {pause_reason}. Pausing system.")
            try:
                # Pause all pending videos, and tag them so the auto-retry sweep
                # never re-queues them and triggers another ban.
                db.query(models.Video).filter(models.Video.status == "pending").update(
                    {"status": "failed", "error_message": f"System Paused: {pause_reason}"}
                )
                db.commit()
                
                # Notify Slack immediately
                slack.notify_slack(
                    f"🛑 *SYSTEM PAUSED AUTOMATICALLY*\n"
                    f"Reason: {pause_reason}\n"
                    f"Video: {video_id}\n"
                    f"Error: {error_str}\n"
                    f"All pending videos have been paused to prevent IP bans."
                )
                
                # Mark current video as failed immediately, do not retry
                if 'video' in locals() and video:
                     video.status = "failed"
                     video.error_message = f"System Paused: {pause_reason}"
                     job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
                     if job:
                         job.status = "failed"
                     db.commit()

                return f"System Paused: {pause_reason}"
                
            except Exception as pause_err:
                logger.error(f"Failed to execute system pause: {pause_err}")

        # Use local video_id variable for logging if video object is detached
        logger.error(f"Error downloading video {video_id}: {e}")
        # Re-query inside the error handler if we need to update status, 
        # or use the already fetched object if expire_on_commit is False.
        # However, to be extra safe, we ensure the object is still bound.
        if 'video' in locals() and video:
            video.retry_count += 1
            video.error_message = str(e)
            if video.retry_count >= 3:
                activity_log.log_activity(db, f"Download failed after 3 retries: {str(e)}", video_id=video_id, level="error")
                video.status = "failed"
                job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
                if job:
                    job.status = "failed"
                
                # Send Slack notification for final failure
                slack.notify_slack(
                    f"🚨 *Video Download Failed (Final)*\n"
                    f"Video ID: {video.video_id}\n"
                    f"Title: {video.title}\n"
                    f"Error: {str(e)}\n"
                    f"Retries: {video.retry_count}/3"
                )
            else:
                activity_log.log_activity(db, f"Download failed (retry {video.retry_count}/3): {str(e)}", video_id=video_id, level="warning")
                video.status = "pending"
                # Commit before self.retry() raises Retry, otherwise the pending
                # status is rolled back and the UI shows a stale state.
                db.commit()
                raise self.retry(exc=e, countdown=60 * (2 ** video.retry_count))
            db.commit()
        return str(e)
    finally:
        # Cleanup source files if download failed significantly
        if 'video' in locals() and video and video.status == "failed":
            try:
                patterns = [
                    f"{video.video_id}_audio.wav",
                    f"{video.video_id}_audio.mp4",
                    f"{video.video_id}_audio.webm",
                    f"{video.video_id}_audio.m4a",
                    f"{video.video_id}_audio.mp3",
                    f"{video.video_id}_transcript.txt",
                    f"{video.video_id}_metadata.json"
                ]
                base_data_dir = paths.data_path()
                data_dir = os.path.join(base_data_dir, "channels", str(video.channel_id), "videos", str(video.video_id))
                for pattern in patterns:
                    file_path = os.path.join(data_dir, pattern)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception:
                pass
        db.close()
    
    return f"Downloaded video {video_id}"


def queue_channel_process(db, channel: models.Channel) -> models.Job:
    """Create a channel-processing job and dispatch it with a pre-generated task id."""
    task_id = str(uuid.uuid4())
    job = models.Job(
        job_type="channel_process",
        entity_id=str(channel.id),
        status="pending",
        celery_task_id=task_id,
    )
    channel.status = "pending"
    channel.celery_task_id = task_id
    db.add(job)
    db.commit()

    try:
        process_channel_task.apply_async(args=[channel.id], task_id=task_id)
    except Exception:
        job.status = "failed"
        db.commit()
        raise
    return job


def queue_video_download(db, video: models.Video) -> models.Job:
    """Create a download job and dispatch it with a pre-generated task id.

    Pre-generating the id lets the worker start before ``celery_task_id`` is
    committed without leaving the job stuck as ``pending``.
    """
    task_id = str(uuid.uuid4())
    job = models.Job(
        job_type="download",
        entity_id=str(video.id),
        status="pending",
        celery_task_id=task_id,
    )
    video.status = "pending"
    video.retry_count = 0
    video.error_message = None
    video.celery_task_id = task_id
    db.add(job)
    db.commit()

    try:
        download_video_task.apply_async(args=[video.id], task_id=task_id)
    except Exception:
        job.status = "failed"
        db.commit()
        raise
    return job


@celery_app.task(bind=True)
def auto_retry_failed_task(self):
    """
    Periodically re-queue failed videos and orphaned pending videos (ones with no
    Celery task attached, e.g. after a crash or a manual reset).

    Safeguards:
    - never retries videos stopped by the user or paused by bot detection,
    - caps automatic rounds per video (AUTO_RETRY_MAX_ROUNDS, 7-day window),
    - queues at most AUTO_RETRY_BATCH_SIZE videos per sweep.
    """
    if not settings_util.get_settings().get("auto_retry", True):
        return "Auto retry disabled"

    # Prevent overlapping sweeps if one takes longer than the beat interval
    if not _redis.set("auto_retry:sweep", 1, nx=True, ex=900):
        return "Retry sweep already running"

    db = database.SessionLocal()
    try:
        max_rounds = int(os.getenv("AUTO_RETRY_MAX_ROUNDS", "5"))
        batch_size = int(os.getenv("AUTO_RETRY_BATCH_SIZE", "10"))

        candidates = (
            db.query(models.Video)
            .filter(
                or_(
                    models.Video.status == "failed",
                    # A pending video with no task id was never queued (or lost its task).
                    and_(models.Video.status == "pending", models.Video.celery_task_id == None),
                )
            )
            .order_by(models.Video.created_at.asc())
            .limit(batch_size * 5)
            .all()
        )

        queued = 0
        skipped = 0
        for video in candidates:
            if queued >= batch_size:
                break

            error = (video.error_message or "").lower()
            if any(marker in error for marker in SKIP_AUTO_RETRY_MARKERS):
                skipped += 1
                continue

            counter_key = f"auto_retry:video:{video.id}"
            rounds = int(_redis.get(counter_key) or 0)
            if rounds >= max_rounds:
                skipped += 1
                continue

            _redis.incr(counter_key)
            _redis.expire(counter_key, 7 * 24 * 3600)

            try:
                queue_video_download(db, video)
            except Exception:
                _redis.decr(counter_key)
                raise

            queued += 1

        if queued:
            activity_log.log_activity(db, f"Auto-retry queued {queued} video(s) for download.")
            logger.info(f"Auto-retry sweep queued {queued} video(s), skipped {skipped}")
        return f"Queued {queued} video(s) for retry"

    except Exception as e:
        db.rollback()
        logger.error(f"Auto-retry sweep failed: {e}", exc_info=True)
        return f"Retry sweep failed: {str(e)}"
    finally:
        db.close()
        _redis.delete("auto_retry:sweep")
