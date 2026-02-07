# main.py
import asyncio
import uvicorn
from discovery import start_mesh_node
from watcher import get_available_resources
from api import app

async def update_mesh_status(node):
    """Periodically tells the mesh if we are idle or busy"""
    while True:
        try:
            stats = get_available_resources()
            status_string = "IDLE" if stats["is_idle"] else "BUSY"
            
            # Store our status in the DHT so others can find us  
            node_data = f"Status:{status_string},RAM:{stats['ram_gb']:.1f}GB,Port:8000"
            await node.set(f"node_{node.node.id.hex()}", node_data)
            print(f"Updating Mesh: I am {status_string} - {stats['ram_gb']:.1f}GB RAM available")
        except Exception as e:
            print(f"Error updating mesh status: {e}")
        
        await asyncio.sleep(30) # Check every 30 seconds

async def start_all():
    # 1. Start the Mesh Discovery
    node = await start_mesh_node()
    
    # 2. Start the Status Updater in the background
    asyncio.create_task(update_mesh_status(node))
    
    # 3. Start the API Server (this handles incoming jobs)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_all())