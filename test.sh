#!/bin/bash
# Grid-X Test Script - Cross-platform (Linux, macOS, Windows WSL2)
# Automates hub + worker setup in Docker containers

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "WSL2"
            else
                echo "Linux"
            fi
            ;;
        Darwin*)
            echo "macOS"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            echo "Windows"
            ;;
        *)
            echo "Unknown"
            ;;
    esac
}

OS_TYPE=$(detect_os)

# Platform-specific banner
echo -e "${BLUE}"
echo "=============================================="
echo "       GRID-X RESOURCE MESH"
echo "       Platform: ${OS_TYPE}"
echo "=============================================="
echo -e "${NC}"

# Check if running on native Windows (not WSL)
if [[ "$OS_TYPE" == "Windows" ]]; then
    echo -e "${RED}ERROR: This script must be run in WSL2, not native Windows${NC}"
    echo ""
    echo "Please do one of the following:"
    echo "  1. Install WSL2: https://docs.microsoft.com/en-us/windows/wsl/install"
    echo "  2. Run this script inside WSL2 Ubuntu"
    echo ""
    echo "Quick WSL2 setup:"
    echo "  wsl --install"
    echo "  wsl --set-default-version 2"
    echo ""
    exit 1
fi

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose not found${NC}"
    echo ""
    case "$OS_TYPE" in
        WSL2)
            echo "Install Docker Desktop for Windows with WSL2 integration:"
            echo "  https://docs.docker.com/desktop/windows/wsl/"
            ;;
        macOS)
            echo "Install Docker Desktop for Mac:"
            echo "  https://docs.docker.com/desktop/mac/install/"
            ;;
        Linux)
            echo "Install docker-compose:"
            echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
            echo "  sudo chmod +x /usr/local/bin/docker-compose"
            ;;
    esac
    echo ""
    exit 1
fi

# Get host's IP address (platform-aware)
get_host_ip() {
    case "$OS_TYPE" in
        WSL2)
            # In WSL2, get the Windows host IP for external access
            # Try to get WSL2's IP that's accessible from Windows
            hostname -I 2>/dev/null | awk '{print $1}' || \
            ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || \
            echo "172.17.0.1"
            ;;
        macOS)
            # macOS uses different network interface names
            ipconfig getifaddr en0 2>/dev/null || \
            ipconfig getifaddr en1 2>/dev/null || \
            ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1 || \
            echo "YOUR_IP"
            ;;
        Linux)
            # Standard Linux This was Earlier but we fixed it now for macos and WSL2
            ip route get 1 2>/dev/null | awk '{print $7; exit}' || \
            hostname -I 2>/dev/null | awk '{print $1}' || \
            echo "YOUR_IP"
            ;;
        *)
            echo "YOUR_IP"
            ;;
    esac
}

# Platform-specific dependency checks
check_dependencies() {
    local missing=0
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not installed${NC}"
        case "$OS_TYPE" in
            WSL2)
                echo "  Install Docker Desktop for Windows with WSL2 integration"
                echo "  https://docs.docker.com/desktop/windows/wsl/"
                ;;
            macOS)
                echo "  Install Docker Desktop for Mac"
                echo "  https://docs.docker.com/desktop/mac/install/"
                ;;
            Linux)
                echo "  Install Docker: curl -fsSL https://get.docker.com | sh"
                ;;
        esac
        missing=1
    else
        echo -e "${GREEN}✓ Docker${NC}"
    fi
    
    # Check Docker daemon
    if ! docker info &>/dev/null 2>&1; then
        echo -e "${RED}✗ Docker daemon not running${NC}"
        case "$OS_TYPE" in
            WSL2)
                echo "  Start Docker Desktop on Windows"
                ;;
            macOS)
                echo "  Start Docker Desktop"
                ;;
            Linux)
                echo "  Start Docker: sudo systemctl start docker"
                ;;
        esac
        missing=1
    else
        echo -e "${GREEN}✓ Docker daemon${NC}"
    fi
    
    # Check Python3
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}⚠ Python3 not found (needed for some commands)${NC}"
    else
        echo -e "${GREEN}✓ Python3${NC}"
    fi
    
    return $missing
}

