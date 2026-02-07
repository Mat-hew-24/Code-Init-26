"""
Onboarding Router - API endpoints for worker onboarding flow
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from services.gridx_wrapper import get_wrapper


router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Store pending workers waiting for connection
BUNDLES_DIR = Path("/tmp/gridx-bundles")


class CreateWorkerRequest(BaseModel):
    name: str


class WorkerBundleResponse(BaseModel):
    success: bool
    worker_name: str
    bundle_path: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


def run_cmd(cmd: list, timeout: int = 30) -> tuple:
    """Run a command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


@router.post("/create-worker")
def create_worker_bundle(request: CreateWorkerRequest):
    """
    Create a new worker bundle for onboarding.
    This runs the add-external logic and creates a downloadable bundle.
    """
    worker_name = request.name.strip()

    if not worker_name:
        raise HTTPException(status_code=400, detail="Worker name is required")

    # Validate name (alphanumeric + hyphens only)
    if not all(c.isalnum() or c in "-_" for c in worker_name):
        raise HTTPException(
            status_code=400,
            detail="Worker name must be alphanumeric (hyphens and underscores allowed)",
        )

    # Check if worker already exists
    wrapper = get_wrapper()
    existing = wrapper.get_worker(worker_name)
    if existing:
        # Worker exists - check if online
        ping = wrapper.ping_worker(worker_name, timeout=3)
        if ping.get("online"):
            return {
                "success": True,
                "worker_name": worker_name,
                "already_exists": True,
                "online": True,
                "message": f"Worker '{worker_name}' is already connected!",
            }
        else:
            # Exists but offline - regenerate bundle
            pass

    # Create the worker bundle by calling test.sh add-external
    gridx_dir = Path(__file__).parent.parent.parent.parent
    test_sh = gridx_dir / "test.sh"

    if not test_sh.exists():
        raise HTTPException(status_code=500, detail="Grid-X test.sh not found")

    # Run add-external command
    success, stdout, stderr = run_cmd(
        ["bash", str(test_sh), "add-external", worker_name], timeout=60
    )

    if not success:
        return {
            "success": False,
            "worker_name": worker_name,
            "error": stderr or "Failed to create worker bundle",
        }

    # Check if bundle was created
    bundle_tarball = Path(f"/tmp/gridx-{worker_name}.tar.gz")
    bundle_dir = Path(f"/tmp/gridx-{worker_name}")

    if not bundle_tarball.exists():
        return {
            "success": False,
            "worker_name": worker_name,
            "error": "Bundle tarball was not created",
        }

    # Move bundle to our bundles directory for serving
    BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
    dest_tarball = BUNDLES_DIR / f"gridx-{worker_name}.tar.gz"
    shutil.copy2(bundle_tarball, dest_tarball)

    return {
        "success": True,
        "worker_name": worker_name,
        "bundle_path": str(dest_tarball),
        "download_url": f"/api/onboarding/download/{worker_name}",
        "message": f"Bundle created for '{worker_name}'. Download and run on the remote machine.",
    }


@router.get("/download/{worker_name}")
def download_worker_bundle(worker_name: str):
    """Download the worker bundle tarball"""
    bundle_path = BUNDLES_DIR / f"gridx-{worker_name}.tar.gz"

    if not bundle_path.exists():
        # Try the original location
        bundle_path = Path(f"/tmp/gridx-{worker_name}.tar.gz")

    if not bundle_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Bundle for worker '{worker_name}' not found. Create it first.",
        )

    return FileResponse(
        path=str(bundle_path),
        filename=f"gridx-{worker_name}.tar.gz",
        media_type="application/gzip",
    )


@router.get("/status/{worker_name}")
def check_worker_status(worker_name: str):
    """
    Check if a worker has connected after onboarding.
    Used for polling to detect when worker joins.
    """
    wrapper = get_wrapper()
    worker = wrapper.get_worker(worker_name)

    if not worker:
        return {
            "worker_name": worker_name,
            "registered": False,
            "online": False,
            "message": "Worker not yet registered in hub config",
        }

    # Worker is registered, check if online
    ping = wrapper.ping_worker(worker_name, timeout=3)
    online = ping.get("online", False)

    return {
        "worker_name": worker_name,
        "registered": True,
        "online": online,
        "ip": worker.get("ip"),
        "message": "Connected and ready!"
        if online
        else "Registered but not yet online",
    }


@router.get("/pending")
def list_pending_workers():
    """List all workers that have bundles but haven't connected yet"""
    wrapper = get_wrapper()
    all_workers = wrapper.get_workers()

    pending = []
    connected = []

    for name, info in all_workers.items():
        ping = wrapper.ping_worker(name, timeout=2)
        worker_info = {
            "name": name,
            "ip": info.get("ip"),
            "online": ping.get("online", False),
        }

        if ping.get("online"):
            connected.append(worker_info)
        else:
            pending.append(worker_info)

    # Also check for bundles without registered workers
    if BUNDLES_DIR.exists():
        for bundle in BUNDLES_DIR.glob("gridx-*.tar.gz"):
            worker_name = bundle.stem.replace("gridx-", "").replace(".tar", "")
            if worker_name not in all_workers:
                pending.append(
                    {
                        "name": worker_name,
                        "ip": None,
                        "online": False,
                        "bundle_only": True,
                    }
                )

    return {
        "pending": pending,
        "connected": connected,
        "pending_count": len(pending),
        "connected_count": len(connected),
    }
