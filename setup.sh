#!/bin/bash

# Grid-X Setup Script
echo "============================================"
echo "         Grid-X Setup & Launch"
echo "============================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Pull required base images
echo "📦 Pulling required Docker images..."
docker pull python:3.9-slim
docker pull alpine:latest

echo "🔧 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "Choose how to run Grid-X:"
echo "1) Single node (development)"
echo "2) Multi-node mesh (using Docker Compose)"
echo "3) Run client to submit jobs"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "🚀 Starting single Grid-X node..."
        python main.py
        ;;
    2)
        echo "🚀 Starting Grid-X mesh with multiple nodes..."
        docker-compose up --build
        ;;
    3)
        echo "📤 Starting Grid-X client..."
        echo "Make sure at least one node is running first!"
        read -p "Press Enter to continue..."
        python client.py
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac