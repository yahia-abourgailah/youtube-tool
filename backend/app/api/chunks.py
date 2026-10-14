from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas, database
import os

from ..tasks.process import reprocess_long_chunks_task

router = APIRouter()

@router.post("/reprocess-lengthy")
def trigger_reprocess_lengthy(db: Session = Depends(database.get_db)):
    job = models.Job(job_type="maintenance", entity_id="chunk_refinement", status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    
    task = reprocess_long_chunks_task.delay()
    job.celery_task_id = task.id
    db.commit()
    
    return {"job_id": job.id, "message": "Chunk refinement started"}

@router.get("/stats", response_model=schemas.ChunkStats)
def get_chunk_stats(db: Session = Depends(database.get_db)):
    durations = [c[0] for c in db.query(models.AudioChunk.duration).all()]
    if not durations:
        return {
            "count": 0,
            "avg_duration": 0,
            "p90_duration": 0,
            "p95_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "total_duration": 0
        }
    
    import numpy as np
    return {
        "count": len(durations),
        "avg_duration": float(np.mean(durations)),
        "p90_duration": float(np.percentile(durations, 90)),
        "p95_duration": float(np.percentile(durations, 95)),
        "min_duration": float(np.min(durations)),
        "max_duration": float(np.max(durations)),
        "total_duration": float(np.sum(durations))
    }

@router.get("/", response_model=schemas.PaginatedChunks)
def read_chunks(
    video_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(database.get_db)
):
    query = db.query(models.AudioChunk)
    if video_id:
        query = query.filter(models.AudioChunk.video_id == video_id)
    if search:
        query = query.filter(
            models.AudioChunk.transcript_text.ilike(f"%{search}%")
            | models.AudioChunk.chunk_id.ilike(f"%{search}%")
        )
    
    total = query.count()
    pages = (total + size - 1) // size
    skip = (page - 1) * size
    items = query.order_by(models.AudioChunk.created_at.desc()).offset(skip).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }

@router.put("/{chunk_id}/transcript", response_model=schemas.AudioChunk)
def update_chunk_transcript(chunk_id: str, body: schemas.AudioChunkTranscriptUpdate, db: Session = Depends(database.get_db)):
    chunk = db.query(models.AudioChunk).filter(models.AudioChunk.chunk_id == chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    chunk.transcript_text = body.transcript_text
    db.commit()
    db.refresh(chunk)
    return chunk

@router.delete("/{chunk_id}")
def delete_chunk(chunk_id: str, db: Session = Depends(database.get_db)):
    chunk = db.query(models.AudioChunk).filter(models.AudioChunk.chunk_id == chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    if chunk.file_path and os.path.exists(chunk.file_path):
        os.remove(chunk.file_path)
    db.delete(chunk)
    db.commit()
    return {"message": "Chunk deleted"}

@router.put("/{chunk_id}/trim", response_model=schemas.AudioChunk)
def trim_chunk(chunk_id: str, body: schemas.AudioChunkTrimRequest, db: Session = Depends(database.get_db)):
    chunk = db.query(models.AudioChunk).filter(models.AudioChunk.chunk_id == chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    if not chunk.file_path or not os.path.exists(chunk.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    if not (0 <= body.trim_start < body.trim_end <= chunk.duration):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trim bounds: must satisfy 0 <= trim_start < trim_end <= {chunk.duration}"
        )

    from pydub import AudioSegment
    audio = AudioSegment.from_wav(chunk.file_path)
    trimmed = audio[int(body.trim_start * 1000):int(body.trim_end * 1000)]
    trimmed.export(chunk.file_path, format="wav")

    old_duration = chunk.duration
    new_duration = body.trim_end - body.trim_start
    chunk.start_time = chunk.start_time + body.trim_start
    chunk.end_time = chunk.end_time - (old_duration - body.trim_end)
    chunk.duration = new_duration
    db.commit()
    db.refresh(chunk)
    return chunk

@router.get("/{chunk_id}/audio")
def get_chunk_audio(chunk_id: str, request: Request, db: Session = Depends(database.get_db)):
    chunk = db.query(models.AudioChunk).filter(models.AudioChunk.chunk_id == chunk_id).first()
    if not chunk or not os.path.exists(chunk.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_path = chunk.file_path
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        start = max(0, start)
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    data = f.read(min(8192, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="audio/wav",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "public, max-age=3600",
            },
        )

    return FileResponse(file_path, media_type="audio/wav", headers={
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Cache-Control": "public, max-age=3600",
    })
