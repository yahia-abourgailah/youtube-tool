from sqlalchemy.orm import Session
from .. import models

def log_activity(db: Session, message: str, video_id: int = None, channel_id: int = None, level: str = "info"):
    """Log an activity to the database."""
    log = models.ActivityLog(
        video_id=video_id,
        channel_id=channel_id,
        message=message,
        level=level
    )
    db.add(log)
    try:
        db.commit()
    except Exception:
        db.rollback()
