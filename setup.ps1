# Grid-X Setup Script for Windows
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "         Grid-X Setup & Launch" -ForegroundColor Cyan  
Write-Host "============================================" -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Pull required base images  
Write-Host "📦 Pulling required Docker images..." -ForegroundColor Yellow
docker pull python:3.9-slim
docker pull alpine:latest

Write-Host "🔧 Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "Choose how to run Grid-X:" -ForegroundColor White
Write-Host "1) Single node (development)" -ForegroundColor White
Write-Host "2) Multi-node mesh (using Docker Compose)" -ForegroundColor White  
Write-Host "3) Run client to submit jobs" -ForegroundColor White

$choice = Read-Host "Enter choice (1-3)"

switch ($choice) {
    1 {
        Write-Host "🚀 Starting single Grid-X node..." -ForegroundColor Green
        python main.py
    }
    2 {
        Write-Host "🚀 Starting Grid-X mesh with multiple nodes..." -ForegroundColor Green
        docker-compose up --build
    }
    3 {
        Write-Host "📤 Starting Grid-X client..." -ForegroundColor Green
        Write-Host "Make sure at least one node is running first!" -ForegroundColor Yellow
        Read-Host "Press Enter to continue..."
        python client.py
    }
    default {
        Write-Host "❌ Invalid choice" -ForegroundColor Red
        exit 1
    }
}