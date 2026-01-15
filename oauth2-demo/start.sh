#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   OAuth 2.0 Demo - Starting All Services${NC}"
echo -e "${BLUE}================================================${NC}"

# Navigate to script directory
cd "$(dirname "$0")"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    docker-compose down
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Stop any existing containers
echo -e "\n${YELLOW}Stopping existing containers...${NC}"
docker-compose down -v 2>/dev/null || true

# Build and start all services
echo -e "\n${YELLOW}Building and starting all services (this may take a few minutes on first run)...${NC}"
docker-compose up --build -d

# Wait for services to be healthy
echo -e "\n${YELLOW}Waiting for services to be ready...${NC}"

# Function to check if a service is healthy
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=60
    local attempt=1

    echo -n "  Waiting for $service_name"
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}Failed!${NC}"
    return 1
}

# Wait for PostgreSQL
echo -n "  Waiting for PostgreSQL"
until docker-compose exec -T postgres pg_isready -U oauth2user -d oauth2db > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e " ${GREEN}Ready!${NC}"

# Wait for Authorization Server
wait_for_service "Authorization Server" "http://localhost:9000/actuator/health"

# Wait for Resource Server
wait_for_service "Resource Server" "http://localhost:8080/actuator/health"

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}   All services are up and running!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  - Authorization Server: ${GREEN}http://localhost:9000${NC}"
echo -e "  - Resource Server:      ${GREEN}http://localhost:8080${NC}"
echo -e "  - PostgreSQL:           ${GREEN}localhost:5432${NC}"
echo ""
echo -e "${BLUE}Demo Credentials:${NC}"
echo -e "  - user / password     (USER role)"
echo -e "  - admin / password    (USER + ADMIN roles)"
echo ""
echo -e "${BLUE}Quick Test:${NC}"
echo -e "  # Get token (Client Credentials):"
echo -e "  curl -X POST http://localhost:9000/oauth2/token \\"
echo -e "    -H 'Content-Type: application/x-www-form-urlencoded' \\"
echo -e "    -H 'Authorization: Basic c2VydmljZS1jbGllbnQ6c2VjcmV0' \\"
echo -e "    -d 'grant_type=client_credentials&scope=read'"
echo ""
echo -e "  # Access protected resource:"
echo -e "  curl http://localhost:8080/api/public/info"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Show logs
docker-compose logs -f
