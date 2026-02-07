# client.py
import asyncio
import requests
from discovery import start_mesh_node

# client.py
import asyncio
import requests
import random
from discovery import start_mesh_node

async def find_and_run_job(image, command):
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

if __name__ == "__main__":
    job_image = "python:3.9-slim"
    job_cmd = "python -c 'print(\"Mesh computation complete.\")'"
    asyncio.run(find_and_run_job(job_image, job_cmd))