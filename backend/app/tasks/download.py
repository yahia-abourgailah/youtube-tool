import os
from ..celery_app import celery_app
from .. import models, database
from ..utils import youtube, logging as activity_log, slack
import logging
import urllib.error
from pytubefix.exceptions import VideoUnavailable, BotDetection

logger = logging.getLogger(__name__)

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
        
        new_videos_count = 0
        for v_data in videos:
            # Check if video already exists
            existing_video = db.query(models.Video).filter(models.Video.video_id == v_data["video_id"]).first()
            if not existing_video:
                video = models.Video(
                    video_id=v_data["video_id"],
                    channel_id=channel.id,
                    title=v_data["title"],
                    duration=v_data["duration"],
                    upload_date=v_data["upload_date"],
                    status="pending"
                )
                db.add(video)
                db.flush()
                # Queue individual video download
                task = download_video_task.delay(video.id)
                video.celery_task_id = task.id
                db.commit()
                new_videos_count += 1
        
        activity_log.log_activity(db, f"Found {len(videos)} videos, queued {new_videos_count} new for processing", channel_id=channel_id)
        
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
    
        base_data_dir = os.getenv("DATA_PATH", os.path.join(os.getcwd(), "data"))
        data_dir = os.path.join(base_data_dir, "channels", str(video.channel_id), "videos", str(video.video_id))
        os.makedirs(data_dir, exist_ok=True)
        
        # Download audio
        audio_path = youtube.download_audio(video.video_id, data_dir)
        if not audio_path:
            raise Exception("Failed to download audio")
            
        # Download transcript
        transcript_path = youtube.download_transcript(video.video_id, data_dir)
        if not transcript_path:
            activity_log.log_activity(db, f"Audio downloaded, but no Arabic transcript found.", video_id=video_id, level="warning")
            video.error_message = "No Arabic transcript found (audio only)"
        else:
            activity_log.log_activity(db, f"Audio and transcript downloaded successfully.", video_id=video_id)
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
                # Pause all pending videos
                db.query(models.Video).filter(models.Video.status == "pending").update({"status": "failed"})
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
                # Retry with countdown
                self.retry(exc=e, countdown=60 * (2 ** video.retry_count))
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
                base_data_dir = os.getenv("DATA_PATH", os.path.join(os.getcwd(), "data"))
                data_dir = os.path.join(base_data_dir, "channels", str(video.channel_id), "videos", str(video.video_id))
                for pattern in patterns:
                    file_path = os.path.join(data_dir, pattern)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception:
                pass
        db.close()
    
    return f"Downloaded video {video_id}"
