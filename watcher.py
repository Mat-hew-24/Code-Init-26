import psutil
import time

def get_available_resources():
    """Get current system resource availability"""
    try:
        # Get CPU usage over a 1-second interval for accuracy
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # Get memory information
        memory = psutil.virtual_memory()
        available_ram_gb = memory.available / (1024**3)
        total_ram_gb = memory.total / (1024**3)
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        available_disk_gb = disk.free / (1024**3)
        
        # Determine if system is idle (CPU < 50% and enough RAM available)
        is_idle = cpu_usage < 50.0 and available_ram_gb > 1.0
        
        return {
            "is_idle": is_idle,
            "cpu_usage": round(cpu_usage, 1),
            "ram_gb": round(available_ram_gb, 1),
            "total_ram_gb": round(total_ram_gb, 1),
            "disk_gb": round(available_disk_gb, 1),
            "timestamp": time.time()
        }
    except Exception as e:
        print(f"Error getting system resources: {e}")
        # Return safe defaults if monitoring fails
        return {
            "is_idle": False,
            "cpu_usage": 100.0,
            "ram_gb": 0.0,
            "total_ram_gb": 0.0,
            "disk_gb": 0.0,
            "timestamp": time.time()
        }