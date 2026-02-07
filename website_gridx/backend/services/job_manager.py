"""
Job Manager - Manages long-running code execution jobs with monitoring and cancellation
"""

import time
import uuid
import threading
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, Future

# Optional psutil import for system monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class JobStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class JobMetrics:
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    execution_time: float = 0.0
    output_length: int = 0
    network_requests: int = 0
    file_operations: int = 0


@dataclass 
class ExecutionJob:
    job_id: str
    code: str
    worker: str
    user_id: str = "anonymous"
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: Optional[int] = None
    
    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None
    
    # Monitoring
    metrics: JobMetrics = field(default_factory=JobMetrics)
    cancellation_token: threading.Event = field(default_factory=threading.Event)
    progress: float = 0.0
    
    # Future object for async execution
    future: Optional[Future] = None


class JobManager:
    """Manages execution jobs with monitoring, cancellation, and resource tracking"""
    
    def __init__(self, max_workers: int = 5):
        self.jobs: Dict[str, ExecutionJob] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.monitoring_thread = None
        self.running = True
        self._start_monitoring()

    def create_job(
        self, 
        code: str, 
        worker: str, 
        user_id: str = "anonymous",
        priority: JobPriority = JobPriority.NORMAL,
        timeout: Optional[int] = None
    ) -> str:
        """Create a new execution job"""
        job_id = str(uuid.uuid4())
        job = ExecutionJob(
            job_id=job_id,
            code=code,
            worker=worker,
            user_id=user_id,
            priority=priority,
            timeout=timeout
        )
        
        self.jobs[job_id] = job
        return job_id

    def submit_job(self, job_id: str, execution_func: Callable) -> bool:
        """Submit a job for execution"""
        if job_id not in self.jobs:
            return False
            
        job = self.jobs[job_id]
        if job.status != JobStatus.PENDING:
            return False
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        
        # Submit to thread pool
        job.future = self.executor.submit(self._execute_with_monitoring, job, execution_func)
        
        return True

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        if job_id not in self.jobs:
            return False
            
        job = self.jobs[job_id]
        
        if job.status not in [JobStatus.RUNNING, JobStatus.PENDING]:
            return False
        
        # Signal cancellation
        job.cancellation_token.set()
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now()
        
        # Cancel future if running
        if job.future:
            job.future.cancel()
            
        return True

    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        """Get job details"""
        return self.jobs.get(job_id)

    def get_user_jobs(self, user_id: str) -> List[ExecutionJob]:
        """Get all jobs for a user"""
        return [job for job in self.jobs.values() if job.user_id == user_id]

    def get_running_jobs(self) -> List[ExecutionJob]:
        """Get all currently running jobs"""
        return [job for job in self.jobs.values() if job.status == JobStatus.RUNNING]

    def get_job_stats(self) -> Dict[str, Any]:
        """Get overall job statistics"""
        total = len(self.jobs)
        by_status = {}
        by_worker = {}
        
        for job in self.jobs.values():
            status = job.status.value
            by_status[status] = by_status.get(status, 0) + 1
            by_worker[job.worker] = by_worker.get(job.worker, 0) + 1
        
        running_jobs = self.get_running_jobs()
        avg_execution_time = 0
        
        if self.jobs:
            completed_jobs = [j for j in self.jobs.values() if j.completed_at and j.started_at]
            if completed_jobs:
                total_time = sum((j.completed_at - j.started_at).total_seconds() for j in completed_jobs)
                avg_execution_time = total_time / len(completed_jobs)
        
        return {
            "total_jobs": total,
            "running_jobs": len(running_jobs),
            "by_status": by_status,
            "by_worker": by_worker,
            "avg_execution_time": round(avg_execution_time, 2),
            "current_cpu_usage": self._get_system_cpu(),
            "current_memory_usage": self._get_system_memory()
        }

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed jobs"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []
        
        for job_id, job in self.jobs.items():
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] 
                and job.completed_at and job.completed_at < cutoff):
                to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.jobs[job_id]
        
        return len(to_remove)

    def _execute_with_monitoring(self, job: ExecutionJob, execution_func: Callable) -> Dict[str, Any]:
        """Execute a job with resource monitoring"""
        start_time = time.time()
        
        try:
            # Check for cancellation before starting
            if job.cancellation_token.is_set():
                job.status = JobStatus.CANCELLED
                return {"success": False, "error": "Job was cancelled before execution"}
            
            # Execute with monitoring
            result = execution_func(job)
            
            # Update metrics
            end_time = time.time()
            job.metrics.execution_time = end_time - start_time
            
            # Check if job was cancelled during execution
            if job.cancellation_token.is_set():
                job.status = JobStatus.CANCELLED
                return {"success": False, "error": "Job was cancelled during execution"}
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now()
            
            return result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            return {"success": False, "error": str(e)}

    def _start_monitoring(self):
        """Start the monitoring thread"""
        def monitor():
            while self.running:
                try:
                    self._monitor_jobs()
                    time.sleep(1)  # Check every second
                except Exception as e:
                    print(f"Monitoring error: {e}")
        
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()

    def _monitor_jobs(self):
        """Monitor running jobs for resource usage and timeouts"""
        current_time = datetime.now()
        
        for job in self.get_running_jobs():
            # Check for timeout
            if job.timeout and job.started_at:
                elapsed = (current_time - job.started_at).total_seconds()
                if elapsed > job.timeout:
                    self.cancel_job(job.job_id)
                    job.status = JobStatus.TIMEOUT
                    job.error = f"Job exceeded timeout of {job.timeout} seconds"
            
            # Update progress (placeholder - would need actual progress tracking)
            if job.started_at:
                elapsed = (current_time - job.started_at).total_seconds()
                # Simple progress estimation based on time
                if job.timeout:
                    job.progress = min(0.9, elapsed / job.timeout * 0.8)
                else:
                    job.progress = min(0.5, elapsed / 300)  # Assume 5 min for unknown jobs

    def _detect_suspicious_patterns(self, job: ExecutionJob) -> List[str]:
        """Detect patterns that might indicate infinite loops or runaway processes"""
        patterns = []
        
        # High CPU usage for extended periods
        if job.metrics.cpu_usage > 90 and job.metrics.execution_time > 30:
            patterns.append("sustained_high_cpu")
        
        # Memory usage growing rapidly
        if job.metrics.memory_usage > 80:
            patterns.append("high_memory_usage")
        
        # Very long execution time without progress
        if job.metrics.execution_time > 300 and job.progress < 0.1:
            patterns.append("long_execution_no_progress")
        
        return patterns

    def _get_system_cpu(self) -> float:
        """Get current system CPU usage"""
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0.0

    def _get_system_memory(self) -> float:
        """Get current system memory usage percentage"""
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.virtual_memory().percent
        except:
            return 0.0

    def shutdown(self):
        """Shutdown the job manager"""
        self.running = False
        
        # Cancel all running jobs
        for job in self.get_running_jobs():
            self.cancel_job(job.job_id)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)


# Global job manager instance
_job_manager = None

def get_job_manager() -> JobManager:
    """Get the global job manager instance"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager