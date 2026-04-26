import threading

from app.config import settings
from app.models.job import JobStatus
from app.services.job_manager import job_manager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class RunRequest(BaseModel):
    job_id: str


@router.post("/photogrammetry/run")
async def run_photogrammetry(request: RunRequest):
    job = job_manager.get_job(request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    upload_dir = settings.UPLOAD_DIR / request.job_id
    if not upload_dir.exists() or not any(upload_dir.iterdir()):
        raise HTTPException(status_code=400, detail="No images found for this job")

    job_manager.update_job(
        request.job_id, status=JobStatus.RECONSTRUCTING, progress=0, stage="starting"
    )

    # Lazy import to avoid loading open3d on systems where it's not installed
    from app.services.colmap_pipeline import ColmapPipeline

    pipeline = ColmapPipeline()
    threading.Thread(target=pipeline.run, args=(request.job_id,), daemon=True).start()

    return {
        "job_id": request.job_id,
        "status": "reconstructing",
        "message": "Pipeline started",
    }
