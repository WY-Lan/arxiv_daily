#!/bin/bash
# Deployment script - Run on ECS server

set -e

echo "=== Starting deployment of Arxiv Daily Push ==="

# Pull latest code
echo ">>> Pulling latest code..."
git pull origin main

# Rebuild and restart container
echo ">>> Rebuilding Docker image..."
docker-compose build

echo ">>> Restarting container..."
docker-compose down
docker-compose up -d

# Show status
echo ">>> Container status:"
docker-compose ps

# Show recent logs
echo ">>> Recent logs:"
docker-compose logs --tail=20

echo "=== Deployment completed ==="