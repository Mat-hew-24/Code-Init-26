# Dockerfile for Grid-X Node
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose ports for API and mesh communication
EXPOSE 8000 8468

# Default command
CMD ["python", "main.py"]