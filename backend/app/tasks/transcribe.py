import os
import logging
import time
import requests
import redis
import io
import re
from difflib import SequenceMatcher
from typing import Optional
from pydub import AudioSegment, silence
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..celery_app import celery_app
from .. import models, database
from ..utils import logging as activity_log, settings as settings_util, paths

logger = logging.getLogger(__name__)

ASR_ENDPOINT = os.getenv("ASR_ENDPOINT", "http://107.170.20.205:8000/transcribe")
ASR_API_KEY = os.getenv("ASR_API_KEY")
ASR_API_SECRET = os.getenv("ASR_API_SECRET")
MAX_WORKERS = int(os.getenv("ASR_WORKERS", "5"))
# ASR server allows ASR_RATE_LIMIT requests per minute; pace calls across all workers via Redis
ASR_RATE_LIMIT = max(1, int(os.getenv("ASR_RATE_LIMIT", "30")))
ASR_MIN_INTERVAL_MS = int(60000 / ASR_RATE_LIMIT * 1.1)
ASR_MODEL_NAME = os.getenv("ASR_MODEL_NAME", "")
ASR_MODEL_VERSION = os.getenv("ASR_MODEL_VERSION", "")
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "ar-EG")
# The ASR server drops the last words when speech runs to the very end of the file,
# so append trailing silence to the copy we send (the chunk file itself is unchanged)
ASR_PAD_MS = int(os.getenv("ASR_PAD_MS", "500"))
# Re-check each chunk's ending by transcribing its last ASR_TAIL_MS on its own (costs 1 extra request per chunk)
ASR_TAIL_CHECK = os.getenv("ASR_TAIL_CHECK", "true").lower() == "true"
ASR_TAIL_MS = int(os.getenv("ASR_TAIL_MS", "4000"))
ASR_RETRY_PADS_MS = [0, 1000, 250]
# Share of the tail clip's words that must appear, in order, at the end of the full transcript
ASR_TAIL_MATCH = float(os.getenv("ASR_TAIL_MATCH", "0.7"))
# Failed chunks are retried by the auto-transcription sweep with exponential
# backoff (15m, 30m, 1h, ...) capped here, so a bad chunk can't hammer the server.
MAX_BACKOFF_MINUTES = int(os.getenv("AUTO_TRANSCRIBE_MAX_BACKOFF_MINUTES", "360"))
_redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def wait_for_asr_slot():
    """Block until this process may send the next ASR request (shared across processes)."""
    while not _redis.set("asr:rate_slot", 1, nx=True, px=ASR_MIN_INTERVAL_MS):
        time.sleep(0.2)


def _collect_asr_meta(data: dict, meta: dict) -> None:
    """Copy model/confidence/language metadata from an ASR response when present."""
    model = data.get("model") or data.get("model_name") or ASR_MODEL_NAME
    version = data.get("version") or data.get("model_version") or ASR_MODEL_VERSION
    language = data.get("language") or data.get("lang") or ASR_LANGUAGE
    confidence = data.get("confidence", data.get("score", data.get("probability")))

    if model:
        meta["asr_model"] = str(model)[:100]
    if version:
        meta["asr_version"] = str(version)[:100]
    if language:
        meta["language"] = str(language)[:20]
    if confidence is not None:
        try:
            meta["confidence"] = float(confidence)
        except (TypeError, ValueError):
            pass