case "$1" in
    # ============== CHECK ==============
    check|deps)
        echo -e "${YELLOW}Checking dependencies for ${OS_TYPE}...${NC}"
        echo ""
        if check_dependencies; then
            echo ""
            echo -e "${GREEN}All dependencies satisfied!${NC}"
        else
            echo ""
            echo -e "${RED}Please install missing dependencies${NC}"
            exit 1
        fi
        ;;

    # ============== START ==============
    start|up)
        echo -e "${YELLOW}Checking dependencies...${NC}"
        if ! check_dependencies; then
            exit 1
        fi
        echo ""
        
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
        echo ""
        ;;

    # ============== SETUP (AUTO) ==============
    setup|init)
        HOST_IP=$(get_host_ip)
        echo -e "${YELLOW}[1/2] Initializing Hub (Public IP: ${HOST_IP})...${NC}"
        
        if [[ "$OS_TYPE" == "macOS" ]]; then
            echo -e "${CYAN}Note: On macOS, Docker runs in a VM. Use 'host.docker.internal' for host access${NC}"
        elif [[ "$OS_TYPE" == "WSL2" ]]; then
            echo -e "${CYAN}Note: On WSL2, networking is bridged through Windows${NC}"
        fi
        
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
        echo -e "${YELLOW}=== PLATFORM: ${OS_TYPE} ===${NC}"
        echo ""
        echo -e "${YELLOW}=== HUB STATUS ===${NC}"
        docker exec gridx-hub python hub.py status

        echo -e "${YELLOW}=== SWARM NODES ===${NC}"
        docker exec gridx-hub docker node ls
        ;;

    # ============== TEST JOB ==============
    test-job|test)
        echo -e "${YELLOW}Running test job...${NC}"
        docker exec gridx-hub python jobs.py run alpine "echo 'Hello from Grid-X cluster on ${OS_TYPE}!'; hostname; sleep 5; echo 'Done!'"
        
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
        if [[ "$OS_TYPE" == "macOS" ]]; then
            echo -e "${YELLOW}Note: GPU passthrough not supported on macOS Docker${NC}"
        elif [[ "$OS_TYPE" == "WSL2" ]]; then
            echo -e "${YELLOW}Note: WSL2 supports GPU with NVIDIA CUDA on WSL2${NC}"
            echo "See: https://docs.nvidia.com/cuda/wsl-user-guide/index.html"
        fi
        
        echo -e "${YELLOW}Running GPU detection job...${NC}"
        docker exec gridx-hub python jobs.py run nvidia/cuda:12.0-base "nvidia-smi || echo 'No GPU available'" --gpus
        
        sleep 5
        echo ""
        echo -e "${YELLOW}Checking job logs...${NC}"
        docker exec gridx-hub python jobs.py list
        ;;

    # ============== CLUSTER INFO ==============
    cluster|info)
        echo -e "${YELLOW}=== CLUSTER INFO (${OS_TYPE}) ===${NC}"
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
# Grid-X Worker Join Script - Cross-platform
# Run this on the remote machine to join the cluster
# Supports: Linux, macOS, WSL2
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "WSL2"
            else
                echo "Linux"
            fi
            ;;
        Darwin*)
            echo "macOS"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            echo "Windows"
            ;;
        *)
            echo "Unknown"
            ;;
    esac
}

OS_TYPE=$(detect_os)

# Check if running on native Windows
if [[ "$OS_TYPE" == "Windows" ]]; then
    echo -e "${RED}ERROR: This script must be run in WSL2, not native Windows${NC}"
    echo "Please run inside WSL2 Ubuntu"
    exit 1
fi

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
echo "       Platform: ${OS_TYPE}"
echo "=============================================="
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo ./join.sh)${NC}"
    exit 1
