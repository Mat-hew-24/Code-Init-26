# client.py
import asyncio
import requests
import random
import json
import os
from discovery import start_mesh_node

async def find_and_run_notebook(filename, notebook_content):
    # Method 1: Try direct connection to common ports first (faster)
    print("🔍 Checking for nodes on common ports...")
    common_ports = [8000, 8001, 8002, 8003]
    
    for port in common_ports:
        if await try_submit_job("127.0.0.1", port, image, command):
            return
    
    # Method 2: If no direct connections work, join the mesh
    print("📡 No direct connections found, joining mesh network...")
    try:
        # Use random port to avoid conflicts
        client_port = random.randint(9000, 9999)
        print(f"Using port {client_port} for mesh connection...")
        
        node = await start_mesh_node(port=client_port)
        
        # Wait for mesh discovery
        await asyncio.sleep(5)
        
        # Search for available nodes in the mesh
        available_nodes = []
        peers = node.protocol.router.get_neighbors(node.protocol.source_node)
        print(f"Found {len(peers)} peers in mesh")
        
        if not peers:
            print("❌ No peers found in mesh network.")
            print("   Make sure at least one Grid-X node is running!")
            print("   Try: python main.py")
            return

        for peer in peers:
            try:
                # Try to get node data from each peer
                node_key = f"node_{peer.id.hex()}"
                node_data = await node.get(node_key)
                
                if node_data and "Status:IDLE" in node_data:
                    # Extract port from node data
                    if "Port:" in node_data:
                        port = node_data.split("Port:")[1].split(",")[0]
                        await try_submit_job(peer.ip, int(port), image, command)
                        return
                        
            except Exception as e:
                print(f"Error checking peer {peer.id.hex()[:8]}: {e}")
                continue
        
        print("❌ No IDLE nodes found in mesh")
        
    except OSError as e:
        if "10048" in str(e):  # Port already in use
            print(f"❌ Port conflict detected. Trying direct API connections...")
            await try_direct_connections(image, command)
        else:
            print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Mesh connection failed: {e}")
        print("   Trying direct connections to known ports...")
        await try_direct_connections(image, command)

async def try_direct_connections(image, command):
    """Try connecting directly to known API endpoints"""
    print("🔗 Attempting direct connections to local nodes...")
    
    # Try different localhost configurations
    hosts_and_ports = [
        ("127.0.0.1", 8000),
        ("127.0.0.1", 8001), 
        ("127.0.0.1", 8002),
        ("localhost", 8000),
        ("localhost", 8001),
        ("localhost", 8002)
    ]
    
    for host, port in hosts_and_ports:
        if await try_submit_job(host, port, image, command):
            return
    
    print("❌ No Grid-X nodes found on common ports")
    print("   Please start a node first with: python main.py")

async def try_submit_job(host, port, image, command):
    """Try to submit a job to a specific host:port"""
    url = f"http://{host}:{port}"
    
    try:
        print(f"   Trying {host}:{port}...")
        
        # Quick health check first
        response = requests.get(f"{url}/health", timeout=3)
        if response.status_code != 200:
            return False
        
        # Check if node is idle
        status_response = requests.get(f"{url}/status", timeout=3)
        if status_response.status_code != 200:
            return False
            
        status_data = status_response.json()
        if not status_data.get("is_idle"):
            print(f"   Node at {host}:{port} is BUSY (CPU: {status_data.get('resources', {}).get('cpu_usage', 'unknown')}%)")
            return False
        
        print(f"✅ Found IDLE node at {host}:{port}")
        print("🚀 Submitting job...")
        
        # Submit the job
        job_data = {"image": image, "command": command, "timeout": 60}
        job_response = requests.post(f"{url}/job", json=job_data, timeout=90)
        
        if job_response.status_code == 200:
            result = job_response.json()
            print_job_result(result, host, port)
            return True
        else:
            print(f"❌ Job submission failed: {job_response.status_code}")
            print(f"   Error: {job_response.text}")
            return False
            
    except requests.exceptions.ConnectTimeout:
        return False  # Silent fail for connection attempts
    except requests.exceptions.ConnectionError:
        return False  # Silent fail for connection attempts  
    except Exception as e:
        print(f"   Error with {host}:{port}: {e}")
        return False

