"""
Exec Router - API endpoints for safe remote command execution with infinite loop protection
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel
import time

from services.gridx_wrapper import get_wrapper
from services.code_analyzer import analyze_python_code
from services.job_manager import get_job_manager, JobPriority, JobStatus


router = APIRouter(prefix="/exec", tags=["exec"])


class ExecRequest(BaseModel):
    worker: Optional[str] = None  # If None, auto-select best worker
    command: str
    timeout: Optional[int] = None  # Remove default for LLM workloads
    user_id: Optional[str] = "anonymous"
    bypass_analysis: Optional[bool] = False
    priority: Optional[str] = "normal"  # low, normal, high, critical


class SafeExecRequest(BaseModel):
    worker: str
    code: str
    timeout: Optional[int] = None
    user_id: Optional[str] = "anonymous"
    allow_risky: Optional[bool] = False
    monitor_resources: Optional[bool] = True
    priority: Optional[str] = "normal"


class JobControlRequest(BaseModel):
    job_id: str
    action: str  # cancel, pause, resume


class BatchExecRequest(BaseModel):
    workers: list[str]  # List of worker names or "all"
    command: str
    timeout: Optional[int] = 30


@router.post("/analyze")
def analyze_code(request: dict):
    """
    Analyze Python code for potential infinite loops and resource issues
    """
    code = request.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    
    try:
        analysis = analyze_python_code(code)
        return {
            "analysis": analysis,
            "recommendation": "safe" if analysis["should_execute"] else "unsafe",
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "analysis": {"should_execute": False, "issues": [], "suggestions": []},
            "recommendation": "unsafe",
            "error": str(e)
        }


@router.post("/safe-execute")
def safe_execute(request: SafeExecRequest):
    """
    Execute code with safety analysis and job management
    """
    # Analyze code first
    analysis = analyze_python_code(request.code)
    
    if not analysis["should_execute"] and not request.allow_risky:
        return {
            "success": False,
            "error": "Code analysis failed - unsafe to execute",
            "analysis": analysis,
            "suggestion": "Review code issues or set allow_risky=true to override"
        }
    
    # Create job for tracking
    job_manager = get_job_manager()
    priority_map = {
        "low": JobPriority.LOW,
        "normal": JobPriority.NORMAL, 
        "high": JobPriority.HIGH,
        "critical": JobPriority.CRITICAL
    }
    
    job_id = job_manager.create_job(
        code=request.code,
        worker=request.worker,
        user_id=request.user_id,
        priority=priority_map.get(request.priority, JobPriority.NORMAL),
        timeout=request.timeout
    )
    
    # Store analysis result
    job = job_manager.get_job(job_id)
    if job:
        job.analysis_result = analysis
    
    def execute_job(job):
        """Execute the job with monitoring"""
        wrapper = get_wrapper()
        return wrapper.exec_on_worker(
            job.worker, 
            job.code, 
            timeout=job.timeout or 300  # Default 5 minutes for LLM workloads
        )
    
    # Submit for async execution
    success = job_manager.submit_job(job_id, execute_job)
    
    if not success:
        return {
            "success": False,
            "error": "Failed to submit job for execution"
        }
    
    return {
        "success": True,
        "job_id": job_id,
        "analysis": analysis,
        "message": "Job submitted for execution",
        "estimated_time": "Unknown (monitoring enabled)"
    }


@router.post("")
def execute_command(request_data: ExecRequest, request: Request):
    """
    Execute a command on a specific worker (legacy endpoint with enhanced safety)
    """
    # Set worker in request state for middleware logging
    request.state.worker = request_data.worker
    
    # Analyze code if it looks like Python
    if not request_data.bypass_analysis and ('python' in request_data.command.lower() or 
                                           any(keyword in request_data.command for keyword in ['def ', 'for ', 'while ', 'if '])):
        analysis = analyze_python_code(request_data.command)
        
        if not analysis["should_execute"]:
            return {
                "success": False,
                "error": "Code analysis detected potential issues",
                "analysis": analysis,
                "suggestion": "Use /safe-execute endpoint or set bypass_analysis=true"
            }
    
    wrapper = get_wrapper()
    timeout = request_data.timeout if request_data.timeout is not None else 300  # Increased default
    result = wrapper.exec_on_worker(request_data.worker, request_data.command, timeout)
    return result


@router.get("/jobs")
def get_jobs(user_id: Optional[str] = None):
    """
    Get execution jobs (all jobs or for specific user)
    """
    job_manager = get_job_manager()
    
    if user_id:
        jobs = job_manager.get_user_jobs(user_id)
    else:
        jobs = list(job_manager.jobs.values())
    
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "worker": job.worker,
                "user_id": job.user_id,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "progress": job.progress,
                "execution_time": job.metrics.execution_time,
                "has_issues": bool(job.analysis_result and job.analysis_result.get("issues"))
            }
            for job in jobs
        ],
        "stats": job_manager.get_job_stats()
    }


@router.get("/jobs/{job_id}")
def get_job_details(job_id: str):
    """
    Get detailed information about a specific job
    """
    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "worker": job.worker,
        "user_id": job.user_id,
        "priority": job.priority.value,
        "code": job.code,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "timeout": job.timeout,
        "result": job.result,
        "error": job.error,
        "analysis_result": job.analysis_result,
        "metrics": {
            "execution_time": job.metrics.execution_time,
            "cpu_usage": job.metrics.cpu_usage,
            "memory_usage": job.metrics.memory_usage,
            "progress": job.progress
        }
    }


@router.post("/jobs/{job_id}/control")
def control_job(job_id: str, action: str):
    """
    Control a job (cancel, etc.)
    """
    job_manager = get_job_manager()
    
    if action == "cancel":
        success = job_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Cannot cancel job")
        return {"success": True, "message": "Job cancelled"}
    
    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@router.get("/stats")
def get_execution_stats():
    """
    Get overall execution statistics
    """
    job_manager = get_job_manager()
    return job_manager.get_job_stats()


@router.delete("/jobs/cleanup")
def cleanup_old_jobs(max_age_hours: int = 24):
    """
    Clean up old completed jobs
    """
    job_manager = get_job_manager()
    removed_count = job_manager.cleanup_old_jobs(max_age_hours)
    return {
        "success": True,
        "removed_jobs": removed_count,
        "message": f"Cleaned up {removed_count} old jobs"
    }
