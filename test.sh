#!/bin/bash
# Grid-X Test Script - Automates hub + worker setup in Docker containers

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BLUE}"
echo "=============================================="
echo "       GRID-X RESOURCE MESH"
echo "=============================================="
echo -e "${NC}"

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Get host's IP address
get_host_ip() {
    # Try to get the main IP (not localhost)
    ip route get 1 2>/dev/null | awk '{print $7; exit}' || \
    hostname -I 2>/dev/null | awk '{print $1}' || \
    echo "YOUR_IP"
}

case "$1" in
    # ============== START ==============
    start|up)
        echo -e "${YELLOW}[1/2] Building containers...${NC}"
        $COMPOSE build

        echo -e "${YELLOW}[2/2] Starting containers...${NC}"
        $COMPOSE up -d

        echo -e "${GREEN}"
        echo "=============================================="
        echo "  Containers started!"
        echo "=============================================="
        echo -e "${NC}"
        echo "Wait ~10 seconds for Docker daemons to start, then run:"
        echo ""
        echo -e "  ${BLUE}./test.sh setup${NC}    # Initialize hub + connect workers"
        echo ""
        echo "Or manually:"
        echo "  docker exec -it gridx-hub bash"
        echo "  docker exec -it gridx-worker1 bash"
        echo ""
        ;;

    # ============== SETUP (AUTO) ==============
    setup|init)
        HOST_IP=$(get_host_ip)
        echo -e "${YELLOW}[1/2] Initializing Hub (Public IP: ${HOST_IP})...${NC}"
        docker exec gridx-hub python hub.py init --ip "$HOST_IP"

        echo -e "${YELLOW}[2/2] Verifying hub...${NC}"
        sleep 2

        echo ""
        echo -e "${GREEN}=============================================="
        echo "  HUB INITIALIZED!"
        echo "==============================================${NC}"
        echo ""
        echo "Check status:"
        echo -e "  ${BLUE}./test.sh status${NC}"
        echo ""
        echo "Add a worker:"
        echo -e "  ${BLUE}./test.sh add-external <worker-name>${NC}"
        echo ""
        echo "After adding workers, check connectivity:"
        echo -e "  ${BLUE}./test.sh ping-workers${NC}"
        echo ""
        ;;

    # ============== STATUS ==============
    status)
        echo -e "${YELLOW}=== HUB STATUS ===${NC}"
        docker exec gridx-hub python hub.py status

        echo -e "${YELLOW}=== SWARM NODES ===${NC}"
        docker exec gridx-hub docker node ls
        ;;

    # ============== TEST JOB ==============
    test-job|test)
        echo -e "${YELLOW}Running test job...${NC}"
        docker exec gridx-hub python jobs.py run alpine "echo 'Hello from Grid-X cluster!'; hostname; sleep 5; echo 'Done!'"
        
        sleep 3
        echo ""
        echo -e "${YELLOW}Checking job status...${NC}"
        docker exec gridx-hub python jobs.py list
        ;;

    # ============== MULTI-NODE TEST ==============
    test-multi)
        echo -e "${YELLOW}Running multi-replica job (tests distribution across nodes)...${NC}"
        docker exec gridx-hub python jobs.py run alpine "echo 'Running on:'; hostname; sleep 30" --replicas 4 --name multitest
        
        sleep 5
        echo ""
        echo -e "${YELLOW}Checking where replicas are running...${NC}"
        docker exec gridx-hub docker service ps gridx-multitest --format "table {{.Name}}\t{{.Node}}\t{{.CurrentState}}"
        ;;

    # ============== GPU TEST ==============
    test-gpu)
        echo -e "${YELLOW}Running GPU detection job...${NC}"
        docker exec gridx-hub python jobs.py run nvidia/cuda:12.0-base "nvidia-smi || echo 'No GPU available'" --gpus
        
        sleep 5
        echo ""
        echo -e "${YELLOW}Checking job logs...${NC}"
        docker exec gridx-hub python jobs.py list
        ;;

    # ============== CLUSTER INFO ==============
    cluster|info)
        echo -e "${YELLOW}=== CLUSTER INFO ===${NC}"
        docker exec gridx-hub python jobs.py cluster
        ;;

    # ============== JUPYTER ==============
    jupyter)
        echo -e "${YELLOW}Starting Jupyter notebook...${NC}"
        docker exec gridx-hub python jobs.py jupyter --cpus 1 --memory 1G
        ;;

    # ============== EXEC ON WORKER ==============
    exec)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo -e "${RED}Usage: $0 exec <worker-name> \"command\"${NC}"
            echo ""
            echo "Examples:"
            echo "  $0 exec worker1 \"hostname\""
            echo "  $0 exec worker2 \"nvidia-smi\""
            echo "  $0 exec 10.0.0.2 \"df -h\""
            echo ""
            echo "Available workers:"
            docker exec gridx-hub python hub.py list-peers 2>/dev/null || echo "  Run './test.sh setup' first"
            exit 1
        fi
        
        WORKER_NAME="$2"
        COMMAND="$3"
        
        echo -e "${YELLOW}Executing on ${WORKER_NAME}...${NC}"
        docker exec gridx-hub python hub.py exec "$WORKER_NAME" "$COMMAND"
        ;;

    # ============== PING WORKERS ==============
    ping-workers|ping)
        echo -e "${YELLOW}Checking worker agents...${NC}"
        docker exec gridx-hub python hub.py ping-workers
        ;;

    # ============== ADD EXTERNAL WORKER ==============
    add-external|add-worker)
        if [ -z "$2" ]; then
            echo -e "${RED}Usage: $0 add-external <worker-name>${NC}"
            echo "Example: $0 add-external laptop1"
            exit 1
        fi
        
        WORKER_NAME="$2"
        HOST_IP=$(get_host_ip)
        
        echo -e "${YELLOW}Adding external worker: ${WORKER_NAME}${NC}"
        docker exec gridx-hub python hub.py add-peer "$WORKER_NAME"
        
        # Create a bundle for the external worker
        BUNDLE_DIR="/tmp/gridx-${WORKER_NAME}"
        rm -rf "$BUNDLE_DIR"
        mkdir -p "$BUNDLE_DIR"
        
        # Copy WireGuard config
        docker exec gridx-hub cat "/etc/gridx/clients/${WORKER_NAME}.conf" > "${BUNDLE_DIR}/wg0.conf"
        
        # Get swarm token
        SWARM_TOKEN=$(docker exec gridx-hub cat /etc/gridx/hub_config.json | grep -o '"swarm_token": "[^"]*"' | cut -d'"' -f4)
        
        # Copy helper scripts
        cp "$SCRIPT_DIR/worker.py" "${BUNDLE_DIR}/" 2>/dev/null || true
        cp "$SCRIPT_DIR/jobs.py" "${BUNDLE_DIR}/" 2>/dev/null || true
        
        # Create the interactive join script
        cat > "${BUNDLE_DIR}/join.sh" << 'JOINEOF'
#!/bin/bash
# ============================================================
# Grid-X Worker Join Script
# Run this on the remote machine to join the cluster
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ============================================
# CONFIGURATION - Will be filled by test.sh
# ============================================
WORKER_NAME="__WORKER_NAME__"
SWARM_TOKEN="__SWARM_TOKEN__"
HUB_VPN_IP="10.0.0.1"
# ============================================

echo -e "${BLUE}"
echo "=============================================="
echo "       GRID-X - Join the Compute Mesh"
echo "=============================================="
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo ./join.sh)${NC}"
    exit 1
fi

# ==================== SYSTEM INFO ====================
echo -e "${CYAN}[System Information]${NC}"

# Get total CPUs
TOTAL_CPUS=$(nproc)
echo "  Total CPUs: $TOTAL_CPUS"

# Get total RAM in GB
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
echo "  Total RAM:  ${TOTAL_RAM_GB} GB"

# Check for NVIDIA GPUs
GPU_COUNT=0
GPU_INFO=""
if command -v nvidia-smi &> /dev/null; then
    GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "")
    if [ "$GPU_COUNT" -gt 0 ]; then
        echo -e "  GPUs:       ${GREEN}$GPU_COUNT ($GPU_INFO)${NC}"
    else
        echo "  GPUs:       None detected"
    fi
else
    echo "  GPUs:       nvidia-smi not found (no NVIDIA GPU or drivers not installed)"
fi

echo ""

# ==================== INTERACTIVE RESOURCE SELECTION ====================
echo -e "${CYAN}[Resource Allocation]${NC}"
echo "How much of your resources do you want to share with the cluster?"
echo ""

# CPU selection
echo -n "  CPUs to share (1-$TOTAL_CPUS) [default: $TOTAL_CPUS]: "
read -r SHARE_CPUS
SHARE_CPUS=${SHARE_CPUS:-$TOTAL_CPUS}

# Validate CPU input
if ! [[ "$SHARE_CPUS" =~ ^[0-9]+$ ]] || [ "$SHARE_CPUS" -lt 1 ] || [ "$SHARE_CPUS" -gt "$TOTAL_CPUS" ]; then
    echo -e "${YELLOW}  Invalid input, using $TOTAL_CPUS CPUs${NC}"
    SHARE_CPUS=$TOTAL_CPUS
fi

# RAM selection
DEFAULT_RAM=$((TOTAL_RAM_GB > 2 ? TOTAL_RAM_GB - 2 : TOTAL_RAM_GB))  # Leave 2GB for system
echo -n "  RAM to share in GB (1-$TOTAL_RAM_GB) [default: $DEFAULT_RAM]: "
read -r SHARE_RAM
SHARE_RAM=${SHARE_RAM:-$DEFAULT_RAM}

# Validate RAM input
if ! [[ "$SHARE_RAM" =~ ^[0-9]+$ ]] || [ "$SHARE_RAM" -lt 1 ] || [ "$SHARE_RAM" -gt "$TOTAL_RAM_GB" ]; then
    echo -e "${YELLOW}  Invalid input, using ${DEFAULT_RAM}GB RAM${NC}"
    SHARE_RAM=$DEFAULT_RAM
fi

# GPU selection (if available)
SHARE_GPUS=0
if [ "$GPU_COUNT" -gt 0 ]; then
    echo -n "  GPUs to share (0-$GPU_COUNT) [default: $GPU_COUNT]: "
    read -r SHARE_GPUS
    SHARE_GPUS=${SHARE_GPUS:-$GPU_COUNT}
    
    if ! [[ "$SHARE_GPUS" =~ ^[0-9]+$ ]] || [ "$SHARE_GPUS" -lt 0 ] || [ "$SHARE_GPUS" -gt "$GPU_COUNT" ]; then
        echo -e "${YELLOW}  Invalid input, using $GPU_COUNT GPUs${NC}"
        SHARE_GPUS=$GPU_COUNT
    fi
fi

