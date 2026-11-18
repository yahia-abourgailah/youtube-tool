import logging
import os
from datetime import datetime, timedelta, timezone

from ..celery_app import celery_app
from .. import models, database

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def prune_activity_logs_task(self, days: int = None):
    """Delete activity logs older than ACTIVITY_LOG_RETENTION_DAYS (0 disables)."""
    retention = int(days if days is not None else os.getenv("ACTIVITY_LOG_RETENTION_DAYS", "90"))
    if retention <= 0:
        return "Activity log retention disabled"

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
    db = database.SessionLocal()
    try:
        deleted = db.query(models.ActivityLog).filter(models.ActivityLog.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
        logger.info(f"Pruned {deleted} activity log(s) older than {retention} days")
        return f"Pruned {deleted} activity log(s)"
    except Exception as exc:
        db.rollback()
        logger.error(f"Could not prune activity logs: {exc}", exc_info=True)
        return f"Prune failed: {exc}"
    finally:
        db.close()
