## Redis: Top K Players in Last Hour

You cannot answer “top scores in last hour” with a single ZSET: a ZSET can sort by score or by time, but not both. Use two indices and intersect them.

### Two-set architecture

- Score board (`leaderboard:scores`): member -> points.
- Time window (`leaderboard:activity`): member -> last-played timestamp.
- Query = intersection of score and time sets.

### Write path (ingestion)

Update both indices on every score event:

```redis
# 1) Update score
ZADD leaderboard:scores 5000 "PlayerA"

# 2) Update last-activity timestamp (unix seconds)
ZADD leaderboard:activity 1732450000 "PlayerA"
```

### Read path (last 1 hour, top 10)

1. Clean the time window (remove users older than 1h):

```redis
ZREMRANGEBYSCORE leaderboard:activity -inf 1732446400   # now - 3600
```

2. Intersect score and time sets, keeping scores:

```redis
# WEIGHTS 1 0 => keep score from set1, ignore score from set2
ZINTERSTORE temp:top10 2 leaderboard:scores leaderboard:activity WEIGHTS 1 0
```

3. Fetch leaderboard:

```redis
ZREVRANGE temp:top10 0 9 WITHSCORES
```

4. Rank for a single user (after the intersection):

```redis
ZREVRANK temp:top10 "PlayerA"
```

### Performance note

- `ZINTERSTORE` is O(N \* K) where N is the smaller set; fine for small sets, expensive at very large scale.
- At larger scale, switch to time-bucketed ZSETs (e.g., per-minute keys) and `ZUNIONSTORE` the last 60 buckets for the rolling hour to avoid scanning inactive users.

### Checklist

- Do not pack timestamps into scores.
- Keep two ZSETs: one for scores, one for activity.
- Filter via `ZINTERSTORE`, read via `ZREVRANGE`, rank via `ZREVRANK`.
- For high scale, pre-bucket by time and union recent buckets.
