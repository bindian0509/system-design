# API Reference

## Base URL

```
Local:      http://localhost:8080
Production: https://api.yourdomain.com
```

## Endpoints

### Score Submission

#### Submit Score (Async)

Submits a score for asynchronous processing.

```http
POST /api/v1/scores
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `playerId` | string | Yes | Unique player identifier |
| `score` | long | Yes | Score value (non-negative) |
| `gameId` | string | No | Game identifier |
| `region` | string | No | Player's region (e.g., "US-EAST") |
| `updateMode` | enum | No | INCREMENT, MAX, or SET (default: INCREMENT) |
| `metadata` | string | No | Additional metadata (JSON) |

**Example:**

```json
{
  "playerId": "player123",
  "score": 1500,
  "gameId": "battle-royale-123",
  "region": "US-EAST",
  "updateMode": "INCREMENT"
}
```

**Response (202 Accepted):**

```json
{
  "eventId": "evt_a1b2c3d4",
  "status": "QUEUED",
  "receivedAt": "2026-01-12T10:30:00Z",
  "message": "Score event queued for processing"
}
```

---

### Leaderboard Queries

#### Get Top Players

Returns the top N players from a leaderboard.

```http
GET /api/v1/leaderboard/top
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | enum | GLOBAL | GLOBAL, REGIONAL, or FRIENDS |
| `period` | enum | DAILY | DAILY, WEEKLY, MONTHLY, ROLLING_1H, ROLLING_24H, ALL_TIME |
| `region` | string | null | Required for REGIONAL scope |
| `limit` | int | 10 | Number of entries (max 100) |

**Example:**

```http
GET /api/v1/leaderboard/top?scope=GLOBAL&period=DAILY&limit=10
```

**Response (200 OK):**

```json
{
  "scope": "GLOBAL",
  "period": "DAILY",
  "region": null,
  "asOf": "2026-01-12T10:30:00Z",
  "periodIdentifier": "2026-01-12",
  "entries": [
    {
      "rank": 1,
      "playerId": "player001",
      "playerName": "ProGamer",
      "avatarUrl": "https://cdn.example.com/avatars/player001.png",
      "score": 50000,
      "region": "US-EAST",
      "isRequester": false
    },
    {
      "rank": 2,
      "playerId": "player002",
      "playerName": "Champion",
      "avatarUrl": null,
      "score": 48500,
      "region": "EU-WEST",
      "isRequester": false
    }
  ],
  "totalPlayers": 5000000,
  "hasMore": true
}
```

---

#### Get Player Rank

Returns a specific player's rank and score.

```http
GET /api/v1/leaderboard/rank/{playerId}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `playerId` | string | Player's unique identifier |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | enum | GLOBAL | GLOBAL or REGIONAL |
| `period` | enum | DAILY | Time window |
| `region` | string | null | For REGIONAL scope |

**Example:**

```http
GET /api/v1/leaderboard/rank/player123?scope=GLOBAL&period=DAILY
```

**Response (200 OK):**

```json
{
  "playerId": "player123",
  "playerName": "CasualGamer",
  "rank": 1234567,
  "score": 2500,
  "percentile": 97.53,
  "totalPlayers": 50000000,
  "scope": "GLOBAL",
  "period": "DAILY",
  "region": null,
  "asOf": "2026-01-12T10:30:00Z"
}
```

**Error Response (404 Not Found):**

```json
{
  "code": "PLAYER_NOT_FOUND",
  "message": "Player player123 not found in GLOBAL/DAILY leaderboard",
  "status": 404,
  "timestamp": "2026-01-12T10:30:00Z"
}
```

---

#### Get Surrounding Players

Returns players ranked around a specific player.

```http
GET /api/v1/leaderboard/around/{playerId}
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | enum | GLOBAL | Leaderboard scope |
| `period` | enum | DAILY | Time window |
| `region` | string | null | For REGIONAL scope |
| `range` | int | 5 | Players above and below (max 50) |

**Example:**

```http
GET /api/v1/leaderboard/around/player123?scope=GLOBAL&period=DAILY&range=5
```

**Response (200 OK):**