fi

# ==================== SYSTEM INFO ====================
echo -e "${CYAN}[System Information]${NC}"

# Get total CPUs (cross-platform)
if command -v nproc &> /dev/null; then
    TOTAL_CPUS=$(nproc)
elif command -v sysctl &> /dev/null; then
    # macOS
    TOTAL_CPUS=$(sysctl -n hw.ncpu)
else
    TOTAL_CPUS=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo "1")
fi
echo "  Total CPUs: $TOTAL_CPUS"

# Get total RAM in GB (cross-platform)
if [[ "$OS_TYPE" == "macOS" ]]; then
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1024 / 1024 / 1024))
else
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
fi
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
    if [[ "$OS_TYPE" == "macOS" ]]; then
        echo "  GPUs:       Not supported on macOS Docker"
    else
        echo "  GPUs:       nvidia-smi not found (no NVIDIA GPU or drivers not installed)"
    fi
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

# GPU selection (if available and not macOS)
SHARE_GPUS=0
if [ "$GPU_COUNT" -gt 0 ] && [[ "$OS_TYPE" != "macOS" ]]; then
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
    case "$OS_TYPE" in
        macOS)
            echo "  brew install wireguard-tools"
            echo "Or download from: https://www.wireguard.com/install/"
            ;;
        WSL2|Linux)
            echo "  Arch:   sudo pacman -S wireguard-tools"
            echo "  Ubuntu: sudo apt install wireguard"
            echo "  Fedora: sudo dnf install wireguard-tools"
            ;;
    esac
    exit 1
fi
echo "  WireGuard: OK"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not installed!${NC}"
    echo ""
    case "$OS_TYPE" in
        macOS)
            echo "Install Docker Desktop for Mac:"
            echo "  https://docs.docker.com/desktop/mac/install/"
            ;;
        WSL2)
            echo "Install Docker Desktop for Windows with WSL2 integration:"
            echo "  https://docs.docker.com/desktop/windows/wsl/"
            ;;
        Linux)
            echo "Install from: https://docs.docker.com/get-docker/"
            echo "Or: curl -fsSL https://get.docker.com | sh"
            ;;
    esac
    exit 1
fi
echo "  Docker: OK"

# Check Docker is running
if ! docker info &>/dev/null; then
    echo -e "${RED}Docker daemon not running!${NC}"
    case "$OS_TYPE" in
        macOS|WSL2)
            echo "Start Docker Desktop"
            ;;
        Linux)
            echo "Start with: sudo systemctl start docker"
            ;;
    esac
    exit 1
fi
echo "  Docker daemon: OK"

# Check NVIDIA runtime (if GPUs selected)
if [ "$SHARE_GPUS" -gt 0 ]; then
    if docker info 2>/dev/null | grep -q nvidia; then
        echo "  NVIDIA runtime: OK"
    else
        echo -e "${YELLOW}  Warning: NVIDIA Docker runtime not detected${NC}"
        if [[ "$OS_TYPE" == "WSL2" ]]; then
            echo "  Install NVIDIA CUDA on WSL2: https://docs.nvidia.com/cuda/wsl-user-guide/"
        else
            echo "  Install nvidia-container-toolkit if needed."
        fi
    fi
fi

# ==================== SETUP WIREGUARD ====================
echo -e "${YELLOW}[2/5] Setting up WireGuard VPN...${NC}"

# Platform-specific WireGuard config location
if [[ "$OS_TYPE" == "macOS" ]]; then
    WG_CONFIG_DIR="/usr/local/etc/wireguard"
    mkdir -p "$WG_CONFIG_DIR"
else
    WG_CONFIG_DIR="/etc/wireguard"
fi

cp "$SCRIPT_DIR/wg0.conf" "$WG_CONFIG_DIR/wg0.conf"
chmod 600 "$WG_CONFIG_DIR/wg0.conf"

wg-quick down wg0 2>/dev/null || true
wg-quick up wg0

