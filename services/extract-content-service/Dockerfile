FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy service-specific files
COPY services/extract-content-service/ .

# Copy shared library
COPY shared-lib/ /app/shared-lib/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /app/shared-storage /app/logs

# Start command (adjust the main file name as needed)
CMD ["python", "main.py"]