# Operations Runbook

This runbook provides operational procedures for managing the Seller-Side Payment System, including incident response, maintenance procedures, and troubleshooting guides.

## Table of Contents

1. [System Health Checks](#system-health-checks)
2. [Common Incidents](#common-incidents)
3. [Maintenance Procedures](#maintenance-procedures)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Emergency Procedures](#emergency-procedures)
6. [Monitoring and Alerting](#monitoring-and-alerting)

---

## System Health Checks

### Daily Health Check Checklist

| Check | Command/Action | Expected Result |
|-------|----------------|-----------------|
| API Health | `curl /health` | 200 OK |
| Database Connection | `SELECT 1` | Success |
| Queue Consumer Lag | Check Kafka dashboard | < 100 messages |
| Scheduler Heartbeat | Check Redis key | Updated < 30s ago |
| Payment Success Rate | Check metrics | > 95% |
| DLQ Size | Query DLQ topic | < 10 messages |

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "=== Seller Payment System Health Check ==="
echo "Timestamp: $(date)"
echo ""

# API Health
echo "1. API Health:"
curl -s http://localhost:8080/health | jq .

# Database
echo ""
echo "2. Database Connection:"
psql -h $DB_HOST -U $DB_USER -d payments -c "SELECT 1 AS connected;" 2>&1

# Redis (Scheduler Lock)
echo ""
echo "3. Scheduler Leader:"
redis-cli GET payout_scheduler_leader

# Kafka Consumer Lag
echo ""
echo "4. Consumer Lag:"
kafka-consumer-groups.sh --bootstrap-server $KAFKA_HOST \
  --describe --group seller-payment-consumer

# Pending Payouts
echo ""
echo "5. Pending Payouts:"
psql -h $DB_HOST -U $DB_USER -d payments -c \
  "SELECT status, COUNT(*) FROM payout_record GROUP BY status;"

# Stuck Payouts
echo ""
echo "6. Stuck Payouts (PROCESSING > 10 min):"
psql -h $DB_HOST -U $DB_USER -d payments -c \
  "SELECT COUNT(*) FROM payout_record
   WHERE status = 'PROCESSING'
   AND processed_at < NOW() - INTERVAL '10 minutes';"
```

---

## Common Incidents

### Incident 1: Payment Gateway Unavailable

**Symptoms**:
- Payment failure rate spikes
- Circuit breaker alerts
- Payouts stuck in PROCESSING

**Impact**: Sellers not receiving payments

**Resolution Steps**:

1. **Verify gateway status**
   ```bash
   # Check gateway health endpoint
   curl -I https://gateway.example.com/health

   # Check recent gateway responses
   grep "gateway" /var/log/payment-processor/app.log | tail -20
   ```

2. **Check circuit breaker state**
   ```bash
   redis-cli GET circuit_breaker:payment_gateway:state
   ```

3. **If gateway is down**:
   - Confirm with gateway provider (check status page)
   - Circuit breaker should automatically pause processing
   - Monitor DLQ for growing queue

4. **When gateway recovers**:
   ```bash
   # Reset circuit breaker manually if needed
   redis-cli DEL circuit_breaker:payment_gateway:state
   redis-cli DEL circuit_breaker:payment_gateway:failure_count
   ```

5. **Process backlog**:
   ```bash
   # Check pending payouts
   psql -c "SELECT COUNT(*) FROM payout_record WHERE status = 'PENDING';"

   # Trigger manual processing if needed
   curl -X POST http://localhost:8080/admin/v1/payouts/process-pending
   ```

**Escalation**: If gateway down > 2 hours, escalate to engineering lead.

---

### Incident 2: High Payment Failure Rate

**Symptoms**:
- Failure rate > 5%
- Multiple error types in logs
- Seller complaints

**Resolution Steps**:

1. **Identify failure pattern**
   ```sql
   -- Group failures by error code
   SELECT error_code, COUNT(*), MAX(created_at)
   FROM payout_record
   WHERE status = 'FAILED'
     AND created_at > NOW() - INTERVAL '1 hour'
   GROUP BY error_code
   ORDER BY COUNT(*) DESC;
   ```

2. **For INVALID_ACCOUNT errors**:
   - Normal if rate < 2% (sellers with bad data)
   - If spike, check if SellerService data is corrupted

3. **For GATEWAY_ERROR**:
   - Check gateway logs
   - Verify credentials haven't expired
   - Check rate limiting

4. **For TIMEOUT errors**:
   - Gateway may be slow
   - Check network connectivity
   - Consider increasing timeout

5. **Retry failed payouts**
   ```sql
   -- Reset recent transient failures for retry
   UPDATE payout_record
   SET status = 'PENDING',
       retry_count = retry_count + 1,
       error_code = NULL,
       error_message = NULL
   WHERE status = 'FAILED'
     AND error_code IN ('TIMEOUT', 'GATEWAY_ERROR')
     AND retry_count < 5
     AND created_at > NOW() - INTERVAL '1 hour';
   ```

---

### Incident 3: Scheduler Not Running

**Symptoms**:
- No new payouts created
- Missing heartbeat
- Sellers complaining about delayed payouts

**Resolution Steps**:

1. **Check scheduler pod status**
   ```bash
   kubectl get pods -l app=payout-scheduler
   kubectl logs -l app=payout-scheduler --tail=100
   ```

2. **Check leader lock**
   ```bash
   redis-cli GET payout_scheduler_leader
   redis-cli TTL payout_scheduler_leader
   ```

3. **If leader lock is stale** (TTL expired but key exists):
   ```bash
   # Force release stale lock
   redis-cli DEL payout_scheduler_leader
   ```

4. **Restart scheduler if needed**
   ```bash
   kubectl rollout restart deployment/payout-scheduler
   ```

5. **Verify scheduler is running**
   ```bash
   # Check for recent payout creations
   psql -c "SELECT COUNT(*) FROM payout_record
            WHERE created_at > NOW() - INTERVAL '10 minutes';"
   ```

6. **Manual trigger if needed**
   ```bash
   curl -X POST http://localhost:8080/admin/v1/scheduler/trigger \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

---

### Incident 4: Database Connection Issues

**Symptoms**:
- Connection timeout errors
- High latency
- Failed transactions

**Resolution Steps**:

1. **Check database status**
   ```bash
   # RDS/Cloud SQL status
   aws rds describe-db-instances --db-instance-identifier payments-db

   # Connection count
   psql -c "SELECT count(*) FROM pg_stat_activity;"
   ```

2. **Check connection pool**
   ```bash
   # Application metrics
   curl http://localhost:8080/actuator/metrics/hikaricp.connections.active
   curl http://localhost:8080/actuator/metrics/hikaricp.connections.pending
   ```

3. **If connections exhausted**:
   - Check for long-running queries
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY duration DESC
   LIMIT 10;
   ```
   - Kill long-running queries if safe
   ```sql
   SELECT pg_terminate_backend(pid);
   ```

4. **If primary unavailable**:
   - Check failover status
   - Verify replica promotion
   - Update connection strings if needed

---

### Incident 5: Consumer Lag Growing

**Symptoms**:
- Kafka consumer lag increasing
- Order events not processed
- Seller balances not updating

**Resolution Steps**:

1. **Check consumer status**
   ```bash
   kafka-consumer-groups.sh --bootstrap-server $KAFKA_HOST \
     --describe --group seller-payment-consumer
   ```

2. **Check consumer logs**
   ```bash
   kubectl logs -l app=order-event-consumer --tail=100
   ```

3. **Scale up consumers**
   ```bash
   kubectl scale deployment order-event-consumer --replicas=5
   ```

4. **Check for poison messages**
   ```bash
   # Check DLQ
   kafka-console-consumer.sh --bootstrap-server $KAFKA_HOST \
     --topic order-events-dlq --from-beginning --max-messages 10
   ```

5. **If backlog is critical**, consider temporarily skipping to latest:
   ```bash
   # WARNING: This loses unprocessed messages
   kafka-consumer-groups.sh --bootstrap-server $KAFKA_HOST \
     --group seller-payment-consumer \
     --topic order-events \
     --reset-offsets --to-latest --execute
   ```

---

## Maintenance Procedures

### Procedure 1: Database Schema Migration

**Pre-requisites**:
- Maintenance window scheduled
- Backup verified
- Rollback script ready

**Steps**:

1. **Create backup**
   ```bash
   pg_dump -h $DB_HOST -U $DB_USER payments > backup_$(date +%Y%m%d).sql
   ```

2. **Apply migration**
   ```bash
   flyway -url=jdbc:postgresql://$DB_HOST/payments migrate
   ```

3. **Verify migration**
   ```bash
   flyway -url=jdbc:postgresql://$DB_HOST/payments info
   ```

4. **Rollback if needed**
   ```bash
   flyway -url=jdbc:postgresql://$DB_HOST/payments undo
   # Or restore from backup
   psql -h $DB_HOST -U $DB_USER payments < backup_YYYYMMDD.sql
   ```

---

### Procedure 2: Rotate Gateway Credentials

**Steps**:

1. **Generate new credentials** in gateway portal

2. **Update secrets**
   ```bash
   # Update Kubernetes secret
   kubectl create secret generic gateway-credentials \
     --from-literal=api-key=$NEW_API_KEY \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. **Rolling restart**
   ```bash
   kubectl rollout restart deployment/payment-processor
   ```

4. **Verify connectivity**
   ```bash
   # Check logs for successful gateway calls
   kubectl logs -l app=payment-processor --tail=20 | grep "gateway"
   ```

5. **Revoke old credentials** after verification

---

### Procedure 3: Scale for High Volume (e.g., Black Friday)

**Pre-scaling steps** (1 week before):

1. **Scale database**
   ```bash
   # Increase instance size
   aws rds modify-db-instance \
     --db-instance-identifier payments-db \
     --db-instance-class db.r5.2xlarge \
     --apply-immediately
   ```

2. **Scale application**
   ```bash
   # Increase replicas
   kubectl scale deployment payment-processor --replicas=10
   kubectl scale deployment order-event-consumer --replicas=8
   kubectl scale deployment status-api --replicas=6
   ```

3. **Increase connection pool**
   ```yaml
   # Update ConfigMap
   hikari:
     maximum-pool-size: 40
   ```

4. **Scale Kafka partitions** if needed
   ```bash
   kafka-topics.sh --bootstrap-server $KAFKA_HOST \
     --alter --topic order-events --partitions 16
   ```

**Post-event** (1 week after):
- Scale back to normal levels
- Review metrics for optimization opportunities

---

## Troubleshooting Guide

### Issue: Seller Balance Mismatch

**Diagnosis**:
```sql
-- Compare expected vs actual balance
SELECT
    sb.seller_id,
    sb.available_balance + sb.pending_balance as current,
    COALESCE(SUM(opm.seller_amount) FILTER (WHERE opm.status NOT IN ('CANCELLED')), 0) as total_earned,
    COALESCE(SUM(pr.amount) FILTER (WHERE pr.status = 'COMPLETED'), 0) as total_paid
FROM seller_balance sb
LEFT JOIN order_payout_mapping opm ON sb.seller_id = opm.seller_id
LEFT JOIN payout_record pr ON sb.seller_id = pr.seller_id
WHERE sb.seller_id = :seller_id
GROUP BY sb.seller_id, sb.available_balance, sb.pending_balance;
```

**Resolution**:
1. Identify discrepancy source from audit log
2. Create manual adjustment if needed
3. Document root cause

---

### Issue: Duplicate Payout

**Diagnosis**:
```sql
-- Find potential duplicates
SELECT seller_id, period_start, period_end, COUNT(*)
FROM payout_record
WHERE status = 'COMPLETED'
GROUP BY seller_id, period_start, period_end
HAVING COUNT(*) > 1;
```

**Resolution**:
1. Verify with gateway which transaction was successful
2. Reverse duplicate in gateway if possible
3. Adjust seller balance
4. Create clawback record if needed
5. Investigate root cause (missing lock? race condition?)

---

### Issue: Payout Stuck in PROCESSING

**Diagnosis**:
```sql
SELECT * FROM payout_record
WHERE status = 'PROCESSING'
  AND processed_at < NOW() - INTERVAL '15 minutes';
```

**Resolution**:
1. Query gateway for actual status
2. Update local status accordingly
3. If gateway has no record, reset to PENDING for retry

```sql
-- If gateway confirms no transaction
UPDATE payout_record
SET status = 'PENDING',
    processed_at = NULL,
    retry_count = retry_count + 1
WHERE payout_id = :payout_id
  AND status = 'PROCESSING';
```

---

## Emergency Procedures

### Emergency: Stop All Payouts

**When**: Security incident, suspected fraud, critical bug

```bash
# 1. Pause scheduler
kubectl scale deployment payout-scheduler --replicas=0

# 2. Pause processors
kubectl scale deployment payment-processor --replicas=0

# 3. Verify no processing
psql -c "SELECT COUNT(*) FROM payout_record WHERE status = 'PROCESSING';"

# 4. Document incident
echo "$(date) - All payouts stopped by $USER - Reason: $REASON" >> /var/log/emergency.log
```

### Emergency: Resume Payouts

```bash
# 1. Verify issue resolved
# 2. Scale up scheduler
kubectl scale deployment payout-scheduler --replicas=1

# 3. Scale up processors
kubectl scale deployment payment-processor --replicas=4

# 4. Monitor for errors
kubectl logs -f -l app=payment-processor

# 5. Document resolution
echo "$(date) - Payouts resumed by $USER" >> /var/log/emergency.log
```

### Emergency: Database Failover

```bash
# 1. Promote replica (automated in most cases)
aws rds failover-db-cluster --db-cluster-identifier payments-cluster

# 2. Verify new primary
psql -h $DB_HOST -c "SELECT pg_is_in_recovery();"
# Should return 'f' (false) for primary

# 3. Update connection strings if needed
# 4. Verify application connectivity
# 5. Notify stakeholders
```

---

## Monitoring and Alerting

### Key Metrics to Monitor

| Metric | Warning | Critical | Dashboard |
|--------|---------|----------|-----------|
| Payment success rate | < 97% | < 95% | Grafana: Payments |
| Gateway latency p99 | > 60s | > 90s | Grafana: Gateway |
| Consumer lag | > 1000 | > 5000 | Grafana: Kafka |
| DLQ size | > 10 | > 50 | Grafana: DLQ |
| Stuck payouts | > 5 | > 20 | Grafana: Payments |
| Database connections | > 80% | > 95% | Grafana: Database |

### Alert Response SLAs

| Severity | Response Time | Resolution Time | Escalation |
|----------|---------------|-----------------|------------|
| P1 (Critical) | 5 minutes | 1 hour | Immediate |
| P2 (High) | 15 minutes | 4 hours | 30 minutes |
| P3 (Medium) | 1 hour | 24 hours | 2 hours |
| P4 (Low) | 4 hours | 1 week | N/A |

### On-Call Responsibilities

1. **Acknowledge** all alerts within SLA
2. **Triage** and determine severity
3. **Communicate** status to stakeholders
4. **Resolve** or escalate appropriately
5. **Document** incident and resolution
6. **Follow up** on action items

### Post-Incident Review Template

```markdown
## Incident Report: [TITLE]

**Date**: YYYY-MM-DD
**Duration**: X hours Y minutes
**Severity**: P1/P2/P3/P4
**Impact**: [Number of affected sellers/payouts]

### Timeline
- HH:MM - Incident detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix implemented
- HH:MM - Incident resolved

### Root Cause
[Description of what caused the incident]

### Resolution
[Steps taken to resolve]

### Action Items
- [ ] Item 1 (Owner, Due Date)
- [ ] Item 2 (Owner, Due Date)

### Lessons Learned
[What we learned and how to prevent recurrence]
```

