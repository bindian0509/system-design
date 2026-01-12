#!/bin/bash

# Demo Data Script for Real-Time Leaderboard
# This script populates the leaderboard with sample players and scores

set -e

BASE_URL="${BASE_URL:-http://localhost:8080}"
NUM_PLAYERS="${NUM_PLAYERS:-100}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Real-Time Leaderboard - Demo Data Generator          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if the server is running
echo -e "${YELLOW}Checking server health...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}Error: Server is not running at ${BASE_URL}${NC}"
    echo -e "${YELLOW}Please start the server first with: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Server is healthy${NC}"
echo ""

# Player names for demo
FIRST_NAMES=("Alex" "Jordan" "Taylor" "Morgan" "Casey" "Riley" "Quinn" "Avery" "Blake" "Cameron"
             "Drew" "Emery" "Finley" "Gray" "Harper" "Indigo" "Jules" "Kai" "Lane" "Max"
             "Nova" "Oakley" "Parker" "Phoenix" "Reese" "Sage" "Skyler" "Storm" "Tatum" "Winter"
             "Zion" "Ash" "Blue" "Charlie" "Dakota" "Eden" "Flynn" "Harley" "Jaden" "Kennedy")

LAST_NAMES=("Smith" "Johnson" "Williams" "Brown" "Jones" "Garcia" "Miller" "Davis" "Rodriguez" "Martinez"
            "Hernandez" "Lopez" "Gonzalez" "Wilson" "Anderson" "Thomas" "Taylor" "Moore" "Jackson" "Martin"
            "Lee" "Perez" "Thompson" "White" "Harris" "Sanchez" "Clark" "Ramirez" "Lewis" "Robinson")

REGIONS=("US-EAST" "US-WEST" "EU-WEST" "EU-CENTRAL" "APAC" "LATAM")

