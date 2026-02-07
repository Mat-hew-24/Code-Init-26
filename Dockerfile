FROM docker:24-dind

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    wireguard-tools \
    iptables \
    ip6tables \
    iproute2 \
    bash \
    curl \
    net-tools \
    iputils \
    openssh-client \
    openrc \
    pciutils \
    && pip3 install --break-system-packages psutil

# Setup OpenRC (Alpine's init system)
RUN mkdir -p /run/openrc && touch /run/openrc/softlevel

# Create directories
RUN mkdir -p /etc/gridx /etc/wireguard /app

# Copy scripts
COPY hub.py /app/hub.py
COPY worker.py /app/worker.py
COPY jobs.py /app/jobs.py

WORKDIR /app

# Default command (will be overridden by compose)
CMD ["sh", "-c", "dockerd-entrypoint.sh & sleep 5 && tail -f /dev/null"]
