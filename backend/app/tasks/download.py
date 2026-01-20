import os
from ..celery_app import celery_app
from .. import models, database
from ..utils import youtube, logging as activity_log, slack
import logging

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
        db.commit()
        return f"Processed channel {channel_id}, found {len(videos)} videos, queued {new_videos_count} new."
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process channel {channel_id}: {str(e)}", exc_info=True)
        if 'channel' in locals() and channel:
            activity_log.log_activity(db, f"Channel processing failed: {str(e)}", channel_id=channel_id, level="error")
            channel.status = "failed"
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
    
        data_dir = os.path.join(os.getcwd(), "data")
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
        db.commit()
        
        # Queue audio splitting task
        from .process import split_audio_task
        task = split_audio_task.delay(video.id)
        video.celery_task_id = task.id
        db.commit()
        
    except Exception as e:
        db.rollback()
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
                data_dir = os.path.join(os.getcwd(), "data")
                for pattern in patterns:
                    file_path = os.path.join(data_dir, pattern)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception:
                pass
        db.close()
    
    return f"Downloaded video {video_id}"
