"""
Jobs Router - API endpoints for job management
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from services.gridx_wrapper import get_wrapper


router = APIRouter(prefix="/jobs", tags=["jobs"])


class RunJobRequest(BaseModel):
    image: str
    command: Optional[str] = None
    name: Optional[str] = None
    cpus: Optional[float] = None
    memory: Optional[str] = None
    gpus: int = 0
    env: Optional[List[str]] = None
    replicas: int = 1


@router.get("")
def list_jobs():
    """List all jobs"""
    wrapper = get_wrapper()
    jobs = wrapper.get_jobs()
    services = wrapper.get_running_services()

    # Create a lookup for running services
    running = {s["name"]: s for s in services}

    result = []
    for job_id, job in jobs.items():
        service_name = job.get("service_name", f"gridx-{job_id}")
        job_data = {
            "id": job_id,
            "type": job.get("type", "job"),
            "image": job.get("image"),
            "command": job.get("command"),
            "created": job.get("created"),
            "running": service_name in running,
            "replicas": running.get(service_name, {}).get("replicas", "0/0"),
        }
        result.append(job_data)

    return {"jobs": result, "count": len(result)}


@router.post("")
def create_job(request: RunJobRequest):
    """Create and run a new job"""
    wrapper = get_wrapper()
    result = wrapper.run_job(
        image=request.image,
        command=request.command,
        name=request.name,
        cpus=request.cpus,
        memory=request.memory,
        gpus=request.gpus,
        env=request.env,
        replicas=request.replicas,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Failed to create job")
        )

    return result


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get a specific job"""
    wrapper = get_wrapper()
    job = wrapper.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return {"id": job_id, **job}


@router.get("/{job_id}/status")
def get_job_status(job_id: str):
    """Get detailed job status"""
    wrapper = get_wrapper()
    status = wrapper.get_job_status(job_id)

    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])

    return status


@router.get("/{job_id}/logs")
def get_job_logs(job_id: str, tail: int = 100):
    """Get logs for a job"""
    wrapper = get_wrapper()
    logs = wrapper.get_job_logs(job_id, tail)

    if logs.get("error"):
        raise HTTPException(status_code=404, detail=logs["error"])

    return logs


@router.delete("/{job_id}")
def delete_job(job_id: str):
    """Delete a job"""
    wrapper = get_wrapper()
    result = wrapper.delete_job(job_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Failed to delete job")
        )

    return result
