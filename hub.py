#!/usr/bin/env python3
"""
Grid-X Hub - Main server that manages WireGuard VPN + Docker Swarm

Run this on your main PC/server.
"""

import subprocess
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


class GridXHub:
    """Main hub that manages VPN and Swarm cluster"""

    def __init__(self):
        self.config_dir = Path("/etc/gridx")
        self.wg_dir = Path("/etc/wireguard")
        self.config_file = self.config_dir / "hub_config.json"

        # Default config
        self.config = {
            "hub_ip": "10.0.0.1",
            "wg_port": 51820,
            "public_ip": None,
            "server_private_key": None,
            "server_public_key": None,
            "swarm_token": None,
            "peers": {},  # {name: {ip, public_key, private_key, cpus, memory, gpus}}
        }

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
        """Run shell command"""
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"  Error: {result.stderr}")
        return result

    def _generate_wg_keypair(self):
        """Generate WireGuard keypair"""
        private = subprocess.run(["wg", "genkey"], capture_output=True, text=True)
        private_key = private.stdout.strip()

        public = subprocess.run(
            ["wg", "pubkey"], input=private_key, capture_output=True, text=True
        )
        public_key = public.stdout.strip()

        return private_key, public_key

    def _get_next_ip(self):
        """Get next available VPN IP"""
        used = {self.config["hub_ip"]}
        for peer in self.config["peers"].values():
            used.add(peer["ip"])

        for i in range(2, 255):
            ip = f"10.0.0.{i}"
            if ip not in used:
                return ip
        raise Exception("No IPs available")

    # ==================== INIT ====================

    def init(self, public_ip):
        """Initialize hub with WireGuard + Docker Swarm"""
        print("\n" + "=" * 60)
        print("       GRID-X HUB INITIALIZATION")
        print("=" * 60)

        self.config["public_ip"] = public_ip

        # 1. Setup WireGuard
        print("\n[1/3] Setting up WireGuard VPN...")
        self._setup_wireguard()

        # 2. Setup Docker Swarm
        print("\n[2/3] Initializing Docker Swarm...")
        self._setup_swarm()

        # 3. Save config
        print("\n[3/3] Saving configuration...")
        self._save_config()

        print("\n" + "=" * 60)
        print("       HUB INITIALIZED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\n  Hub VPN IP: {self.config['hub_ip']}")
        print(f"  Public IP: {public_ip}")
        print(f"  WireGuard Port: {self.config['wg_port']}")
        print(f"\n  To add a worker, run:")
        print(f"    python hub.py add-peer <name>")
        print()

    def _setup_wireguard(self):
        """Setup WireGuard server"""
        self.wg_dir.mkdir(parents=True, exist_ok=True)

        # Generate keys if not exist
        if not self.config["server_private_key"]:
            print("  Generating server keys...")
            priv, pub = self._generate_wg_keypair()
            self.config["server_private_key"] = priv
            self.config["server_public_key"] = pub

        # Create WireGuard config
        wg_conf = f"""[Interface]
Address = {self.config["hub_ip"]}/24
ListenPort = {self.config["wg_port"]}
PrivateKey = {self.config["server_private_key"]}
PostUp = sysctl -w net.ipv4.ip_forward=1
"""

        # Add existing peers
        for name, peer in self.config["peers"].items():
            wg_conf += f"""
[Peer]
# {name}
PublicKey = {peer["public_key"]}
AllowedIPs = {peer["ip"]}/32
PersistentKeepalive = 25
"""

        # Write config
        wg_conf_path = self.wg_dir / "wg0.conf"
        wg_conf_path.write_text(wg_conf)
        wg_conf_path.chmod(0o600)
        print(f"  Config written to {wg_conf_path}")

        # Start WireGuard
        self._run(["wg-quick", "down", "wg0"], check=False)
        self._run(["wg-quick", "up", "wg0"])
        # Try to enable on boot (may fail in containers without systemd)
        if os.path.exists("/run/systemd/system"):
            self._run(["systemctl", "enable", "wg-quick@wg0"], check=False)
        print("  WireGuard started!")

    def _setup_swarm(self):
        """Setup Docker Swarm"""
        # Leave existing swarm
        self._run(["docker", "swarm", "leave", "--force"], check=False)

        # Initialize swarm on VPN IP
        result = self._run(
            ["docker", "swarm", "init", "--advertise-addr", self.config["hub_ip"]]
        )

        if result.returncode == 0:
            # Get join token
            token_result = self._run(["docker", "swarm", "join-token", "-q", "worker"])
            self.config["swarm_token"] = token_result.stdout.strip()
            print(f"  Swarm initialized!")
            print(f"  Join token: {self.config['swarm_token'][:20]}...")
        else:
            print(f"  Error initializing swarm: {result.stderr}")

    # ==================== ADD PEER ====================

    def add_peer(self, name, cpus=None, memory=None, gpus=0):
        """Add a new peer/worker to the VPN"""
        print(f"\n[+] Adding peer: {name}")

        if name in self.config["peers"]:
            print(f"  Error: Peer '{name}' already exists!")
            return

        # Generate keys for peer
        priv, pub = self._generate_wg_keypair()
        ip = self._get_next_ip()

        # Save peer info
        self.config["peers"][name] = {
            "ip": ip,
            "public_key": pub,
            "private_key": priv,
            "cpus": cpus,
            "memory": memory,
            "gpus": gpus,
        }
        self._save_config()

        # Regenerate WireGuard config with new peer
        self._setup_wireguard()

        # Generate client config
        client_conf = f"""[Interface]
PrivateKey = {priv}
Address = {ip}/24

[Peer]
PublicKey = {self.config["server_public_key"]}
AllowedIPs = 10.0.0.0/24
Endpoint = {self.config["public_ip"]}:{self.config["wg_port"]}
PersistentKeepalive = 25
"""

        # Save client config
        client_dir = self.config_dir / "clients"
        client_dir.mkdir(parents=True, exist_ok=True)
        client_file = client_dir / f"{name}.conf"
        client_file.write_text(client_conf)

        print(f"\n  Peer added successfully!")
        print(f"  VPN IP: {ip}")
        print(f"  Config file: {client_file}")

        print(f"\n" + "=" * 60)
        print(f"  SEND THIS TO THE WORKER ({name}):")
        print("=" * 60)
        print(f"\n--- {name}.conf ---")
        print(client_conf)
        print("--- end ---")
        print(f"\n  Swarm Join Command:")
        print(
            f"  docker swarm join --token {self.config['swarm_token']} {self.config['hub_ip']}:2377"
        )
        print()

    # ==================== REMOVE PEER ====================

    def remove_peer(self, name):
        """Remove a peer from VPN"""
        if name not in self.config["peers"]:
            print(f"  Error: Peer '{name}' not found!")
            return

        del self.config["peers"][name]
        self._save_config()

        # Regenerate WireGuard config
        self._setup_wireguard()

        # Remove client config
        client_file = self.config_dir / "clients" / f"{name}.conf"
        if client_file.exists():
            client_file.unlink()

        print(f"  Peer '{name}' removed!")

    # ==================== EXEC ON WORKER ====================

    def exec_on_worker(self, name, command, timeout=30):
        """Execute a command on a worker via the HTTP agent"""
        if name not in self.config["peers"]:
            print(f"  Error: Peer '{name}' not found!")
            print(f"  Available peers: {', '.join(self.config['peers'].keys())}")
            return None

        peer = self.config["peers"][name]
        ip = peer["ip"]
        url = f"http://{ip}:7576/exec"
        data = json.dumps({"cmd": command}).encode()

        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            print(f"  Running on {name} ({ip}): {command}")
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

    def exec_command(self, name, command):
        """Execute command on worker and print results"""
        result = self.exec_on_worker(name, command)

        if result:
            print("-" * 50)
            if result.get("output"):
                print(result["output"], end="")
            if result.get("error"):
                print(f"STDERR: {result['error']}", end="")
            print("-" * 50)
            print(f"  Exit code: {result.get('exit_code', 'N/A')}")
            return result.get("exit_code", 1) == 0
        return False

    # ==================== PING WORKERS ====================

    def ping_worker(self, name, timeout=5):
        """Ping a single worker's agent"""
        if name not in self.config["peers"]:
            return False, "Not found"

        ip = self.config["peers"][name]["ip"]
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

        if not self.config["peers"]:
            print("\n  No workers registered. Add workers with:")
            print("    python hub.py add-peer <name>")
            return

        print(f"\n{'WORKER':<15} {'VPN IP':<15} {'AGENT STATUS':<15}")
        print("-" * 45)

        online = 0
        for name, peer in self.config["peers"].items():
            ip = peer.get("ip", "?")
            ok, _ = self.ping_worker(name)
            if ok:
                status = "\033[32mONLINE\033[0m"  # Green
                online += 1
            else:
                status = "\033[31mOFFLINE\033[0m"  # Red
            print(f"{name:<15} {ip:<15} {status}")

        print("-" * 45)
        print(f"  {online}/{len(self.config['peers'])} workers online\n")

    # ==================== STATUS ====================

    def status(self):
        """Show hub status"""
        print("\n" + "=" * 60)
        print("       GRID-X HUB STATUS")
        print("=" * 60)

        # WireGuard status
        print("\n[WireGuard VPN]")
        wg_result = self._run(["wg", "show"], check=False)
        if wg_result.returncode == 0 and wg_result.stdout.strip():
            print("  Status: RUNNING")
            # Count connected peers
            lines = wg_result.stdout.split("\n")
            handshakes = [l for l in lines if "latest handshake" in l]
            print(f"  Connected peers: {len(handshakes)}")
        else:
            print("  Status: STOPPED")

        print(f"  Hub IP: {self.config['hub_ip']}")
        print(f"  Registered peers: {len(self.config['peers'])}")

        for name, peer in self.config["peers"].items():
            resources = []
            if peer.get("cpus"):
                resources.append(f"{peer['cpus']} CPU")
            if peer.get("memory"):
                resources.append(f"{peer['memory']}GB RAM")
            if peer.get("gpus"):
                resources.append(f"{peer['gpus']} GPU")
            res_str = f" ({', '.join(resources)})" if resources else ""

            # Check agent status
            ok, _ = self.ping_worker(name)
            agent_status = (
                "\033[32m[agent OK]\033[0m" if ok else "\033[31m[agent OFF]\033[0m"
            )
            print(f"    - {name}: {peer['ip']}{res_str} {agent_status}")

        # Docker Swarm status
        print("\n[Docker Swarm]")
        swarm_result = self._run(
            [
                "docker",
                "node",
                "ls",
                "--format",
                "{{.Hostname}}\t{{.Status}}\t{{.Availability}}",
            ],
            check=False,
        )

        if swarm_result.returncode == 0:
            print("  Status: ACTIVE")
            nodes = [l for l in swarm_result.stdout.strip().split("\n") if l]
            print(f"  Nodes: {len(nodes)}")
            for node in nodes:
                print(f"    - {node}")
        else:
            print("  Status: NOT INITIALIZED")

        # Cluster resources
        print("\n[Cluster Resources]")
        info_result = self._run(
            ["docker", "info", "--format", "{{json .}}"], check=False
        )
        if info_result.returncode == 0:
            try:
                info = json.loads(info_result.stdout)
                print(f"  CPUs: {info.get('NCPU', 'N/A')}")
                mem_gb = round(info.get("MemTotal", 0) / (1024**3), 1)
                print(f"  Memory: {mem_gb} GB")
            except:
                pass

        print()

    # ==================== LIST PEERS ====================

    def list_peers(self):
        """List all registered peers"""
        print("\n[Registered Peers]")
        if not self.config["peers"]:
            print("  No peers registered")
            return

        print(f"  {'NAME':<15} {'VPN IP':<15} {'CPUS':<8} {'RAM':<10} {'GPUS':<6}")
        print("  " + "-" * 54)
        for name, peer in self.config["peers"].items():
            cpus = peer.get("cpus", "-")
            memory = f"{peer.get('memory', '-')}GB" if peer.get("memory") else "-"
            gpus = peer.get("gpus", 0) or "-"
            print(
                f"  {name:<15} {peer['ip']:<15} {str(cpus):<8} {memory:<10} {str(gpus):<6}"
            )

    # ==================== GET JOIN INFO ====================

    def join_info(self, name=None):
        """Get join information for a peer"""
        if name and name in self.config["peers"]:
            peer = self.config["peers"][name]
            client_file = self.config_dir / "clients" / f"{name}.conf"

            print(f"\n[Join Info for {name}]")
            print(f"  VPN IP: {peer['ip']}")
            print(f"  Config file: {client_file}")
            print(f"\n  WireGuard Config:")
            if client_file.exists():
                print(client_file.read_text())

        print(f"\n  Swarm Join Command:")
        print(
            f"  docker swarm join --token {self.config['swarm_token']} {self.config['hub_ip']}:2377"
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Grid-X Hub - WireGuard + Docker Swarm Manager"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize hub")
    init_parser.add_argument("--ip", required=True, help="Your public IP address")

    # add-peer
    add_parser = subparsers.add_parser("add-peer", help="Add a new peer/worker")
    add_parser.add_argument("name", help="Peer name")
    add_parser.add_argument("--cpus", type=int, help="Number of CPUs worker will share")
    add_parser.add_argument("--memory", type=int, help="RAM in GB worker will share")
    add_parser.add_argument("--gpus", type=int, default=0, help="Number of GPUs")

    # remove-peer
    remove_parser = subparsers.add_parser("remove-peer", help="Remove a peer")
    remove_parser.add_argument("name", help="Peer name")

    # exec
    exec_parser = subparsers.add_parser("exec", help="Execute command on a worker")
    exec_parser.add_argument("name", help="Worker name")
    exec_parser.add_argument("cmd", help="Command to execute")

    # ping-workers
    subparsers.add_parser("ping-workers", help="Check which workers are online")

    # status
    subparsers.add_parser("status", help="Show hub status")

    # list-peers
    subparsers.add_parser("list-peers", help="List all peers")

    # join-info
    join_parser = subparsers.add_parser("join-info", help="Get join info for peer")
    join_parser.add_argument("--name", help="Peer name (optional)")

    args = parser.parse_args()

    if os.geteuid() != 0:
        print("Error: This script must be run as root (sudo)")
        sys.exit(1)

    hub = GridXHub()

    if args.command == "init":
        hub.init(args.ip)
    elif args.command == "add-peer":
        hub.add_peer(args.name, cpus=args.cpus, memory=args.memory, gpus=args.gpus)
    elif args.command == "remove-peer":
        hub.remove_peer(args.name)
    elif args.command == "exec":
        hub.exec_command(args.name, args.cmd)
    elif args.command == "ping-workers":
        hub.ping_workers()
    elif args.command == "status":
        hub.status()
    elif args.command == "list-peers":
        hub.list_peers()
    elif args.command == "join-info":
        hub.join_info(args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
