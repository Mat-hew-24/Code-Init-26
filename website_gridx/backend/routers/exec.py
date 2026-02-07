"""
Exec Router - API endpoints for remote command execution
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from pydantic import BaseModel

from services.gridx_wrapper import get_wrapper


router = APIRouter(prefix="/exec", tags=["exec"])


class ExecRequest(BaseModel):
    worker: str
    command: str
    timeout: Optional[int] = 30


class BatchExecRequest(BaseModel):
    workers: list[str]  # List of worker names or "all"
    command: str
    timeout: Optional[int] = 30


@router.post("")
def execute_command(request_data: ExecRequest, request: Request):
    """Execute a command on a specific worker"""
    # Set worker in request state for middleware logging
    request.state.worker = request_data.worker
    
    wrapper = get_wrapper()
    timeout = request_data.timeout if request_data.timeout is not None else 30
    result = wrapper.exec_on_worker(request_data.worker, request_data.command, timeout)
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
