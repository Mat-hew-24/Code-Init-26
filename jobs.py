#!/usr/bin/env python3
"""
Grid-X Jobs - Submit and manage compute jobs on the swarm

Run this from the hub or any machine connected to the VPN.
"""
import subprocess
import json
import os
import sys
import time
import random
import string
import urllib.request
import urllib.error
from pathlib import Path


class GridXJobs:
    """Job manager for Grid-X cluster"""

    def __init__(self):
        self.config_dir = Path.home() / ".gridx"
        self.jobs_file = self.config_dir / "jobs.json"
        self.jobs = {}
        self._load_jobs()

    def _load_jobs(self):
        if self.jobs_file.exists():
            with open(self.jobs_file) as f:
                self.jobs = json.load(f)

    def _save_jobs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.jobs_file, "w") as f:
            json.dump(self.jobs, f, indent=2)

    def _run(self, cmd, check=True, capture=True):
        """Run shell command"""
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd)
        if check and result.returncode != 0:
            if capture:
                print(f"  Error: {result.stderr}")
        return result

    def _generate_id(self, prefix="job"):
        """Generate short unique ID"""
        chars = string.ascii_lowercase + string.digits
        suffix = "".join(random.choices(chars, k=6))
        return f"{prefix}-{suffix}"

    def _check_swarm(self):
        """Check if we can connect to swarm"""
        result = self._run(
            ["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"], check=False
        )
        if result.stdout.strip() != "active":
            print("Error: Not connected to Docker Swarm!")
            print("Make sure you're on the hub or a connected worker.")
            sys.exit(1)

    # ==================== RUN JOB ====================

    def run(
        self,
        image,
        command=None,
        name=None,
        cpus=None,
        memory=None,
        gpus=0,
        env=None,
        replicas=1,
    ):
        """
        Run a compute job on the cluster

        Example:
            python jobs.py run python:3.11 "python -c 'print(1+1)'"
            python jobs.py run pytorch/pytorch:latest "python train.py" --cpus 4 --memory 8G
            python jobs.py run nvidia/cuda:12.0-base "nvidia-smi" --gpus 1
        """
        self._check_swarm()

        job_id = name or self._generate_id()
        service_name = f"gridx-{job_id}"

        print(f"\n[+] Creating job: {job_id}")
        print(f"    Image: {image}")
        if command:
            print(f"    Command: {command}")
        if gpus:
            print(f"    GPUs: {gpus}")

        # Build docker service create command
        cmd = [
            "docker",
            "service",
            "create",
            "--name",
            service_name,
            "--replicas",
            str(replicas),
            "--restart-condition",
            "none",  # Don't restart after completion
        ]

        # Resource limits
        if cpus:
            cmd.extend(["--limit-cpu", str(cpus)])
            cmd.extend(["--reserve-cpu", str(cpus)])
        if memory:
            cmd.extend(["--limit-memory", memory])
            cmd.extend(["--reserve-memory", memory])

        # GPU support (requires nvidia runtime configured on workers)
        # Workers need to have NVIDIA Container Toolkit and advertise GPUs
        if gpus:
            cmd.extend(["--generic-resource", f"gpu={gpus}"])

        # Environment variables
        if env:
            for e in env:
                cmd.extend(["--env", e])

        # Add image
        cmd.append(image)

        # Add command if provided
        if command:
            cmd.extend(["sh", "-c", command])

        # Run
        result = self._run(cmd)

        if result.returncode == 0:
            service_id = result.stdout.strip()
            print(f"    Service ID: {service_id[:12]}")

            # Save job info
            self.jobs[job_id] = {
                "service_name": service_name,
                "service_id": service_id,
                "image": image,
                "command": command,
                "cpus": cpus,
                "memory": memory,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "job",
            }
            self._save_jobs()

            print(f"\n    Job submitted successfully!")
            print(f"    Check status: python jobs.py status {job_id}")
            print(f"    View logs: python jobs.py logs {job_id}")
            return job_id
        else:
            print(f"    Failed to create job!")
            return None

    # ==================== JUPYTER SESSION ====================

    def jupyter(self, name=None, cpus=None, memory=None, password=None):
        """
        Start a Jupyter notebook session

        Creates a Jupyter environment that users can access for ML work.
        """
        self._check_swarm()

        job_id = name or self._generate_id("jupyter")
        service_name = f"gridx-{job_id}"

        # Generate token if not provided
        token = password or "".join(
            random.choices(string.ascii_letters + string.digits, k=16)
        )

        print(f"\n[+] Creating Jupyter session: {job_id}")

        # Use scipy-notebook which has good ML libraries
        # Alternative: pytorch/pytorch, tensorflow/tensorflow
        image = "jupyter/scipy-notebook:latest"

        # Build command
        cmd = [
            "docker",
            "service",
            "create",
            "--name",
            service_name,
            "--replicas",
            "1",
            # Publish port - swarm will route it
            "--publish",
            "published=8888,target=8888,mode=host",
            "--env",
            f"JUPYTER_TOKEN={token}",
            # Don't run as root in jupyter image
            "--env",
            "GRANT_SUDO=yes",
            "--user",
            "root",
        ]

        # Resource limits
        if cpus:
            cmd.extend(["--limit-cpu", str(cpus)])
        if memory:
            cmd.extend(["--limit-memory", memory])

        cmd.append(image)

        # Start jupyter
        cmd.extend(
            [
                "start-notebook.sh",
                "--NotebookApp.token=" + token,
                "--NotebookApp.allow_origin='*'",
            ]
        )

        result = self._run(cmd)

        if result.returncode == 0:
            service_id = result.stdout.strip()

            # Save job info
            self.jobs[job_id] = {
                "service_name": service_name,
                "service_id": service_id,
                "image": image,
                "token": token,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "jupyter",
            }
            self._save_jobs()

            print(f"\n    Jupyter session created!")
            print(f"    Token: {token}")
            print()
            print("    Waiting for container to start...")
            time.sleep(3)

            # Find which node it's running on
            ps_result = self._run(
                [
                    "docker",
                    "service",
                    "ps",
                    service_name,
                    "--format",
                    "{{.Node}}\t{{.CurrentState}}",
                ],
                check=False,
            )

            if ps_result.stdout.strip():
                lines = ps_result.stdout.strip().split("\n")
                for line in lines:
                    if "Running" in line:
                        node = line.split("\t")[0]
                        print(f"    Running on node: {node}")
                        print(f"\n    Access Jupyter at:")
                        print(f"    http://<node-ip>:8888/?token={token}")
                        print(
                            f"\n    If on VPN, try: http://10.0.0.x:8888/?token={token}"
                        )
                        break

            print(f"\n    To stop: python jobs.py delete {job_id}")
            return job_id
        else:
            print(f"    Failed to create Jupyter session!")
            return None

    # ==================== ML TRAINING JOB ====================

    def train(
        self,
        script_url,
        name=None,
        framework="pytorch",
        cpus=None,
        memory=None,
        gpus=0,
    ):
        """
        Run an ML training job

        Example:
            python jobs.py train https://raw.githubusercontent.com/user/repo/train.py
            python jobs.py train ./train.py --framework tensorflow
        """
        self._check_swarm()

        job_id = name or self._generate_id("train")
        service_name = f"gridx-{job_id}"

        # Select image based on framework
        images = {
            "pytorch": "pytorch/pytorch:latest",
            "tensorflow": "tensorflow/tensorflow:latest",
            "sklearn": "python:3.11-slim",
        }
        image = images.get(framework, "python:3.11")

        print(f"\n[+] Creating training job: {job_id}")
        print(f"    Framework: {framework}")
        print(f"    Script: {script_url}")

        # Build command to download and run script
        if script_url.startswith("http"):
            run_cmd = f"pip install requests && python -c \"import requests; exec(requests.get('{script_url}').text)\""
        else:
            # Assume local file - would need volume mount
            print("    Note: Local files require volume mounting (not yet supported)")
            run_cmd = f"python {script_url}"

        cmd = [
            "docker",
            "service",
            "create",
            "--name",
            service_name,
            "--replicas",
            "1",
            "--restart-condition",
            "none",
        ]

        if cpus:
            cmd.extend(["--limit-cpu", str(cpus)])
        if memory:
            cmd.extend(["--limit-memory", memory])
        if gpus:
            cmd.extend(["--generic-resource", f"gpu={gpus}"])

        cmd.append(image)
        cmd.extend(["sh", "-c", run_cmd])

        result = self._run(cmd)

        if result.returncode == 0:
            service_id = result.stdout.strip()

            self.jobs[job_id] = {
                "service_name": service_name,
                "service_id": service_id,
                "image": image,
                "script": script_url,
                "framework": framework,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "training",
            }
            self._save_jobs()

            print(f"\n    Training job submitted!")
            print(f"    Check logs: python jobs.py logs {job_id}")
            return job_id
        else:
            print(f"    Failed to create training job!")
            return None

    # ==================== LIST JOBS ====================

    def list_jobs(self):
        """List all jobs"""
        self._check_swarm()

        print("\n" + "=" * 70)
        print("       GRID-X JOBS")
        print("=" * 70)

        # Get running services
        result = self._run(
            [
                "docker",
                "service",
                "ls",
                "--filter",
                "name=gridx-",
                "--format",
                "{{.Name}}\t{{.Replicas}}\t{{.Image}}",
            ],
            check=False,
        )

        running = {}
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    running[parts[0]] = {
                        "replicas": parts[1],
                        "image": parts[2] if len(parts) > 2 else "",
                    }

        if not self.jobs and not running:
            print("\n  No jobs found.")
            return

        print(f"\n{'ID':<15} {'TYPE':<10} {'STATUS':<15} {'CREATED':<20}")
        print("-" * 70)

        for job_id, job in self.jobs.items():
            service_name = job.get("service_name", f"gridx-{job_id}")
            job_type = job.get("type", "job")

            if service_name in running:
                status = f"Running ({running[service_name]['replicas']})"
            else:
                status = "Stopped"

            created = job.get("created", "N/A")
            print(f"{job_id:<15} {job_type:<10} {status:<15} {created:<20}")

        print()

    # ==================== JOB STATUS ====================

    def status(self, job_id):
        """Show detailed status of a job"""
        self._check_swarm()

        if job_id not in self.jobs:
            print(f"  Error: Job '{job_id}' not found!")
            print("  Run 'python jobs.py list' to see all jobs.")
            return

        job = self.jobs[job_id]
        service_name = job.get("service_name", f"gridx-{job_id}")

        print(f"\n[Job: {job_id}]")
        print(f"  Type: {job.get('type', 'job')}")
        print(f"  Image: {job.get('image', 'N/A')}")
        print(f"  Created: {job.get('created', 'N/A')}")

        if job.get("type") == "jupyter":
            print(f"  Token: {job.get('token', 'N/A')}")

        # Get service status
        print(f"\n[Service Status]")
        result = self._run(
            [
                "docker",
                "service",
                "ps",
                service_name,
                "--format",
                "{{.ID}}\t{{.Node}}\t{{.CurrentState}}\t{{.Error}}",
            ],
            check=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            print(f"  {'TASK ID':<15} {'NODE':<15} {'STATE':<25}")
            print("  " + "-" * 55)
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 3:
                    task_id = parts[0][:12]
                    node = parts[1][:15]
                    state = parts[2][:25]
                    print(f"  {task_id:<15} {node:<15} {state:<25}")
                    if len(parts) > 3 and parts[3]:
                        print(f"    Error: {parts[3]}")
        else:
            print("  Service not running")

        print()

    # ==================== LOGS ====================

    def logs(self, job_id, follow=False, tail=50):
        """Show logs from a job"""
        self._check_swarm()

        if job_id not in self.jobs:
            print(f"  Error: Job '{job_id}' not found!")
            return

        job = self.jobs[job_id]
        service_name = job.get("service_name", f"gridx-{job_id}")

        cmd = ["docker", "service", "logs", "--tail", str(tail)]
        if follow:
            cmd.append("--follow")
        cmd.append(service_name)

        print(f"\n[Logs: {job_id}]")
        print("-" * 50)

        # Run without capture to stream output
        self._run(cmd, capture=False, check=False)

    # ==================== DELETE JOB ====================

    def delete(self, job_id, force=False):
        """Delete a job"""
        self._check_swarm()

        if job_id not in self.jobs:
            # Try to delete by service name anyway
            service_name = f"gridx-{job_id}"
        else:
            job = self.jobs[job_id]
            service_name = job.get("service_name", f"gridx-{job_id}")

        print(f"\n[-] Deleting job: {job_id}")

        result = self._run(["docker", "service", "rm", service_name], check=False)

        if result.returncode == 0:
            if job_id in self.jobs:
                del self.jobs[job_id]
                self._save_jobs()
            print(f"    Job deleted!")
        else:
            print(f"    Service not found or already deleted")
            if force and job_id in self.jobs:
                del self.jobs[job_id]
                self._save_jobs()
                print(f"    Removed from local registry")

    # ==================== CLUSTER INFO ====================

    def cluster_info(self):
        """Show cluster resources and utilization"""
        self._check_swarm()

        print("\n" + "=" * 70)
        print("       GRID-X CLUSTER INFO")
        print("=" * 70)

        # Get nodes
        result = self._run(
            [
                "docker",
                "node",
                "ls",
                "--format",
                "{{.ID}}\t{{.Hostname}}\t{{.Status}}\t{{.Availability}}",
            ],
            check=False,
        )

        if result.returncode != 0:
            print("\n  Error: Cannot connect to swarm manager")
            return

        print(f"\n[Nodes]")
        print(f"  {'HOSTNAME':<20} {'STATUS':<12} {'AVAILABILITY':<12}")
        print("  " + "-" * 44)

        nodes = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 4:
                node_id, hostname, status, avail = parts[:4]
                nodes.append(node_id)
                print(f"  {hostname:<20} {status:<12} {avail:<12}")

        # Get total resources per node
        print(f"\n[Resources per Node]")
        for node_id in nodes[:5]:  # Limit to first 5 nodes for speed
            inspect_result = self._run(
                [
                    "docker",
                    "node",
                    "inspect",
                    node_id,
                    "--format",
                    "{{.Description.Hostname}}\t{{.Description.Resources.NanoCPUs}}\t{{.Description.Resources.MemoryBytes}}",
                ],
                check=False,
            )

            if inspect_result.returncode == 0:
                parts = inspect_result.stdout.strip().split("\t")
                if len(parts) >= 3:
                    hostname = parts[0]
                    cpus = int(parts[1]) / 1e9 if parts[1].isdigit() else 0
                    mem_gb = int(parts[2]) / (1024**3) if parts[2].isdigit() else 0
                    print(f"  {hostname}: {cpus:.0f} CPUs, {mem_gb:.1f} GB RAM")

        # Get running services
        print(f"\n[Running Services]")
        services_result = self._run(
            [
                "docker",
                "service",
                "ls",
                "--format",
                "{{.Name}}\t{{.Replicas}}",
            ],
            check=False,
        )

        if services_result.stdout.strip():
            count = 0
            for line in services_result.stdout.strip().split("\n"):
                if line.startswith("gridx-"):
                    parts = line.split("\t")
                    print(f"  {parts[0]}: {parts[1] if len(parts) > 1 else 'N/A'}")
                    count += 1
            if count == 0:
                print("  No Grid-X services running")
        else:
            print("  No services running")

        print()

    # ==================== EXEC ON WORKER ====================

    def _get_worker_ip(self, worker):
        """Get worker IP from name or return if already an IP"""
        import re

        # Check if it's already an IP address
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", worker):
            return worker

        # Try to get from hub config
        hub_config = Path("/etc/gridx/hub_config.json")
        if hub_config.exists():
            try:
                with open(hub_config) as f:
                    config = json.load(f)
                peers = config.get("peers", {})
                if worker in peers:
                    return peers[worker]["ip"]
            except:
                pass

        # Check home dir config too
        home_config = Path.home() / ".gridx" / "hub_config.json"
        if home_config.exists():
            try:
                with open(home_config) as f:
                    config = json.load(f)
                peers = config.get("peers", {})
                if worker in peers:
                    return peers[worker]["ip"]
            except:
                pass

        return None

    def exec_on_worker(self, worker, command, timeout=30):
        """
        Execute a command on a worker via the HTTP agent.

        Args:
            worker: Worker name or VPN IP address
            command: Command to execute
            timeout: Request timeout in seconds

        Returns:
            dict with output, error, exit_code or None on failure
        """
        ip = self._get_worker_ip(worker)
        if not ip:
            print(f"  Error: Worker '{worker}' not found!")
            print("  Use a VPN IP (e.g., 10.0.0.2) or a registered worker name.")
            return None

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
                return result

        except urllib.error.URLError as e:
            print(f"  Error: Cannot connect to worker agent at {ip}:7576")
            print(f"  {e.reason}")
            print("  Make sure the worker's command agent is running:")
            print("    python worker.py agent")
            return None
        except TimeoutError:
            print(f"  Error: Request to {ip} timed out after {timeout}s")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            return None

    def exec_command(self, worker, command):
        """Execute command on worker and print results"""
        print(f"\n[Exec on {worker}]")
        print(f"  Command: {command}")
        print("-" * 50)

        result = self.exec_on_worker(worker, command)

        if result:
            if result.get("output"):
                print(result["output"], end="")
            if result.get("error"):
                print(f"STDERR: {result['error']}", end="")
            print("-" * 50)
            print(f"  Exit code: {result.get('exit_code', 'N/A')}")
            return result.get("exit_code", 1) == 0
        return False

    def ping_worker(self, worker, timeout=5):
        """Ping a single worker's agent"""
        ip = self._get_worker_ip(worker)
        if not ip:
            return False, "Worker not found"

        url = f"http://{ip}:7576/ping"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return True, ip
        except:
            pass
        return False, ip

    def ping_workers(self):
        """Ping all registered workers to check agent status"""
        print("\n" + "=" * 60)
        print("       GRID-X WORKER AGENT STATUS")
        print("=" * 60)

        # Try to load hub config
        hub_config = Path("/etc/gridx/hub_config.json")
        config = None

        if hub_config.exists():
            try:
                with open(hub_config) as f:
                    config = json.load(f)
            except:
                pass

        if not config:
            # Try home dir
            home_config = Path.home() / ".gridx" / "hub_config.json"
            if home_config.exists():
                try:
                    with open(home_config) as f:
                        config = json.load(f)
                except:
                    pass

        if not config or not config.get("peers"):
            print("\n  No workers registered. Add workers with:")
            print("    python hub.py add-peer <name>")
            return

        print(f"\n{'WORKER':<15} {'VPN IP':<15} {'AGENT STATUS':<15}")
        print("-" * 45)

        online = 0
        for name, peer in config["peers"].items():
            ip = peer.get("ip", "?")
            ok, _ = self.ping_worker(name)
            if ok:
                status = "\033[32mONLINE\033[0m"  # Green
                online += 1
            else:
                status = "\033[31mOFFLINE\033[0m"  # Red
            print(f"{name:<15} {ip:<15} {status}")

        print("-" * 45)
        print(f"  {online}/{len(config['peers'])} workers online\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Grid-X Jobs - Run compute jobs on the cluster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a simple job
  python jobs.py run python:3.11 "python -c 'print(1+1)'"

  # Run with resource limits
  python jobs.py run pytorch/pytorch "python train.py" --cpus 4 --memory 8G

  # Start a Jupyter notebook
  python jobs.py jupyter --cpus 2 --memory 4G

  # Run ML training
  python jobs.py train https://example.com/train.py --framework pytorch

  # List and manage jobs
  python jobs.py list
  python jobs.py status myjob
  python jobs.py logs myjob
  python jobs.py delete myjob
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run a compute job")
    run_parser.add_argument("image", help="Docker image to use")
    run_parser.add_argument("cmd", nargs="?", help="Command to run")
    run_parser.add_argument("--name", help="Job name")
    run_parser.add_argument("--cpus", type=float, help="CPU limit")
    run_parser.add_argument("--memory", help="Memory limit (e.g., 4G)")
    run_parser.add_argument(
        "--gpus", type=int, default=0, help="Number of GPUs to request"
    )
    run_parser.add_argument(
        "--env", "-e", action="append", help="Environment variables"
    )
    run_parser.add_argument(
        "--replicas", type=int, default=1, help="Number of replicas"
    )

    # jupyter
    jupyter_parser = subparsers.add_parser("jupyter", help="Start Jupyter notebook")
    jupyter_parser.add_argument("--name", help="Session name")
    jupyter_parser.add_argument("--cpus", type=float, help="CPU limit")
    jupyter_parser.add_argument("--memory", help="Memory limit")
    jupyter_parser.add_argument("--password", help="Jupyter token/password")

    # train
    train_parser = subparsers.add_parser("train", help="Run ML training job")
    train_parser.add_argument("script", help="Script URL or path")
    train_parser.add_argument("--name", help="Job name")
    train_parser.add_argument(
        "--framework",
        choices=["pytorch", "tensorflow", "sklearn"],
        default="pytorch",
        help="ML framework",
    )
    train_parser.add_argument("--cpus", type=float, help="CPU limit")
    train_parser.add_argument("--memory", help="Memory limit")
    train_parser.add_argument(
        "--gpus", type=int, default=0, help="Number of GPUs to request"
    )

    # list
    subparsers.add_parser("list", help="List all jobs")
    subparsers.add_parser("ls", help="List all jobs (alias)")

    # status
    status_parser = subparsers.add_parser("status", help="Show job status")
    status_parser.add_argument("job_id", help="Job ID")

    # logs
    logs_parser = subparsers.add_parser("logs", help="Show job logs")
    logs_parser.add_argument("job_id", help="Job ID")
    logs_parser.add_argument("--follow", "-f", action="store_true", help="Follow logs")
    logs_parser.add_argument("--tail", type=int, default=50, help="Lines to show")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a job")
    delete_parser.add_argument("job_id", help="Job ID")
    delete_parser.add_argument("--force", action="store_true", help="Force delete")

    # rm (alias for delete)
    rm_parser = subparsers.add_parser("rm", help="Delete a job (alias)")
    rm_parser.add_argument("job_id", help="Job ID")
    rm_parser.add_argument("--force", action="store_true", help="Force delete")

    # cluster
    subparsers.add_parser("cluster", help="Show cluster info")
    subparsers.add_parser("info", help="Show cluster info (alias)")

    # exec
    exec_parser = subparsers.add_parser("exec", help="Execute command on a worker")
    exec_parser.add_argument("worker", help="Worker name or VPN IP")
    exec_parser.add_argument("cmd", help="Command to execute")

    # ping-workers
    subparsers.add_parser("ping-workers", help="Check which workers are online")

    args = parser.parse_args()
    jobs = GridXJobs()

    if args.command == "run":
        jobs.run(
            args.image,
            args.cmd,
            name=args.name,
            cpus=args.cpus,
            memory=args.memory,
            gpus=args.gpus,
            env=args.env,
            replicas=args.replicas,
        )
    elif args.command == "jupyter":
        jobs.jupyter(
            name=args.name,
            cpus=args.cpus,
            memory=args.memory,
            password=args.password,
        )
    elif args.command == "train":
        jobs.train(
            args.script,
            name=args.name,
            framework=args.framework,
            cpus=args.cpus,
            memory=args.memory,
            gpus=args.gpus,
        )
    elif args.command in ["list", "ls"]:
        jobs.list_jobs()
    elif args.command == "status":
        jobs.status(args.job_id)
    elif args.command == "logs":
        jobs.logs(args.job_id, follow=args.follow, tail=args.tail)
    elif args.command in ["delete", "rm"]:
        jobs.delete(args.job_id, force=args.force)
    elif args.command in ["cluster", "info"]:
        jobs.cluster_info()
    elif args.command == "exec":
        jobs.exec_command(args.worker, args.cmd)
    elif args.command == "ping-workers":
        jobs.ping_workers()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
