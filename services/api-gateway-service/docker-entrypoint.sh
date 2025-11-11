#!/bin/bash
set -e

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done

# Wait for Redis
echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 1
done

echo "All dependencies are ready - starting service..."

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port 8000