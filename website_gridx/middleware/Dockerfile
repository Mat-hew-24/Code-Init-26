FROM python:3.11-slim

WORKDIR /app

# Copy application code
COPY . .

# Expose port
EXPOSE 7575

# Run the middleware
CMD ["python", "middleware.py", "--port", "7575", "--backend", "http://backend:8000"]
