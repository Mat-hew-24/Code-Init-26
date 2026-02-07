"""
Workers Router - API endpoints for worker management
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from services.gridx_wrapper import get_wrapper


router = APIRouter(prefix="/workers", tags=["workers"])


class ExecRequest(BaseModel):
    command: str
    timeout: Optional[int] = 30


@router.get("")
def list_workers():
    """List all registered workers"""
    wrapper = get_wrapper()
    workers = wrapper.get_workers()

    # Add online status for each worker
    result = []
    for name, info in workers.items():
        worker_data = {
            "name": name,
            "ip": info.get("ip"),
            "cpus": info.get("cpus"),
            "memory": info.get("memory"),
            "gpus": info.get("gpus", 0),
        }
        # Quick ping check
        ping_result = wrapper.ping_worker(name, timeout=2)
        worker_data["online"] = ping_result.get("online", False)
        result.append(worker_data)

    return {"workers": result, "count": len(result)}


@router.get("/ping")
def ping_all_workers():
    """Ping all workers to check their status"""
    wrapper = get_wrapper()
    results = wrapper.ping_all_workers()

    online_count = sum(1 for r in results.values() if r.get("online"))
    total_configured = len(results)
    
    return {
        "workers": results, 
        "online": online_count, 
        "total": total_configured,
        "configured": total_configured,
        "offline": total_configured - online_count
    }


@router.get("/{name}")
def get_worker(name: str):
    """Get a specific worker's info"""
    wrapper = get_wrapper()
    worker = wrapper.get_worker(name)

    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker '{name}' not found")

    # Get detailed status if worker is online
    status = wrapper.get_worker_status(name)
    ping = wrapper.ping_worker(name)

    return {
        "name": name,
        "ip": worker.get("ip"),
        "cpus": worker.get("cpus"),
        "memory": worker.get("memory"),
        "gpus": worker.get("gpus", 0),
        "online": ping.get("online", False),
        "status": status,
    }


@router.get("/{name}/ping")
def ping_worker(name: str):
    """Ping a specific worker"""
    wrapper = get_wrapper()
    result = wrapper.ping_worker(name)
    return result


@router.get("/{name}/status")
def get_worker_status(name: str):
    """Get detailed status from worker agent"""
    wrapper = get_wrapper()
    status = wrapper.get_worker_status(name)

    if not status:
        raise HTTPException(
            status_code=503, detail=f"Worker '{name}' is offline or unreachable"
        )

    return status


@router.post("/{name}/exec")
def exec_on_worker(name: str, request: ExecRequest):
    """Execute a command on a worker"""
    wrapper = get_wrapper()
    timeout = request.timeout if request.timeout is not None else 30
    result = wrapper.exec_on_worker(name, request.command, timeout)
    return result