echo "  VPN interface: wg0"
if [[ "$OS_TYPE" == "macOS" ]]; then
    echo "  VPN IP: $(ifconfig wg0 2>/dev/null | grep 'inet ' | awk '{print $2}')"
else
    echo "  VPN IP: $(ip addr show wg0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)"
fi

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
    if [[ "$OS_TYPE" == "macOS" ]]; then
        echo "  4. On macOS, check System Preferences > Security & Privacy > Firewall"
    fi
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
OS_TYPE=$OS_TYPE
WORKER_NAME=$WORKER_NAME
SHARE_CPUS=$SHARE_CPUS
SHARE_RAM=$SHARE_RAM
SHARE_GPUS=$SHARE_GPUS
HUB_VPN_IP=$HUB_VPN_IP
JOINED_AT=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)
EOF

# ==================== SUCCESS ====================
echo ""
echo -e "${GREEN}=============================================="
echo "  SUCCESS! Joined Grid-X Cluster"
echo "  Platform: ${OS_TYPE}"
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
        sed -i.bak "s|__WORKER_NAME__|$WORKER_NAME|g" "${BUNDLE_DIR}/join.sh" && rm -f "${BUNDLE_DIR}/join.sh.bak"
        sed -i.bak "s|__SWARM_TOKEN__|$SWARM_TOKEN|g" "${BUNDLE_DIR}/join.sh" && rm -f "${BUNDLE_DIR}/join.sh.bak"
        
        chmod +x "${BUNDLE_DIR}/join.sh"
        
        # Create leave script
        cat > "${BUNDLE_DIR}/leave.sh" << 'LEAVEEOF'
#!/bin/bash
# Grid-X Worker Leave Script - Cross-platform
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
# Grid-X Worker Status Script - Cross-platform
echo "=== Grid-X Worker Status ==="
echo ""
echo "[Platform]"
case "$(uname -s)" in
    Linux*)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            echo "  OS: WSL2"
        else
            echo "  OS: Linux"
        fi
        ;;
    Darwin*)
        echo "  OS: macOS"
        ;;
    *)
        echo "  OS: Unknown"
        ;;
esac
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
        
        # Create README
        cat > "${BUNDLE_DIR}/README.md" << 'READMEEOF'
# Grid-X Worker Bundle

This bundle allows you to join a Grid-X compute cluster.

## Supported Platforms
- Linux (native)
- macOS (Darwin)
- Windows (via WSL2)

## Prerequisites

### Linux
```bash
sudo apt install wireguard docker.io  # Ubuntu/Debian
sudo pacman -S wireguard-tools docker  # Arch
```

### macOS
```bash
brew install wireguard-tools
# Install Docker Desktop for Mac
```

### Windows (WSL2)
1. Install WSL2: `wsl --install`
2. Install Docker Desktop with WSL2 integration
3. Run these scripts inside WSL2 Ubuntu

## Quick Start

```bash
# Extract the bundle
tar -xzf gridx-WORKERNAME.tar.gz
cd gridx-WORKERNAME

# Join the cluster (requires root/sudo)
sudo ./join.sh

# Check status
./status.sh

# Leave the cluster
sudo ./leave.sh
```

## What Gets Installed
- WireGuard VPN connection to the hub
- Docker Swarm worker node
- Command agent (Python service)

## Files Included
- `join.sh` - Interactive setup script
- `leave.sh` - Leave the cluster
- `status.sh` - Check connection status
- `wg0.conf` - WireGuard VPN configuration
- `worker.py` - Command agent (if available)

## Troubleshooting

### Cannot reach hub
1. Check your internet connection
2. Verify UDP port 51820 is not blocked by firewall
3. Check hub is running: ping 10.0.0.1 (after VPN is up)

### Docker errors
- Ensure Docker daemon is running
- On macOS/WSL2: Start Docker Desktop
- On Linux: `sudo systemctl start docker`