def print_job_result(result, host, port):
    """Print job results in a nice format"""
    print()
    print("=" * 60)
    print(f"🎯 JOB COMPLETED ON {host}:{port}")
    print("=" * 60)
    print(f"Status: {result.get('status', 'Unknown')}")
    print(f"Exit Code: {result.get('exit_code', 'Unknown')}")
    print(f"Container: {result.get('container_id', 'Unknown')}")
    print()
    print("📄 OUTPUT:")
    print("-" * 30)
    output = result.get('logs', 'No output').strip()
    if output:
        print(output)
    else:
        print("(No output)")
    print("-" * 30)
    print("=" * 60)
    print("✅ Grid-X job execution complete!")
    print("=" * 60)

async def find_and_run_notebook(filename, notebook_content):
    """Find an available node and execute a Jupyter notebook"""
    # Method 1: Try direct connection to common ports first
    print(f"🔍 Looking for available nodes to execute {filename}...")
    
    common_ports = [8000, 8001, 8002, 8003]
    
    for port in common_ports:
        if await try_submit_notebook("127.0.0.1", port, filename, notebook_content):
            return
    
    # Method 2: Join mesh network if direct connections fail
    print("📡 Searching mesh network for nodes...")
    try:
        client_port = random.randint(9000, 9999)
        print(f"Using port {client_port} for mesh connection...")
        
        node = await start_mesh_node(port=client_port)
        await asyncio.sleep(5)
        
        peers = node.protocol.router.get_neighbors(node.protocol.source_node)
        print(f"Found {len(peers)} peers in mesh")
        
        if not peers:
            print("❌ No peers found in mesh network.")
            print("   Make sure at least one Grid-X node is running!")
            return

        for peer in peers:
            try:
                node_key = f"node_{peer.id.hex()}"
                node_data = await node.get(node_key)
                
                if node_data and "Status:IDLE" in node_data:
                    if "Port:" in node_data:
                        port = node_data.split("Port:")[1].split(",")[0]
                        await try_submit_notebook(peer.ip, int(port), filename, notebook_content)
                        return
            except Exception as e:
                print(f"Error checking peer: {e}")
                continue
        
        print("❌ No IDLE nodes found in mesh")
        
    except Exception as e:
        print(f"❌ Mesh connection failed: {e}")
        await try_direct_notebook_connections(filename, notebook_content)

async def try_direct_notebook_connections(filename, notebook_content):
    """Try direct connections for notebook execution"""
    print("🔗 Attempting direct connections for notebook execution...")
    
    hosts_and_ports = [
        ("127.0.0.1", 8000),
        ("127.0.0.1", 8001), 
        ("127.0.0.1", 8002),
        ("localhost", 8000),
        ("localhost", 8001),
        ("localhost", 8002)
    ]
    
    for host, port in hosts_and_ports:
        if await try_submit_notebook(host, port, filename, notebook_content):
            return
    
    print("❌ No Grid-X nodes found for notebook execution")
    print("   Please start a node first with: python main.py")

