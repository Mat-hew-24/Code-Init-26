from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from lockdown import run_task_and_get_results
from watcher import get_available_resources
import time

app = FastAPI(
    title="Grid-X Node API",
    description="Decentralized resource mesh node API",
    version="1.0.0"
)

class JobRequest(BaseModel):
    image: str
    command: str
    timeout: int = 30

@app.get("/")
async def root():
    return {"message": "Grid-X Node is running", "timestamp": time.time()}

@app.get("/status")
async def check_status():
    """Get current node status and available resources"""
    try:
        stats = get_available_resources()
        return {
            "status": "IDLE" if stats["is_idle"] else "BUSY",
            "is_idle": stats["is_idle"],
            "resources": {
                "cpu_usage": stats["cpu_usage"],
                "available_ram_gb": stats["ram_gb"],
                "total_ram_gb": stats["total_ram_gb"],
                "available_disk_gb": stats["disk_gb"]
            },
            "timestamp": stats["timestamp"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")

@app.post("/job")
async def receive_job(job: JobRequest):
    """Submit a computational job to this node"""
    try:
        # Check if node is available
        stats = get_available_resources()
        
        if not stats["is_idle"]:
            raise HTTPException(
                status_code=503, 
                detail=f"Host is currently busy (CPU: {stats['cpu_usage']}%)"
            )

        # Validate job parameters
        if not job.image or not job.command:
            raise HTTPException(
                status_code=400, 
                detail="Both 'image' and 'command' fields are required"
            )

        if job.timeout > 300:  # Max 5 minutes
            raise HTTPException(
                status_code=400, 
                detail="Timeout cannot exceed 300 seconds"
            )

        print(f"Executing job: {job.command} on image {job.image}")
        
        # Execute the job
        result = run_task_and_get_results(job.image, job.command, job.timeout)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])

        return {
            "status": "completed",
            "exit_code": result["exit_code"],
            "logs": result["logs"],
            "container_id": result.get("container_id"),
            "execution_time": time.time()
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "Grid-X Node"}