#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping OAuth 2.0 Demo services...${NC}"

cd "$(dirname "$0")"

docker-compose down

echo -e "${GREEN}All services stopped.${NC}"