def _asr_request(segment: AudioSegment, chunk_id: int, max_retries: int, meta_out: Optional[dict] = None) -> Optional[str]:
    """Send one audio segment to the ASR server. Returns the text ('' if none), or None on failure."""
    headers = {
        "X-API-Key": ASR_API_KEY,
        "X-API-Secret": ASR_API_SECRET,
    }
    audio_buffer = io.BytesIO()
    segment.export(audio_buffer, format="wav")

    for attempt in range(max_retries):
        try:
            wait_for_asr_slot()
            audio_buffer.seek(0)
            files = {"audio": ("chunk.raw", audio_buffer, "application/octet-stream")}
            response = requests.post(ASR_ENDPOINT, headers=headers, files=files, timeout=180)

            if response.status_code == 200:
                data = response.json()
                if meta_out is not None:
                    _collect_asr_meta(data, meta_out)
                return data.get("text", data.get("transcription", "")) or ""

            elif response.status_code == 429:
                wait_time = 60
                logger.warning(f"Rate limited on chunk {chunk_id}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            elif response.status_code >= 500:
                wait_time = 10 * (attempt + 1)
                logger.warning(f"Server error {response.status_code} on chunk {chunk_id}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            else:
                logger.error(f"ASR API error for chunk {chunk_id}: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on chunk {chunk_id} (attempt {attempt + 1}/{max_retries})")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id}: {e}")
            return None

    logger.error(f"Chunk {chunk_id} failed after {max_retries} retries")
    return None


def _padded(segment: AudioSegment, pad_ms: int) -> AudioSegment:
    if pad_ms <= 0:
        return segment
    return segment + AudioSegment.silent(duration=pad_ms, frame_rate=segment.frame_rate)


_AR_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_GLUED_PUNCT = re.compile(r"([.,،؛;:!?؟…]+)(?=\w)")
_AR_MARKS = re.compile(r"[\u064B-\u0652\u0640]|[^\w]")


def _tokens(text: str) -> list:
    """(original word, normalized word) pairs, so spelling variants like ة/ه or أ/ا still match."""
    pairs = []
    # "بتغني..كل" -> "بتغني.. كل": punctuation glued to the next word hides that word
    text = _GLUED_PUNCT.sub(r"\1 ", text)
    for word in text.split():
        norm = _AR_MARKS.sub("", word).lower().translate(_AR_LETTERS)
        if norm:
            pairs.append((word, norm))
    return pairs


def _closest_word(word: str, candidates: list) -> str:
    """The most similar candidate (exact match first), or the word itself if none is close enough."""
    if word in candidates:
        return word
    best = max(candidates, key=lambda c: SequenceMatcher(None, word, c).ratio(), default=None)
    return best if best is not None and _same_word(word, best) else word


def _same_word(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.75


def _tail_covered(full_text: str, tail_text: str) -> bool:
    """
    True if the words heard in the tail clip appear, in order, at the end of the full transcript.
    Checking only the last words isn't enough: when the speaker repeats a phrase the ASR keeps
    one copy, and the last words still match while the repetition is missing.
    """
    tail = [n for _, n in _tokens(tail_text)]
    if not tail:
        return True
    window = [n for _, n in _tokens(full_text)][-(len(tail) + 4):]
    if not all(any(_same_word(t, w) for w in window) for t in tail[-2:]):
        return False
    tail_norm = [_closest_word(t, window) for t in tail]
    matched = sum(b.size for b in SequenceMatcher(None, window, tail_norm, autojunk=False).get_matching_blocks())
    return matched / len(tail) >= ASR_TAIL_MATCH


def _stitch(full_text: str, tail_text: str) -> Optional[str]:
    """
    Append the words of the tail clip that come after the end of the full transcript.
    The tail clip starts inside the chunk, so its first words overlap the end of the
    full transcript; we find that overlap and append what follows it.
    Returns None if the overlap can't be found reliably.
    """
    tail = _tokens(tail_text)
    window = [n for _, n in _tokens(full_text)][-(len(tail) + 4):]
    # Map spelling variants onto the word used in the full transcript so exact matching works
    tail_norm = [_closest_word(n, window) for _, n in tail]
    blocks = SequenceMatcher(None, window, tail_norm, autojunk=False).get_matching_blocks()
    # The overlap must reach (almost) the end of the full transcript
    ends = [b.b + b.size for b in blocks if b.size and b.a + b.size >= len(window) - 1]
    if not ends:
        return None
    cut = max(ends)
    missing = tail[cut:]
    head = full_text.rstrip()
    # The full transcript often ends with a half word ("خطو"); replace it with the complete one
    if missing and window and window[-1] != tail_norm[cut - 1 if cut else 0] and _same_word(window[-1], missing[0][1]):
        head = head.rsplit(maxsplit=1)[0] if " " in head else ""
    return f"{head} {' '.join(orig for orig, _ in missing)}".strip()


def _tail_clip(segment: AudioSegment) -> AudioSegment:
    """Last ~ASR_TAIL_MS of the chunk, starting at a pause so the first word isn't cut in half."""
    target = len(segment) - ASR_TAIL_MS
    lo, hi = max(0, target - 1500), min(len(segment), target + 1000)
    pauses = silence.detect_silence(segment[lo:hi], min_silence_len=100, silence_thresh=segment.dBFS - 16, seek_step=10)
    if pauses:
        mid = min(pauses, key=lambda p: abs(lo + (p[0] + p[1]) // 2 - target))
        target = lo + (mid[0] + mid[1]) // 2
    return segment[max(0, target):]


def transcribe_audio_file(file_path: str, chunk_id: int, max_retries: int = 5) -> tuple[Optional[str], dict]:
    """
    Transcribe one chunk file. The ASR server sometimes drops the last words of a file,
    so (when ASR_TAIL_CHECK is on) the last few seconds are also transcribed on their own;
    if those words are missing from the full transcript, retry with other paddings and
    finally append the missing words from the tail clip.

    Returns ``(text, metadata)``; metadata holds whatever model/confidence/language
    information the ASR server reported.
    """
    meta: dict = {}
    segment = AudioSegment.from_file(file_path)
    text = _asr_request(_padded(segment, ASR_PAD_MS), chunk_id, max_retries, meta_out=meta)
    if not text or not ASR_TAIL_CHECK or len(segment) < ASR_TAIL_MS + 2000:
        return text, meta

    tail_text = _asr_request(_padded(_tail_clip(segment), ASR_PAD_MS), chunk_id, max_retries, meta_out=meta)
    if not tail_text or _tail_covered(text, tail_text):
        return text, meta

    logger.info(f"Chunk {chunk_id}: transcript is missing its last words, retrying with other paddings")
    for pad_ms in ASR_RETRY_PADS_MS:
        retry_text = _asr_request(_padded(segment, pad_ms), chunk_id, max_retries, meta_out=meta)
        if retry_text and _tail_covered(retry_text, tail_text):
            logger.info(f"Chunk {chunk_id}: complete transcript with {pad_ms}ms padding")
            return retry_text, meta

    stitched = _stitch(text, tail_text)
    if stitched is None:
        logger.warning(f"Chunk {chunk_id}: could not recover the missing ending, keeping transcript as is")
        return text, meta
    logger.info(f"Chunk {chunk_id}: appended missing ending from tail clip")
    return stitched, meta


def process_chunk_transcription(chunk_id: int, file_path: str, max_retries: int = 5, force: bool = False) -> bool:
    """
    Helper function to transcribe a single chunk via external ASR API.
    Creates its own DB session to be thread-safe.
    """
    db = database.SessionLocal()
    try:
        # Skip if already transcribed (handles replayed tasks after crash)
        chunk = db.query(models.AudioChunk).filter(models.AudioChunk.id == chunk_id).first()
        if chunk and chunk.transcript_text and not force:
            return True

        if not os.path.exists(paths.resolve(file_path)):
            logger.warning(f"Audio file not found: {file_path}")
            return False

        transcribed_text, meta = transcribe_audio_file(paths.resolve(file_path), chunk_id, max_retries)
        if transcribed_text is None:
            return False
        if not transcribed_text:
            logger.warning(f"Empty transcription for chunk {chunk_id}")
            return False

        chunk = db.query(models.AudioChunk).filter(models.AudioChunk.id == chunk_id).first()
        if chunk:
            chunk.transcript_text = transcribed_text
            if meta.get("asr_model"):
                chunk.asr_model = meta["asr_model"]
            if meta.get("asr_version"):
                chunk.asr_version = meta["asr_version"]
            if meta.get("language"):
                chunk.language = meta["language"]
            if meta.get("confidence") is not None:
                chunk.confidence = meta["confidence"]
            db.commit()
            # Keep a .txt copy next to the audio so transcripts are recoverable
            # even if the database is lost.
            try:
                txt_path = paths.transcript_path(file_path)
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(transcribed_text.strip())
            except Exception as e:
                logger.warning(f"Could not write transcript sidecar for chunk {chunk_id}: {e}")
            return True
        return False

    except Exception as e:
        logger.error(f"Error processing chunk {chunk_id}: {e}")
        return False
    finally:
        db.close()


@celery_app.task(bind=True)
def transcribe_channel_task(self, channel_id: int, force_retranscribe: bool = False, job_id: int = None):
    """
    Transcribe all audio chunks for a given channel using external ASR API.
    Processes chunks in parallel with ThreadPoolExecutor.
    """
    db = database.SessionLocal()
    try:
        channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
        if not channel:
            return "Channel not found"

        job = _find_job(db, self.request.id, job_id)
        if job:
            job.status = "processing"
            db.commit()

        activity_log.log_activity(db, f"Starting transcription for channel: {channel.name or channel.url}", channel_id=channel_id)

        chunks_query = db.query(models.AudioChunk).join(models.Video).filter(models.Video.channel_id == channel_id)

        if not force_retranscribe:
            chunks_query = chunks_query.filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            )

        chunks_data = [(c.id, c.file_path) for c in chunks_query.all()]

        if not chunks_data:
            activity_log.log_activity(db, "No chunks to transcribe.", channel_id=channel_id)
            job = _find_job(db, self.request.id, job_id)
            if job:
                job.status = "completed"
                job.progress = 100
                db.commit()
            return "No chunks to transcribe"

        total = len(chunks_data)
        logger.info(f"Found {total} chunks to transcribe for channel {channel_id}")
        logger.info(f"ASR endpoint: {ASR_ENDPOINT}, workers: {MAX_WORKERS}")

        success_count = 0
        fail_count = 0
        processed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_chunk_transcription, cid, path, force=force_retranscribe): cid
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
                    job = _find_job(db, self.request.id, job_id)
                    if job:
                        job.progress = round(processed / total * 100, 1)
                        db.commit()

        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}", channel_id=channel_id)
        # Mark the transcription job as completed
        job = _find_job(db, self.request.id, job_id)
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
            job = _find_job(db, self.request.id, job_id)
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()


@celery_app.task(bind=True)
def transcribe_videos_task(self, video_ids: list, force_retranscribe: bool = False, job_id: int = None):
    """
    Transcribe all audio chunks for specific videos using external ASR API.
    Processes chunks in parallel with ThreadPoolExecutor.
    """
    db = database.SessionLocal()
    # Initialized before the try so the finally block can use them even if the
    # task fails before the counting starts.
    success_count = 0
    fail_count = 0
    try:
        videos = db.query(models.Video).filter(models.Video.id.in_(video_ids)).all()
        if not videos:
            return "No videos found"

        job = _find_job(db, self.request.id, job_id)
        if job:
            job.status = "processing"
            db.commit()

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
            if job:
                job.status = "completed"
                job.progress = 100
                db.commit()
            return "No chunks to transcribe"

        total = len(chunks_data)
        logger.info(f"Found {total} chunks to transcribe for {len(video_ids)} video(s)")
        logger.info(f"ASR endpoint: {ASR_ENDPOINT}, workers: {MAX_WORKERS}")

        processed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_chunk_transcription, cid, path, force=force_retranscribe): cid
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
                    if job:
                        job.progress = round(processed / total * 100, 1)
                        db.commit()

        activity_log.log_activity(db, f"Video transcription completed. Success: {success_count}, Failed: {fail_count}")
        job = _find_job(db, self.request.id, job_id)
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Video transcription task failed: {e}")
        try:
            job = _find_job(db, self.request.id, job_id)
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()
        # Allow the auto-transcription sweep to retry chunks that failed, but
        # back off exponentially so a permanently failing chunk (silence, music)
        # is not re-sent to the ASR server every sweep. Progress resets the backoff.
        for vid in video_ids:
            _redis.delete(f"transcribe:video:{vid}")
            attempts_key = f"auto_transcribe:attempts:{vid}"
            retry_key = f"auto_transcribe:retry_at:{vid}"
            if fail_count:
                attempts = _redis.incr(attempts_key)
                _redis.expire(attempts_key, 7 * 24 * 3600)
                delay_minutes = min(15 * (2 ** (attempts - 1)), MAX_BACKOFF_MINUTES)
                _redis.set(retry_key, time.time() + delay_minutes * 60, ex=7 * 24 * 3600)
            else:
                _redis.delete(attempts_key, retry_key)