### VPN issues
- Check WireGuard is installed: `wg --version`
- View VPN status: `wg show`
- Restart VPN: `sudo wg-quick down wg0 && sudo wg-quick up wg0`

## Support
For issues, contact your Grid-X cluster administrator.
READMEEOF
        
        # Create tarball
        TARBALL="/tmp/gridx-${WORKER_NAME}.tar.gz"
        tar -czf "$TARBALL" -C /tmp "gridx-${WORKER_NAME}"
        
        echo ""
        echo -e "${GREEN}=============================================="
        echo "  EXTERNAL WORKER BUNDLE CREATED"
        echo "  Platform-compatible: Linux, macOS, WSL2"
        echo "==============================================${NC}"
        echo ""
        echo -e "${CYAN}Bundle location:${NC} ${TARBALL}"
        echo ""
        echo -e "${CYAN}Transfer to remote machine:${NC}"
        echo "  scp ${TARBALL} user@remote-host:~/"
        echo ""
        echo -e "${CYAN}On the remote machine run:${NC}"
        echo "  tar -xzf gridx-${WORKER_NAME}.tar.gz"
        echo "  cd gridx-${WORKER_NAME}"
        echo "  sudo ./join.sh"
        echo ""
        
        case "$OS_TYPE" in
            WSL2)
                WINDOWS_IP=$(ip route | grep default | awk '{print $3}')
                echo -e "${CYAN}Or serve via HTTP (WSL2):${NC}"
                echo "  cd /tmp && python3 -m http.server 8000"
                echo "  # Access from Windows: http://${WINDOWS_IP}:8000/"
                ;;
            macOS)
                echo -e "${CYAN}Or serve via HTTP (macOS):${NC}"
                echo "  cd /tmp && python3 -m http.server 8000"
                echo "  # Access: http://$(get_host_ip):8000/"
                ;;
            *)
                echo -e "${CYAN}Or serve via HTTP:${NC}"
                echo "  cd /tmp && python3 -m http.server 8000"
                echo "  # Remote: curl -O http://${HOST_IP}:8000/gridx-${WORKER_NAME}.tar.gz"
                ;;
        esac
        
        echo ""
        echo -e "${CYAN}Bundle contents:${NC}"
        echo "  README.md  - Platform-specific instructions"
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
        
        case "$OS_TYPE" in
            WSL2)
                WINDOWS_IP=$(ip route | grep default | awk '{print $3}')
                echo "Access from WSL2: http://${HOST_IP}:8000/"
                echo "Access from Windows: http://${WINDOWS_IP}:8000/"
                ;;
            *)
                echo "Other machines can download bundles from:"
                echo "  http://${HOST_IP}:8000/"
                ;;
        esac
        
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
    help|--help|-h)
        echo "Usage: $0 {command}"
        echo ""
        echo -e "${CYAN}Platform: ${OS_TYPE}${NC}"
        echo ""
        echo -e "${CYAN}Container Management:${NC}"
        echo "  check         - Check dependencies for your platform"
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
        echo "  $0 check"
        echo "  $0 start && sleep 10 && $0 setup"
        echo "  $0 add-external myworker"
        echo "  # Transfer bundle to worker machine and run: sudo ./join.sh"
        echo "  $0 ping-workers"
        echo ""
        echo -e "${CYAN}Platform Notes:${NC}"
        case "$OS_TYPE" in
            WSL2)
                echo "  - Running on WSL2 (Windows Subsystem for Linux)"
                echo "  - Docker Desktop integration required"
                echo "  - Network accessible from both WSL2 and Windows"
                ;;
            macOS)
                echo "  - Running on macOS"
                echo "  - Docker runs in a VM (limited GPU support)"
                echo "  - Use 'host.docker.internal' for host access"
                ;;
            Linux)
                echo "  - Running on native Linux"
                echo "  - Full Docker and GPU support"
                ;;
        esac
        echo ""
        ;;

    *)
        echo -e "${YELLOW}Unknown command: $1${NC}"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac