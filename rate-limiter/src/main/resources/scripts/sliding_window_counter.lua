-- Sliding Window Counter Rate Limiting Script
--
-- KEYS[1] = current window key
-- KEYS[2] = previous window key
-- ARGV[1] = window size in seconds
-- ARGV[2] = current timestamp (seconds)
-- ARGV[3] = max requests (limit)
-- ARGV[4] = weight/increment amount (default 1)
--
-- Returns: {allowed (0/1), weighted_count, limit, reset_time}

local curr_key = KEYS[1]
local prev_key = KEYS[2]
local window_size = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local weight = tonumber(ARGV[4]) or 1

-- Get current counts
local curr_count = tonumber(redis.call('GET', curr_key) or '0')
local prev_count = tonumber(redis.call('GET', prev_key) or '0')

-- Calculate window boundaries
local window_start = math.floor(now / window_size) * window_size
local elapsed = now - window_start

-- Calculate weight for previous window (how much of it is still in our sliding window)
local prev_weight = (window_size - elapsed) / window_size
local weighted_count = math.floor(prev_count * prev_weight) + curr_count

-- Check if adding weight would exceed limit
if weighted_count + weight > limit then
    -- Rejected
    local reset_time = window_start + window_size
    return {0, weighted_count, limit, reset_time}
end

-- Allowed - increment current window counter
local new_count = redis.call('INCRBY', curr_key, weight)

-- Set expiry on current window key (2x window size for safety)
redis.call('EXPIRE', curr_key, window_size * 2)

-- Recalculate weighted count with new value
local new_weighted_count = math.floor(prev_count * prev_weight) + new_count
local reset_time = window_start + window_size

return {1, new_weighted_count, limit, reset_time}
