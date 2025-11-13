FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first (for better caching)
COPY shared-lib /app/shared-lib

# Copy service-specific files
COPY services/api-gateway-service /app/services/api-gateway-service

# Set working directory to the service
WORKDIR /app/services/api-gateway-service

RUN pip install --no-cache-dir /app/shared-lib
RUN pip install --no-cache-dir fastapi uvicorn redis python-dotenv pytest requests user_agents python-jose passlib[bcrypt] langgraph langgraph-sdk sqlalchemy psycopg2-binary pdfplumber python-multipart boto3

# Create necessary directories
RUN mkdir -p /app/shared-storage/raw \
    /app/shared-storage/processed \
    /app/shared-storage/transcoded \
    /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]