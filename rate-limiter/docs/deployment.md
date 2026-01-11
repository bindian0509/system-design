# Deployment Guide

This document provides instructions for deploying the Distributed Rate Limiter.

## Prerequisites

- Java 21+
- Maven 3.8+
- Docker & Docker Compose
- Redis 7+ (for production)
- Kubernetes (for production deployment)

## Local Development

### Quick Start

```bash
# Start Redis
docker-compose up -d redis

# Run the application
./mvnw spring-boot:run

# Or run with Docker
docker-compose up -d rate-limiter
```

### With Monitoring Stack

```bash
# Start all services including Prometheus and Grafana
docker-compose --profile monitoring up -d
```

Access:
- Rate Limiter: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis host | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `REDIS_PASSWORD` | Redis password | (empty) |
| `JAVA_OPTS` | JVM options | -Xms256m -Xmx512m |

### Rate Limit Configuration

Edit `application.yml` or use environment variables:

```yaml
rate-limiter:
  enabled: true
  algorithm: SLIDING_WINDOW_COUNTER
  failure-mode: FAIL_OPEN  # or FAIL_CLOSED

  local-cache:
    enabled: true
    sync-interval-ms: 100
    max-entries: 100000

  default-rules:
    - id: per-user-limit
      scope: USER
      max-requests: 1000
      window-size-seconds: 60
      priority: 10
      enabled: true
```

## Production Deployment

### Redis Cluster Setup

For production, use Redis Cluster with at least 3 master nodes:

```yaml
spring:
  data:
    redis:
      cluster:
        nodes:
          - redis-node-1:6379
          - redis-node-2:6379
          - redis-node-3:6379
      password: ${REDIS_PASSWORD}
```

### Kubernetes Deployment

1. Create ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rate-limiter-config
data:
  REDIS_HOST: redis-cluster.default.svc.cluster.local
  REDIS_PORT: "6379"
```

2. Create Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rate-limiter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rate-limiter
  template:
    metadata:
      labels:
        app: rate-limiter
    spec:
      containers:
        - name: rate-limiter
          image: rate-limiter:latest
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: rate-limiter-config
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
```

3. Create Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rate-limiter
spec:
  selector:
    app: rate-limiter
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
```

### Scaling Considerations

| Scale | Rate Limiter Pods | Redis Cluster |
|-------|-------------------|---------------|
| Small (<10K RPS) | 2 pods | Single Redis |
| Medium (<100K RPS) | 3-5 pods | 3 node cluster |
| Large (<1M RPS) | 10+ pods | 6+ node cluster |

### Performance Tuning

1. **Local Cache**: Increase `max-entries` for higher cache hit rates
2. **Sync Interval**: Lower for consistency, higher for throughput
3. **JVM Options**: Configure based on available memory

```bash
JAVA_OPTS="-Xms1g -Xmx2g -XX:+UseG1GC -XX:MaxGCPauseMillis=100"
```

## Health Checks

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic health check |
| `/ready` | Readiness check with dependencies |
| `/actuator/prometheus` | Prometheus metrics |

### Monitoring Alerts

Set up alerts for:

1. **High Rejection Rate**: > 10% rejections in 5 minutes
2. **Redis Latency**: p99 > 50ms for 2 minutes
3. **Circuit Breaker Open**: Any circuit breaker state change
4. **Cache Hit Rate Low**: < 80% for 5 minutes

## Troubleshooting

### Common Issues

1. **Redis Connection Failures**
   - Check Redis host/port configuration
   - Verify network connectivity
   - Check Redis password

2. **High Latency**
   - Enable local caching if disabled
   - Reduce sync interval
   - Scale Redis cluster

3. **Memory Issues**
   - Increase JVM heap size
   - Reduce local cache size
   - Monitor cache evictions

### Logs

```bash
# View application logs
kubectl logs -f deployment/rate-limiter

# Enable debug logging
kubectl set env deployment/rate-limiter LOGGING_LEVEL_COM_RATELIMITER=DEBUG
```
