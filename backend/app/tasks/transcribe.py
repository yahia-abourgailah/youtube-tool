import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..celery_app import celery_app
from .. import models, database
from ..utils import logging as activity_log
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def process_chunk_transcription(chunk_id: int, file_path: str, api_key: str, model_name: str) -> bool:
    """
    Helper function to transcribe a single chunk.
    Creates its own DB session to be thread-safe.
    """
    db = database.SessionLocal()
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Audio file not found: {file_path}")
            return False

        client = genai.Client(api_key=api_key)
        
        # Upload file
        with open(file_path, "rb") as f:
            audio_data = f.read()

        response = client.models.generate_content(
            model=model_name, 
            contents=[
                types.Part.from_bytes(
                    data=audio_data,
                    mime_type="audio/wav"  # تأكد من مطابقة الصيغة (audio/mpeg للـ mp3)
                ),
                """Transcribe this audio file accurately in Egyptian Arabic. 
                - Use Egyptian dialect spelling (Ammiya).
                - Don't convert to formal Arabic.
                - Use punctuation appropriately based on the audio.
                - Only provide the transcribed text without additional commentary."""
            ]
        )
        
        transcribed_text = response.text
        if transcribed_text:
            # Re-fetch chunk in this session to update
            chunk = db.query(models.AudioChunk).filter(models.AudioChunk.id == chunk_id).first()
            if chunk:
                chunk.transcript_text = transcribed_text
                db.commit()
                return True
        else:
            logger.warning(f"Empty response for chunk {chunk_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_id}: {e}")
        return False
    finally:
        db.close()

@celery_app.task(bind=True)
def transcribe_channel_task(self, channel_id: int, force_retranscribe: bool = False):
    """
    Transcribe all audio chunks for a given channel using Gemini API with parallel workers.
    """
    db = database.SessionLocal()
    try:
        # Check API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
            return "Failed: GEMINI_API_KEY missing"

        # Check Model
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
        if not channel:
            return "Channel not found"

        activity_log.log_activity(db, f"Starting parallel transcription for channel: {channel.name or channel.url}", channel_id=channel_id)
        
        # Get chunks
        chunks_query = db.query(models.AudioChunk).join(models.Video).filter(models.Video.channel_id == channel_id)
        
        if not force_retranscribe:
            chunks_query = chunks_query.filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            )
            
        # We fetch only necessary data (id, file_path) to pass to threads
        # This prevents detached instance issues
        chunks_data = [(c.id, c.file_path) for c in chunks_query.all()]
        
        if not chunks_data:
            activity_log.log_activity(db, "No chunks to transcribe.", channel_id=channel_id)
            return "No chunks to transcribe"

        logger.info(f"Found {len(chunks_data)} chunks to transcribe for channel {channel_id}")
        
        success_count = 0
        fail_count = 0
        total = len(chunks_data)
        
        # Use ThreadPoolExecutor for concurrency
        workers = 5  # As requested: 4 to 5 workers
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Map futures to chunk IDs for logging if needed
            future_to_chunk = {
                executor.submit(process_chunk_transcription, cid, path, api_key, model_name): cid 
                for cid, path in chunks_data
            }
            
            for i, future in enumerate(as_completed(future_to_chunk)):
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    logger.error(f"Chunk processing generated an exception: {exc}")
                    fail_count += 1
                
                # Log progress every 10 chunks or so
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{total} chunks processed.")

        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}", channel_id=channel_id)
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Transcription task failed: {e}")
        return f"Task Failed: {str(e)}"
    finally:
        db.close()
