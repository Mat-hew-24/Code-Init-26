"""
Exec Router - API endpoints for remote command execution
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from pydantic import BaseModel

from services.gridx_wrapper import get_wrapper


router = APIRouter(prefix="/exec", tags=["exec"])


class ExecRequest(BaseModel):
    worker: Optional[str] = None  # If None, auto-select best worker
    command: str
    timeout: Optional[int] = 30


class BatchExecRequest(BaseModel):
    workers: list[str]  # List of worker names or "all"
    command: str
    timeout: Optional[int] = 30


@router.post("/auto")
def auto_execute(command: str, timeout: Optional[int] = 30):
    """Execute a command on the best available worker (simplified endpoint)"""
    wrapper = get_wrapper()
    timeout = timeout if timeout is not None else 30
    result = wrapper.exec_on_best_worker(command, timeout)
    return result


@router.post("")
def execute_command(request_data: ExecRequest, request: Request):
    """Execute a command on a specific worker or auto-select best worker"""
    wrapper = get_wrapper()
    timeout = request_data.timeout if request_data.timeout is not None else 30

    if request_data.worker:
        # Execute on specified worker
        request.state.worker = request_data.worker
        result = wrapper.exec_on_worker(
            request_data.worker, request_data.command, timeout
        )
    else:
        # Auto-select best worker
        result = wrapper.exec_on_best_worker(request_data.command, timeout)
        request.state.worker = result.get("worker")

    return result


@router.post("/batch")
def batch_execute(request: BatchExecRequest):
    """Execute a command on multiple workers"""
    wrapper = get_wrapper()

    # Get target workers
    if request.workers == ["all"]:
        workers = list(wrapper.get_workers().keys())
    else:
        workers = request.workers

    if not workers:
        raise HTTPException(status_code=400, detail="No workers specified")

    timeout = request.timeout if request.timeout is not None else 30

    # Execute on each worker
    results = {}
    for name in workers:
        results[name] = wrapper.exec_on_worker(name, request.command, timeout)

    success_count = sum(1 for r in results.values() if r.get("success"))

    return {"results": results, "success_count": success_count, "total": len(workers)}


@router.get("/workers/best")
def get_best_worker():
    """Get the best available worker for task execution"""
    wrapper = get_wrapper()
    best_worker = wrapper.get_best_worker()

    if not best_worker:
        raise HTTPException(status_code=503, detail="No workers available")

    worker_info = wrapper.get_worker(best_worker)
    status = wrapper.get_worker_status(best_worker)

    return {
        "name": best_worker,
        "info": worker_info,
        "status": status,
        "reason": "Selected based on lowest load and resource availability",
    }


@router.get("/workers/online")
def get_online_workers():
    """Get all online workers"""
    wrapper = get_wrapper()
    online_workers = wrapper.get_online_workers()

    return {"workers": online_workers, "count": len(online_workers)}
