from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "youtube_audio_extractor",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.tasks.download", "app.tasks.process", "app.tasks.export", "app.tasks.transcribe"]
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    task_acks_late=True,
    broker_transport_options={"visibility_timeout": 43200},  # 12 hours — prevents Redis re-delivering long tasks
    worker_concurrency=5,
    task_prefetch_multiplier=1
)
