#!/bin/bash

# Load Test Script for Leaderboard
# Tests throughput and latency under load

set -e

BASE_URL="${BASE_URL:-http://localhost:8080}"
CONCURRENT="${CONCURRENT:-10}"
REQUESTS="${REQUESTS:-1000}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Real-Time Leaderboard - Load Test                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if ab (Apache Benchmark) is available
if ! command -v ab &> /dev/null; then
    echo -e "${RED}Error: Apache Benchmark (ab) is not installed${NC}"
    echo "Install with: brew install httpd (macOS) or apt install apache2-utils (Linux)"
    exit 1
fi

# Check server health
echo -e "${YELLOW}Checking server health...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}Error: Server is not running at ${BASE_URL}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Server is healthy${NC}"
echo ""

# Test 1: Read Performance (Top 10 Query)
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Test 1: Top 10 Leaderboard Query (READ)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo "Concurrent: ${CONCURRENT}, Total Requests: ${REQUESTS}"
echo ""

ab -n $REQUESTS -c $CONCURRENT -q \
   "${BASE_URL}/api/v1/leaderboard/top?scope=GLOBAL&period=DAILY&limit=10" 2>/dev/null | \
   grep -E "(Requests per second|Time per request|Failed requests|50%|95%|99%)"

echo ""

# Test 2: Read Performance (Player Rank)
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Test 2: Player Rank Query (READ)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo "Concurrent: ${CONCURRENT}, Total Requests: ${REQUESTS}"
echo ""

ab -n $REQUESTS -c $CONCURRENT -q \
   "${BASE_URL}/api/v1/leaderboard/rank/player_00050?scope=GLOBAL&period=DAILY" 2>/dev/null | \
   grep -E "(Requests per second|Time per request|Failed requests|50%|95%|99%)"

echo ""

# Test 3: Write Performance (Score Submission)
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Test 3: Score Submission (WRITE)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo "Concurrent: ${CONCURRENT}, Total Requests: $((REQUESTS / 2))"
echo ""

# Create temp file with POST data
TMPFILE=$(mktemp)
echo '{"playerId":"loadtest_player","score":100,"region":"US-EAST","updateMode":"INCREMENT"}' > $TMPFILE

ab -n $((REQUESTS / 2)) -c $CONCURRENT -q \
   -p $TMPFILE -T "application/json" \
   "${BASE_URL}/api/v1/scores" 2>/dev/null | \
   grep -E "(Requests per second|Time per request|Failed requests|50%|95%|99%)"

rm -f $TMPFILE

echo ""
echo -e "${GREEN}Load test complete!${NC}"
