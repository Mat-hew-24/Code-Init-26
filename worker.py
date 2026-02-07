#!/usr/bin/env python3
"""
Grid-X Worker - Run on machines that want to share resources

This script:
1. Sets up WireGuard VPN connection to hub
2. Joins the Docker Swarm cluster
3. Runs command agent for remote execution
"""

import subprocess
import json
import os
import sys
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Try to import psutil, but don't fail if not available
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class CommandAgent:
    """HTTP server that accepts commands from hub over VPN"""

    def __init__(self, port=7576, bind_ip="0.0.0.0"):
        self.port = port
        self.bind_ip = bind_ip
        self.worker = GridXWorker()

    def start(self):
        """Start the HTTP command agent"""
        agent = self

        class AgentHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Custom logging
                print(f"  [{self.client_address[0]}] {args[0]}")

            def send_json(self, data, status=200):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                if self.path == "/ping":
                    self.send_json({"status": "ok", "agent": "gridx-worker"})

                elif self.path == "/status":
                    info = agent.worker.get_system_info()
                    info["hostname"] = socket.gethostname()
                    info["agent_port"] = agent.port
                    gpu_info = agent.worker.get_gpu_info()
                    info.update(gpu_info)
                    self.send_json(info)

                elif self.path == "/":
                    self.send_json(
                        {
                            "service": "Grid-X Worker Agent",
                            "endpoints": {
                                "GET /ping": "Health check",
                                "GET /status": "Worker status and resources",
                                "POST /exec": 'Execute command (JSON body: {"cmd": "..."})',
                            },
                        }
                    )
                else:
                    self.send_json({"error": "Not found"}, 404)

            def do_POST(self):
                if self.path == "/exec":
                    try:
                        # Read request body
                        content_length = int(self.headers.get("Content-Length", 0))
                        body = self.rfile.read(content_length).decode()
                        data = json.loads(body) if body else {}

                        cmd = data.get("cmd", "")
                        if not cmd:
                            self.send_json({"error": "No command provided"}, 400)
                            return

                        # Execute command
                        print(f"  Executing: {cmd}")
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=300,  # 5 minute timeout
                        )

                        self.send_json(
                            {
                                "output": result.stdout,
                                "error": result.stderr,
                                "exit_code": result.returncode,
                            }
                        )

                    except json.JSONDecodeError:
                        self.send_json({"error": "Invalid JSON"}, 400)
                    except subprocess.TimeoutExpired:
                        self.send_json(
                            {"error": "Command timed out (5 min limit)"}, 408
                        )
                    except Exception as e:
                        self.send_json({"error": str(e)}, 500)
                else:
                    self.send_json({"error": "Not found"}, 404)

        # Get hostname for display
        hostname = socket.gethostname()

        print(f"\n{'=' * 60}")
        print(f"       GRID-X WORKER AGENT")
        print(f"{'=' * 60}")
        print(f"\n  Hostname: {hostname}")
        print(f"  Listening on: http://{self.bind_ip}:{self.port}")
        print(f"\n  Endpoints:")
        print(f"    GET  /ping   - Health check")
        print(f"    GET  /status - Worker info")
        print(f"    POST /exec   - Execute command")
        print(f"\n  Press Ctrl+C to stop\n")

        try:
            server = HTTPServer((self.bind_ip, self.port), AgentHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n  Agent stopped.")
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"  Error: Port {self.port} already in use!")
                print(f"  Another agent may be running. Kill it with:")
                print(f"    pkill -f 'python.*worker.py.*agent'")
            else:
                print(f"  Error: {e}")
            sys.exit(1)


