import asyncio
from kademlia.network import Server

async def start_mesh_node(port=8468, bootstrap_peers=None):
    node = Server()
    await node.listen(port)
    
    # Bootstrap: Connect to known peers to join the mesh
    if bootstrap_peers is None:
        bootstrap_peers = []
        # Try to connect to a common port if this isn't the seed node
        if port != 8468:
            bootstrap_peers.append(("127.0.0.1", 8468))
    
    if bootstrap_peers:
        try:
            await node.bootstrap(bootstrap_peers)
            print(f"Successfully joined mesh via {bootstrap_peers}")
        except Exception as e:
            print(f"Warning: Could not bootstrap to {bootstrap_peers}: {e}")
            print("This node will start as a seed node")

    # Announce this node's availability with its unique ID  
    node_data = f"Status:Idle,Port:8000,Timestamp:{asyncio.get_event_loop().time():.0f}"
    await node.set(f"node_{node.node.id.hex()}", node_data)
    
    print(f"Node {node.node.id.hex()[:8]} is live on the Grid-X mesh on port {port}")
    return node
