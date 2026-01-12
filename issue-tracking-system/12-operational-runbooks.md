# Operational Runbooks

[← Back to README](./README.md) | [← Previous: SLOs & Metrics](./11-slos-metrics-alerting.md)

## Runbook Index

| Runbook | Severity | On-Call Team |
|---------|----------|--------------|
| [Tenant Isolation Incident](#runbook-tenant-isolation-incident) | P0 | Platform + Security |
| [Search Degradation](#runbook-search-degradation) | P1 | Search |
| [Database Failover](#runbook-database-failover) | P0 | Database |
| [Kafka Consumer Lag](#runbook-kafka-consumer-lag) | P1 | Platform |
| [Cache Failure](#runbook-cache-failure) | P1 | Platform |

---

## Runbook: Tenant Isolation Incident

### Metadata

| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **On-Call** | Platform Team + Security Team |
| **SLA** | Acknowledge: 5 min, Resolve: 1 hour |

### Detection

**Triggers:**
- Alert: "Cross-tenant data access detected"
- Alert: "RLS policy violation logged"
- User report of seeing another tenant's data
- Audit log anomaly detection

**Sources:**
- Audit log monitoring system
- User support tickets (keyword: "wrong data", "other company")
- Security scanning tools

### Immediate Actions (SLA: < 5 minutes)

#### 1. Disable Affected Tenant API Access

```bash
# Disable tenant immediately
curl -X POST https://api.internal/admin/tenants/{tenant_id}/disable \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "security_incident",
    "ticket": "INC-XXXX",
    "disable_type": "full"
  }'
```

#### 2. Revoke All Active Sessions

```bash
# Invalidate all sessions for affected tenant
redis-cli -h redis.internal KEYS "session:*:${TENANT_ID}:*" | xargs redis-cli DEL

# Invalidate API tokens
curl -X POST https://api.internal/admin/tenants/{tenant_id}/tokens/revoke-all \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### 3. Page Security Team

```bash
./scripts/page-security.sh "P0: Tenant isolation incident - ${TENANT_ID}"
```

#### 4. Create Incident Channel

- Slack: `#incident-YYYYMMDD-isolation`
- Add: Platform lead, Security lead, affected tenant's account manager
- Set topic: "P0: Tenant Isolation - {TENANT_ID}"

### Investigation

#### 1. Determine Scope of Exposure

```sql
-- Query audit logs for unusual access patterns
SELECT
    actor_user_id,
    actor_tenant_id,
    resource_tenant_id,
    action,
    COUNT(*) as access_count,
    MIN(created_at) as first_access,
    MAX(created_at) as last_access
FROM audit_logs
WHERE resource_tenant_id = 'affected_tenant_id'
  AND actor_tenant_id != resource_tenant_id
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY actor_user_id, actor_tenant_id, resource_tenant_id, action
ORDER BY access_count DESC;
```

#### 2. Identify Root Cause

Check for:
- [ ] RLS policy disabled/modified
- [ ] Application query missing tenant_id filter
- [ ] Connection pool tenant context leak
- [ ] Cache key collision
- [ ] API endpoint missing auth check

```bash
# Check recent deployments
kubectl rollout history deployment/issue-service

# Check RLS policies
psql -c "SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
         FROM pg_policies
         WHERE tablename = 'issues';"

# Check recent config changes
git log --oneline -20 -- config/

# Check application logs for errors
kubectl logs -l app=issue-service --since=1h | grep -i "tenant\|rls\|policy"
```

#### 3. Document Exposed Data

| Question | Answer |
|----------|--------|
| What data types were exposed? | Issues / Comments / Attachments |
| Which specific records? | List IDs |
| Time window of exposure? | From - To |
| Number of affected records? | Count |
| Which tenants accessed the data? | Tenant IDs |

### Resolution

#### 1. Deploy Hotfix (if code bug)

```bash
# Fast-track hotfix deployment
./scripts/deploy.sh --hotfix --service=issue-service --version=v1.2.3-hotfix

# Verify deployment
kubectl rollout status deployment/issue-service
```

#### 2. Restore RLS Policies (if configuration issue)

```sql
-- Re-enable RLS
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues FORCE ROW LEVEL SECURITY;

-- Verify policies exist
SELECT * FROM pg_policies WHERE tablename = 'issues';

-- Re-create policy if missing
CREATE POLICY tenant_isolation ON issues
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
```

#### 3. Clear Affected Caches

```bash
# Invalidate all caches for affected tenants
redis-cli -h redis.internal KEYS "*:${TENANT_ID}:*" | xargs redis-cli DEL
redis-cli -h redis.internal KEYS "*:${EXPOSED_TENANT_ID}:*" | xargs redis-cli DEL
```

#### 4. Re-enable Tenant Access (after verification)

```bash
# Verify fix
./scripts/verify-tenant-isolation.sh ${TENANT_ID}

# Re-enable tenant
curl -X POST https://api.internal/admin/tenants/{tenant_id}/enable \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Communication

#### 1. Notify Affected Tenants

Use template: `templates/security-incident-notification.md`

Include:
- What happened (high-level)
- What data was affected
- What we did to fix it
- Next steps
- Contact information

**Legal review required before sending**

#### 2. Update Status Page

```markdown
**Incident: Data Access Issue**
Status: Investigating
Affected: Limited number of tenants
Started: 2026-01-12 10:30 UTC

We identified an issue affecting data isolation for a small number of accounts.
We have isolated the affected accounts and are investigating.

Updates will be posted every 30 minutes.
```

### Post-Incident

- [ ] Blameless postmortem within 48 hours
- [ ] Update access pattern monitoring rules
- [ ] Add regression tests for this failure mode
- [ ] Review and update RLS policies
- [ ] Conduct security audit of similar code paths
- [ ] Update this runbook with lessons learned
- [ ] Review with compliance team

### Escalation Path

1. Platform On-Call Engineer
2. Platform Team Lead
3. VP of Engineering
4. CISO (if data breach confirmed)
5. Legal (if customer notification required)

---

## Runbook: Search Degradation

### Metadata

| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **On-Call** | Search Team |
| **SLA** | Acknowledge: 15 min, Resolve: 2 hours |

### Detection

**Triggers:**
- Alert: "Search latency p95 > 500ms"
- Alert: "Search error rate > 1%"
- Alert: "Kafka consumer lag > 10s"
- Alert: "Elasticsearch cluster status YELLOW/RED"

### Diagnosis Tree

```
Search Degradation
├── Is ES cluster healthy?
│   ├── YES → Check consumer lag
│   └── NO → Go to "ES Cluster Issues"
│
├── Is consumer lag high?
│   ├── YES → Go to "Consumer Lag Issues"
│   └── NO → Check query patterns
│
└── Are queries slow?
    ├── YES → Go to "Query Performance Issues"
    └── NO → Check network/load balancer
```

### Immediate Actions

#### 1. Check Elasticsearch Cluster Health

```bash
curl -s 'http://elasticsearch.internal:9200/_cluster/health?pretty'
```

Expected output:
```json
{
  "status": "green",
  "number_of_nodes": 25,
  "active_shards": 720
}
```

#### 2. Check Consumer Lag

```bash
kafka-consumer-groups.sh \
  --bootstrap-server kafka.internal:9092 \
  --group search-indexer-group \
  --describe
```

Expected: Lag < 1000 per partition

#### 3. Check Hot Threads (for slow queries)

```bash
curl -s 'http://elasticsearch.internal:9200/_nodes/hot_threads'
```

### ES Cluster Issues

#### Cluster Status: YELLOW

1. **Identify unassigned shards**
```bash
curl -s 'http://elasticsearch.internal:9200/_cat/shards?v&h=index,shard,prirep,state,unassigned.reason' \
  | grep UNASSIGNED
```

2. **Check disk space**
```bash
curl -s 'http://elasticsearch.internal:9200/_cat/allocation?v'
```

If disk > 85%:
```bash
# Delete old indices
curl -X DELETE 'http://elasticsearch.internal:9200/issue-tracker-shared-2025.*'

# Or add nodes
./scripts/es-add-node.sh
```

3. **Force shard allocation** (if node recovered)
```bash
curl -X POST 'http://elasticsearch.internal:9200/_cluster/reroute?retry_failed=true'
```

#### Cluster Status: RED

1. **Identify missing primary shards**
```bash
curl -s 'http://elasticsearch.internal:9200/_cat/shards?v' | grep -E 'p.*UNASSIGNED'
```

2. **Check node status**
```bash
curl -s 'http://elasticsearch.internal:9200/_cat/nodes?v&h=name,heap.percent,ram.percent,cpu,load_1m,node.role'
```

3. **If node permanently lost, allocate stale primary**
```bash
# WARNING: May lose some recent data
curl -X POST 'http://elasticsearch.internal:9200/_cluster/reroute' \
  -H 'Content-Type: application/json' \
  -d '{
    "commands": [{
      "allocate_stale_primary": {
        "index": "issue-tracker-shared-2026.01",
        "shard": 0,
        "node": "es-data-1",
        "accept_data_loss": true
      }
    }]
  }'
```

### Consumer Lag Issues

#### 1. Scale Up Indexer Replicas

```bash
kubectl scale deployment search-indexer --replicas=16
```

#### 2. If Backlog Critical, Pause Non-Essential Consumers

```bash
# Pause analytics consumer to prioritize search
kubectl scale deployment analytics-sink --replicas=0
```

#### 3. Check for Poison Messages

```bash
# Check DLQ
kafka-console-consumer.sh \
  --bootstrap-server kafka.internal:9092 \
  --topic search-indexer-dlq \
  --from-beginning \
  --max-messages 10
```

#### 4. If Poison Message Blocking, Skip It

```bash
# Manually commit offset past poison message
kafka-consumer-groups.sh \
  --bootstrap-server kafka.internal:9092 \
  --group search-indexer-group \
  --topic issues.updated \
  --reset-offsets \
  --shift-by 1 \
  --execute
```

### Query Performance Issues

#### 1. Identify Slow Queries

```bash
curl -s 'http://elasticsearch.internal:9200/_nodes/stats/indices/search?pretty' \
  | jq '.nodes[].indices.search'
```

#### 2. Enable Slow Query Log

```bash
curl -X PUT 'http://elasticsearch.internal:9200/issue-tracker-*/_settings' \
  -H 'Content-Type: application/json' \
  -d '{
    "index.search.slowlog.threshold.query.warn": "1s",
    "index.search.slowlog.threshold.query.info": "500ms"
  }'

# Check slow log
tail -f /var/log/elasticsearch/issue-tracker_index_search_slowlog.log
```

#### 3. Add Query Caching

```bash
curl -X PUT 'http://elasticsearch.internal:9200/issue-tracker-*/_settings' \
  -H 'Content-Type: application/json' \
  -d '{"index.requests.cache.enable": true}'
```

### Fallback to Database Search

If ES cannot be recovered quickly:

#### 1. Enable Database Fallback

```bash
curl -X POST 'https://feature-flags.internal/api/v1/flags' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flag": "search.use_database_fallback",
    "enabled": true,
    "rollout_percentage": 100
  }'
```

#### 2. Monitor Database Load

- Watch for increased query latency
- Watch for connection pool saturation

#### 3. Communicate to Users

```markdown
**Search Performance Notice**

Search functionality is currently operating in degraded mode.
- Search may be slower than usual
- Some advanced filters may not work
- Autocomplete is temporarily disabled

We are working to restore full functionality.
```

### Recovery Validation

Before declaring recovered:

- [ ] ES cluster status is GREEN
- [ ] Consumer lag < 1000 total
- [ ] Search latency p95 < 500ms for 10 minutes
- [ ] Search error rate < 0.1% for 10 minutes
- [ ] Run search regression tests: `./scripts/run-search-tests.sh`
- [ ] Disable database fallback flag

### Post-Incident

- [ ] Document what happened and timeline
- [ ] Review indexer scaling policies
- [ ] Review ES cluster capacity
- [ ] Update alerting thresholds if needed
- [ ] Update this runbook

---

## Runbook: Database Failover

### Metadata

| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **On-Call** | Database Team |
| **SLA** | Acknowledge: 5 min, Resolve: 30 min |

### Detection

**Triggers:**
- Alert: "PostgreSQL primary unreachable"
- Alert: "Patroni leader election triggered"
- Alert: "Write operations failing"

### Automatic Failover (Patroni)

Patroni handles automatic failover. Monitor:

```bash
# Check Patroni cluster status
patronictl -c /etc/patroni/patroni.yml list
```

Expected:
```
+ Cluster: issue-tracker-primary (1234567890) ---+----+-----------+
| Member  | Host     | Role    | State     | TL | Lag in MB |
+---------+----------+---------+-----------+----+-----------+
| node1   | 10.0.1.1 | Leader  | running   | 5  |           |
| node2   | 10.0.1.2 | Replica | streaming | 5  |         0 |
| node3   | 10.0.1.3 | Replica | streaming | 5  |         0 |
+---------+----------+---------+-----------+----+-----------+
```

### Manual Failover (if needed)

```bash
# Perform manual switchover
patronictl -c /etc/patroni/patroni.yml switchover --leader node1 --candidate node2 --force

# Verify new leader
patronictl -c /etc/patroni/patroni.yml list
```

### Post-Failover Checks

1. **Verify applications reconnected**
```bash
kubectl logs -l app=issue-service --since=5m | grep -i "connection\|database"
```

2. **Check replication status**
```sql
SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn
FROM pg_stat_replication;
```

3. **Verify no data loss**
```sql
-- Check for gaps in sequences
SELECT last_value FROM issues_id_seq;
```

---

## Runbook: Kafka Consumer Lag

### Metadata

| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **On-Call** | Platform Team |
| **SLA** | Acknowledge: 15 min, Resolve: 2 hours |

### Detection

**Triggers:**
- Alert: "Kafka consumer lag > 10000"
- Alert: "Consumer group not consuming"

### Diagnosis

```bash
# Check consumer group status
kafka-consumer-groups.sh \
  --bootstrap-server kafka.internal:9092 \
  --describe \
  --group search-indexer-group

# Check for stuck partitions
kafka-consumer-groups.sh \
  --bootstrap-server kafka.internal:9092 \
  --describe \
  --group search-indexer-group \
  --members --verbose
```

### Resolution

#### 1. Scale Consumers

```bash
kubectl scale deployment search-indexer --replicas=16
```

#### 2. Check for Errors

```bash
kubectl logs -l app=search-indexer --since=30m | grep -i error
```

#### 3. Reset Offsets (if stuck)

```bash
# Reset to latest (skip backlog)
kafka-consumer-groups.sh \
  --bootstrap-server kafka.internal:9092 \
  --group search-indexer-group \
  --topic issues.updated \
  --reset-offsets \
  --to-latest \
  --execute
```

---

## Runbook: Cache Failure

### Metadata

| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **On-Call** | Platform Team |
| **SLA** | Acknowledge: 15 min, Resolve: 1 hour |

### Detection

**Triggers:**
- Alert: "Redis cluster unreachable"
- Alert: "Cache hit rate < 50%"
- Alert: "Response latency increased"

### Diagnosis

```bash
# Check Redis cluster status
redis-cli -h redis.internal cluster info

# Check node status
redis-cli -h redis.internal cluster nodes
```

### Resolution

#### 1. If Node Failed, Wait for Auto-Recovery

Redis Cluster automatically promotes replicas.

#### 2. If Cluster Degraded, Add Nodes

```bash
# Add new node
redis-cli -h new-node.internal cluster meet redis.internal 6379

# Rebalance slots
redis-cli -h redis.internal --cluster rebalance redis.internal:6379
```

#### 3. Application Fallback

Applications automatically fall back to database if cache unavailable.
Monitor for increased database load.

---

## Next

[Technology Stack →](./13-technology-stack.md)
