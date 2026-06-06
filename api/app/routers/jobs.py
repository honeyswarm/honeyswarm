"""Job status (was the PepperJobs / Salt JID tracking blueprint)."""
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.refs import link_id
from app.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "command_id": job.command_id,
        "job_type": job.job_type,
        "job_description": job.job_description,
        "status": job.status,
        "complete": job.complete,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "job_response": job.job_response,
        "hive": link_id(job.hive),
    }


@router.get("")
async def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    jobs = await Job.find_all().sort(-Job.created_at).limit(limit).to_list()
    return [_serialize(j) for j in jobs]


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = await Job.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return _serialize(job)