echo ""
echo -e "${YELLOW}You will share: ${SHARE_CPUS} CPUs, ${SHARE_RAM}GB RAM, ${SHARE_GPUS} GPUs${NC}"
echo ""
echo -n "Continue? [Y/n]: "
read -r CONFIRM
if [[ "$CONFIRM" =~ ^[Nn] ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""

# ==================== CHECK DEPENDENCIES ====================
echo -e "${YELLOW}[1/5] Checking dependencies...${NC}"

# Check WireGuard
if ! command -v wg &> /dev/null; then
    echo -e "${RED}WireGuard not installed!${NC}"
    echo ""
    echo "Install with:"
    echo "  Arch:   sudo pacman -S wireguard-tools"
    echo "  Ubuntu: sudo apt install wireguard"
    echo "  Fedora: sudo dnf install wireguard-tools"
    exit 1
fi
echo "  WireGuard: OK"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not installed!${NC}"
    echo ""
    echo "Install from: https://docs.docker.com/get-docker/"
    echo "Or: curl -fsSL https://get.docker.com | sh"
    exit 1
fi
echo "  Docker: OK"

# Check Docker is running
if ! docker info &>/dev/null; then
    echo -e "${RED}Docker daemon not running!${NC}"
    echo "Start with: sudo systemctl start docker"
    exit 1
fi
echo "  Docker daemon: OK"

# Check NVIDIA runtime (if GPUs selected)
if [ "$SHARE_GPUS" -gt 0 ]; then
    if docker info 2>/dev/null | grep -q nvidia; then
        echo "  NVIDIA runtime: OK"
    else
        echo -e "${YELLOW}  Warning: NVIDIA Docker runtime not detected${NC}"
        echo "  GPU jobs may not work. Install nvidia-container-toolkit if needed."
    fi
fi

# ==================== SETUP WIREGUARD ====================
echo -e "${YELLOW}[2/5] Setting up WireGuard VPN...${NC}"

cp "$SCRIPT_DIR/wg0.conf" /etc/wireguard/wg0.conf
chmod 600 /etc/wireguard/wg0.conf

wg-quick down wg0 2>/dev/null || true
wg-quick up wg0

echo "  VPN interface: wg0"
echo "  VPN IP: $(ip addr show wg0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)"

# ==================== TEST VPN CONNECTION ====================
echo -e "${YELLOW}[3/5] Testing VPN connection...${NC}"

if ping -c 2 -W 3 "$HUB_VPN_IP" &>/dev/null; then
    echo -e "  ${GREEN}Hub reachable at $HUB_VPN_IP${NC}"
else
    echo -e "${RED}  Cannot reach hub at $HUB_VPN_IP${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check that the hub is running"
    echo "  2. Check firewall allows UDP port 51820"
    echo "  3. Verify your internet connection"
    exit 1
fi

# ==================== START COMMAND AGENT ====================
echo -e "${YELLOW}[4/5] Starting command agent...${NC}"

# Check if worker.py exists in the bundle
if [ -f "$SCRIPT_DIR/worker.py" ]; then
    # Copy worker.py to a known location
    mkdir -p /opt/gridx
    cp "$SCRIPT_DIR/worker.py" /opt/gridx/worker.py
    
    # Start the command agent in background
    nohup python3 /opt/gridx/worker.py agent > /var/log/gridx-agent.log 2>&1 &
    AGENT_PID=$!
    echo "  Command agent started (PID: $AGENT_PID)"
    echo "  Log file: /var/log/gridx-agent.log"
    
    # Save PID for later
    echo "$AGENT_PID" > /var/run/gridx-agent.pid
else
    echo -e "${YELLOW}  Warning: worker.py not found in bundle${NC}"
    echo "  The hub will not be able to execute commands on this worker"
    echo "  Copy worker.py to this machine and run: python3 worker.py agent"
fi

echo -e "  ${GREEN}Command agent configured${NC}"

# ==================== JOIN DOCKER SWARM ====================
echo -e "${YELLOW}[5/5] Joining Docker Swarm cluster...${NC}"

# Leave existing swarm
docker swarm leave --force 2>/dev/null || true

# Join swarm
if docker swarm join --token "$SWARM_TOKEN" "$HUB_VPN_IP:2377"; then
    echo -e "  ${GREEN}Joined swarm cluster!${NC}"
else
    echo -e "${RED}  Failed to join swarm!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check that hub's Docker swarm is running"
    echo "  2. Check that port 2377 is reachable via VPN"
    exit 1
fi

# ==================== SAVE CONFIG ====================
mkdir -p ~/.gridx
cat > ~/.gridx/worker_config << EOF
WORKER_NAME=$WORKER_NAME
SHARE_CPUS=$SHARE_CPUS
SHARE_RAM=$SHARE_RAM
SHARE_GPUS=$SHARE_GPUS
HUB_VPN_IP=$HUB_VPN_IP
JOINED_AT=$(date -Iseconds)
EOF

# ==================== SUCCESS ====================
echo ""
echo -e "${GREEN}=============================================="
echo "  SUCCESS! Joined Grid-X Cluster"
echo "==============================================${NC}"
echo ""
echo "  Worker: $WORKER_NAME"
echo "  Sharing: ${SHARE_CPUS} CPUs, ${SHARE_RAM}GB RAM, ${SHARE_GPUS} GPUs"
echo ""
echo "  Your machine is now part of the compute mesh!"
echo "  The hub can now schedule jobs on this worker."
echo ""
echo -e "${CYAN}Commands:${NC}"
echo "  Check status:    docker info | grep Swarm"
echo "  View services:   docker service ls"
echo "  Leave cluster:   docker swarm leave"
echo "  VPN status:      wg show"
echo "  Agent status:    curl http://localhost:7576/ping"
echo "  Agent logs:      tail -f /var/log/gridx-agent.log"
echo ""
echo -e "${CYAN}Config saved to:${NC} ~/.gridx/worker_config"
echo ""
JOINEOF

        # Replace placeholders in join.sh
        sed -i "s|__WORKER_NAME__|$WORKER_NAME|g" "${BUNDLE_DIR}/join.sh"
        sed -i "s|__SWARM_TOKEN__|$SWARM_TOKEN|g" "${BUNDLE_DIR}/join.sh"
        
        chmod +x "${BUNDLE_DIR}/join.sh"
        
        # Create leave script
        cat > "${BUNDLE_DIR}/leave.sh" << 'LEAVEEOF'
#!/bin/bash
# Grid-X Worker Leave Script
echo "Leaving Grid-X cluster..."

# Stop the command agent
if [ -f /var/run/gridx-agent.pid ]; then
    AGENT_PID=$(cat /var/run/gridx-agent.pid)
    kill "$AGENT_PID" 2>/dev/null || true
    rm -f /var/run/gridx-agent.pid
    echo "  Stopped command agent"
fi

docker swarm leave --force 2>/dev/null || true
wg-quick down wg0 2>/dev/null || true
echo "Done! You have left the cluster."
LEAVEEOF
        chmod +x "${BUNDLE_DIR}/leave.sh"
        
        # Create status script
        cat > "${BUNDLE_DIR}/status.sh" << 'STATUSEOF'
#!/bin/bash
# Grid-X Worker Status Script
echo "=== Grid-X Worker Status ==="
echo ""
echo "[Swarm]"
docker info 2>/dev/null | grep -A5 "Swarm:" | head -6
echo ""
echo "[VPN]"
wg show 2>/dev/null || echo "VPN not connected"
echo ""
echo "[Command Agent]"
if curl -s http://localhost:7576/ping 2>/dev/null | grep -q "ok"; then
    echo "  Status: RUNNING on port 7576"
else
    echo "  Status: NOT RUNNING"
fi
echo ""
echo "[Config]"
cat ~/.gridx/worker_config 2>/dev/null || echo "No config found"
STATUSEOF
        chmod +x "${BUNDLE_DIR}/status.sh"
        
        # Create tarball
        TARBALL="/tmp/gridx-${WORKER_NAME}.tar.gz"
        tar -czf "$TARBALL" -C /tmp "gridx-${WORKER_NAME}"
        
        echo ""
        echo -e "${GREEN}=============================================="
        echo "  EXTERNAL WORKER BUNDLE CREATED"
        echo "==============================================${NC}"
        echo ""
        echo -e "${CYAN}Bundle location:${NC} ${TARBALL}"
        echo ""
        echo -e "${CYAN}Send to remote machine:${NC}"
        echo "  scp ${TARBALL} user@remote-host:~/"
        echo ""
        echo -e "${CYAN}On the remote machine run:${NC}"
        echo "  tar -xzf gridx-${WORKER_NAME}.tar.gz"
        echo "  cd gridx-${WORKER_NAME}"
        echo "  sudo ./join.sh"
        echo ""
        echo -e "${CYAN}Or serve via HTTP (run on this machine):${NC}"
        echo "  cd /tmp && python3 -m http.server 8000"
        echo "  # Remote: curl -O http://${HOST_IP}:8000/gridx-${WORKER_NAME}.tar.gz"
        echo ""
        echo -e "${CYAN}Bundle contents:${NC}"
        echo "  join.sh    - Interactive setup script"
        echo "  leave.sh   - Leave the cluster"
        echo "  status.sh  - Check connection status"
        echo "  wg0.conf   - WireGuard VPN config"
        echo ""
        ;;

    # ============== LIST EXTERNAL ==============
    list-external|list-workers)
        echo -e "${YELLOW}=== REGISTERED WORKERS ===${NC}"
        docker exec gridx-hub python hub.py list-peers
        
        echo ""
        echo -e "${YELLOW}=== CONNECTED TO SWARM ===${NC}"
        docker exec gridx-hub docker node ls
        ;;

    # ============== REMOVE WORKER ==============
    remove-worker|remove-external)
        if [ -z "$2" ]; then
            echo -e "${RED}Usage: $0 remove-worker <worker-name>${NC}"
            exit 1
        fi
        
        WORKER_NAME="$2"
        echo -e "${YELLOW}Removing worker: ${WORKER_NAME}${NC}"
        
        # Remove from WireGuard
        docker exec gridx-hub python hub.py remove-peer "$WORKER_NAME"
        
        # Try to remove from swarm (may fail if node is offline)
        NODE_ID=$(docker exec gridx-hub docker node ls --filter "name=${WORKER_NAME}" -q 2>/dev/null || true)
        if [ -n "$NODE_ID" ]; then
            docker exec gridx-hub docker node rm --force "$NODE_ID" 2>/dev/null || true
        fi
        
        echo -e "${GREEN}Worker ${WORKER_NAME} removed${NC}"
        ;;

    # ============== SERVE BUNDLES ==============
    serve)
        echo -e "${YELLOW}Starting HTTP server to serve worker bundles...${NC}"
        HOST_IP=$(get_host_ip)
        echo ""
        echo "Other machines can download bundles from:"
        echo "  http://${HOST_IP}:8000/"
        echo ""
        echo "Press Ctrl+C to stop"
        cd /tmp && python3 -m http.server 8000
        ;;

    # ============== SHELL ==============
    hub|shell-hub)
        docker exec -it gridx-hub bash
        ;;

    # ============== LOGS ==============
    logs)
        $COMPOSE logs -f
        ;;

    # ============== STOP ==============
    stop|down)
        echo -e "${YELLOW}Stopping containers...${NC}"
        $COMPOSE down
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    # ============== CLEAN ==============
    clean|reset)
        echo -e "${YELLOW}Removing containers and volumes...${NC}"
        $COMPOSE down -v
        echo -e "${GREEN}Cleaned!${NC}"
        ;;

    # ============== HELP ==============
    *)
        echo "Usage: $0 {command}"
        echo ""
        echo -e "${CYAN}Container Management:${NC}"
        echo "  start         - Build and start hub container"
        echo "  setup         - Initialize hub (WireGuard + Swarm)"
        echo "  stop          - Stop hub container"
        echo "  clean         - Remove container and volumes"
        echo ""
        echo -e "${CYAN}Status & Testing:${NC}"
        echo "  status        - Show hub and swarm status"
        echo "  ping-workers  - Check which worker agents are online"
        echo "  cluster       - Show cluster resources"
        echo "  test-job      - Run a simple test job"
        echo "  test-multi    - Run multi-replica job (test distribution)"
        echo "  test-gpu      - Run GPU detection job"
        echo "  jupyter       - Start a Jupyter notebook session"
        echo ""
        echo -e "${CYAN}Remote Execution:${NC}"
        echo "  exec <worker> \"cmd\"     - Execute command on a worker"
        echo ""
        echo -e "${CYAN}Worker Management:${NC}"
        echo "  add-external <name>     - Create bundle for external worker"
        echo "  remove-worker <name>    - Remove a worker"
        echo "  list-workers            - List all workers"
        echo "  serve                   - Start HTTP server to share bundles"
        echo ""
        echo -e "${CYAN}Shell Access:${NC}"
        echo "  hub           - Open shell in hub container"
        echo ""
        echo -e "${CYAN}Quick Start:${NC}"
        echo "  $0 start && sleep 10 && $0 setup"
        echo "  $0 add-external myworker"
        echo "  # Transfer bundle to worker machine and run: sudo ./join.sh"
        echo "  $0 ping-workers"
        echo ""
        ;;
esac
