# Grid-X: Decentralized Resource Mesh

Share idle CPU/GPU resources across a network of computers using Docker Swarm + WireGuard VPN.

```
                    WIREGUARD VPN MESH (10.0.0.x)
    
    ┌─────────────────┐
    │   HUB (Server)  │  <- WireGuard Server + Docker Swarm Manager
    │   10.0.0.1      │
    └────────┬────────┘
             │
    ┌────────┼────────┬─────────────────┐
    ▼        ▼        ▼                 ▼
┌────────┐ ┌────────┐ ┌────────┐    ┌────────┐
│Worker 1│ │Worker 2│ │Worker 3│ ...│Worker N│
│10.0.0.2│ │10.0.0.3│ │10.0.0.4│    │10.0.0.x│
└────────┘ └────────┘ └────────┘    └────────┘
```

## Quick Start (Local Testing)

Use `test.sh` to quickly spin up a local Docker-based cluster:

```bash
# Start containers (1 hub + 3 workers)
./test.sh start

# Wait for containers to start
sleep 15

# Initialize hub and connect workers
./test.sh setup

# Check cluster status
./test.sh status

# Run a test job
./test.sh test-job

# SSH into a worker
./test.sh ssh worker1

# Create bundle for external machine
./test.sh add-external mylaptop

# Clean up
./test.sh clean
```

### test.sh Commands

| Command | Description |
|---------|-------------|
| `./test.sh start` | Build and start containers |
| `./test.sh setup` | Initialize hub + connect workers |
| `./test.sh status` | Show cluster status |
| `./test.sh ssh <worker>` | SSH into a worker from hub |
| `./test.sh add-external <name>` | Create join bundle for external machine |
| `./test.sh test-job` | Run a test compute job |
| `./test.sh test-gpu` | Run GPU detection job |
| `./test.sh cluster` | Show cluster resources |
| `./test.sh logs <container>` | View container logs |
| `./test.sh clean` | Stop and remove all containers |

## Production Deployment

### 1. Hub Setup (Run once on central server)

```bash
# Install dependencies
sudo pacman -S wireguard-tools docker  # Arch
# or: sudo apt install wireguard docker.io  # Ubuntu

# Initialize hub
sudo python hub.py init --ip YOUR_PUBLIC_IP

# Add workers
sudo python hub.py add-peer worker1
sudo python hub.py add-peer worker2

# SSH into workers (after they join)
sudo python hub.py ssh worker1

# Show SSH public key (for manual setup)
sudo python hub.py ssh-pubkey
```

### 2. Worker Setup (Run on each PC sharing resources)

```bash
# Install dependencies
sudo pacman -S wireguard-tools docker python-psutil  # Arch
# or: sudo apt install wireguard docker.io python3-psutil  # Ubuntu

# Start Docker service
sudo systemctl start docker

# Interactive setup (paste config from hub admin)
sudo python worker.py setup

# Or quick join with files
sudo python worker.py join --wg-config worker1.conf --token "SWMTKN-xxx"
```

### 3. Adding External Workers

Create a join bundle for external machines:

```bash
# From hub
sudo python hub.py add-peer mylaptop

# Or using test.sh (creates a complete bundle)
./test.sh add-external mylaptop
```

This creates a `gridx-mylaptop-bundle/` directory with:
- `join.sh` - Interactive setup script (asks for CPU/RAM/GPU allocation)
- `leave.sh` - Script to leave the cluster
- `status.sh` - Script to check connection status
- WireGuard config and join token

The user runs:
```bash
cd gridx-mylaptop-bundle
sudo ./join.sh
```

The interactive prompt asks:
- How many CPUs to share (e.g., 4)
- How much RAM to share (e.g., 8G)
- How many GPUs to share (e.g., 1)

## Submit Jobs

```bash
# Run from hub or any connected machine

# Simple compute job
python jobs.py run python:3.11 "python -c 'print(2**100)'"

# Job with resource limits
python jobs.py run pytorch/pytorch "python train.py" --cpus 4 --memory 8G

# Job with GPU (specify number of GPUs)
python jobs.py run nvidia/cuda:12.0-base "nvidia-smi" --gpus 1

# Multi-GPU training
python jobs.py run pytorch/pytorch "python train.py" --cpus 8 --memory 16G --gpus 2

# Start Jupyter notebook
python jobs.py jupyter --cpus 2 --memory 4G

# ML training job
python jobs.py train https://example.com/train.py --framework pytorch --gpus 1

# List jobs
python jobs.py list

# View logs
python jobs.py logs <job-id>

# Delete job
python jobs.py delete <job-id>

# Show cluster resources
python jobs.py cluster
```

## Commands Reference

### hub.py (Server)

| Command | Description |
|---------|-------------|
| `init --ip IP` | Initialize hub with public IP |
| `add-peer NAME` | Add new worker to network |
| `remove-peer NAME` | Remove worker |
| `status` | Show VPN and Swarm status |
| `list-peers` | List all registered peers |
| `join-info --name NAME` | Show join info for a peer |
| `ssh NAME` | SSH into a worker |
| `ssh-pubkey` | Show hub's SSH public key |

### worker.py (Client PCs)

| Command | Description |
|---------|-------------|
| `setup` | Interactive setup wizard |
| `join --wg-config FILE --token TOKEN` | Quick join |
| `status` | Show connection status |
| `leave` | Leave the cluster |

