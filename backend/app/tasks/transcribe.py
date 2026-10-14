import os
import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..celery_app import celery_app
from .. import models, database
from ..utils import logging as activity_log, settings as settings_util

logger = logging.getLogger(__name__)

ASR_ENDPOINT = os.getenv("ASR_ENDPOINT", "http://107.170.20.205:8000/transcribe")
ASR_API_KEY = os.getenv("ASR_API_KEY")
ASR_API_SECRET = os.getenv("ASR_API_SECRET")
MAX_WORKERS = int(os.getenv("ASR_WORKERS", "5"))


def process_chunk_transcription(chunk_id: int, file_path: str, max_retries: int = 3) -> bool:
    """
    Helper function to transcribe a single chunk via external ASR API.
    Creates its own DB session to be thread-safe.
    Retries on 429/5xx errors with backoff.
    """
    db = database.SessionLocal()
    try:
        # Skip if already transcribed (handles replayed tasks after crash)
        chunk = db.query(models.AudioChunk).filter(models.AudioChunk.id == chunk_id).first()
        if chunk and chunk.transcript_text:
            return True

        if not os.path.exists(file_path):
            logger.warning(f"Audio file not found: {file_path}")
            return False

        headers = {
            "X-API-Key": ASR_API_KEY,
            "X-API-Secret": ASR_API_SECRET,
        }

        for attempt in range(max_retries):
            try:
                with open(file_path, "rb") as f:
                    files = {"audio": ("chunk.raw", f, "application/octet-stream")}
                    response = requests.post(ASR_ENDPOINT, headers=headers, files=files, timeout=180)

                if response.status_code == 200:
                    data = response.json()
                    transcribed_text = data.get("text", data.get("transcription", ""))
                    if transcribed_text:
                        chunk = db.query(models.AudioChunk).filter(models.AudioChunk.id == chunk_id).first()
                        if chunk:
                            chunk.transcript_text = transcribed_text
                            db.commit()
                            return True
                    else:
                        logger.warning(f"Empty transcription for chunk {chunk_id}")
                        return False

                elif response.status_code == 429:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"Rate limited on chunk {chunk_id}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)

                elif response.status_code >= 500:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"Server error {response.status_code} on chunk {chunk_id}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)

                else:
                    logger.error(f"ASR API error for chunk {chunk_id}: {response.status_code} - {response.text}")
                    return False

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on chunk {chunk_id} (attempt {attempt + 1}/{max_retries})")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_id}: {e}")
                return False

        logger.error(f"Chunk {chunk_id} failed after {max_retries} retries")
        return False

    except Exception as e:
        logger.error(f"Error processing chunk {chunk_id}: {e}")
        return False
    finally:
        db.close()


@celery_app.task(bind=True)
def transcribe_channel_task(self, channel_id: int, force_retranscribe: bool = False):
    """
    Transcribe all audio chunks for a given channel using external ASR API.
    Processes chunks in parallel with ThreadPoolExecutor.
    """
    db = database.SessionLocal()
    try:
        channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
        if not channel:
            return "Channel not found"

        activity_log.log_activity(db, f"Starting transcription for channel: {channel.name or channel.url}", channel_id=channel_id)

        chunks_query = db.query(models.AudioChunk).join(models.Video).filter(models.Video.channel_id == channel_id)

        if not force_retranscribe:
            chunks_query = chunks_query.filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            )

        chunks_data = [(c.id, c.file_path) for c in chunks_query.all()]

        if not chunks_data:
            activity_log.log_activity(db, "No chunks to transcribe.", channel_id=channel_id)
            return "No chunks to transcribe"

        total = len(chunks_data)
        logger.info(f"Found {total} chunks to transcribe for channel {channel_id}")
        logger.info(f"ASR endpoint: {ASR_ENDPOINT}, workers: {MAX_WORKERS}")

        success_count = 0
        fail_count = 0
        processed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_chunk_transcription, cid, path): cid
                for cid, path in chunks_data
            }

            for future in as_completed(futures):
                chunk_id = futures[future]
                processed += 1
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    logger.error(f"Chunk {chunk_id} generated an exception: {exc}")
                    fail_count += 1

                if processed % 50 == 0:
                    logger.info(f"Progress: {processed}/{total} chunks processed. Success: {success_count}, Failed: {fail_count}")

        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}", channel_id=channel_id)
        # Mark the transcription job as completed
        job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Transcription task failed: {e}")
        # Mark the transcription job as failed
        try:
            job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()


