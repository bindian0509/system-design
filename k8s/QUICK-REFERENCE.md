# Kubernetes Quick Reference Cheat Sheet

## Common kubectl Commands

### Context and Configuration

```bash
# View current context
kubectl config current-context

# List all contexts
kubectl config get-contexts

# Switch context
kubectl config use-context prod-eks-cluster

# Set default namespace
kubectl config set-context --current --namespace=ecommerce-prod
```

### Resource Management

```bash
# Get resources
kubectl get pods
kubectl get pods -A                    # All namespaces
kubectl get pods -o wide               # More details
kubectl get pods -w                    # Watch mode
kubectl get pods -l app=order-service  # Label selector

# Describe resource (detailed info)
kubectl describe pod order-service-abc123
kubectl describe deployment order-service

# Create/Apply
kubectl apply -f deployment.yaml
kubectl apply -f ./manifests/          # Apply directory

# Delete
kubectl delete pod order-service-abc123
kubectl delete deployment order-service
kubectl delete -f deployment.yaml

# Edit resource (opens in editor)
kubectl edit deployment order-service

# Scale
kubectl scale deployment order-service --replicas=5

# Rollout
kubectl rollout status deployment/order-service
kubectl rollout history deployment/order-service
kubectl rollout undo deployment/order-service
kubectl rollout restart deployment/order-service
```

### Logs and Debugging

```bash
# View logs
kubectl logs pod-name
kubectl logs pod-name -c container-name        # Specific container
kubectl logs -f pod-name                       # Follow logs
kubectl logs --tail=100 pod-name              # Last 100 lines
kubectl logs --since=1h pod-name              # Last hour
kubectl logs -l app=order-service --all-containers=true  # All pods with label

# Execute command in pod
kubectl exec -it pod-name -- bash
kubectl exec pod-name -- ls /app
kubectl exec -it pod-name -c container-name -- sh

# Port forwarding
kubectl port-forward pod-name 8080:8080
kubectl port-forward svc/order-service 8080:80

# Copy files
kubectl cp pod-name:/path/to/file ./local-file
kubectl cp ./local-file pod-name:/path/to/file

# Get shell access
kubectl run debug --rm -it --image=busybox -- sh
```

### Resource Inspection

```bash
# Get YAML/JSON
kubectl get pod order-service-abc123 -o yaml
kubectl get deployment order-service -o json

# Get specific fields
kubectl get pods -o jsonpath='{.items[*].metadata.name}'
kubectl get pods -o custom-columns=NAME:.metadata.name,STATUS:.status.phase

# Events
kubectl get events
kubectl get events --sort-by='.lastTimestamp'
kubectl get events --field-selector involvedObject.name=order-service

# Top (resource usage)
kubectl top nodes
kubectl top pods
kubectl top pods -n ecommerce-prod --sort-by=memory
```

## Resource Manifest Templates

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
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

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
  namespace: default
spec:
  type: ClusterIP  # or NodePort, LoadBalancer
  selector:
    app: myapp
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  namespace: default
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: myapp
            port:
              number: 80
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
  namespace: default
data:
  database.host: "postgres.default"
  database.port: "5432"
  config.yaml: |
    server:
      port: 8080
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
  namespace: default
type: Opaque
stringData:
  username: admin
  password: secretpassword
```

### HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Troubleshooting Guide

### Pod Issues

| Problem | Commands to Run |
|---------|----------------|
| Pod stuck in Pending | `kubectl describe pod <pod>` - Check events for scheduling issues |
| Pod CrashLoopBackOff | `kubectl logs <pod>` and `kubectl describe pod <pod>` |
| Pod ImagePullBackOff | Check image name, registry access, secrets |
| Pod high restart count | `kubectl describe pod <pod>` - Look at liveness probe failures |

### Common Issues

```bash
# Check pod events
kubectl get events --field-selector involvedObject.name=<pod-name>

# Check pod logs
kubectl logs <pod-name> --previous  # Previous container instance

# Check resource constraints
kubectl top nodes
kubectl top pods
kubectl describe node <node-name>

# Check network connectivity
kubectl exec -it <pod-name> -- ping <service-name>
kubectl exec -it <pod-name> -- nslookup <service-name>
kubectl exec -it <pod-name> -- curl <service-name>:80

# Check service endpoints
kubectl get endpoints <service-name>

# Check RBAC permissions
kubectl auth can-i get pods
kubectl auth can-i --list --namespace=default
```

## Resource Limits Quick Reference

### CPU Units

- `1` or `1000m` = 1 CPU core
- `500m` = 0.5 CPU core (half a core)
- `100m` = 0.1 CPU core (10% of a core)

### Memory Units

- `1Gi` = 1 GiB (1024 MiB)
- `1G` = 1 GB (1000 MB)
- `512Mi` = 512 MiB
- `256Mi` = 256 MiB

### Storage Units

- `1Ti` = 1 TiB
- `1Gi` = 1 GiB
- `100Gi` = 100 GiB

## Label Selectors

### Equality-based

```yaml
# In manifests
selector:
  matchLabels:
    app: myapp
    tier: backend

