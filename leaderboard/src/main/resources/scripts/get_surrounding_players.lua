-- Lua script for getting surrounding players with their scores
-- KEYS[1] = leaderboard key
-- ARGV[1] = playerId
-- ARGV[2] = range (number of players above and below)
-- Returns: array of [playerId, score, rank] for each player

local key = KEYS[1]
local playerId = ARGV[1]
local range = tonumber(ARGV[2])

-- Get the player's current rank (0-indexed)
local playerRank = redis.call('ZREVRANK', key, playerId)

if not playerRank then
    return nil
end

-- Calculate start and end positions
local startPos = math.max(0, playerRank - range)
local endPos = playerRank + range

-- Get the range of players with scores
local players = redis.call('ZREVRANGE', key, startPos, endPos, 'WITHSCORES')

local result = {}
local currentRank = startPos + 1  -- Convert to 1-indexed

for i = 1, #players, 2 do
    local pid = players[i]
    local pScore = players[i + 1]
    table.insert(result, pid)
    table.insert(result, pScore)
    table.insert(result, tostring(currentRank))
    currentRank = currentRank + 1
end

return result
