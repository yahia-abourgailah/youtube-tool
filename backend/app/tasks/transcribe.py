import os
import logging
from ..celery_app import celery_app
from .. import models, database
from ..utils import logging as activity_log
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def transcribe_channel_task(self, channel_id: int, force_retranscribe: bool = False):
    """
    Transcribe all audio chunks for a given channel using Gemini API.
    """
    db = database.SessionLocal()
    try:
        # Check API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
            return "Failed: GEMINI_API_KEY missing"

        client = genai.Client(api_key=api_key)

        channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
        if not channel:
            return "Channel not found"

        activity_log.log_activity(db, f"Starting transcription for channel: {channel.name or channel.url}", channel_id=channel_id)
        
        # Get chunks
        chunks_query = db.query(models.AudioChunk).join(models.Video).filter(models.Video.channel_id == channel_id)
        
        if not force_retranscribe:
            # Filter out chunks that already have valid transcript (not empty/null)
            # Checking length > 5 as arbitrary "valid" length
            chunks_query = chunks_query.filter(
                (models.AudioChunk.transcript_text == None) | (models.AudioChunk.transcript_text == "")
            )
            
        chunks = chunks_query.all()
        
        if not chunks:
            activity_log.log_activity(db, "No chunks to transcribe.", channel_id=channel_id)
            return "No chunks to transcribe"

        logger.info(f"Found {len(chunks)} chunks to transcribe for channel {channel_id}")
        
        success_count = 0
        fail_count = 0
        
        for i, chunk in enumerate(chunks):
            try:
                if not os.path.exists(chunk.file_path):
                    logger.warning(f"Audio file not found: {chunk.file_path}")
                    fail_count += 1
                    continue
                
                logger.info(f"Transcribing chunk {chunk.id} ({i+1}/{len(chunks)})...")
                
                # Upload file
                # TODO: Check if we need to manage file lifecycle on Gemini side. 
                # For now, we upload, transcribe, and rely on Gemini's auto-cleanup or quota.
                # Ideally we should delete the file from Gemini after usage if the API allows.
                uploaded_file = client.files.upload(file=chunk.file_path)
                
                # Wait for processing if video/large file (usually audio is instant but good practice)
                # For small chunks it should be ready.
                
                model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
                response = client.models.generate_content(
                    model=model_name, 
                    contents=[
                        """Transcribe this audio file accurately in Egyptian Arabic. 
                        - Use Egyptian dialect spelling (Ammiya).
                        - Don't convert to formal Arabic.
                        - Only provide the transcribed text without additional commentary.""",
                        uploaded_file
                    ]
                )
                
                transcribed_text = response.text
                if transcribed_text:
                    chunk.transcript_text = transcribed_text
                    db.commit()
                    success_count += 1
                else:
                    logger.warning(f"Empty response for chunk {chunk.id}")
                    fail_count += 1
                

                
            except Exception as e:
                logger.error(f"Error transcribing chunk {chunk.id}: {e}")
                fail_count += 1
                activity_log.log_activity(db, f"Transcription failed for chunk {chunk.chunk_id}: {str(e)}", video_id=chunk.video_id, level="error")
                # Continue to next chunk
        
        activity_log.log_activity(db, f"Transcription completed. Success: {success_count}, Failed: {fail_count}", channel_id=channel_id)
        return f"Transcription completed. Success: {success_count}, Failed: {fail_count}"

    except Exception as e:
        db.rollback()
        logger.error(f"Transcription task failed: {e}")
        return f"Task Failed: {str(e)}"
    finally:
        db.close()
