"""
Middleware Router - API endpoints for admin monitoring functionality
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import json
import time
from datetime import datetime
from pydantic import BaseModel

from services.gridx_wrapper import get_wrapper

router = APIRouter(prefix="/middleware", tags=["middleware"])

# In-memory storage for request logs and stats
_request_logs: List[Dict[str, Any]] = []
_request_stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "by_endpoint": {},
    "by_worker": {},
    "by_method": {}
}

class RequestLog(BaseModel):
    endpoint: str
    method: str = "GET"
    worker: str = None
    duration_ms: int = 0
    success: bool = True
    timestamp: str = None

def log_request(endpoint: str, method: str = "GET", worker: str = None, 
                duration_ms: int = 0, success: bool = True):
    """Log a request for monitoring (called by FastAPI middleware)"""
    global _request_logs, _request_stats
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    log_entry = {
        "endpoint": endpoint,
        "method": method,
        "worker": worker,
        "duration_ms": duration_ms,
        "success": success,
        "timestamp": timestamp
    }
    
    _request_logs.append(log_entry)
    
    # Keep only last 200 entries
    if len(_request_logs) > 200:
        _request_logs.pop(0)
    
    # Update stats
    _request_stats["total"] += 1
    if success:
        _request_stats["success"] += 1
    else:
        _request_stats["failed"] += 1
    
    # Update by endpoint
    if endpoint not in _request_stats["by_endpoint"]:
        _request_stats["by_endpoint"][endpoint] = 0
    _request_stats["by_endpoint"][endpoint] += 1
    
    # Update by worker
    if worker:
        if worker not in _request_stats["by_worker"]:
            _request_stats["by_worker"][worker] = 0
        _request_stats["by_worker"][worker] += 1
    
    # Update by method
    if method not in _request_stats["by_method"]:
        _request_stats["by_method"][method] = 0
    _request_stats["by_method"][method] += 1

@router.get("/health")
def middleware_health():
    """Middleware health check"""
    return {"status": "ok", "middleware": "active", "timestamp": datetime.now().isoformat()}

@router.get("/stats")
def get_middleware_stats():
    """Get request statistics"""
    # Count connected backend servers by checking common ports
    backend_servers_online = 0
    import socket
    ports = [8000, 8001, 8002, 8003, 8004, 8005]
    
    for port in ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.1)
                result = sock.connect_ex(('localhost', port))
                if result == 0:
                    backend_servers_online += 1
        except:
            pass
    
    return {
        **_request_stats,
        "backend_servers": backend_servers_online,
        "success_rate": round((_request_stats["success"] / max(_request_stats["total"], 1)) * 100, 2),
        "active_workers": len(_request_stats["by_worker"]),
        "top_endpoints": list(_request_stats["by_endpoint"].keys())[:10]
    }

@router.get("/logs")
def get_request_logs():
    """Get recent request logs"""
    return {"logs": _request_logs}

@router.get("/config")
def get_middleware_config():
    """Get middleware configuration and hub status"""
    try:
        wrapper = get_wrapper()
        hub_status = wrapper.get_hub_status()
    except Exception as e:
        # If wrapper fails (e.g., WireGuard not available), return basic config
        hub_status = {
            "status": "error", 
            "message": "Unable to get hub status", 
            "error": str(e)
        }
    
    config = {
        "middleware": {
            "version": "1.0.0",
            "logging_enabled": True,
            "max_log_entries": 200,
            "total_requests": _request_stats["total"]
        },
        "hub": hub_status,
        "endpoints": {
            "workers": "/api/workers",
            "jobs": "/api/jobs",
            "exec": "/api/exec",
            "status": "/api/status",
            "onboarding": "/api/onboarding"
        },
        "system": {
            "platform": "windows" if "win" in str(wrapper.__class__).lower() else "linux",
            "middleware_active": True
        }
    }
    
    return config

@router.post("/log")
def add_request_log(log_entry: RequestLog):
    """Add a request log entry"""
    if not log_entry.timestamp:
        log_entry.timestamp = datetime.now().strftime("%H:%M:%S")
    
    log_request(
        endpoint=log_entry.endpoint,
        method=log_entry.method,
        worker=log_entry.worker,
        duration_ms=log_entry.duration_ms,
        success=log_entry.success
    )
    
    return {"success": True}

@router.delete("/logs")
def clear_request_logs():
    """Clear all request logs"""
    global _request_logs, _request_stats
    _request_logs.clear()
    _request_stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "by_endpoint": {},
        "by_worker": {},
        "by_method": {}
    }
    return {"success": True, "message": "Logs cleared"}

# Log some sample data for demonstration
def _init_sample_data():
    """Initialize with some sample data"""
    import random
    endpoints = ["/api/workers", "/api/jobs", "/api/status", "/api/workers/exec"]
    workers = ["worker-1", "worker-2", "gpu-node"]
    methods = ["GET", "POST", "DELETE"]
    
    for i in range(20):
        log_request(
            endpoint=random.choice(endpoints),
            method=random.choice(methods),
            worker=random.choice(workers) if random.random() > 0.4 else None,
            duration_ms=random.randint(50, 2000),
            success=random.random() > 0.15
        )

# Initialize sample data on import
_init_sample_data()