```json
{
  "playerId": "player123",
  "playerRank": 1000,
  "playerScore": 2500,
  "entries": [
    {"rank": 995, "playerId": "p995", "playerName": "User995", "score": 2510, "isRequester": false},
    {"rank": 996, "playerId": "p996", "playerName": "User996", "score": 2508, "isRequester": false},
    {"rank": 997, "playerId": "p997", "playerName": "User997", "score": 2506, "isRequester": false},
    {"rank": 998, "playerId": "p998", "playerName": "User998", "score": 2504, "isRequester": false},
    {"rank": 999, "playerId": "p999", "playerName": "User999", "score": 2502, "isRequester": false},
    {"rank": 1000, "playerId": "player123", "playerName": "CasualGamer", "score": 2500, "isRequester": true},
    {"rank": 1001, "playerId": "p1001", "playerName": "User1001", "score": 2498, "isRequester": false},
    {"rank": 1002, "playerId": "p1002", "playerName": "User1002", "score": 2496, "isRequester": false},
    {"rank": 1003, "playerId": "p1003", "playerName": "User1003", "score": 2494, "isRequester": false},
    {"rank": 1004, "playerId": "p1004", "playerName": "User1004", "score": 2492, "isRequester": false},
    {"rank": 1005, "playerId": "p1005", "playerName": "User1005", "score": 2490, "isRequester": false}
  ],
  "scope": "GLOBAL",
  "period": "DAILY",
  "region": null,
  "asOf": "2026-01-12T10:30:00Z",
  "totalPlayers": 50000000
}
```

---

### Friend Leaderboard

#### Get Friend Leaderboard

```http
GET /api/v1/leaderboard/friends/{playerId}
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | enum | DAILY | Time window |
| `limit` | int | 10 | Number of entries |

**Response (200 OK):**

```json
{
  "scope": "FRIENDS",
  "period": "DAILY",
  "entries": [
    {"rank": 1, "playerId": "friend1", "playerName": "BestFriend", "score": 5000, "isRequester": false},
    {"rank": 2, "playerId": "player123", "playerName": "Me", "score": 2500, "isRequester": true},
    {"rank": 3, "playerId": "friend2", "playerName": "AnotherFriend", "score": 2000, "isRequester": false}
  ],
  "totalPlayers": 25
}
```

---

### Historical Data

#### Get Historical Leaderboard

```http
GET /api/v1/leaderboard/history/{periodId}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `periodId` | string | Period identifier (e.g., "2026-01-10") |

**Example:**

```http
GET /api/v1/leaderboard/history/2026-01-10?scope=GLOBAL&period=DAILY
```

---

### Health Endpoints

#### Liveness Probe

```http
GET /health
```

**Response:**

```json
{
  "status": "ok",
  "timestamp": "2026-01-12T10:30:00Z"
}
```

#### Readiness Probe

```http
GET /ready
```

**Response:**

```json
{
  "status": "ready",
  "components": {
    "redis": {"status": "healthy", "details": "PONG received"},
    "websocket": {"status": "healthy", "details": "42 active connections"}
  },
  "timestamp": "2026-01-12T10:30:00Z"
}
```

---

## WebSocket API

### Connection

```
Endpoint: /ws/leaderboard
Protocol: STOMP over WebSocket/SockJS
```

### Subscription Destinations

| Destination | Description |
|-------------|-------------|
| `/topic/leaderboard/global/daily` | Global daily leaderboard updates |
| `/topic/leaderboard/global/weekly` | Global weekly leaderboard updates |
| `/topic/leaderboard/regional/{region}/daily` | Regional daily updates |
| `/topic/player/{playerId}` | Player-specific notifications |

### Message Format

```json
{
  "type": "RANK_CHANGED",
  "playerId": "player123",
  "playerName": "CasualGamer",
  "newRank": 999,
  "previousRank": 1005,
  "score": 2500,
  "scope": "GLOBAL",
  "period": "DAILY",
  "region": null,
  "timestamp": "2026-01-12T10:30:00Z"
}
```

### Notification Types

| Type | Description |
|------|-------------|
| `ENTERED_TOP_N` | Player entered the top N |
| `RANK_CHANGED` | Player's rank changed |
| `EXITED_TOP_N` | Player dropped out of top N |
| `NEW_HIGH_SCORE` | New personal high score |
| `LEADERBOARD_REFRESH` | Periodic refresh notification |

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PLAYER_NOT_FOUND` | 404 | Player not in leaderboard |
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `INVALID_ARGUMENT` | 400 | Invalid argument value |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
