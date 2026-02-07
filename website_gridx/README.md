# Grid-X Web Interface

A minimal web interface for the Grid-X decentralized compute mesh. Provides three frontends:

- **Host Dashboard** - Manage workers, jobs, and view cluster status
- **Client Interface** - Colab-lite Python code runner
- **Admin View** - Middleware monitoring and request logging

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        website_gridx/                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /host             /client             /admin                    │
│  (Dashboard)       (Colab-Lite)        (Monitor)                │
│       │                │                   │                     │
│       └────────────────┴───────────────────┘                     │
│                        │                                         │
│                 ┌──────▼──────┐                                 │
│                 │   Backend   │  FastAPI on :8000               │
│                 └──────┬──────┘                                 │
│                        │                                         │
│                 ┌──────▼──────┐                                 │
│                 │ Middleware  │  HTTP on :7575 (optional)       │
│                 └──────┬──────┘                                 │
│                        │                                         │
│              ┌─────────┴─────────┐                              │
│              ▼                   ▼                              │
│         Worker A            Worker B                            │
│         (7576)              (7576)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Run Directly (Development)

```bash
# Install dependencies
cd website_gridx/backend
pip install -r requirements.txt

# Start the backend (from website_gridx/backend)
python main.py

# In another terminal, start the middleware (optional)
cd website_gridx/middleware
python middleware.py
```

Then open:
- http://localhost:8000/host - Host Dashboard
- http://localhost:8000/client - Client Interface
- http://localhost:8000/admin - Admin View
- http://localhost:8000/docs - API Documentation

### Option 2: Run with Docker Compose

```bash
cd website_gridx
docker-compose up -d
```

Then open:
- http://localhost:8000/host - Host Dashboard
- http://localhost:8000/client - Client Interface  
- http://localhost:8000/admin - Admin View

### Option 3: Run Inside Hub Container

If you're running inside the Grid-X hub container:

```bash
# Inside the hub container
cd /path/to/website_gridx/backend
pip install -r requirements.txt
python main.py &

# Start middleware
cd /path/to/website_gridx/middleware
python middleware.py &
```

## File Structure

```
website_gridx/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── routers/
│   │   ├── workers.py       # Worker endpoints
│   │   ├── jobs.py          # Job endpoints
│   │   └── exec.py          # Execution endpoints
│   ├── services/
│   │   └── gridx_wrapper.py # Wraps hub.py, jobs.py
│   ├── requirements.txt
│   └── Dockerfile
├── middleware/
│   ├── middleware.py        # Request routing/logging
│   └── Dockerfile
├── frontend/
│   ├── host/
│   │   └── index.html       # Host Dashboard
│   ├── client/
│   │   └── index.html       # Colab-Lite Interface
│   └── admin/
│       └── index.html       # Admin Monitor
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Workers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workers` | List all workers |
| GET | `/api/workers/ping` | Ping all workers |
| GET | `/api/workers/{name}` | Get worker details |
| GET | `/api/workers/{name}/ping` | Ping specific worker |
| GET | `/api/workers/{name}/status` | Get worker system status |
| POST | `/api/workers/{name}/exec` | Execute command on worker |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List all jobs |
| POST | `/api/jobs` | Create new job |
| GET | `/api/jobs/{id}` | Get job details |
| GET | `/api/jobs/{id}/status` | Get job status |
| GET | `/api/jobs/{id}/logs` | Get job logs |
| DELETE | `/api/jobs/{id}` | Delete job |

### Exec

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/exec` | Execute command on worker |
| POST | `/api/exec/batch` | Execute on multiple workers |

### Hub Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Get hub status |
| GET | `/api/services` | List running services |
| GET | `/api/health` | Health check |

### Middleware (when running)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/middleware/health` | Middleware health |
| GET | `/middleware/logs` | Request logs |
| GET | `/middleware/stats` | Request statistics |
| GET | `/middleware/config` | Hub configuration |
| POST | `/middleware/exec/{worker}` | Direct worker exec |

## Frontends

### Host Dashboard (`/host`)

- View all registered workers with online/offline status
- View and manage running jobs
- Create new jobs
- Execute commands on workers
- View job logs
- See hub status (VPN, Swarm)

### Client Interface (`/client`)

Colab-lite code runner:
- Select a worker from available list
- Write Python code in the editor
- Run code on remote workers
- Quick command buttons (hostname, nvidia-smi, etc.)
- Code templates (Hello World, NumPy, PyTorch, Training)
- View output with execution time

Keyboard shortcuts:
- `Ctrl+Enter` - Run Python code
- `Shift+Enter` - Run shell command

### Admin View (`/admin`)

Middleware monitoring:
- Request statistics (total, success, failed)
- Live request logs
- Requests by endpoint
- Requests by worker
- Activity chart
- Hub configuration view
- Recent executions table

## Requirements

- Python 3.11+
- FastAPI, Uvicorn
- Grid-X hub must be set up (`/etc/gridx/hub_config.json`)
- Docker socket access for job management

## Notes

- No authentication (as requested)
- All frontends served from the backend
- Middleware is optional but enables request logging
- CORS enabled for all origins
- Auto-refresh every 30 seconds on dashboards
