from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from .. import models, schemas, database
from ..tasks.export import export_dataset_task
from ..utils import paths
from ..utils.csv_safety import neutralize_csv_formula
import glob
import os
import csv
import io
import tempfile
import zipfile

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

    task = export_dataset_task.delay(
        job.id,
        request.repo_id,
        request.hf_token,
        request.private,
        request.channel_ids,
        request.channel_names,
        request.split,
        request.val_ratio,
        request.test_ratio,
    )
    job.celery_task_id = task.id
    db.commit()

    return {"job_id": job.id, "message": "Export started"}

@router.get("/download")
def download_export():
    data_dir = paths.data_path()
    parquet_files = sorted(glob.glob(os.path.join(data_dir, "hf_dataset*.parquet")))
    manifest_path = os.path.join(data_dir, "hf_dataset_manifest.json")

    if not parquet_files:
        raise HTTPException(
            status_code=404,
            detail="No exported parquet file found. Run an export first via POST /api/export/"
        )

    if len(parquet_files) == 1 and not os.path.exists(manifest_path):
        return FileResponse(parquet_files[0], filename=os.path.basename(parquet_files[0]))

    # A split export produces several parquet files; bundle them with the manifest.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in parquet_files:
                archive.write(path, arcname=os.path.basename(path))
            if os.path.exists(manifest_path):
                archive.write(manifest_path, arcname=os.path.basename(manifest_path))
    except Exception:
        os.unlink(tmp.name)
        raise

    return FileResponse(
        tmp.name,
        filename="egyptian_asr_dataset.zip",
        background=BackgroundTask(os.remove, tmp.name),
    )


@router.get("/csv")
def download_csv(video_ids: str = None, include_untranscribed: bool = False, db: Session = Depends(database.get_db)):
    """Export audio chunks as CSV. Optionally filter by comma-separated video IDs (YouTube IDs)."""
    query = db.query(
        models.AudioChunk.chunk_id,
        models.AudioChunk.file_path,
        models.AudioChunk.transcript_text,
        models.AudioChunk.duration,
        models.AudioChunk.start_time,
        models.AudioChunk.end_time,
        models.AudioChunk.asr_model,
        models.AudioChunk.language,
        models.AudioChunk.confidence,
        models.Video.video_id.label("youtube_id"),
    ).join(models.Video)

    if not include_untranscribed:
        query = query.filter(
            models.AudioChunk.transcript_text != None,
            models.AudioChunk.transcript_text != "",
        )

    if video_ids:
        ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        query = query.filter(models.Video.video_id.in_(ids))

    chunks = query.all()

    if not chunks:
        raise HTTPException(status_code=404, detail="No audio chunks found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "chunk_id", "file_path", "transcript", "duration", "start_time", "end_time",
        "asr_model", "language", "confidence", "youtube_id",
    ])
    for row in chunks:
        writer.writerow([neutralize_csv_formula(value) for value in row])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transcripts.csv"}
    )