@celery_app.task(bind=True)
def transcribe_videos_task(self, video_ids: list, force_retranscribe: bool = False):
    """
    Transcribe all audio chunks for specific videos using external ASR API.
    Processes chunks in parallel with ThreadPoolExecutor.
    """
    db = database.SessionLocal()
    try:
        videos = db.query(models.Video).filter(models.Video.id.in_(video_ids)).all()
        if not videos:
            return "No videos found"

        video_titles = ", ".join(v.title or v.video_id for v in videos)
        activity_log.log_activity(db, f"Starting transcription for {len(videos)} video(s): {video_titles[:200]}")

        chunks_query = db.query(models.AudioChunk).join(models.Video).filter(models.Video.id.in_(video_ids))

        if not force_retranscribe:
            chunks_query = chunks_query.filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            )

        chunks_data = [(c.id, c.file_path) for c in chunks_query.all()]

        if not chunks_data:
            activity_log.log_activity(db, "No chunks to transcribe for selected videos.")
            return "No chunks to transcribe"

        total = len(chunks_data)
        logger.info(f"Found {total} chunks to transcribe for {len(video_ids)} video(s)")
        logger.info(f"ASR endpoint: {ASR_ENDPOINT}, workers: {MAX_WORKERS}")

        success_count = 0
        fail_count = 0
        processed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_chunk_transcription, cid, path): cid
                for cid, path in chunks_data
            }

            for future in as_completed(futures):
                chunk_id = futures[future]
                processed += 1
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    logger.error(f"Chunk {chunk_id} generated an exception: {exc}")
                    fail_count += 1

                if processed % 50 == 0:
                    logger.info(f"Progress: {processed}/{total} chunks processed. Success: {success_count}, Failed: {fail_count}")

        activity_log.log_activity(db, f"Video transcription completed. Success: {success_count}, Failed: {fail_count}")
        job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Video transcription task failed: {e}")
        try:
            job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()


@celery_app.task(bind=True)
def transcribe_all_untranscribed_task(self):
    """
    Find and transcribe ALL chunks that have no transcript, regardless of video/channel.
    Useful after crashes or partial runs.
    """
    db = database.SessionLocal()
    try:
        chunks_data = [
            (c.id, c.file_path)
            for c in db.query(models.AudioChunk).filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            ).all()
        ]

        if not chunks_data:
            activity_log.log_activity(db, "No untranscribed chunks found.")
            return "No chunks to transcribe"

        total = len(chunks_data)
        logger.info(f"Found {total} untranscribed chunks across all videos")
        logger.info(f"ASR endpoint: {ASR_ENDPOINT}, workers: {MAX_WORKERS}")
        activity_log.log_activity(db, f"Starting transcription for {total} untranscribed chunks")

        success_count = 0
        fail_count = 0
        processed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_chunk_transcription, cid, path): cid
                for cid, path in chunks_data
            }

            for future in as_completed(futures):
                chunk_id = futures[future]
                processed += 1
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    logger.error(f"Chunk {chunk_id} generated an exception: {exc}")
                    fail_count += 1

                if processed % 50 == 0:
                    logger.info(f"Progress: {processed}/{total} chunks processed. Success: {success_count}, Failed: {fail_count}")

        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}")
        job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Transcribe-all task failed: {e}")
        try:
            job = db.query(models.Job).filter(models.Job.celery_task_id == self.request.id).first()
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()