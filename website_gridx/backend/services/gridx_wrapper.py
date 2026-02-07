"""
GridX Wrapper - Wraps existing hub.py, jobs.py functionality for the web API

This module provides a clean interface to the gridx functionality without
modifying the original files.
"""

import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List, Any


class GridXWrapper:
    """
    Wrapper around existing gridx scripts.
    Provides methods that can be called from the FastAPI backend.
    """

    def __init__(self):
        self.config_dir = Path("/etc/gridx")
        self.config_file = self.config_dir / "hub_config.json"
        self.jobs_dir = Path.home() / ".gridx"
        self.jobs_file = self.jobs_dir / "jobs.json"
        self.container_name = "gridx-hub"
        self.config = {}
        self.jobs = {}
        self._load_config()
        self._load_jobs()

    def _load_config(self):
        """Load hub configuration from Docker container or host"""
        self.config = {}

        # First try to read from Docker container
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container_name,
                    "cat",
                    "/etc/gridx/hub_config.json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                self.config = json.loads(result.stdout)
                return
        except Exception:
            pass

        # Fallback to host filesystem
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.config = json.load(f)
            except:
                self.config = {}

    def _load_jobs(self):
        """Load jobs registry"""
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file) as f:
                    self.jobs = json.load(f)
            except:
                self.jobs = {}

    def _run(self, cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command"""
        return subprocess.run(cmd, capture_output=True, text=True)

    # ==================== WORKERS ====================

    def get_workers(self) -> Dict[str, Any]:
        """Get all registered workers/peers"""
        self._load_config()
        return self.config.get("peers", {})

    def get_worker(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific worker"""
        self._load_config()
        return self.config.get("peers", {}).get(name)

    def ping_worker(self, name: str, timeout: int = 5) -> Dict[str, Any]:
        """Ping a worker's command agent"""
        worker = self.get_worker(name)
        if not worker:
            return {"online": False, "error": "Worker not found"}

        ip = worker.get("ip")
        url = f"http://{ip}:7576/ping"

        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return {"online": True, "ip": ip}
        except Exception as e:
            return {"online": False, "ip": ip, "error": str(e)}

        return {"online": False, "ip": ip}

    def ping_all_workers(self) -> Dict[str, Dict[str, Any]]:
        """Ping all workers and return status"""
        workers = self.get_workers()
        results = {}
        for name in workers:
            results[name] = self.ping_worker(name)
        return results

    def get_worker_status(
        self, name: str, timeout: int = 5
    ) -> Optional[Dict[str, Any]]:
        """Get detailed status from worker agent"""
        worker = self.get_worker(name)
        if not worker:
            return None

        ip = worker.get("ip")
        url = f"http://{ip}:7576/status"

        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    data["ip"] = ip
                    data["name"] = name
                    return data
        except:
            pass
        return None

    def get_best_worker(self) -> Optional[str]:
        """Get the best available worker for task execution"""
        workers = self.get_workers()
        if not workers:
            return None

        # Ping all workers to find online ones
        online_workers = []
        for name in workers:
            ping_result = self.ping_worker(name, timeout=2)
            if ping_result.get("online"):
                # Get detailed status for load assessment
                status = self.get_worker_status(name, timeout=3)
                if status:
                    online_workers.append(
                        {
                            "name": name,
                            "status": status,
                            "cpu_percent": status.get("cpu_percent", 0),
                            "memory_percent": status.get("memory_percent", 0),
                            "gpus": workers[name].get("gpus", 0),
                        }
                    )

        if not online_workers:
            return None

        # Sort by load (lower CPU/memory usage = better)
        # Prefer workers with GPUs for GPU-intensive tasks
        online_workers.sort(
            key=lambda w: (
                w["cpu_percent"] + w["memory_percent"],  # Total load
                -w["gpus"],  # Prefer more GPUs (negative for descending)
            )
        )

        return online_workers[0]["name"]

    def get_online_workers(self) -> List[str]:
        """Get list of all online worker names"""
        workers = self.get_workers()
        online = []
        for name in workers:
            ping_result = self.ping_worker(name, timeout=2)
            if ping_result.get("online"):
                online.append(name)
        return online

    def exec_on_worker(
        self, name: str, command: str, timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a command on a worker"""
        worker = self.get_worker(name)
        if not worker:
            return {"success": False, "error": "Worker not found"}

        ip = worker.get("ip")
        url = f"http://{ip}:7576/exec"
        data = json.dumps({"cmd": command}).encode()

        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
                result["success"] = result.get("exit_code", 1) == 0
                result["worker"] = name
                result["ip"] = ip
                return result
        except urllib.error.URLError as e:
            return {
                "success": False,
                "error": f"Cannot connect: {e.reason}",
                "worker": name,
            }
        except TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "worker": name,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "worker": name}

    def exec_on_best_worker(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a command on the best available worker"""
        best_worker = self.get_best_worker()
        if not best_worker:
            return {"success": False, "error": "No workers available", "worker": None}

        result = self.exec_on_worker(best_worker, command, timeout)
        result["auto_selected"] = True
        return result

    # ==================== JOBS ====================

    def get_jobs(self) -> Dict[str, Any]:
        """Get all jobs"""
        self._load_jobs()
        return self.jobs

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job"""
        self._load_jobs()
        return self.jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job status from Docker"""
        job = self.get_job(job_id)
        if not job:
            return {"error": "Job not found"}

        service_name = job.get("service_name", f"gridx-{job_id}")

        # Get service status
        result = self._run(
            [
                "docker",
                "service",
                "ps",
                service_name,
                "--format",
                "{{.ID}}\t{{.Node}}\t{{.CurrentState}}\t{{.Error}}",
            ]
        )

        tasks = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 3:
                    tasks.append(
                        {
                            "id": parts[0][:12],
                            "node": parts[1],
                            "state": parts[2],
                            "error": parts[3] if len(parts) > 3 else None,
                        }
                    )

        return {
            "job_id": job_id,
            "service_name": service_name,
            "type": job.get("type", "job"),
            "image": job.get("image"),
            "created": job.get("created"),
            "tasks": tasks,
            "running": any("Running" in t.get("state", "") for t in tasks),
        }

    def get_job_logs(self, job_id: str, tail: int = 100) -> Dict[str, Any]:
        """Get logs for a job"""
        job = self.get_job(job_id)
        if not job:
            return {"error": "Job not found"}

        service_name = job.get("service_name", f"gridx-{job_id}")

        result = self._run(
            ["docker", "service", "logs", "--tail", str(tail), service_name]
        )

        return {
            "job_id": job_id,
            "logs": result.stdout + result.stderr if result.returncode == 0 else "",
            "error": result.stderr if result.returncode != 0 else None,
        }

    def run_job(
        self,
        image: str,
        command: Optional[str] = None,
        name: Optional[str] = None,
        cpus: Optional[float] = None,
        memory: Optional[str] = None,
        gpus: int = 0,
        env: Optional[List[str]] = None,
        replicas: int = 1,
    ) -> Dict[str, Any]:
        """Run a new job via docker service"""
        import random
        import string
        import time

        # Generate job ID
        if not name:
            suffix = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=6)
            )
            name = f"job-{suffix}"

        service_name = f"gridx-{name}"

        # Build command
        cmd = [
            "docker",
            "service",
            "create",
            "--name",
            service_name,
            "--replicas",
            str(replicas),
            "--restart-condition",
            "none",
        ]

        if cpus:
            cmd.extend(["--limit-cpu", str(cpus)])
        if memory:
            cmd.extend(["--limit-memory", memory])
        if gpus:
            cmd.extend(["--generic-resource", f"gpu={gpus}"])
        if env:
            for e in env:
                cmd.extend(["--env", e])

        cmd.append(image)

        if command:
            cmd.extend(["sh", "-c", command])

        result = self._run(cmd)

        if result.returncode == 0:
            service_id = result.stdout.strip()

            # Save to jobs registry
            self._load_jobs()
            self.jobs[name] = {
                "service_name": service_name,
                "service_id": service_id,
                "image": image,
                "command": command,
                "cpus": cpus,
                "memory": memory,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "job",
            }
            self.jobs_dir.mkdir(parents=True, exist_ok=True)
            with open(self.jobs_file, "w") as f:
                json.dump(self.jobs, f, indent=2)

            return {"success": True, "job_id": name, "service_id": service_id}
        else:
            return {"success": False, "error": result.stderr}

    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a job"""
        job = self.get_job(job_id)
        service_name = (
            job.get("service_name", f"gridx-{job_id}") if job else f"gridx-{job_id}"
        )

        result = self._run(["docker", "service", "rm", service_name])

        if result.returncode == 0:
            # Remove from registry
            self._load_jobs()
            if job_id in self.jobs:
                del self.jobs[job_id]
                with open(self.jobs_file, "w") as f:
                    json.dump(self.jobs, f, indent=2)
            return {"success": True, "job_id": job_id}
        else:
            return {"success": False, "error": result.stderr or "Service not found"}

    # ==================== HUB STATUS ====================

    def get_hub_status(self) -> Dict[str, Any]:
        """Get overall hub status"""
        self._load_config()

        status = {
            "hub_ip": self.config.get("hub_ip", "10.0.0.1"),
            "public_ip": self.config.get("public_ip"),
            "wg_port": self.config.get("wg_port", 51820),
            "peers_count": len(self.config.get("peers", {})),
            "wireguard": {"status": "unknown"},
            "swarm": {"status": "unknown"},
        }

        # Check WireGuard
        wg_result = self._run(["wg", "show"])
        if wg_result.returncode == 0 and wg_result.stdout.strip():
            status["wireguard"]["status"] = "running"
            # Count connected peers
            lines = wg_result.stdout.split("\n")
            handshakes = [l for l in lines if "latest handshake" in l]
            status["wireguard"]["connected_peers"] = len(handshakes)
        else:
            status["wireguard"]["status"] = "stopped"

        # Check Docker Swarm
        swarm_result = self._run(
            [
                "docker",
                "node",
                "ls",
                "--format",
                "{{.Hostname}}\t{{.Status}}\t{{.Availability}}",
            ]
        )

        if swarm_result.returncode == 0:
            status["swarm"]["status"] = "active"
            nodes = []
            for line in swarm_result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        nodes.append(
                            {
                                "hostname": parts[0],
                                "status": parts[1],
                                "availability": parts[2],
                            }
                        )
            status["swarm"]["nodes"] = nodes
        else:
            status["swarm"]["status"] = "inactive"

        return status

    def get_running_services(self) -> List[Dict[str, Any]]:
        """Get all running gridx services"""
        result = self._run(
            [
                "docker",
                "service",
                "ls",
                "--filter",
                "name=gridx-",
                "--format",
                "{{.Name}}\t{{.Replicas}}\t{{.Image}}",
            ]
        )

        services = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    services.append(
                        {
                            "name": parts[0],
                            "replicas": parts[1],
                            "image": parts[2] if len(parts) > 2 else "",
                        }
                    )
        return services


# Singleton instance
_wrapper = None


def get_wrapper() -> GridXWrapper:
    """Get the singleton wrapper instance"""
    global _wrapper
    if _wrapper is None:
        _wrapper = GridXWrapper()
    return _wrapper