class GridXWorker:
    """Worker that joins the Grid-X cluster"""

    def __init__(self):
        self.config_dir = Path.home() / ".gridx"
        self.config_file = self.config_dir / "worker_config.json"
        self.wg_dir = Path("/etc/wireguard")

        self.config = {"hub_ip": None, "my_ip": None, "status": "disconnected"}
        self._load_config()

    def _load_config(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                self.config.update(json.load(f))

    def _save_config(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def _run(self, cmd, check=True):
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"  Error: {result.stderr}")
        return result

    def get_system_info(self):
        """Get system resources"""
        if HAS_PSUTIL:
            return {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "memory_available_gb": round(
                    psutil.virtual_memory().available / (1024**3), 1
                ),
            }
        else:
            # Fallback without psutil
            cpu_count = os.cpu_count() or 1
            try:
                with open("/proc/meminfo") as f:
                    meminfo = f.read()
                mem_total = int(
                    [l for l in meminfo.split("\n") if "MemTotal" in l][0].split()[1]
                ) / (1024**2)
                mem_avail = int(
                    [l for l in meminfo.split("\n") if "MemAvailable" in l][0].split()[
                        1
                    ]
                ) / (1024**2)
            except:
                mem_total = 0
                mem_avail = 0
            return {
                "cpu_count": cpu_count,
                "cpu_percent": 0,
                "memory_total_gb": round(mem_total, 1),
                "memory_available_gb": round(mem_avail, 1),
            }

    def get_gpu_info(self):
        """Get GPU information"""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=count,name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(", ")
                return {
                    "gpu_count": int(parts[0]) if parts[0].isdigit() else 1,
                    "gpu_name": parts[1] if len(parts) > 1 else "Unknown",
                    "gpu_memory_mb": int(parts[2])
                    if len(parts) > 2 and parts[2].isdigit()
                    else 0,
                }
        except:
            pass
        return {"gpu_count": 0, "gpu_name": None, "gpu_memory_mb": 0}

    def setup_wireguard(self, config_content):
        """Setup WireGuard with provided config"""
        print("\n[1] Setting up WireGuard VPN...")

        self.wg_dir.mkdir(parents=True, exist_ok=True)

        # Write config
        wg_conf = self.wg_dir / "wg0.conf"
        wg_conf.write_text(config_content)
        wg_conf.chmod(0o600)

        # Stop existing
        self._run(["wg-quick", "down", "wg0"], check=False)

        # Start
        result = self._run(["wg-quick", "up", "wg0"])

        if result.returncode == 0:
            print("  WireGuard connected!")

            # Enable on boot (may fail in containers without systemd)
            if os.path.exists("/run/systemd/system"):
                self._run(["systemctl", "enable", "wg-quick@wg0"], check=False)
            return True
        else:
            print("  Failed to start WireGuard!")
            return False

    def test_connection(self, hub_ip="10.0.0.1"):
        """Test VPN connection to hub"""
        print(f"\n[2] Testing connection to hub ({hub_ip})...")

        result = self._run(["ping", "-c", "2", hub_ip], check=False)

        if result.returncode == 0:
            print("  Connection successful!")
            return True
        else:
            print("  Cannot reach hub! Check VPN config.")
            return False

    def join_swarm(self, token, hub_ip="10.0.0.1"):
        """Join Docker Swarm cluster"""
        print("\n[3] Joining Docker Swarm cluster...")

        # Leave existing swarm
        self._run(["docker", "swarm", "leave", "--force"], check=False)

        # Join
        result = self._run(
            ["docker", "swarm", "join", "--token", token, f"{hub_ip}:2377"]
        )

        if result.returncode == 0:
            print("  Joined swarm successfully!")
            self.config["hub_ip"] = hub_ip
            self.config["status"] = "connected"
            self._save_config()
            return True
        else:
            print("  Failed to join swarm!")
            return False

    def leave(self):
        """Leave the Grid-X cluster"""
        print("\n[Leaving Grid-X cluster...]")

        # Leave swarm
        self._run(["docker", "swarm", "leave", "--force"], check=False)

        # Stop WireGuard
        self._run(["wg-quick", "down", "wg0"], check=False)

        self.config["status"] = "disconnected"
        self._save_config()

        print("  Left cluster successfully!")

    def status(self):
        """Show worker status"""
        print("\n" + "=" * 60)
        print("       GRID-X WORKER STATUS")
        print("=" * 60)

        # System info
        info = self.get_system_info()
        print("\n[System Resources]")
        print(f"  CPU Cores: {info['cpu_count']}")
        print(f"  CPU Usage: {info['cpu_percent']}%")
        print(
            f"  Memory: {info['memory_available_gb']}/{info['memory_total_gb']} GB available"
        )

        # GPU info
        gpu_info = self.get_gpu_info()
        if gpu_info["gpu_count"] > 0:
            print(f"  GPU: {gpu_info['gpu_count']}x {gpu_info['gpu_name']}")

        # WireGuard status
        print("\n[WireGuard VPN]")
        wg_result = self._run(["wg", "show"], check=False)
        if wg_result.returncode == 0 and wg_result.stdout.strip():
            print("  Status: CONNECTED")
            # Get our IP
            ip_result = self._run(["ip", "addr", "show", "wg0"], check=False)
            if "inet " in ip_result.stdout:
                import re

                match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", ip_result.stdout)
                if match:
                    print(f"  VPN IP: {match.group(1)}")
        else:
            print("  Status: DISCONNECTED")

        # Docker Swarm status
        print("\n[Docker Swarm]")
        swarm_result = self._run(
            ["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"], check=False
        )
        state = swarm_result.stdout.strip()

        if state == "active":
            print("  Status: CONNECTED TO SWARM")
            # Get node ID
            node_result = self._run(
                ["docker", "info", "--format", "{{.Swarm.NodeID}}"], check=False
            )
            print(f"  Node ID: {node_result.stdout.strip()[:12]}")
        else:
            print("  Status: NOT IN SWARM")

        # Agent status
        print("\n[Command Agent]")
        try:
            import urllib.request

            req = urllib.request.urlopen("http://127.0.0.1:7576/ping", timeout=2)
            if req.status == 200:
                print("  Status: RUNNING on port 7576")
        except:
            print("  Status: NOT RUNNING")
            print("  Start with: python worker.py agent")

        print()

    def interactive_setup(self):
        """Interactive setup wizard"""
        print("\n" + "=" * 60)
        print("       GRID-X WORKER SETUP")
        print("=" * 60)

        # Show system info
        info = self.get_system_info()
        print(f"\n[Your System]")
        print(f"  CPU: {info['cpu_count']} cores")
        print(f"  RAM: {info['memory_total_gb']} GB")

        # Check Docker
        docker_result = self._run(["docker", "--version"], check=False)
        if docker_result.returncode != 0:
            print("\n  ERROR: Docker not installed!")
            print("  Please install Docker first.")
            sys.exit(1)
        print("  Docker: Installed")

        # Get WireGuard config
        print("\n" + "-" * 60)
        print("Paste the WireGuard config from your hub admin")
        print("(Paste, then press Enter twice)")
        print("-" * 60 + "\n")

        lines = []
        empty = 0
        while True:
            line = input()
            if line == "":
                empty += 1
                if empty >= 2:
                    break
            else:
                empty = 0
                lines.append(line)

        wg_config = "\n".join(lines)

        if not wg_config.strip():
            print("No config provided!")
            sys.exit(1)

        # Setup WireGuard
        if not self.setup_wireguard(wg_config):
            sys.exit(1)

        # Test connection
        if not self.test_connection():
            sys.exit(1)

        # Get swarm token
        print("\n" + "-" * 60)
        print("Enter the Docker Swarm join token from hub:")
        token = input("Token: ").strip()

        # Join swarm
        if not self.join_swarm(token):
            sys.exit(1)

        print("\n" + "=" * 60)
        print("       WORKER SETUP COMPLETE!")
        print("=" * 60)
        print("\nYou are now part of the Grid-X cluster!")
        print("Your resources are available for jobs.")
        print("\nTo start command agent: python worker.py agent &")
        print("To check status: python worker.py status")
        print("To leave cluster: sudo python worker.py leave")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Grid-X Worker")
    subparsers = parser.add_subparsers(dest="command")

    # setup
    subparsers.add_parser("setup", help="Interactive setup")

    # join (quick join with args)
    join_parser = subparsers.add_parser("join", help="Quick join")
    join_parser.add_argument("--wg-config", required=True, help="WireGuard config file")
    join_parser.add_argument("--token", required=True, help="Swarm join token")
    join_parser.add_argument("--hub-ip", default="10.0.0.1", help="Hub VPN IP")

    # agent
    agent_parser = subparsers.add_parser("agent", help="Start command agent")
    agent_parser.add_argument(
        "--port", type=int, default=7576, help="Port to listen on (default: 7576)"
    )
    agent_parser.add_argument(
        "--bind", default="0.0.0.0", help="IP to bind to (default: 0.0.0.0)"
    )

    # status
    subparsers.add_parser("status", help="Show status")

    # leave
    subparsers.add_parser("leave", help="Leave cluster")

    args = parser.parse_args()

    # Check root for most commands
    if args.command in ["setup", "join", "leave"] and os.geteuid() != 0:
        print("Error: This command requires root (sudo)")
        sys.exit(1)

    if args.command == "agent":
        agent = CommandAgent(port=args.port, bind_ip=args.bind)
        agent.start()
    elif args.command == "setup":
        worker = GridXWorker()
        worker.interactive_setup()
    elif args.command == "join":
        worker = GridXWorker()
        wg_config = Path(args.wg_config).read_text()
        if worker.setup_wireguard(wg_config):
            if worker.test_connection(args.hub_ip):
                worker.join_swarm(args.token, args.hub_ip)
    elif args.command == "status":
        worker = GridXWorker()
        worker.status()
    elif args.command == "leave":
        worker = GridXWorker()
        worker.leave()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
