# Worker Management Fix - Grid-X Hub

## The Problem

Your Grid-X system was showing all workers but only allowing you to use the first one because **there was no automatic worker selection mechanism**. The API required explicit worker specification for every command.

## The Solution

I've implemented an **intelligent worker management system** with the following features:

### 🚀 New Features Added

#### 1. **Automatic Worker Selection**

- The system now automatically selects the best available worker based on:
  - CPU usage (lower is better)
  - Memory usage (lower is better)
  - GPU availability (more GPUs preferred)
  - Online status

#### 2. **New API Endpoints**

| Endpoint                       | Description                              |
| ------------------------------ | ---------------------------------------- |
| `POST /api/exec/auto`          | Execute command on best available worker |
| `GET /api/exec/workers/best`   | Get recommended worker                   |
| `GET /api/exec/workers/online` | List all online workers                  |
| `GET /api/workers/pool/status` | Detailed worker pool status              |
| `GET /api/workers/pool/health` | Overall pool health metrics              |

#### 3. **Enhanced Exec Endpoint**

- `POST /api/exec` now supports optional worker field
- If no worker specified, automatically selects the best one

## 🛠️ How to Use

### Option 1: Automatic Execution (Recommended)

**Simple API Call:**

```bash
curl -X POST "http://localhost:8000/api/exec/auto?command=hostname&timeout=30"
```

**JSON API Call:**

```bash
curl -X POST "http://localhost:8000/api/exec" \
  -H "Content-Type: application/json" \
  -d '{"command": "python --version"}'
```

### Option 2: Use the Worker Manager Script

Run the interactive worker manager:

```bash
python worker_manager.py
```

This provides a menu-driven interface to:

- View worker pool status
- Execute commands automatically
- Monitor worker health
- Test different workers

### Option 3: Check Worker Pool Status

**Get pool overview:**

```bash
curl "http://localhost:8000/api/workers/pool/status"
```

**Check pool health:**

```bash
curl "http://localhost:8000/api/workers/pool/health"
```

## 📊 Example Responses

### Pool Status Response:

```json
{
  "total_workers": 3,
  "online_workers": 2,
  "offline_workers": 1,
  "recommended_worker": "worker-gpu-01",
  "workers": {
    "worker-gpu-01": {
      "name": "worker-gpu-01",
      "ip": "10.0.0.2",
      "online": true,
      "status": "active",
      "cpu_percent": 15.2,
      "memory_percent": 34.1,
      "gpus": 1
    }
  }
}
```

### Auto Execution Response:

```json
{
  "success": true,
  "worker": "worker-gpu-01",
  "auto_selected": true,
  "stdout": "Python 3.9.7",
  "stderr": "",
  "exit_code": 0
}
```

## 🔧 Implementation Details

### Files Modified:

1. **`services/gridx_wrapper.py`**
   - Added `get_best_worker()` - intelligent worker selection
   - Added `get_online_workers()` - list online workers
   - Added `exec_on_best_worker()` - auto-execute commands

2. **`routers/exec.py`**
   - Made `worker` field optional in requests
   - Added auto-selection logic
   - Added new endpoints for worker management

3. **`routers/workers.py`**
   - Added pool status and health endpoints
   - Enhanced worker monitoring

### Worker Selection Algorithm:

```python
# Workers are ranked by:
1. Online status (must be reachable)
2. Combined CPU + Memory usage (lower = better)
3. GPU count (more = better for GPU tasks)
4. Availability and response time
```

## 🚨 Troubleshooting

### If No Workers Are Available:

1. **Check worker connectivity:**

   ```bash
   curl "http://localhost:8000/api/workers/ping"
   ```

2. **Check individual workers:**

   ```bash
   curl "http://localhost:8000/api/workers/{worker_name}/ping"
   ```

3. **Restart workers:**
   ```bash
   # On each worker machine
   sudo systemctl restart gridx-worker
   # OR
   python worker.py --restart
   ```

### If Only First Worker Responds:

1. **Check VPN connectivity:**

   ```bash
   sudo wg show
   ping 10.0.0.2  # worker IP
   ```

2. **Check worker agent ports:**

   ```bash
   nmap -p 7576 10.0.0.2  # should show open
   ```

3. **Check Docker swarm:**
   ```bash
   docker node ls
   ```

## 📈 Monitoring

Use the worker manager to continuously monitor your pool:

```bash
python worker_manager.py
# Select option 1 for pool status
# Select option 7 for demo execution
```

## 🎯 Next Steps

1. **Start your Grid-X backend:**

   ```bash
   cd website_gridx/backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Test automatic execution:**

   ```bash
   curl -X POST "http://localhost:8000/api/exec/auto?command=hostname"
   ```

3. **Monitor your workers:**
   ```bash
   python worker_manager.py
   ```

Your workers should now be **automatically selected and load-balanced** instead of only using the first one!
