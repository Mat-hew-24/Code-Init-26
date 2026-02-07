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
    """Execute a command on a specific worker"""
    wrapper = get_wrapper()
    timeout = request.timeout if request.timeout is not None else 30
    result = wrapper.exec_on_worker(name, request.command, timeout)
    return result


@router.get("/pool/status")
def get_worker_pool_status():
    """Get detailed status of all workers in the pool"""
    wrapper = get_wrapper()
    workers = wrapper.get_workers()

    pool_status = {
        "total_workers": len(workers),
        "online_workers": 0,
        "offline_workers": 0,
        "workers": {},
    }

    for name, info in workers.items():
        # Check if worker is online
        ping_result = wrapper.ping_worker(name, timeout=3)
        is_online = ping_result.get("online", False)

        worker_data = {
            "name": name,
            "ip": info.get("ip"),
            "cpus": info.get("cpus"),
            "memory": info.get("memory"),
            "gpus": info.get("gpus", 0),
            "online": is_online,
            "status": "active" if is_online else "inactive",
        }

        # Get detailed status if online
        if is_online:
            status = wrapper.get_worker_status(name, timeout=3)
            if status:
                worker_data.update(
                    {
                        "cpu_percent": status.get("cpu_percent", 0),
                        "memory_percent": status.get("memory_percent", 0),
                        "disk_usage": status.get("disk_usage", {}),
                        "uptime": status.get("uptime", 0),
                    }
                )
            pool_status["online_workers"] += 1
        else:
            pool_status["offline_workers"] += 1

        pool_status["workers"][name] = worker_data

    # Add recommended worker
    best_worker = wrapper.get_best_worker()
    pool_status["recommended_worker"] = best_worker

    return pool_status


@router.get("/pool/health")
def get_pool_health():
    """Get overall health status of the worker pool"""
    wrapper = get_wrapper()
    online_workers = wrapper.get_online_workers()
    total_workers = len(wrapper.get_workers())

    if total_workers == 0:
        health_status = "no_workers"
        health_score = 0
    elif len(online_workers) == 0:
        health_status = "all_offline"
        health_score = 0
    elif len(online_workers) == total_workers:
        health_status = "excellent"
        health_score = 100
    elif len(online_workers) / total_workers >= 0.8:
        health_status = "good"
        health_score = 80
    elif len(online_workers) / total_workers >= 0.5:
        health_status = "fair"
        health_score = 60
    else:
        health_status = "poor"
        health_score = 40

    return {
        "health_status": health_status,
        "health_score": health_score,
        "online_workers": len(online_workers),
        "total_workers": total_workers,
        "availability_percentage": (
            (len(online_workers) / total_workers * 100) if total_workers > 0 else 0
        ),
        "online_worker_names": online_workers,
    }


def exec_on_worker(name: str, request: ExecRequest):
    """Execute a command on a worker"""
    wrapper = get_wrapper()
    timeout = request.timeout if request.timeout is not None else 30
    result = wrapper.exec_on_worker(name, request.command, timeout)
    return result
