#!/bin/bash

# OAuth 2.0 Demo - Docker Runner Script
# Usage: ./run.sh [command]
# Commands: start, stop, restart, logs, status, clean, test

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           OAuth 2.0 Demo - Spring Boot                       ║"
    echo "║   Authorization Server (9000) + Resource Server (8080)       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=60
    local attempt=1

    echo -n "    Waiting for $service_name"
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

start_services() {
    print_header
    print_info "Starting OAuth 2.0 Demo services..."
    echo ""

    # Build and start all services
    print_info "Building Docker images (this may take a few minutes on first run)..."
    docker-compose build --parallel

    print_info "Starting services..."
    docker-compose up -d

    echo ""
    print_info "Waiting for services to be healthy..."

    # Wait for PostgreSQL
    echo -n "    Waiting for PostgreSQL"
    until docker-compose exec -T postgres pg_isready -U oauth2user -d oauth2db > /dev/null 2>&1; do
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}Ready!${NC}"

    # Wait for Authorization Server
    wait_for_service "Authorization Server" "http://localhost:9000/actuator/health"

    # Wait for Resource Server
    wait_for_service "Resource Server" "http://localhost:8080/actuator/health"

    echo ""
    print_status "All services are up and running!"
    echo ""
    print_connection_info
}

stop_services() {
    print_info "Stopping all services..."
    docker-compose down
    print_status "All services stopped."
}

restart_services() {
    print_info "Restarting all services..."
    docker-compose down
    start_services
}

show_logs() {
    docker-compose logs -f
}

show_status() {
    print_header
    echo -e "${BLUE}Service Status:${NC}"
    echo ""
    docker-compose ps
    echo ""

    # Check health endpoints
    echo -e "${BLUE}Health Checks:${NC}"
    echo ""

    # PostgreSQL
    if docker-compose exec -T postgres pg_isready -U oauth2user -d oauth2db > /dev/null 2>&1; then
        print_status "PostgreSQL:          http://localhost:5432 (healthy)"
    else
        print_error "PostgreSQL:          http://localhost:5432 (unhealthy)"
    fi

    # Authorization Server
    if curl -s http://localhost:9000/actuator/health | grep -q '"status":"UP"' 2>/dev/null; then
        print_status "Authorization Server: http://localhost:9000 (healthy)"
    else
        print_error "Authorization Server: http://localhost:9000 (unhealthy)"
    fi

    # Resource Server
    if curl -s http://localhost:8080/actuator/health | grep -q '"status":"UP"' 2>/dev/null; then
        print_status "Resource Server:      http://localhost:8080 (healthy)"
    else
        print_error "Resource Server:      http://localhost:8080 (unhealthy)"
    fi
}

clean_all() {
    print_warning "This will stop all services and remove all data (including database)."
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping services and cleaning up..."
        docker-compose down -v --remove-orphans
        docker-compose rm -f
        print_status "Cleanup complete."
    else
        print_info "Cleanup cancelled."
    fi
}

print_connection_info() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Connection Information:${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Authorization Server: http://localhost:9000"
    echo "  Resource Server:      http://localhost:8080"
    echo "  PostgreSQL:           localhost:5432"
    echo ""
    echo -e "${BLUE}Demo Users:${NC}"
    echo "  user  / password  (USER role)"
    echo "  admin / password  (USER + ADMIN roles)"
    echo ""
    echo -e "${BLUE}OAuth Clients:${NC}"
    echo "  web-client     / secret  (Authorization Code)"
    echo "  spa-client     / (none)  (Authorization Code + PKCE)"
    echo "  service-client / secret  (Client Credentials)"
    echo ""
    echo -e "${BLUE}Quick Test Commands:${NC}"
    echo ""
    echo "  # Test public endpoint (no auth)"
    echo "  curl http://localhost:8080/api/public/info"
    echo ""
    echo "  # Get token via Client Credentials"
    echo "  curl -X POST http://localhost:9000/oauth2/token \\"
    echo "    -H 'Content-Type: application/x-www-form-urlencoded' \\"
    echo "    -H 'Authorization: Basic c2VydmljZS1jbGllbnQ6c2VjcmV0' \\"
    echo "    -d 'grant_type=client_credentials&scope=read'"
    echo ""
    echo "  # Access protected resource (replace TOKEN)"
    echo "  curl http://localhost:8080/api/protected \\"
    echo "    -H 'Authorization: Bearer TOKEN'"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

run_tests() {
    print_header
    print_info "Running OAuth 2.0 flow tests..."
    echo ""

    # Test 1: Public endpoint
    echo -e "${BLUE}Test 1: Public endpoint (no auth required)${NC}"
    response=$(curl -s http://localhost:8080/api/public/info)
    if echo "$response" | grep -q "OAuth 2.0 Resource Server"; then
        print_status "Public endpoint working"
        echo "  Response: $(echo $response | head -c 100)..."
    else
        print_error "Public endpoint failed"
    fi
    echo ""

    # Test 2: Client Credentials flow
    echo -e "${BLUE}Test 2: Client Credentials flow${NC}"
    token_response=$(curl -s -X POST http://localhost:9000/oauth2/token \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -H "Authorization: Basic c2VydmljZS1jbGllbnQ6c2VjcmV0" \
        -d "grant_type=client_credentials&scope=read")

    if echo "$token_response" | grep -q "access_token"; then
        print_status "Token obtained successfully"
        access_token=$(echo "$token_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
        echo "  Token: ${access_token:0:50}..."

        # Test 3: Protected resource with token
        echo ""
        echo -e "${BLUE}Test 3: Protected resource with token${NC}"
        protected_response=$(curl -s http://localhost:8080/api/protected \
            -H "Authorization: Bearer $access_token")

        if echo "$protected_response" | grep -q "successfully accessed"; then
            print_status "Protected resource accessible with token"
            echo "  Response: $(echo $protected_response | head -c 100)..."
        else
            print_error "Protected resource access failed"
            echo "  Response: $protected_response"
        fi
    else
        print_error "Failed to obtain token"
        echo "  Response: $token_response"
    fi

    echo ""
    print_status "Tests completed!"
}

show_help() {
    print_header
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     Start all services (default)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      Show service logs (follow mode)"
    echo "  status    Show service status and health"
    echo "  clean     Stop services and remove all data"
    echo "  test      Run OAuth flow tests"
    echo "  help      Show this help message"
    echo ""
}

# Main command handler
case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    clean)
        clean_all
        ;;
    test)
        run_tests
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
