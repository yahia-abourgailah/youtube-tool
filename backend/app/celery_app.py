from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "youtube_audio_extractor",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.tasks.download", "app.tasks.process", "app.tasks.export", "app.tasks.transcribe", "app.tasks.maintenance"]
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
    # Each download/split task can hold a long video in memory; keep this low on a laptop
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "2")),
    worker_max_tasks_per_child=int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "10")),
    task_prefetch_multiplier=1
)

# Periodic safety nets. Each task checks its own "auto_*" setting, so it is a
# cheap no-op when the corresponding toggle is off.
beat_schedule = {}

_auto_sweep_minutes = int(os.getenv("AUTO_TRANSCRIBE_SWEEP_MINUTES", "15"))
if _auto_sweep_minutes > 0:
    beat_schedule["auto-transcribe-sweep"] = {
        "task": "app.tasks.transcribe.auto_transcribe_sweep_task",
        "schedule": _auto_sweep_minutes * 60.0,
    }

_auto_retry_minutes = int(os.getenv("AUTO_RETRY_SWEEP_MINUTES", "15"))
if _auto_retry_minutes > 0:
    beat_schedule["auto-retry-failed"] = {
        "task": "app.tasks.download.auto_retry_failed_task",
        "schedule": _auto_retry_minutes * 60.0,
    }

_activity_retention_days = int(os.getenv("ACTIVITY_LOG_RETENTION_DAYS", "90"))
if _activity_retention_days > 0:
    beat_schedule["prune-activity-logs"] = {
        "task": "app.tasks.maintenance.prune_activity_logs_task",
        "schedule": 24 * 60 * 60.0,
    }

if beat_schedule:
    celery_app.conf.beat_schedule = beat_schedule
