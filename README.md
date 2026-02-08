
# Grid-X - Decentralized Compute Mesh

A distributed resource-sharing system that allows teams to pool laptop/desktop compute resources across users using Docker containers and WireGuard VPN.

## Overview

Grid-X creates a secure mesh network where multiple computers can share their CPU, memory, and GPU resources. It uses:
- **WireGuard VPN** for secure peer-to-peer networking
- **Docker Swarm** for container orchestration
- **FastAPI** for the web management interface

This enables use cases like:
- Running ML training jobs across multiple machines
- Sharing GPU resources for inference
- Distributed computing for data processing
- Jupyter notebook sessions on remote hardware

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Grid-X Hub                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  WireGuard   │  │    Docker    │  │    FastAPI Backend   │   │
│  │   Server     │  │    Swarm     │  │    (Web Interface)   │   │
│  │  (VPN Hub)   │  │   Manager    │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           │ WireGuard VPN      │ Swarm Join         │ REST API
           │ (10.0.0.x/24)      │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Worker Node 1  │  │   Worker Node 2  │  │   Worker Node 3  │
│   (Laptop A)     │  │   (Desktop B)    │  │   (GPU Server)   │
│                  │  │                  │  │                  │
│  - CPU: 8 cores  │  │  - CPU: 16 cores │  │  - CPU: 32 cores │
│  - RAM: 16GB     │  │  - RAM: 32GB     │  │  - RAM: 64GB     │
│  - GPU: None     │  │  - GPU: None     │  │  - GPU: RTX 4090 │
│                  │  │                  │  │                  │
│  Agent :7576     │  │  Agent :7576     │  │  Agent :7576     │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Components

### Core Scripts

| File | Description |
|------|-------------|
| `hub.py` | Hub server that manages WireGuard VPN and Docker Swarm cluster |
| `worker.py` | Worker agent that connects to the hub and accepts remote commands |
| `jobs.py` | Job submission and management (Docker services, Jupyter sessions) |
| `worker_manager.py` | CLI utility to interact with the worker pool |
| `test.sh` | Automated setup script (supports Linux, macOS, WSL2) |

### Web Interface (`website_gridx/`)

| Component | Description |
|-----------|-------------|
| `backend/` | FastAPI REST API that wraps hub/jobs/worker functionality |
| `frontend/host/` | Host dashboard for managing workers and jobs |
| `frontend/client/` | Client interface (Colab-lite style code execution) |
| `frontend/admin/` | Admin monitoring dashboard |
| `frontend/onboard/` | Worker onboarding wizard |
| `middleware/` | Request routing and monitoring proxy |

### Backend Services

| Service | Description |
|---------|-------------|
| `gridx_wrapper.py` | Wraps existing CLI tools for REST API access |
| `code_analyzer.py` | Analyzes Python code for infinite loops and safety issues |
| `job_manager.py` | Manages long-running jobs with monitoring and cancellation |

## Installation

### Prerequisites

- Docker and Docker Compose
- Linux, macOS, or Windows with WSL2
- WireGuard (installed automatically in containers)

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd Code-Init-26

# Start the hub (first terminal)
./test.sh start-hub

# Add a worker (in hub container)
./test.sh add-worker worker-1

# On the worker machine, copy the bundle and run
./test.sh start-worker
```

### Using Docker Compose

```bash
# Start hub with web interface
docker-compose up -d

# Start web interface separately
cd website_gridx
docker-compose up -d
```

## Usage

### Hub Operations

```bash
# Initialize hub with public IP
python hub.py init --ip <PUBLIC_IP>

# Add a peer/worker
python hub.py add-peer laptop-john --cpus 8 --memory 16G

# List all peers
python hub.py list-peers

# Get worker config for onboarding
python hub.py get-config laptop-john
```

### Worker Operations

```bash
# Join the cluster (using config from hub)
python worker.py join --config worker_config.json

# Start command agent
python worker.py agent --port 7576

# Check status
python worker.py status
```

### Job Submission

```bash
# Run a compute job
python jobs.py run python:3.11 "python -c 'print(sum(range(1000000)))'"

# Run with resource limits
python jobs.py run pytorch/pytorch:latest "python train.py" \
    --cpus 4 --memory 8G --gpus 1

# Start a Jupyter session
python jobs.py jupyter --name ml-session --cpus 4 --memory 16G

# Check job status
python jobs.py status <job-id>

# View logs
python jobs.py logs <job-id>
```

### Worker Manager CLI

```bash
python worker_manager.py