def _find_job(db, celery_task_id: str, job_id: int = None):
    """Find a Job by explicit id (preferred) or by Celery task id."""
    if job_id:
        return db.query(models.Job).filter(models.Job.id == job_id).first()
    return db.query(models.Job).filter(models.Job.celery_task_id == celery_task_id).first()


def queue_video_transcription(db, video_id: int, force: bool = False):
    """
    Create a transcription job for one video and dispatch it.
    Returns the Celery task, or None if the video is already queued.
    """
    lock_key = f"transcribe:video:{video_id}"
    # The lock prevents the periodic sweep from queueing the same video twice.
    # Its TTL is a safety net: if a worker dies without clearing it, a later
    # sweep will pick the video up again.
    if not _redis.set(lock_key, 1, nx=True, ex=24 * 3600):
        return None

    job = models.Job(
        job_type="transcription",
        entity_id=f"video_{video_id}",
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        # Pass job_id explicitly: the worker may pick the task up before we commit
        # celery_task_id, and then the job would never be marked completed.
        task = transcribe_videos_task.delay([video_id], force, job.id)
    except Exception:
        _redis.delete(lock_key)
        job.status = "failed"
        db.commit()
        raise

    job.celery_task_id = task.id
    db.commit()
    return task


@celery_app.task(bind=True)
def auto_transcribe_sweep_task(self):
    """
    Safety net for automatic transcription: find videos that still have untranscribed
    chunks and queue them. Runs periodically via Celery beat; queue_video_transcription
    skips videos that are already in flight.
    """
    if not settings_util.get_settings().get("auto_transcribe", True):
        return "Auto transcription disabled"

    # Prevent overlapping sweeps if one takes longer than the beat interval
    if not _redis.set("auto_transcribe:sweep", 1, nx=True, ex=900):
        return "Sweep already running"

    db = database.SessionLocal()
    try:
        rows = db.query(models.AudioChunk.video_id).filter(
            (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
        ).distinct().all()
        video_ids = [r[0] for r in rows if r[0] is not None]

        if not video_ids:
            return "No untranscribed chunks"

        queued = 0
        waiting = 0
        batch_size = int(os.getenv("AUTO_TRANSCRIBE_BATCH_SIZE", "20"))
        for video_id in video_ids:
            if queued >= batch_size:
                break
            retry_at = _redis.get(f"auto_transcribe:retry_at:{video_id}")
            try:
                if retry_at and time.time() < float(retry_at):
                    waiting += 1
                    continue
            except (TypeError, ValueError):
                pass
            if queue_video_transcription(db, video_id) is not None:
                queued += 1

        if queued:
            logger.info(f"Auto-transcription sweep queued {queued} video(s), {waiting} backing off")
            activity_log.log_activity(db, f"Auto-transcription sweep queued {queued} video(s) with untranscribed chunks.")
        return f"Queued {queued} video(s) for transcription"

    except Exception as e:
        db.rollback()
        logger.error(f"Auto-transcription sweep failed: {e}", exc_info=True)
        return f"Sweep failed: {str(e)}"
    finally:
        db.close()
        _redis.delete("auto_transcribe:sweep")


@celery_app.task(bind=True)
def transcribe_all_untranscribed_task(self, job_id: int = None):
    """
    Find and transcribe ALL chunks that have no transcript, regardless of video/channel.
    Useful after crashes or partial runs.
    """
    db = database.SessionLocal()
    try:
        job = _find_job(db, self.request.id, job_id)
        if job:
            job.status = "processing"
            db.commit()

        chunks_data = [
            (c.id, c.file_path)
            for c in db.query(models.AudioChunk).filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            ).all()
        ]

        if not chunks_data:
            activity_log.log_activity(db, "No untranscribed chunks found.")
            if job:
                job.status = "completed"
                job.progress = 100
                db.commit()
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
                    job = _find_job(db, self.request.id, job_id)
                    if job:
                        job.progress = round(processed / total * 100, 1)
                        db.commit()

        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}")
        job = _find_job(db, self.request.id, job_id)
        if job:
            job.status = "completed"
            job.progress = 100
        db.commit()
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Transcribe-all task failed: {e}")
        try:
            job = _find_job(db, self.request.id, job_id)
            if job:
                job.status = "failed"
            db.commit()
        except Exception:
            pass
        return f"Task Failed: {str(e)}"
    finally:
        db.close()