# In kubectl
kubectl get pods -l app=myapp
kubectl get pods -l app=myapp,tier=backend
kubectl get pods -l app!=myapp
```

### Set-based

```yaml
# In manifests
selector:
  matchExpressions:
  - key: app
    operator: In
    values: [myapp, otherapp]
  - key: tier
    operator: NotIn
    values: [frontend]

# In kubectl
kubectl get pods -l 'app in (myapp, otherapp)'
kubectl get pods -l 'tier notin (frontend)'
kubectl get pods -l 'env'           # Has env label
kubectl get pods -l '!env'          # Doesn't have env label
```

## DNS Names

### Service DNS

```
<service-name>.<namespace>.svc.cluster.local

# Examples
order-service.ecommerce-prod.svc.cluster.local
postgres.default.svc.cluster.local

# Short forms (within same namespace)
order-service
order-service.ecommerce-prod
```

### Headless Service (StatefulSet)

```
<pod-name>.<service-name>.<namespace>.svc.cluster.local

# Examples
postgres-0.postgres.default.svc.cluster.local
postgres-1.postgres.default.svc.cluster.local
```

## Useful Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgd='kubectl get deployments'
alias kgs='kubectl get services'
alias kd='kubectl describe'
alias kdp='kubectl describe pod'
alias kdd='kubectl describe deployment'
alias kl='kubectl logs'
alias klf='kubectl logs -f'
alias ke='kubectl exec -it'
alias kaf='kubectl apply -f'
alias kdel='kubectl delete'
alias kgpa='kubectl get pods -A'
alias kgpw='kubectl get pods -o wide'
alias kctx='kubectl config use-context'
alias kns='kubectl config set-context --current --namespace'
```

## JSON Path Examples

```bash
# Get all pod names
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# Get pod IPs
kubectl get pods -o jsonpath='{.items[*].status.podIP}'

# Get container images
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}'

# Get node names where pods are running
kubectl get pods -o jsonpath='{.items[*].spec.nodeName}'

# Custom columns
kubectl get pods -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
NODE:.spec.nodeName,\
IP:.status.podIP
```

## Deployment Strategies

### Rolling Update (Zero Downtime)

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

### Recreate (Downtime)

```yaml
spec:
  strategy:
    type: Recreate
```

### Blue-Green (Manual)

```bash
# Deploy green
kubectl apply -f deployment-green.yaml

# Test green
kubectl port-forward deployment/myapp-green 8080:8080

# Switch service to green
kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'

# Delete blue
kubectl delete deployment myapp-blue
```

### Canary (Manual)

```bash
# Deploy canary with 1 replica
kubectl apply -f deployment-canary.yaml

# Original has 9 replicas = 90% traffic
# Canary has 1 replica = 10% traffic

# Monitor metrics, then:
kubectl scale deployment myapp --replicas=0
kubectl scale deployment myapp-canary --replicas=10
```

## Quick Diagnostics

```bash
# Cluster health
kubectl cluster-info
kubectl get componentstatuses
kubectl get nodes

# Resource usage
kubectl top nodes
kubectl top pods -A

# API resources
kubectl api-resources
kubectl api-versions

# Check RBAC
kubectl auth can-i create pods
kubectl auth can-i '*' '*' --all-namespaces

# Network debugging pod
kubectl run tmp-shell --rm -i --tty --image nicolaka/netshoot -- /bin/bash

# Check DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
```

## Performance Tips

```bash
# Use server-side filtering
kubectl get pods --field-selector=status.phase=Running

# Limit output
kubectl get pods --limit=10

# Use cached discovery
export KUBECTL_ENABLE_ALPHA_COMMANDS=true
kubectl --cache-dir=/tmp/kubectl-cache get pods

# Increase timeout for slow clusters
kubectl get pods --request-timeout=30s
```

## Helm Quick Reference

```bash
# Search charts
helm search repo prometheus

# Install
helm install my-release prometheus-community/prometheus

# Upgrade
helm upgrade my-release prometheus-community/prometheus

# Rollback
helm rollback my-release 1

# List releases
helm list
helm list -A

# Get values
helm get values my-release

# Uninstall
helm uninstall my-release
```

## Common Patterns

### Wait for pod to be ready

```bash
kubectl wait --for=condition=ready pod -l app=myapp --timeout=300s
```

### Delete all pods in a namespace

```bash
kubectl delete pods --all -n default
```

### Force delete stuck pod

```bash
kubectl delete pod <pod-name> --grace-period=0 --force
```

### Get all resources in namespace

```bash
kubectl get all -n default
kubectl api-resources --verbs=list --namespaced -o name | \
  xargs -n 1 kubectl get --show-kind --ignore-not-found -n default
```

### Create secret from file

```bash
kubectl create secret generic my-secret \
  --from-file=ssh-privatekey=/path/to/key \
  --from-literal=password=mypassword
```

### Dry run and output YAML

```bash
kubectl create deployment myapp --image=myapp:latest --dry-run=client -o yaml > deployment.yaml
```

---

**Tip**: Keep this cheat sheet handy during interviews and always explain your commands as you use them!