### jobs.py (Job Management)

| Command | Description |
|---------|-------------|
| `run IMAGE [CMD]` | Run compute job |
| `jupyter` | Start Jupyter notebook |
| `train SCRIPT` | Run ML training |
| `list` | List all jobs |
| `status JOB_ID` | Show job status |
| `logs JOB_ID` | View job logs |
| `delete JOB_ID` | Delete a job |
| `cluster` | Show cluster resources |

### Job Options

| Option | Description | Example |
|--------|-------------|---------|
| `--cpus` | Number of CPUs | `--cpus 4` |
| `--memory` | Memory limit | `--memory 8G` |
| `--gpus` | Number of GPUs | `--gpus 2` |
| `--name` | Custom job name | `--name my-training` |
| `--env` | Environment vars | `--env KEY=VALUE` |
| `--replicas` | Number of replicas | `--replicas 3` |

## SSH Access

SSH from hub to any worker:

```bash
# Using hub.py
sudo python hub.py ssh worker1

# Using test.sh (in local testing)
./test.sh ssh worker1
```

The hub generates an SSH keypair during `init`. Workers are automatically configured to accept SSH connections from the hub.

## GPU Support

Workers with GPUs can advertise them to the cluster:

```bash
# Check GPU detection
./test.sh test-gpu

# Submit GPU job
python jobs.py run nvidia/cuda:12.0-base "nvidia-smi" --gpus 1

# Multi-GPU job
python jobs.py run pytorch/pytorch:2.0-cuda "python train.py" --gpus 4
```

**Requirements:**
- NVIDIA drivers installed on worker
- NVIDIA Container Toolkit (`nvidia-docker2`)
- Docker configured with nvidia runtime

## Architecture

### How It Works

1. **WireGuard VPN** creates a secure private network (10.0.0.x) connecting all machines
2. **Docker Swarm** pools compute resources from all connected workers
3. **Jobs** are distributed across the cluster based on resource availability
4. **SSH** allows direct access from hub to workers for debugging

### Network Flow

```
[User] -> jobs.py -> [Docker Swarm Manager (Hub)]
                          |
              [Schedules on available worker]
                          |
              [Worker runs container]
```

### Security

- All traffic encrypted via WireGuard
- No ports exposed except WireGuard (51820) on hub
- Containers are isolated (can't access host files)
- Each worker gets unique VPN identity
- SSH access controlled via keypair

## Resource Constraints

Docker Swarm schedules containers on nodes with available resources:

```bash
# Request specific resources
python jobs.py run pytorch/pytorch --cpus 4 --memory 8G --gpus 1 "python train.py"

# The container will be placed on a node with >= 4 CPUs, 8GB RAM, and 1 GPU
```

**Important**: A single container cannot span multiple nodes. If you need 16 CPUs but your biggest node has 8, the job will fail.

## Troubleshooting

### Hub can't reach workers
```bash
# Check WireGuard status
sudo wg show

# Verify peer is connected (should show "latest handshake")
```

### SSH not working
```bash
# Check SSH key on hub
python hub.py ssh-pubkey

# Make sure sshd is running on worker
docker exec -it worker1 service ssh status
```

### Worker can't join swarm
```bash
# Check VPN connection
ping 10.0.0.1

# Check Docker is running
sudo systemctl status docker

# Manual swarm join
docker swarm join --token TOKEN 10.0.0.1:2377
```

### Job won't start
```bash
# Check cluster resources
python jobs.py cluster

# Check job status
python jobs.py status <job-id>

# Check if image can be pulled
docker pull <image>
```

### GPU jobs failing
```bash
# Check GPU is detected
nvidia-smi

# Check nvidia-docker is installed
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# Check Swarm sees the GPU
docker node inspect <node-id> --format '{{.Description.Resources.GenericResources}}'
```

## Port Requirements

| Port | Protocol | Purpose | Where |
|------|----------|---------|-------|
| 51820 | UDP | WireGuard VPN | Hub only (public) |
| 2377 | TCP | Swarm management | VPN only |
| 7946 | TCP/UDP | Swarm node communication | VPN only |
| 4789 | UDP | Overlay network traffic | VPN only |
| 22 | TCP | SSH (internal) | VPN only |

## Files Created

```
/etc/gridx/
├── hub_config.json      # Hub configuration
├── ssh/
│   ├── id_rsa           # Hub SSH private key
│   └── id_rsa.pub       # Hub SSH public key
└── clients/
    ├── worker1.conf     # Worker WireGuard configs
    └── worker2.conf

/etc/wireguard/
└── wg0.conf             # Active WireGuard config

~/.gridx/
├── worker_config.json   # Worker local config
└── jobs.json            # Job tracking
```

## Project Structure

```
gridx-simple/
├── Dockerfile           # Container image (includes openssh-server)
├── docker-compose.yml   # Local testing setup (1 hub + 3 workers)
├── hub.py              # Hub management (VPN, Swarm, SSH)
├── worker.py           # Worker setup and management
├── jobs.py             # Job submission and management
├── test.sh             # Local testing helper script
└── README.md           # This file
```

## Dependencies

```bash
# Python packages (worker only)
pip install psutil

# System packages
# - wireguard-tools
# - docker
# - openssh-server (for workers)
```

## License

MIT - Built for hackathon