# Interactive menu:
# 1. Show pool status
# 2. Show pool health
# 3. Get best worker
# 4. Execute command (auto-select worker)
# 5. Execute on specific worker
# 6. Execute on all workers
# 7. Demo automatic execution
```

## REST API

The web backend exposes these endpoints:

### Workers
- `GET /api/workers` - List all workers
- `GET /api/workers/ping` - Ping all workers
- `GET /api/workers/{name}` - Get worker details
- `GET /api/workers/{name}/status` - Get detailed status
- `POST /api/workers/{name}/exec` - Execute command on worker
- `GET /api/workers/pool/status` - Full pool status
- `GET /api/workers/pool/health` - Pool health check

### Execution
- `POST /api/exec` - Execute command (auto or specific worker)
- `POST /api/exec/analyze` - Analyze code for safety issues
- `POST /api/exec/safe-execute` - Execute with safety analysis
- `GET /api/exec/jobs` - List execution jobs
- `GET /api/exec/jobs/{id}` - Get job details

### Jobs
- `GET /api/jobs` - List all jobs
- `POST /api/jobs` - Create a new job
- `GET /api/jobs/{id}` - Get job details
- `GET /api/jobs/{id}/logs` - Get job logs
- `DELETE /api/jobs/{id}` - Delete a job

### Onboarding
- `POST /api/onboarding/create-worker` - Create worker bundle
- `GET /api/onboarding/download/{name}` - Download worker bundle
- `GET /api/onboarding/status/{name}` - Check worker connection status

### Monitoring
- `GET /api/status` - Hub status
- `GET /api/health` - Health check
- `GET /api/middleware/stats` - Request statistics
- `GET /api/middleware/logs` - Request logs

## Web Interfaces

Access via browser after starting the web stack:

| Interface | URL | Purpose |
|-----------|-----|---------|
| Host Dashboard | `http://localhost:8000/host` | Manage workers, view pool status, submit jobs |
| Client (Colab-lite) | `http://localhost:8000/client` | Execute code on remote workers |
| Admin Panel | `http://localhost:8000/admin` | Monitor requests, view logs |
| Onboarding | `http://localhost:8000/onboard` | Add new workers via wizard |

## Security

- All inter-node communication uses WireGuard VPN (encrypted)
- Worker agents only accept commands from within the VPN (10.0.0.x network)
- Code analysis prevents obvious infinite loops and dangerous patterns
- Job manager allows cancellation of runaway processes

## Configuration

### Hub Config (`/etc/gridx/hub_config.json`)

```json
{
  "hub_ip": "10.0.0.1",
  "wg_port": 51820,
  "public_ip": "192.168.1.100",
  "server_public_key": "...",
  "swarm_token": "...",
  "peers": {
    "worker-1": {
      "ip": "10.0.0.2",
      "public_key": "...",
      "cpus": 8,
      "memory": "16G",
      "gpus": 0
    }
  }
}
```

### Worker Config (`~/.gridx/worker_config.json`)

```json
{
  "hub_ip": "10.0.0.1",
  "my_ip": "10.0.0.2",
  "status": "connected"
}
```

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Full support | Native WireGuard kernel module |
| macOS | Full support | Via Docker Desktop |
| Windows (WSL2) | Full support | Requires WSL2 + Docker Desktop |
| Windows (native) | Not supported | Use WSL2 instead |

## Project Structure

```
.
├── hub.py                 # Hub server (VPN + Swarm management)
├── worker.py              # Worker agent (joins cluster, executes commands)
├── jobs.py                # Job submission (Docker services)
├── worker_manager.py      # CLI for worker pool management
├── test.sh                # Automated setup script
├── Dockerfile             # Hub/Worker container image
├── docker-compose.yml     # Hub deployment
└── website_gridx/
    ├── docker-compose.yml # Web stack deployment
    ├── backend/
    │   ├── main.py        # FastAPI app
    │   ├── routers/       # API route handlers
    │   │   ├── workers.py
    │   │   ├── jobs.py
    │   │   ├── exec.py
    │   │   ├── onboarding.py
    │   │   └── middleware.py
    │   └── services/      # Business logic
    │       ├── gridx_wrapper.py
    │       ├── code_analyzer.py
    │       └── job_manager.py
    ├── frontend/
    │   ├── host/          # Host dashboard
    │   ├── client/        # Colab-lite interface
    │   ├── admin/         # Admin panel
    │   └── onboard/       # Onboarding wizard
    └── middleware/        # Request proxy/monitoring
```

## Troubleshooting

### WireGuard Connection Issues
```bash
# Check WireGuard status
wg show wg0

# Restart WireGuard
wg-quick down wg0 && wg-quick up wg0
```

### Docker Swarm Issues
```bash
# Check swarm status
docker info | grep -i swarm

# Re-join swarm
docker swarm leave --force
docker swarm join --token <TOKEN> <HUB_IP>:2377
```

### Worker Agent Issues
```bash
# Check if agent is running
curl http://<WORKER_IP>:7576/ping

# View agent logs
docker logs gridx-worker

# Restart agent
python worker.py agent
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on multiple platforms (Linux, macOS, WSL2)
5. Submit a pull request

## License

MIT License
