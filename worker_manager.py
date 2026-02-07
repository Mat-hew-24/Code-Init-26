#!/usr/bin/env python3
"""
Worker Manager - Utility script to manage and interact with Grid-X workers

This script demonstrates how to:
1. Check worker pool status
2. Execute commands automatically on best workers
3. Monitor worker health
"""

import requests
import json
import time
from typing import Dict, List, Any


class WorkerManager:
    """Manager for Grid-X worker pool"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base = api_base_url.rstrip("/")

    def get_pool_status(self) -> Dict[str, Any]:
        """Get detailed status of all workers"""
        response = requests.get(f"{self.api_base}/api/workers/pool/status")
        response.raise_for_status()
        return response.json()

    def get_pool_health(self) -> Dict[str, Any]:
        """Get overall health of worker pool"""
        response = requests.get(f"{self.api_base}/api/workers/pool/health")
        response.raise_for_status()
        return response.json()

    def get_best_worker(self) -> Dict[str, Any]:
        """Get the best worker for task execution"""
        response = requests.get(f"{self.api_base}/api/exec/workers/best")
        response.raise_for_status()
        return response.json()

    def execute_auto(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute command on best available worker"""
        response = requests.post(
            f"{self.api_base}/api/exec/auto",
            params={"command": command, "timeout": timeout},
        )
        response.raise_for_status()
        return response.json()

    def execute_on_worker(
        self, worker_name: str, command: str, timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute command on specific worker"""
        data = {"worker": worker_name, "command": command, "timeout": timeout}
        response = requests.post(f"{self.api_base}/api/exec", json=data)
        response.raise_for_status()
        return response.json()

    def execute_on_all(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute command on all workers"""
        data = {"workers": ["all"], "command": command, "timeout": timeout}
        response = requests.post(f"{self.api_base}/api/exec/batch", json=data)
        response.raise_for_status()
        return response.json()

    def print_pool_summary(self):
        """Print a nice summary of the worker pool"""
        try:
            status = self.get_pool_status()
            health = self.get_pool_health()

            print("\n" + "=" * 60)
            print("              GRID-X WORKER POOL STATUS")
            print("=" * 60)

            print(
                f"\n📊 Pool Health: {health['health_status'].upper()} ({health['health_score']}%)"
            )
            print(
                f"🔢 Workers: {health['online_workers']}/{health['total_workers']} online"
            )
            print(f"📈 Availability: {health['availability_percentage']:.1f}%")

            if status.get("recommended_worker"):
                print(f"⭐ Recommended: {status['recommended_worker']}")

            print(
                f"\n{'Worker':<15} {'Status':<10} {'IP':<15} {'CPU%':<8} {'Memory%':<10} {'GPUs':<6}"
            )
            print("-" * 70)

            for name, worker in status["workers"].items():
                cpu_pct = worker.get("cpu_percent", "N/A")
                mem_pct = worker.get("memory_percent", "N/A")
                status_icon = "🟢" if worker["online"] else "🔴"

                print(
                    f"{name:<15} {status_icon} {worker['status']:<8} "
                    f"{worker.get('ip', 'N/A'):<15} "
                    f"{cpu_pct:<8} {mem_pct:<10} {worker.get('gpus', 0):<6}"
                )

            print("\n" + "=" * 60)

        except Exception as e:
            print(f"❌ Error getting pool status: {e}")

    def demo_auto_execution(self):
        """Demonstrate automatic worker selection"""
        commands = [
            "hostname",
            "echo 'Hello from Grid-X!'",
            "python3 --version",
            "nvidia-smi | head -5" if self._has_gpu_workers() else "ls /tmp",
        ]

        print("\n" + "=" * 60)
        print("           AUTOMATIC WORKER EXECUTION DEMO")
        print("=" * 60)

        for cmd in commands:
            print(f"\n🚀 Executing: {cmd}")
            try:
                result = self.execute_auto(cmd, timeout=10)
                worker = result.get("worker", "unknown")
                success = result.get("success", False)
                output = result.get("stdout", "").strip()

                if success:
                    print(f"✅ Worker: {worker}")
                    if output:
                        print(f"📝 Output: {output}")
                else:
                    error = result.get("error", "Unknown error")
                    print(f"❌ Failed on {worker}: {error}")

            except Exception as e:
                print(f"❌ Request failed: {e}")
            time.sleep(1)

    def _has_gpu_workers(self) -> bool:
        """Check if any workers have GPUs"""
        try:
            status = self.get_pool_status()
            return any(w.get("gpus", 0) > 0 for w in status["workers"].values())
        except:
            return False


def main():
    """Main demo function"""
    manager = WorkerManager()

    print("Grid-X Worker Manager")
    print("=====================")

    while True:
        print("\nOptions:")
        print("1. Show pool status")
        print("2. Show pool health")
        print("3. Get best worker")
        print("4. Execute command (auto-select)")
        print("5. Execute on specific worker")
        print("6. Execute on all workers")
        print("7. Demo automatic execution")
        print("0. Exit")

        choice = input("\nSelect option: ").strip()

        try:
            if choice == "1":
                manager.print_pool_summary()

            elif choice == "2":
                health = manager.get_pool_health()
                print(f"\n🏥 Pool Health: {json.dumps(health, indent=2)}")

            elif choice == "3":
                best = manager.get_best_worker()
                print(f"\n⭐ Best Worker: {json.dumps(best, indent=2)}")

            elif choice == "4":
                cmd = input("Enter command: ").strip()
                if cmd:
                    result = manager.execute_auto(cmd)
                    print(f"\n📋 Result: {json.dumps(result, indent=2)}")

            elif choice == "5":
                worker = input("Enter worker name: ").strip()
                cmd = input("Enter command: ").strip()
                if worker and cmd:
                    result = manager.execute_on_worker(worker, cmd)
                    print(f"\n📋 Result: {json.dumps(result, indent=2)}")

            elif choice == "6":
                cmd = input("Enter command: ").strip()
                if cmd:
                    result = manager.execute_on_all(cmd)
                    print(f"\n📋 Results: {json.dumps(result, indent=2)}")

            elif choice == "7":
                manager.demo_auto_execution()

            elif choice == "0":
                break

            else:
                print("❌ Invalid option")

        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
