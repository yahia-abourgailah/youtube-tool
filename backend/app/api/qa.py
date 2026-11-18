from collections import defaultdict
from datetime import datetime, timezone
import os

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, database
from ..utils import paths, qa

router = APIRouter()


@router.get("/report")
def qa_report(
    min_chars: int = 2,
    min_chars_per_second: float = 0.3,
    max_chars_per_second: float = 25.0,
    sample_limit: int = 50,
    db: Session = Depends(database.get_db),
):
    """Scan the dataset and report quality problems without modifying anything."""
    rows = db.query(
        models.AudioChunk.id,
        models.AudioChunk.chunk_id,
        models.AudioChunk.video_id,
        models.AudioChunk.file_path,
        models.AudioChunk.duration,
        models.AudioChunk.transcript_text,
        models.AudioChunk.asr_model,
        models.AudioChunk.language,
    ).all()

    issues = defaultdict(list)
    counts = {code: 0 for code in qa.ISSUE_LABELS}
    transcribed = 0
    total_duration = 0.0
    missing_audio = 0

    for row in rows:
        file_exists = bool(row.file_path) and os.path.exists(paths.resolve(row.file_path))
        if not file_exists:
            missing_audio += 1
        if (row.transcript_text or "").strip():
            transcribed += 1
        total_duration += row.duration or 0

        codes = qa.classify_chunk(
            row.transcript_text,
            row.duration,
            file_exists,
            min_chars=min_chars,
            min_chars_per_second=min_chars_per_second,
            max_chars_per_second=max_chars_per_second,
        )
        for code in codes:
            counts[code] = counts.get(code, 0) + 1
            if len(issues[code]) < sample_limit:
                issues[code].append({
                    "chunk_id": row.chunk_id,
                    "video_id": row.video_id,
                    "duration": row.duration,
                    "transcript": (row.transcript_text or "")[:160],
                    "asr_model": row.asr_model,
                    "language": row.language,
                })

    duplicates = (
        db.query(
            models.AudioChunk.transcript_text,
            func.count(models.AudioChunk.id).label("count"),
        )
        .filter(
            models.AudioChunk.transcript_text != None,
            models.AudioChunk.transcript_text != "",
        )
        .group_by(models.AudioChunk.transcript_text)
        .having(func.count(models.AudioChunk.id) > 1)
        .order_by(func.count(models.AudioChunk.id).desc())
        .limit(sample_limit)
        .all()
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "min_chars": min_chars,
            "min_chars_per_second": min_chars_per_second,
            "max_chars_per_second": max_chars_per_second,
            "sample_limit": sample_limit,
        },
        "summary": {
            "total_chunks": len(rows),
            "transcribed_chunks": transcribed,
            "untranscribed_chunks": len(rows) - transcribed,
            "missing_audio_chunks": missing_audio,
            "total_duration_hours": round(total_duration / 3600, 2),
            "duplicate_transcripts": len(duplicates),
        },
        "issue_counts": counts,
        "issues": dict(issues),
        "duplicates": [
            {"transcript": text[:160], "count": count}
            for text, count in duplicates
        ],
        "issue_labels": qa.ISSUE_LABELS,
    }
