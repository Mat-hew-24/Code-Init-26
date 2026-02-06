import subprocess
import platform
import json
import shutil
import uuid
import re
import os
from api import register_node
import shellingham # Optional: pip install shellingham to detect shell reliably

def ensure_local_bin_in_path():
    local_bin = os.path.expanduser("~/.local/bin")
    path_statement = f'\n# Grid-X Path\nexport PATH="{local_bin}:$PATH"\n'

    # Identify which config file to edit
    shell_name = os.environ.get("SHELL", "")
    if "zsh" in shell_name:
        config_file = os.path.expanduser("~/.zshrc")
    elif "bash" in shell_name:
        config_file = os.path.expanduser("~/.bashrc")
    else:
        config_file = os.path.expanduser("~/.profile")

    # Check if it's already there to avoid duplicates
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            if local_bin in f.read():
                return

    # Append the path
    with open(config_file, "a") as f:
        f.write(path_statement)

    print(f"✅ Added {local_bin} to {config_file}. Please run 'source {config_file}' or restart your terminal.")

def get_config_path():
    config_dir = os.path.expanduser("~/.gridx")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "token")


def os_type():
    return platform.system()

def run_command(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, timeout=15, stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError as e:
        # This provides better debugging info
        print(f"\n❌ Command Failed: {cmd}")
        print(f"Error Output: {e.output}")
        raise e


def get_cpu_count():
    os_name = os_type()
    if os_name == "Windows":
        return int(run_command("echo %NUMBER_OF_PROCESSORS%"))
    elif os_name == "Darwin":
        return int(run_command("sysctl -n hw.ncpu"))
    elif os_name == "Linux":
        return int(run_command("nproc"))
    raise Exception("Unsupported OS")

def get_memory_gb():
    os_name = os_type()

    if os_name == "Windows":
        out = run_command("wmic ComputerSystem get TotalPhysicalMemory /Value")
        digits = re.findall(r'\d+', out)
        return int(digits[0]) // (1024 ** 3)

    elif os_name == "Darwin":
        out = run_command("sysctl -n hw.memsize")
        return int(out) // (1024 ** 3)

    elif os_name == "Linux":
        out = run_command("grep MemTotal /proc/meminfo")
        kb = int(re.findall(r'\d+', out)[0])
        return kb // (1024 ** 2)

    raise Exception("Unsupported OS")

def get_gpu_count():
    if shutil.which("nvidia-smi") is None:
        return 0
    out = run_command("nvidia-smi -L")
    return len(out.splitlines())


def share_resources(cpu_req: int, memory_req_gb: int, gpu_req: int):
    if not shutil.which("docker"):
        print("Error: Docker is not installed or not in PATH.")
        return

    cpu_total = get_cpu_count()
    mem_total = get_memory_gb()
    gpu_total = get_gpu_count()

    if cpu_req > cpu_total:
        raise Exception("Not enough CPU available")

    if memory_req_gb > mem_total:
        raise Exception("Not enough memory available")

    if gpu_req > gpu_total:
        raise Exception("Not enough GPUs available")

    print("Resource check passed")

    container_name = f"gridx-node-{uuid.uuid4().hex[:8]}"
    port = 2200 + (uuid.uuid4().int % 4000)

    # UPDATED DOCKER COMMAND:
    # 1. Removed --read-only and security-opt for now as they block SSH initialization
    # 2. Added essential Environment Variables (-e)
    docker_cmd = [
        "docker run -d",
        f"--name {container_name}",
        f"--cpus={cpu_req}",
        f"--memory={memory_req_gb}g",
        "-e PUID=1000",
        "-e PGID=1000",
        "-e TZ=Etc/UTC",
        "-e USER_PASSWORD=gridx_pass",  # Required to keep service alive
        "-e PASSWORD_ACCESS=true",      # Allows SSH login via password
        f"-p {port}:22"
    ]

    if gpu_req > 0:
        # Note: Requires nvidia-container-toolkit installed on host
        docker_cmd.append(f"--gpus all")

    docker_cmd.append("linuxserver/openssh-server")

    # Join and execute
    full_command = " ".join(docker_cmd)
    container_id = run_command(full_command)

    payload = {
        "host_id": container_name,
        "container_id": container_id,
        "resources": {
            "cpu": cpu_req,
            "memory_gb": memory_req_gb,
            "gpus": gpu_req
        },
        "access": {
            "type": "ssh",
            "port": port
        },
        "runtime": "docker",
        "status": "available"
    }

    print("\n=== CLUSTER REGISTRATION PAYLOAD ===")
    print(json.dumps(payload, indent=2))


    token_path = get_config_path()
    if not os.path.exists(token_path):
        with open(token_path, "w") as f:
            f.write("dev-token-xyz")
        print(f"Created a temporary token at {token_path}")

    token = open(token_path).read().strip()
    try:
        register_node(payload, token)
        print("Node registered with Grid-X backend")
    except Exception as e:
        print(f"⚠️ Warning: Backend registration skipped: {e}")

    print("Node registered with Grid-X backend")

    return payload

def list_gridx_containers():
    # Improved format string for terminal readability
    cmd = (
        "docker ps -a "
        "--filter 'name=gridx-node-' "
        "--format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'"
    )
    try:
        out = run_command(cmd)
        if not out or len(out.splitlines()) <= 1: # Only header exists
            print("No Grid-X containers found.")
            return
        print(out)
    except Exception as e:
        print(f"Error listing containers: {e}")


def start_container(container_id):
    run_command(f"docker start {container_id}")
    print(f"✅ Started container {container_id}")


def stop_container(container_id):
    run_command(f"docker stop {container_id}")
    print(f"🛑 Stopped container {container_id}")


def stop_all_gridx_containers():
    cmd = (
        "docker ps -a "
        "--filter 'name=gridx-node-' "
        "--format '{{.ID}}'"
    )
    out = run_command(cmd)
    if not out:
        print("No Grid-X containers to stop.")
        return

    for cid in out.splitlines():
        run_command(f"docker stop {cid}")
        print(f"🛑 Stopped {cid}")