async def try_submit_notebook(host, port, filename, notebook_content):
    """Try to submit a notebook to a specific host:port"""
    url = f"http://{host}:{port}"
    
    try:
        print(f"   Trying {host}:{port} for notebook execution...")
        
        # Check if node supports notebooks
        response = requests.get(f"{url}/health", timeout=3)
        if response.status_code != 200:
            return False
        
        # Check if node is idle
        status_response = requests.get(f"{url}/status", timeout=3)
        if status_response.status_code != 200:
            return False
            
        status_data = status_response.json()
        if not status_data.get("is_idle"):
            print(f"   Node at {host}:{port} is BUSY")
            return False
        
        print(f"✅ Found IDLE node at {host}:{port}")
        print(f"📔 Submitting notebook {filename}...")
        
        # Submit the notebook
        notebook_data = {
            "notebook_content": notebook_content,
            "image": "jupyter/datascience-notebook:latest",
            "timeout": 300
        }
        
        job_response = requests.post(f"{url}/notebook", json=notebook_data, timeout=320)
        
        if job_response.status_code == 200:
            result = job_response.json()
            print_notebook_result(result, host, port, filename)
            
            # Save executed notebook
            save_executed_notebook(result, filename)
            return True
        else:
            print(f"❌ Notification submission failed: {job_response.status_code}")
            print(f"   Error: {job_response.text}")
            return False
            
    except requests.exceptions.ConnectTimeout:
        return False
    except requests.exceptions.ConnectionError:
        return False
    except Exception as e:
        print(f"   Error with {host}:{port}: {e}")
        return False

def print_notebook_result(result, host, port, filename):
    """Print notebook execution results"""
    print()
    print("=" * 60)
    print(f"📔 NOTEBOOK EXECUTED ON {host}:{port}")
    print("=" * 60)
    print(f"Notebook: {filename}")
    print(f"Status: {result.get('status', 'Unknown')}")
    print(f"Exit Code: {result.get('exit_code', 'Unknown')}")
    print(f"Container: {result.get('container_id', 'Unknown')}")
    print()
    
    if result.get('exit_code') == 0:
        print("✅ Notebook executed successfully!")
        print(f"📄 Executed notebook saved as: executed_{filename}")
    else:
        print("❌ Notebook execution failed!")
        print("📄 EXECUTION LOGS:")
        print("-" * 30)
        logs = result.get('logs', 'No logs available').strip()
        if logs:
            print(logs)
        print("-" * 30)
    
    print("=" * 60)

def save_executed_notebook(result, original_filename):
    """Save the executed notebook to disk"""
    try:
        executed_notebook = result.get('executed_notebook')
        if executed_notebook:
            # Generate output filename
            base_name = os.path.splitext(original_filename)[0]
            output_filename = f"executed_{base_name}.ipynb"
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(executed_notebook)
            
            print(f"📁 Executed notebook saved as: {output_filename}")
        else:
            print("⚠️ No executed notebook content received")
    except Exception as e:
        print(f"❌ Error saving executed notebook: {e}")

async def find_and_run_job(image, command):
    # 1. Try direct connection to common ports first (faster)
    print("🔍 Checking for nodes on common ports...")
    common_ports = [8000, 8001, 8002, 8003]
    
    for port in common_ports:
        if await try_submit_job("127.0.0.1", port, image, command):
            return
    
    # 2. If no direct connections work, join the mesh
    print("📡 No direct connections found, joining mesh network...")
    try:
        # Use random port to avoid conflicts
        client_port = random.randint(9000, 9999)
        print(f"Using port {client_port} for mesh connection...")
        
        node = await start_mesh_node(port=client_port)
        
        # Wait for mesh discovery
        await asyncio.sleep(5)
        
        # Search for available nodes in the mesh
        available_nodes = []
        peers = node.protocol.router.get_neighbors(node.protocol.source_node)
        print(f"Found {len(peers)} peers in mesh")
        
        if not peers:
            print("❌ No peers found in mesh network.")
            print("   Make sure at least one Grid-X node is running!")
            print("   Try: python main.py")
            return

        for peer in peers:
            try:
                # Try to get node data from each peer
                node_key = f"node_{peer.id.hex()}"
                node_data = await node.get(node_key)
                
                if node_data and "Status:IDLE" in node_data:
                    # Extract port from node data
                    if "Port:" in node_data:
                        port = node_data.split("Port:")[1].split(",")[0]
                        await try_submit_job(peer.ip, int(port), image, command)
                        return
                        
            except Exception as e:
                print(f"Error checking peer {peer.id.hex()[:8]}: {e}")
                continue
        
        print("❌ No IDLE nodes found in mesh")
        
    except OSError as e:
        if "10048" in str(e):  # Port already in use
            print(f"❌ Port conflict detected. Trying direct API connections...")
            await try_direct_connections(image, command)
        else:
            print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Mesh connection failed: {e}")
        print("   Trying direct connections to known ports...")
        await try_direct_connections(image, command)

