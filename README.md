# Grid-X: Decentralized Resource Mesh

Grid-X is a decentralized mesh network that allows users to securely trade computational resources (CPU/GPU cycles) using Docker containers for sandboxing.

## Features

- **Decentralized Discovery**: Uses Kademlia DHT for peer discovery
- **Secure Execution**: Docker containers with strict security policies
- **Resource Monitoring**: Real-time CPU and RAM monitoring
- **API Interface**: RESTful API for job submission
- **Mesh Communication**: P2P mesh networking for resource sharing

## Prerequisites

1. **Docker Desktop** (for Windows) or Docker Engine (for Linux)
   - Download from: https://www.docker.com/products/docker-desktop/
   - Make sure Docker is running before starting Grid-X

2. **Python 3.9+**
   - Download from: https://python.org

3. **Git** (to clone the repository)

## Quick Start

### Option 1: Automated Setup (Recommended)

**Windows:**

```powershell
python setup.ps1
```

**Linux/Mac:**

```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup

1. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Pull Required Docker Images**

   ```bash
   docker pull python:3.9-slim
   docker pull alpine:latest
   ```

3. **Start a Grid Node**

   ```bash
   python main.py
   ```

4. **Submit a Job (in another terminal)**
   ```bash
   python client.py
   ```

## How It Works

### 1. Node Discovery

- Each node joins a Kademlia DHT mesh network
- Nodes announce their availability and resource status
- Clients can discover available nodes through the mesh

### 2. Job Execution

- Jobs are submitted as Docker images + commands
- Containers run with strict security policies:
  - No network access
  - Read-only filesystem
  - Memory and CPU limits
  - Non-root user execution
  - No new privileges

### 3. Resource Trading

- Nodes advertise when they're IDLE or BUSY
- Clients find IDLE nodes and submit computational tasks
- Results are returned securely through the API

## API Endpoints

### Node API (Port 8000)

- `GET /status` - Check if node is idle/busy
- `POST /job` - Submit a computational job
  ```json
  {
    "image": "python:3.9-slim",
    "command": "python -c 'print(\"Hello Grid-X!\")'"
  }
  ```

## Example Usage

### Running a Python Computation

```python
# Job data
{
    "image": "python:3.9-slim",
    "command": "python -c 'import math; print(f\"Pi is approximately {math.pi}\")'"
}
```

### Running Data Processing

```python
{
    "image": "alpine:latest",
    "command": "sh -c 'echo Processing data...; sleep 2; echo Done!'"
}
```

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Node A    │    │   Node B    │    │   Node C    │
│ (IDLE)      │◄──►│ (BUSY)      │◄──►│ (IDLE)      │
│             │    │             │    │             │
│ Kademlia    │    │ Kademlia    │    │ Kademlia    │
│ DHT Port    │    │ DHT Port    │    │ DHT Port    │
│ 8468        │    │ 8468        │    │ 8468        │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   │                   │
   ┌───▼───┐           ┌───▼───┐           ┌───▼───┐
   │ API   │           │ API   │           │ API   │
   │ :8000 │           │ :8000 │           │ :8000 │
   └───────┘           └───────┘           └───────┘
       ▲                                       ▲
       │                                       │
  ┌────┴─────┐                         ┌──────┴──────┐
  │  Client  │                         │   Client    │
  │ (Submit  │                         │  (Submit    │
  │   Job)   │                         │    Job)     │
  └──────────┘                         └─────────────┘
```

## Security Features

- **Container Isolation**: Each job runs in a separate Docker container
- **No Network Access**: Containers cannot access external networks
- **Resource Limits**: CPU and memory usage is strictly limited
- **Read-Only Filesystem**: Prevents malicious file modifications
- **No Privilege Escalation**: Containers run with minimal permissions

## Troubleshooting

### "Docker not available" Error

- Make sure Docker Desktop is installed and running
- On Windows, ensure Docker Desktop is set to use Windows containers

### "No peers found" Message

- Make sure at least one node is running before starting the client
- Wait 10-15 seconds for nodes to discover each other

### Port Already in Use

- Change the ports in the code if 8000 or 8468 are already taken
- Use Docker Compose to run multiple nodes with different ports

## Development

### Project Structure

```
Grid-X/
├── main.py           # Main node server
├── discovery.py      # Mesh discovery using Kademlia
├── api.py           # REST API endpoints
├── client.py        # Job submission client
├── lockdown.py      # Docker security wrapper
├── watcher.py       # Resource monitoring
├── requirements.txt # Python dependencies
├── Dockerfile       # Container definition
├── docker-compose.yml # Multi-node setup
└── setup.ps1/.sh   # Automated setup scripts
```

### Running Tests

Test the system by running multiple nodes:

1. **Terminal 1**: `python main.py` (Node 1 on default ports)
2. **Terminal 2**: Modify ports in discovery.py and main.py, then start Node 2
3. **Terminal 3**: `python client.py` (Submit jobs)

## License

This project is open source and available under the MIT License.

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.
