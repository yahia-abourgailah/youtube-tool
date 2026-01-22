from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, database
from ..tasks.export import export_dataset_task
import os

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
    parquet_path = os.path.join(data_dir, "hf_dataset.parquet")
    if not os.path.exists(parquet_path):
        raise HTTPException(status_code=404, detail="Exported file not found")
    from fastapi.responses import FileResponse
    return FileResponse(parquet_path, filename="egyptian_asr_dataset.parquet")