# Function to generate random player name
generate_name() {
    local first_idx=$((RANDOM % ${#FIRST_NAMES[@]}))
    local last_idx=$((RANDOM % ${#LAST_NAMES[@]}))
    echo "${FIRST_NAMES[$first_idx]}${LAST_NAMES[$last_idx]}${RANDOM:0:3}"
}

# Function to generate random region
generate_region() {
    local idx=$((RANDOM % ${#REGIONS[@]}))
    echo "${REGIONS[$idx]}"
}

# Function to generate random score (between 100 and 50000)
generate_score() {
    echo $((RANDOM % 49900 + 100))
}

echo -e "${YELLOW}Creating ${NUM_PLAYERS} sample players...${NC}"
echo ""

# Create players
declare -a PLAYER_IDS
for i in $(seq 1 $NUM_PLAYERS); do
    PLAYER_ID="player_$(printf '%05d' $i)"
    PLAYER_NAME=$(generate_name)
    REGION=$(generate_region)

    # Create player
    response=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/players" \
        -H "Content-Type: application/json" \
        -d "{
            \"playerId\": \"${PLAYER_ID}\",
            \"displayName\": \"${PLAYER_NAME}\",
            \"region\": \"${REGION}\"
        }" 2>/dev/null)

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        PLAYER_IDS+=("$PLAYER_ID:$REGION")
        if [ $((i % 10)) -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} Created $i players..."
        fi
    fi
done

echo -e "${GREEN}✓ Created ${#PLAYER_IDS[@]} players${NC}"
echo ""

echo -e "${YELLOW}Submitting scores for players...${NC}"
echo ""

# Submit initial scores for all players
score_count=0
for player_data in "${PLAYER_IDS[@]}"; do
    PLAYER_ID="${player_data%%:*}"
    REGION="${player_data##*:}"
    SCORE=$(generate_score)

    response=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/scores" \
        -H "Content-Type: application/json" \
        -d "{
            \"playerId\": \"${PLAYER_ID}\",
            \"score\": ${SCORE},
            \"gameId\": \"demo-game-001\",
            \"region\": \"${REGION}\",
            \"updateMode\": \"SET\"
        }" 2>/dev/null)

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "202" ] || [ "$http_code" = "200" ]; then
        ((score_count++))
        if [ $((score_count % 20)) -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} Submitted $score_count scores..."
        fi
    fi
done

echo -e "${GREEN}✓ Submitted $score_count initial scores${NC}"
echo ""

# Create some top players with high scores
echo -e "${YELLOW}Creating elite players with high scores...${NC}"

ELITE_PLAYERS=(
    "ProGamer2024:50000:US-EAST"
    "ChampionX:48500:EU-WEST"
    "LegendaryPlayer:47200:APAC"
    "MasterBlaster:45800:US-WEST"
    "NinjaWarrior:44100:EU-CENTRAL"
    "DragonSlayer:42500:US-EAST"
    "PhoenixRising:41200:LATAM"
    "ShadowStrike:39800:EU-WEST"
    "ThunderBolt:38500:APAC"
    "IceQueen:37200:US-EAST"
)

for elite in "${ELITE_PLAYERS[@]}"; do
    IFS=':' read -r NAME SCORE REGION <<< "$elite"
    PLAYER_ID="elite_$(echo "$NAME" | tr '[:upper:]' '[:lower:]')"

    # Create elite player
    curl -s -X POST "${BASE_URL}/api/v1/players" \
        -H "Content-Type: application/json" \
        -d "{
            \"playerId\": \"${PLAYER_ID}\",
            \"displayName\": \"${NAME}\",
            \"region\": \"${REGION}\"
        }" > /dev/null 2>&1

    # Submit elite score
    curl -s -X POST "${BASE_URL}/api/v1/scores" \
        -H "Content-Type: application/json" \
        -d "{
            \"playerId\": \"${PLAYER_ID}\",
            \"score\": ${SCORE},
            \"gameId\": \"demo-game-001\",
            \"region\": \"${REGION}\",
            \"updateMode\": \"SET\"
        }" > /dev/null 2>&1

    echo -e "  ${GREEN}✓${NC} Created elite player: ${NAME} (Score: ${SCORE})"
done

echo ""

# Add some friend relationships for demo
echo -e "${YELLOW}Creating friend relationships...${NC}"

# Make first 5 players friends with each other
for i in $(seq 1 5); do
    PLAYER_ID="player_$(printf '%05d' $i)"
    for j in $(seq 1 5); do
        if [ $i -ne $j ]; then
            FRIEND_ID="player_$(printf '%05d' $j)"
            curl -s -X POST "${BASE_URL}/api/v1/leaderboard/friends/${PLAYER_ID}/add/${FRIEND_ID}" > /dev/null 2>&1
        fi
    done
done
echo -e "${GREEN}✓ Created friend relationships for demo players${NC}"
echo ""

# Wait for score processing
echo -e "${YELLOW}Waiting for score processing (3 seconds)...${NC}"
sleep 3

# Display results
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Demo data generation complete!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}Fetching Top 10 Leaderboard:${NC}"
echo ""
curl -s "${BASE_URL}/api/v1/leaderboard/top?scope=GLOBAL&period=DAILY&limit=10" | \
    python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('╔════╦════════════════════════╦════════════╗')
    print('║ #  ║ Player                 ║ Score      ║')
    print('╠════╬════════════════════════╬════════════╣')
    for entry in data.get('entries', []):
        rank = entry.get('rank', '-')
        name = entry.get('playerName', entry.get('playerId', 'Unknown'))[:20]
        score = entry.get('score', 0)
        print(f'║ {rank:<2} ║ {name:<22} ║ {score:>10} ║')
    print('╚════╩════════════════════════╩════════════╝')
    print(f\"Total players: {data.get('totalPlayers', 0)}\")
except:
    print('Could not parse response')
" 2>/dev/null || echo "(Install python3 for formatted output)"

echo ""
echo -e "${YELLOW}Try these API endpoints:${NC}"
echo ""
echo "  # Get top 10 players"
echo "  curl '${BASE_URL}/api/v1/leaderboard/top?scope=GLOBAL&period=DAILY&limit=10'"
echo ""
echo "  # Get a player's rank"
echo "  curl '${BASE_URL}/api/v1/leaderboard/rank/elite_progamer2024?scope=GLOBAL&period=DAILY'"
echo ""
echo "  # Get surrounding players"
echo "  curl '${BASE_URL}/api/v1/leaderboard/around/player_00050?scope=GLOBAL&period=DAILY&range=5'"
echo ""
echo "  # Get friend leaderboard"
echo "  curl '${BASE_URL}/api/v1/leaderboard/friends/player_00001?period=DAILY'"
echo ""
echo "  # Submit a new score"
echo "  curl -X POST '${BASE_URL}/api/v1/scores' -H 'Content-Type: application/json' \\"
echo "       -d '{\"playerId\":\"player_00001\",\"score\":1000,\"region\":\"US-EAST\"}'"
echo ""
echo -e "${GREEN}Happy demo!${NC}"
