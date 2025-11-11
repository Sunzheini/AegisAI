FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library
COPY shared-lib /app/shared-lib

# Copy service-specific files
COPY services/ai-service /app/services/ai-service

# Set working directory to the service
WORKDIR /app/services/ai-service

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /app/shared-storage/raw \
    /app/shared-storage/processed \
    /app/shared-storage/transcoded \
    /app/logs

# Start the service (adjust entry point as needed)
CMD ["python", "main.py"]