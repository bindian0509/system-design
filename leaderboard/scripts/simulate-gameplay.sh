#!/bin/bash

# Simulate Gameplay - Continuously generates score updates
# Useful for demonstrating real-time leaderboard updates

set -e

BASE_URL="${BASE_URL:-http://localhost:8080}"
INTERVAL="${INTERVAL:-1}"  # seconds between score updates
DURATION="${DURATION:-60}" # total duration in seconds

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Real-Time Leaderboard - Gameplay Simulator         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Simulating gameplay for ${DURATION} seconds...${NC}"
echo -e "${YELLOW}Score updates every ${INTERVAL} second(s)${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

REGIONS=("US-EAST" "US-WEST" "EU-WEST" "EU-CENTRAL" "APAC" "LATAM")

# Track start time
START_TIME=$(date +%s)
UPDATE_COUNT=0

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED -ge $DURATION ]; then
        break
    fi

    # Random player (1-100)
    PLAYER_NUM=$((RANDOM % 100 + 1))
    PLAYER_ID="player_$(printf '%05d' $PLAYER_NUM)"

    # Random score increment (10-500)
    SCORE=$((RANDOM % 490 + 10))

    # Random region
    REGION_IDX=$((RANDOM % ${#REGIONS[@]}))
    REGION="${REGIONS[$REGION_IDX]}"

    # Submit score
    response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "${BASE_URL}/api/v1/scores" \
        -H "Content-Type: application/json" \
        -d "{
            \"playerId\": \"${PLAYER_ID}\",
            \"score\": ${SCORE},
            \"gameId\": \"gameplay-sim\",
            \"region\": \"${REGION}\",
            \"updateMode\": \"INCREMENT\"
        }" 2>/dev/null)

    ((UPDATE_COUNT++))

    if [ "$response" = "202" ]; then
        echo -e "[$(date +%H:%M:%S)] ${GREEN}✓${NC} ${PLAYER_ID} earned +${SCORE} points (${REGION})"
    else
        echo -e "[$(date +%H:%M:%S)] ${YELLOW}!${NC} Failed to update ${PLAYER_ID} (HTTP ${response})"
    fi

    sleep $INTERVAL
done

echo ""
echo -e "${GREEN}Simulation complete!${NC}"
echo -e "Total updates: ${UPDATE_COUNT}"
echo -e "Duration: ${DURATION} seconds"
