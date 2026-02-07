"""
Grid-X Middleware - Request routing and validation layer

This middleware runs inside the hub container on port 7575 and handles:
- Request validation and logging
- Traffic routing between clients and workers
- Request monitoring for the admin view
"""

import json
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Lock
from collections import deque
from typing import Dict, Any, Optional


class RequestLog:
    """Thread-safe request log for monitoring"""

    def __init__(self, max_size: int = 1000):
        self.requests = deque(maxlen=max_size)
        self.lock = Lock()
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "by_endpoint": {},
            "by_worker": {},
        }

    def add(self, request: Dict[str, Any]):
        """Add a request to the log"""
        with self.lock:
            self.requests.append(request)
            self.stats["total"] += 1

            if request.get("success"):
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1

            # Track by endpoint
            endpoint = request.get("endpoint", "unknown")
            self.stats["by_endpoint"][endpoint] = (
                self.stats["by_endpoint"].get(endpoint, 0) + 1
            )

            # Track by worker
            worker = request.get("worker")
            if worker:
                self.stats["by_worker"][worker] = (
                    self.stats["by_worker"].get(worker, 0) + 1
                )

    def get_recent(self, count: int = 50) -> list:
        """Get recent requests"""
        with self.lock:
            return list(self.requests)[-count:]

    def get_stats(self) -> Dict[str, Any]:
        """Get request statistics"""
        with self.lock:
            return dict(self.stats)


class GridXMiddleware:
    """Middleware server for Grid-X request routing"""

    def __init__(self, port: int = 7575, backend_url: str = "http://localhost:8000"):
        self.port = port
        self.backend_url = backend_url
        self.request_log = RequestLog()
        self.config_file = Path("/etc/gridx/hub_config.json")

    def _load_config(self) -> Dict[str, Any]:
        """Load hub configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _get_worker_ip(self, name: str) -> Optional[str]:
        """Get worker IP from config"""
        config = self._load_config()
        peers = config.get("peers", {})
        if name in peers:
            return peers[name].get("ip")
        return None

    def _forward_to_worker(
        self,
        worker: str,
        endpoint: str,
        data: Optional[bytes] = None,
        method: str = "GET",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Forward a request to a worker's command agent"""
        ip = self._get_worker_ip(worker)
        if not ip:
            return {"error": f"Worker '{worker}' not found", "success": False}

        url = f"http://{ip}:7576{endpoint}"

        try:
            req = urllib.request.Request(url, data=data, method=method)
            if data:
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
                result["success"] = True
                return result
        except urllib.error.URLError as e:
            return {"error": str(e.reason), "success": False}
        except TimeoutError:
            return {"error": "Request timed out", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def _forward_to_backend(
        self,
        path: str,
        data: Optional[bytes] = None,
        method: str = "GET",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Forward a request to the FastAPI backend"""
        url = f"{self.backend_url}{path}"

        try:
            req = urllib.request.Request(url, data=data, method=method)
            if data:
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e), "success": False}

    def start(self):
        """Start the middleware server"""
        middleware = self

        class MiddlewareHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                print(f"  [{self.client_address[0]}] {args[0]}")

            def send_json(self, data: Dict, status: int = 200):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
                )
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_OPTIONS(self):
                """Handle CORS preflight"""
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
                )
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self):
                start_time = time.time()
                path = self.path

                # Middleware-specific endpoints
                if path == "/middleware/health":
                    self.send_json({"status": "ok", "service": "gridx-middleware"})
                    return

                if path == "/middleware/logs":
                    logs = middleware.request_log.get_recent(100)
                    self.send_json({"logs": logs})
                    return

                if path == "/middleware/stats":
                    stats = middleware.request_log.get_stats()
                    self.send_json(stats)
                    return

                if path == "/middleware/config":
                    config = middleware._load_config()
                    # Remove private keys for security
                    safe_config = {
                        "hub_ip": config.get("hub_ip"),
                        "public_ip": config.get("public_ip"),
                        "wg_port": config.get("wg_port"),
                        "peers": {
                            name: {
                                "ip": peer.get("ip"),
                                "cpus": peer.get("cpus"),
                                "memory": peer.get("memory"),
                                "gpus": peer.get("gpus"),
                            }
                            for name, peer in config.get("peers", {}).items()
                        },
                    }
                    self.send_json(safe_config)
                    return

                # Forward to backend
                result = middleware._forward_to_backend(path)

                # Log the request
                middleware.request_log.add(
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "method": "GET",
                        "endpoint": path,
                        "duration_ms": round((time.time() - start_time) * 1000, 2),
                        "success": "error" not in result,
                        "client": self.client_address[0],
                    }
                )

                self.send_json(result)

            def do_POST(self):
                start_time = time.time()
                path = self.path

                # Read body
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length > 0 else None

                # Direct worker exec via middleware
                if path.startswith("/middleware/exec/"):
                    worker = path.split("/")[-1]
                    result = middleware._forward_to_worker(
                        worker, "/exec", body, "POST"
                    )

                    middleware.request_log.add(
                        {
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "method": "POST",
                            "endpoint": f"/exec/{worker}",
                            "worker": worker,
                            "duration_ms": round((time.time() - start_time) * 1000, 2),
                            "success": result.get("success", False),
                            "client": self.client_address[0],
                        }
                    )

                    self.send_json(result)
                    return

                # Forward to backend
                result = middleware._forward_to_backend(path, body, "POST")

                # Log the request
                worker = None
                try:
                    if body:
                        data = json.loads(body)
                        worker = data.get("worker")
                except:
                    pass

                middleware.request_log.add(
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "method": "POST",
                        "endpoint": path,
                        "worker": worker,
                        "duration_ms": round((time.time() - start_time) * 1000, 2),
                        "success": "error" not in result,
                        "client": self.client_address[0],
                    }
                )

                self.send_json(result)

            def do_DELETE(self):
                start_time = time.time()
                path = self.path

                result = middleware._forward_to_backend(path, method="DELETE")

                middleware.request_log.add(
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "method": "DELETE",
                        "endpoint": path,
                        "duration_ms": round((time.time() - start_time) * 1000, 2),
                        "success": "error" not in result,
                        "client": self.client_address[0],
                    }
                )

                self.send_json(result)

        print(f"\n{'=' * 60}")
        print(f"       GRID-X MIDDLEWARE")
        print(f"{'=' * 60}")
        print(f"\n  Listening on: http://0.0.0.0:{self.port}")
        print(f"  Backend URL: {self.backend_url}")
        print(f"\n  Endpoints:")
        print(f"    GET  /middleware/health - Health check")
        print(f"    GET  /middleware/logs   - Request logs")
        print(f"    GET  /middleware/stats  - Request statistics")
        print(f"    GET  /middleware/config - Hub config (safe)")
        print(f"    POST /middleware/exec/<worker> - Direct worker exec")
        print(f"    *    /* - Forward to backend")
        print(f"\n  Press Ctrl+C to stop\n")

        try:
            server = HTTPServer(("0.0.0.0", self.port), MiddlewareHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n  Middleware stopped.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Grid-X Middleware")
    parser.add_argument("--port", type=int, default=7575, help="Port to listen on")
    parser.add_argument(
        "--backend", default="http://localhost:8000", help="Backend URL"
    )

    args = parser.parse_args()

    middleware = GridXMiddleware(port=args.port, backend_url=args.backend)
    middleware.start()


if __name__ == "__main__":
    main()
