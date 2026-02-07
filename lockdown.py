import docker
import os

def get_docker_client():
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Docker not available: {e}. Please ensure Docker is installed and running.")

def run_task_and_get_results(image_name, command, timeout=30):
    client = get_docker_client()
    container = None
    
    try:
        print(f"Starting Docker container with image: {image_name}")
        
        # Security-focused container configuration
        container = client.containers.run(
            image=image_name,
            command=command,
            detach=True,
            network_disabled=True,  # No network access
            read_only=True,         # Read-only filesystem
            mem_limit="512m",       # Limit memory usage
            nano_cpus=int(0.5 * 1e9),  # Limit to 0.5 CPU cores  
            security_opt=["no-new-privileges:true"],  # Prevent privilege escalation
            user="nobody",          # Run as non-root user
            remove=False            # We'll remove manually for better cleanup
        )

        print(f"Container {container.short_id} started, waiting for completion...")
        
        # Wait for completion with timeout
        result = container.wait(timeout=timeout)
        
        # Capture all output
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")
        exit_code = result["StatusCode"]

        print(f"Container finished with exit code: {exit_code}")
        
        return {
            "exit_code": exit_code,
            "logs": logs,
            "status": "success",
            "container_id": container.short_id
        }

    except docker.errors.ImageNotFound:
        return {
            "status": "error", 
            "message": f"Docker image '{image_name}' not found. Please pull the image first."
        }
    except docker.errors.ContainerError as e:
        return {
            "status": "error",
            "message": f"Container execution failed: {e}"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Unexpected error: {str(e)}"
        }
    
    finally:
        # Always cleanup the container
        if container:
            try:
                container.remove(force=True)
                print(f"Container {container.short_id} removed")
            except Exception as e:
                print(f"Warning: Failed to remove container: {e}")