if __name__ == "__main__":
    # Example usage for regular jobs
    job_image = "python:3.9-slim"
    job_cmd = "python -c 'print(\"Grid computation complete.\")'"
    asyncio.run(find_and_run_job(job_image, job_cmd))

async def try_direct_connections(image, command):
    """Try connecting directly to known API endpoints"""
    print("🔗 Attempting direct connections to local nodes...")
    
    # Try different localhost configurations
    hosts_and_ports = [
        ("127.0.0.1", 8000),
        ("127.0.0.1", 8001), 
        ("127.0.0.1", 8002),
        ("localhost", 8000),
        ("localhost", 8001),
        ("localhost", 8002)
    ]
    
    for host, port in hosts_and_ports:
        if await try_submit_job(host, port, image, command):
            return
    
    print("❌ No Grid-X nodes found on common ports")
    print("   Please start a node first with: python main.py")

async def try_submit_job(host, port, image, command):
    """Try to submit a job to a specific host:port"""
    url = f"http://{host}:{port}"
    
    try:
        print(f"   Trying {host}:{port}...")
        
        # Quick health check first
        response = requests.get(f"{url}/health", timeout=3)
        if response.status_code != 200:
            return False
        
        # Check if node is idle
        status_response = requests.get(f"{url}/status", timeout=3)
        if status_response.status_code != 200:
            return False
            
        status_data = status_response.json()
        if not status_data.get("is_idle"):
            print(f"   Node at {host}:{port} is BUSY (CPU: {status_data.get('resources', {}).get('cpu_usage', 'unknown')}%)")
            return False
        
        print(f"✅ Found IDLE node at {host}:{port}")
        print("🚀 Submitting job...")
        
        # Submit the job
        job_data = {"image": image, "command": command, "timeout": 60}
        job_response = requests.post(f"{url}/job", json=job_data, timeout=90)
        
        if job_response.status_code == 200:
            result = job_response.json()
            print_job_result(result, host, port)
            return True
        else:
            print(f"❌ Job submission failed: {job_response.status_code}")
            print(f"   Error: {job_response.text}")
            return False
            
    except requests.exceptions.ConnectTimeout:
        return False  # Silent fail for connection attempts
    except requests.exceptions.ConnectionError:
        return False  # Silent fail for connection attempts  
    except Exception as e:
        print(f"   Error with {host}:{port}: {e}")
        return False

def print_job_result(result, host, port):
    """Print job results in a nice format"""
    print()
    print("=" * 60)
    print(f"🎯 JOB COMPLETED ON {host}:{port}")
    print("=" * 60)
    print(f"Status: {result.get('status', 'Unknown')}")
    print(f"Exit Code: {result.get('exit_code', 'Unknown')}")
    print(f"Container: {result.get('container_id', 'Unknown')}")
    print()
    print("📄 OUTPUT:")
    print("-" * 30)
    output = result.get('logs', 'No output').strip()
    if output:
        print(output)
    else:
        print("(No output)")
    print("-" * 30)
    print("=" * 60)
    print("✅ Grid-X job execution complete!")
    print("=" * 60)
    job_image = "python:3.9-slim"
    job_cmd = "python -c 'print(\"Mesh computation complete.\")'"
    asyncio.run(find_and_run_job(job_image, job_cmd))