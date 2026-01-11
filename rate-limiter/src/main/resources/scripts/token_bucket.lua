-- Token Bucket Rate Limiting Script
--
-- KEYS[1] = bucket key (stores tokens:last_refill_time)
-- ARGV[1] = max tokens (bucket capacity)
-- ARGV[2] = refill rate (tokens per second)
-- ARGV[3] = current timestamp (milliseconds)
-- ARGV[4] = tokens to consume (default 1)
-- ARGV[5] = TTL in seconds
--
-- Returns: {allowed (0/1), tokens_remaining, tokens_consumed, reset_time_ms}

local bucket_key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local consume = tonumber(ARGV[4]) or 1
local ttl = tonumber(ARGV[5])

-- Get current bucket state
local bucket = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- Initialize bucket if it doesn't exist
if tokens == nil then
    tokens = max_tokens
    last_refill = now
end

-- Calculate tokens to add based on elapsed time
local elapsed_ms = now - last_refill
local tokens_to_add = elapsed_ms * refill_rate / 1000

-- Refill bucket (capped at max capacity)
tokens = math.min(max_tokens, tokens + tokens_to_add)

-- Check if enough tokens available
if tokens < consume then
    -- Rejected - not enough tokens
    -- Calculate when enough tokens will be available
    local tokens_needed = consume - tokens
    local ms_until_available = tokens_needed * 1000 / refill_rate
    local reset_time = now + ms_until_available

    -- Update last_refill time even on rejection
    redis.call('HSET', bucket_key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', bucket_key, ttl)

    return {0, math.floor(tokens), consume, math.floor(reset_time)}
end

-- Consume tokens
local new_tokens = tokens - consume

-- Save new bucket state
redis.call('HSET', bucket_key, 'tokens', new_tokens, 'last_refill', now)
redis.call('EXPIRE', bucket_key, ttl)

-- Calculate reset time (when bucket would be full)
local ms_until_full = (max_tokens - new_tokens) * 1000 / refill_rate
local reset_time = now + ms_until_full

return {1, math.floor(new_tokens), consume, math.floor(reset_time)}
