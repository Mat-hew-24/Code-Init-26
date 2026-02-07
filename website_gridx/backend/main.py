"""
Grid-X Web API - FastAPI backend for the web interface

This wraps the existing gridx functionality (hub.py, jobs.py, worker.py)
and exposes it via a REST API.
"""

import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from routers import workers, jobs, exec, onboarding, middleware
from services.gridx_wrapper import get_wrapper

app = FastAPI(
    title="Grid-X API",
    description="REST API for Grid-X decentralized compute mesh",
    version="1.0.0",
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests for admin monitoring"""
    start_time = time.time()
    
    # Call the actual route handler
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Extract worker from request if available (for exec endpoints)
    worker = None
    if hasattr(request.state, 'worker'):
        worker = request.state.worker
    elif 'worker' in str(request.url.query):
        # Try to extract worker from query params
        query_params = dict(request.query_params)
        worker = query_params.get('worker')
    
    # Log the request using middleware router function
    try:
        from routers.middleware import log_request
        log_request(
            endpoint=str(request.url.path),
            method=request.method,
            worker=worker,
            duration_ms=int(duration_ms),
            success=(200 <= response.status_code < 400)
        )
    except Exception as e:
        # Don't let logging errors break the request
        print(f"Logging error: {e}")
    
    return response

# Include routers
app.include_router(workers.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(exec.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(middleware.router, prefix="/api")


# ==================== Hub Status Endpoints ====================


@app.get("/api/status")
def get_hub_status():
    """Get overall hub status"""
    try:
        wrapper = get_wrapper()
        return wrapper.get_hub_status()
    except Exception as e:
        # Return fallback status if hub wrapper fails
        return {
            "status": "partial",
            "message": "Hub status unavailable",
            "error": str(e),
            "api": "online",
            "timestamp": time.time()
        }


@app.get("/api/services")
def get_running_services():
    """Get all running gridx services"""
    wrapper = get_wrapper()
    services = wrapper.get_running_services()
    return {"services": services, "count": len(services)}


@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "gridx-api"}


# ==================== Static Files (Frontends) ====================

# Mount frontend directories
frontend_dir = Path(__file__).parent.parent / "frontend"

if (frontend_dir / "host").exists():
    app.mount(
        "/host",
        StaticFiles(directory=str(frontend_dir / "host"), html=True),
        name="host",
    )

if (frontend_dir / "client").exists():
    app.mount(
        "/client",
        StaticFiles(directory=str(frontend_dir / "client"), html=True),
        name="client",
    )

if (frontend_dir / "admin").exists():
    app.mount(
        "/admin",
        StaticFiles(directory=str(frontend_dir / "admin"), html=True),
        name="admin",
    )

if (frontend_dir / "onboard").exists():
    app.mount(
        "/onboard",
        StaticFiles(directory=str(frontend_dir / "onboard"), html=True),
        name="onboard",
    )


@app.get("/")
def root():
    """Root endpoint - show available frontends"""
    return {
        "service": "Grid-X Web Interface",
        "version": "1.0.0",
        "frontends": {
            "host": "/host - Host Dashboard (manage workers/containers)",
            "onboard": "/onboard - Add Worker (onboarding wizard)",
            "client": "/client - Client Interface (Colab-lite code runner)",
            "admin": "/admin - Admin View (middleware monitoring)",
        },
        "api": {
            "docs": "/docs - OpenAPI documentation",
            "status": "/api/status - Hub status",
            "workers": "/api/workers - Worker management",
            "jobs": "/api/jobs - Job management",
            "exec": "/api/exec - Remote execution",
            "onboarding": "/api/onboarding - Worker onboarding",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
