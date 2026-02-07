import docker
import os

def get_docker_client():
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Docker not available: {e}. Please ensure Docker is installed and running.")

import docker
import os
import json
import tempfile
import base64

def get_docker_client():
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Docker not available: {e}. Please ensure Docker is installed and running.")

def run_notebook_and_get_results(notebook_content, image_name="jupyter/datascience-notebook:latest", timeout=300):
    """Execute a Jupyter notebook in a secure Docker container"""
    client = get_docker_client()
    container = None
    
    try:
        print(f"Starting Jupyter notebook execution with image: {image_name}")
        
        # Validate notebook content is valid JSON
        try:
            notebook_json = json.loads(notebook_content)
            if 'cells' not in notebook_json:
                return {"status": "error", "message": "Invalid notebook format - no cells found"}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid notebook JSON: {e}"}
        
        # Create a temporary directory for notebook files
        with tempfile.TemporaryDirectory() as temp_dir:
            notebook_path = os.path.join(temp_dir, "notebook.ipynb")
            output_path = os.path.join(temp_dir, "executed.ipynb")
            
            # Write notebook to temporary file
            with open(notebook_path, 'w', encoding='utf-8') as f:
                f.write(notebook_content)
            
            # Create container with mounted volume
            container = client.containers.run(
                image=image_name,
                command=f"bash -c 'cd /tmp/notebooks && jupyter nbconvert --to notebook --execute notebook.ipynb --output executed.ipynb'",
                detach=True,
                volumes={
                    temp_dir: {'bind': '/tmp/notebooks', 'mode': 'rw'}
                },
                network_disabled=True,       # No network access
                mem_limit="1g",              # Increased memory for notebooks
                nano_cpus=int(1.0 * 1e9),   # Allow 1 full CPU core
                security_opt=["no-new-privileges:true"],
                user="jovyan",               # Jupyter's default user
                remove=False,
                working_dir="/tmp/notebooks"
            )

            print(f"Container {container.short_id} started, executing notebook...")
            
            # Wait for completion with timeout
            result = container.wait(timeout=timeout)
            
            # Capture logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")
            exit_code = result["StatusCode"]
            
            # Read executed notebook if successful
            executed_notebook = None
            if exit_code == 0 and os.path.exists(output_path):
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        executed_notebook = f.read()
                    print("✅ Notebook executed successfully")
                except Exception as e:
                    print(f"Warning: Could not read executed notebook: {e}")
                    executed_notebook = notebook_content  # Return original if can't read output
            else:
                print(f"❌ Notebook execution failed with exit code: {exit_code}")
                executed_notebook = notebook_content  # Return original on failure

            return {
                "exit_code": exit_code,
                "executed_notebook": executed_notebook or notebook_content,
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