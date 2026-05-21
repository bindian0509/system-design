#!/bin/bash
# Build and push Docker images

set -e

REGISTRY=${REGISTRY:-"localhost:5000"}
VERSION=${VERSION:-"latest"}

echo "Building Docker images..."

# Build API image
echo "Building scheduler-api:$VERSION..."
docker build -t "$REGISTRY/scheduler-api:$VERSION" -f Dockerfile.api .

# Build Worker image
echo "Building scheduler-worker:$VERSION..."
docker build -t "$REGISTRY/scheduler-worker:$VERSION" -f Dockerfile.worker .

# Build Scheduler image
echo "Building scheduler-cron:$VERSION..."
docker build -t "$REGISTRY/scheduler-cron:$VERSION" -f Dockerfile.scheduler .

echo "Build complete!"
echo ""
echo "Images built:"
echo "  - $REGISTRY/scheduler-api:$VERSION"
echo "  - $REGISTRY/scheduler-worker:$VERSION"
echo "  - $REGISTRY/scheduler-cron:$VERSION"
echo ""
echo "To push to registry:"
echo "  docker push $REGISTRY/scheduler-api:$VERSION"
echo "  docker push $REGISTRY/scheduler-worker:$VERSION"
echo "  docker push $REGISTRY/scheduler-cron:$VERSION"
