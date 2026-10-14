from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from .. import models, schemas, database
from ..tasks.export import export_dataset_task
import os
import csv
import io

router = APIRouter()

@router.post("/")
def trigger_export(
    request: schemas.ExportRequest,
    db: Session = Depends(database.get_db)
):
    job = models.Job(job_type="export", entity_id="hf_dataset", status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    task = export_dataset_task.delay(job.id, request.repo_id, request.hf_token, request.private, request.channel_ids, request.channel_names)
    job.celery_task_id = task.id
    db.commit()

    return {"job_id": job.id, "message": "Export started"}

@router.get("/download")
def download_export():
    data_dir = os.getenv("DATA_PATH", os.path.join(os.getcwd(), "data"))

    # Try exact path first
    parquet_path = os.path.join(data_dir, "hf_dataset.parquet")
    if os.path.exists(parquet_path):
        return FileResponse(parquet_path, filename="egyptian_asr_dataset.parquet")

    # Try per-subset parquet files (DatasetDict saves as hf_dataset_{config}.parquet)
    for f in os.listdir(data_dir):
        if f.startswith("hf_dataset") and f.endswith(".parquet"):
            return FileResponse(os.path.join(data_dir, f), filename=f)

    raise HTTPException(
        status_code=404,
        detail="No exported parquet file found. Run an export first via POST /api/export/"
    )

@router.get("/csv")
def download_csv(video_ids: str = None, db: Session = Depends(database.get_db)):
    """Export audio chunks as CSV. Optionally filter by comma-separated video IDs (YouTube IDs)."""
    query = db.query(
        models.AudioChunk.chunk_id,
        models.AudioChunk.file_path,
        models.AudioChunk.transcript_text,
        models.AudioChunk.duration,
        models.AudioChunk.start_time,
        models.AudioChunk.end_time,
        models.Video.video_id.label("youtube_id"),
    ).join(models.Video)

    if video_ids:
        ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        query = query.filter(models.Video.video_id.in_(ids))

    chunks = query.all()

    if not chunks:
        raise HTTPException(status_code=404, detail="No audio chunks found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["chunk_id", "file_path", "transcript", "duration", "start_time", "end_time", "youtube_id"])
    for row in chunks:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transcripts.csv"}
    )
