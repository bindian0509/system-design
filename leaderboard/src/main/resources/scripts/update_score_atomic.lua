-- Lua script for atomic score update with rank retrieval
-- KEYS[1] = leaderboard key
-- ARGV[1] = playerId
-- ARGV[2] = score
-- ARGV[3] = update mode (INCREMENT, MAX, SET)
-- ARGV[4] = TTL in seconds (-1 for no expiry)
-- Returns: [newScore, rank (0-indexed), totalPlayers]

local key = KEYS[1]
local playerId = ARGV[1]
local score = tonumber(ARGV[2])
local mode = ARGV[3]
local ttl = tonumber(ARGV[4])

local currentScore = redis.call('ZSCORE', key, playerId)
local newScore = score

if mode == 'INCREMENT' then
    if currentScore then
        newScore = tonumber(currentScore) + score
    end
elseif mode == 'MAX' then
    if currentScore and tonumber(currentScore) >= score then
        newScore = tonumber(currentScore)
    end
-- mode == 'SET' uses score directly
end

redis.call('ZADD', key, newScore, playerId)

if ttl > 0 then
    redis.call('EXPIRE', key, ttl)
end

local rank = redis.call('ZREVRANK', key, playerId)
local total = redis.call('ZCARD', key)

return {tostring(newScore), tostring(rank), tostring(total)}
