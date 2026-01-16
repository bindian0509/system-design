#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           OAuth 2.0 Demo - Spring Boot                    ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✔ $1${NC}"
}

print_error() {
    echo -e "${RED}✖ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1

    print_info "Waiting for $service_name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [ "$http_code" = "200" ]; then
            print_success "$service_name is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    print_error "$service_name failed to start within timeout"
    return 1
}

wait_for_postgres() {
    local max_attempts=${1:-20}
    local attempt=1

    print_info "Waiting for PostgreSQL to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if docker exec oauth2-postgres pg_isready -U oauth2user -d oauth2db > /dev/null 2>&1; then
            print_success "PostgreSQL is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    print_error "PostgreSQL failed to start within timeout"
    return 1
}

start_services() {
    print_header

    print_info "Building and starting all services..."
    docker-compose up -d --build

    echo ""
    print_info "Waiting for services to be healthy..."

    # Wait for PostgreSQL
    wait_for_postgres 20

    # Wait for Authorization Server
    wait_for_service "Authorization Server" "http://localhost:9001/actuator/health" 60

    # Wait for Resource Server
    wait_for_service "Resource Server" "http://localhost:8080/actuator/health" 60

    echo ""
    print_success "All services are up and running!"
    echo ""
    show_info
}

stop_services() {
    print_info "Stopping all services..."
    docker-compose down
    print_success "All services stopped"
}

restart_services() {
    stop_services
    echo ""
    start_services
}

show_logs() {
    docker-compose logs -f
}

show_status() {
    echo ""
    print_info "Service Status:"
    echo ""
    docker-compose ps
    echo ""

    # Health checks
    echo -e "${BLUE}Health Checks:${NC}"

    if curl -s http://localhost:9001/actuator/health > /dev/null 2>&1; then
        print_success "Authorization Server (http://localhost:9001) - Healthy"
    else
        print_error "Authorization Server (http://localhost:9001) - Not responding"
    fi

    if curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
        print_success "Resource Server (http://localhost:8080) - Healthy"
    else
        print_error "Resource Server (http://localhost:8080) - Not responding"
    fi
}

clean_all() {
    print_info "Stopping services and removing volumes..."
    docker-compose down -v --remove-orphans
    print_success "Cleanup complete"
}

show_info() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Services:${NC}"
    echo "  • Authorization Server: http://localhost:9001"
    echo "  • Resource Server:      http://localhost:8080"
    echo "  • PostgreSQL:           localhost:5432"
    echo ""
    echo -e "${GREEN}Demo Credentials:${NC}"
    echo "  • User:  user / password  (USER role)"
    echo "  • Admin: admin / password (USER + ADMIN roles)"
    echo ""
    echo -e "${GREEN}OAuth Clients:${NC}"
    echo "  • web-client     (secret: secret) - Authorization Code"
    echo "  • spa-client     (public)         - Authorization Code + PKCE"
    echo "  • service-client (secret: service-secret) - Client Credentials"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

run_tests() {
    echo ""
    print_info "Running OAuth 2.0 Flow Tests..."
    echo ""

    # Test 1: Public endpoint
    echo -e "${YELLOW}Test 1: Public Endpoint${NC}"
    curl -s http://localhost:8080/api/public/health | jq . 2>/dev/null || curl -s http://localhost:8080/api/public/health
    echo ""

    # Test 2: Client Credentials Flow
    echo -e "${YELLOW}Test 2: Client Credentials Flow${NC}"
    TOKEN_RESPONSE=$(curl -s -X POST http://localhost:9001/oauth2/token \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -H "Authorization: Basic c2VydmljZS1jbGllbnQ6c2VydmljZS1zZWNyZXQ=" \
        -d "grant_type=client_credentials&scope=read write")

    echo "$TOKEN_RESPONSE" | jq . 2>/dev/null || echo "$TOKEN_RESPONSE"

    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token' 2>/dev/null)

    if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
        echo ""
        echo -e "${YELLOW}Test 3: Access Protected Resource with Token${NC}"
        curl -s http://localhost:8080/api/protected \
            -H "Authorization: Bearer $ACCESS_TOKEN" | jq . 2>/dev/null || \
        curl -s http://localhost:8080/api/protected \
            -H "Authorization: Bearer $ACCESS_TOKEN"
        echo ""
        print_success "All tests passed!"
    else
        print_error "Failed to get access token"
    fi

    echo ""
    echo -e "${YELLOW}Interactive Authorization Code Flow:${NC}"
    echo "Open in browser: http://localhost:9001/oauth2/authorize?response_type=code&client_id=web-client&redirect_uri=http://localhost:3000/callback&scope=openid%20profile%20read"
    echo ""
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start   - Build and start all services (default)"
    echo "  stop    - Stop all services"
    echo "  restart - Restart all services"
    echo "  logs    - Show service logs"
    echo "  status  - Show service status"
    echo "  clean   - Stop services and remove volumes"
    echo "  test    - Run OAuth flow tests"
    echo "  info    - Show connection info"
    echo "  help    - Show this help message"
    echo ""
}

# Main
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
    info)
        show_info
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
