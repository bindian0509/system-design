# Kubernetes Networking

## Networking Model Overview

```mermaid
graph TB
    subgraph "Kubernetes Networking Requirements"
        R1[Every Pod gets unique IP]
        R2[Pods can communicate without NAT]
        R3[Nodes can communicate with Pods without NAT]
        R4[Pod sees same IP as others see it]
    end

    subgraph "AWS VPC CNI Implementation"
        VPC[AWS VPC]
        SUBNET[VPC Subnets]
        ENI[EC2 ENI Elastic Network Interfaces]
        PODIP[Pod IPs from VPC CIDR]

        VPC --> SUBNET
        SUBNET --> ENI
        ENI --> PODIP
    end

    R1 & R2 & R3 & R4 --> VPC
```

## Pod-to-Pod Communication

```mermaid
graph LR
    subgraph "Node 1 - IP: 10.0.1.100"
        POD1[Pod A<br/>IP: 10.0.1.47<br/>Container: 8080]
        VETH1[veth pair]
        POD1 --> VETH1
    end

    subgraph "Node 2 - IP: 10.0.2.200"
        POD2[Pod B<br/>IP: 10.0.2.89<br/>Container: 8080]
        VETH2[veth pair]
        POD2 --> VETH2
    end

    subgraph "AWS VPC"
        ROUTE[VPC Route Tables]
    end

    VETH1 -.Direct route.-> ROUTE
    ROUTE -.Direct route.-> VETH2

    POD1 -.curl 10.0.2.89:8080.-> POD2

    style POD1 fill:#90EE90
    style POD2 fill:#87CEEB
```

## Service Types

```mermaid
graph TB
    subgraph "Service Types"
        CLUSTERIP[ClusterIP<br/>Internal only<br/>Default]
        NODEPORT[NodePort<br/>Node IP + Static Port<br/>30000-32767]
        LB[LoadBalancer<br/>Cloud LB + NodePort<br/>External traffic]
        EXTNAME[ExternalName<br/>DNS CNAME<br/>External service]
    end

    CLUSTERIP --> NODEPORT
    NODEPORT --> LB

    style CLUSTERIP fill:#90EE90
    style LB fill:#FFD700
```

## ClusterIP Service (Internal)

```mermaid
graph TB
    subgraph "Service: order-service (ClusterIP: 10.100.200.50)"
        SVC[Service Endpoint<br/>order-service.ecommerce-prod.svc.cluster.local]
    end

    subgraph "Backend Pods"
        P1[order-service-1<br/>10.0.1.47:8080]
        P2[order-service-2<br/>10.0.2.89:8080]
        P3[order-service-3<br/>10.0.3.112:8080]
    end

    CLIENT[Client Pod] -->|curl order-service:80| SVC
    SVC -.Round-robin.-> P1
    SVC -.Round-robin.-> P2
    SVC -.Round-robin.-> P3

    subgraph "kube-proxy (iptables)"
        IPTABLES[iptables rules:<br/>DNAT 10.100.200.50:80<br/>→ Pod IPs:8080]
    end

    SVC --> IPTABLES
    IPTABLES --> P1
    IPTABLES --> P2
    IPTABLES --> P3
```

### ClusterIP YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: ecommerce-prod
  labels:
    app: order-service
spec:
  type: ClusterIP  # Default, can be omitted

  # Label selector for backend pods
  selector:
    app: order-service

  # Service ports
  ports:
  - name: http
    port: 80          # Service port
    targetPort: 8080  # Container port
    protocol: TCP
  - name: metrics
    port: 9090
    targetPort: 9090

  # Session affinity (sticky sessions)
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600

  # IP family
  ipFamilies:
  - IPv4
  ipFamilyPolicy: SingleStack
```

## NodePort Service

```mermaid
graph TB
    INTERNET((Internet))

    subgraph "Node 1 - Public IP: 54.123.45.67"
        NP1[NodePort: 30080]
    end

    subgraph "Node 2 - Public IP: 54.123.45.68"
        NP2[NodePort: 30080]
    end

    subgraph "Node 3 - Public IP: 54.123.45.69"
        NP3[NodePort: 30080]
    end

    INTERNET -->|curl 54.123.45.67:30080| NP1
    INTERNET -->|curl 54.123.45.68:30080| NP2

    subgraph "Service: api-service (ClusterIP: 10.100.200.100)"
        SVC[Service]
    end

    NP1 --> SVC
    NP2 --> SVC
    NP3 --> SVC

    subgraph "Pods"
        P1[api-1<br/>10.0.1.10:8080]
        P2[api-2<br/>10.0.2.20:8080]
    end

    SVC --> P1
    SVC --> P2
```

### NodePort YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
  namespace: ecommerce-prod
spec:
  type: NodePort

  selector:
    app: api-service

  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080  # Optional, auto-assigned if omitted (30000-32767)
    protocol: TCP
```

## LoadBalancer Service (AWS ELB/NLB)

```mermaid
graph TB
    INTERNET((Internet))

    subgraph "AWS"
        subgraph "Network Load Balancer"
            NLB[NLB<br/>nlb-abc123.elb.us-east-1.amazonaws.com]
            TG1[Target Group 1<br/>us-east-1a]
            TG2[Target Group 2<br/>us-east-1b]
            TG3[Target Group 3<br/>us-east-1c]

            NLB --> TG1
            NLB --> TG2
            NLB --> TG3
        end

        subgraph "EKS Cluster"
            subgraph "Node 1 - AZ 1a"
                NP1[NodePort: 31234]
                P1[Pod: 10.0.1.10:8080]
            end

            subgraph "Node 2 - AZ 1b"
                NP2[NodePort: 31234]
                P2[Pod: 10.0.2.20:8080]
            end

            subgraph "Node 3 - AZ 1c"
                NP3[NodePort: 31234]
                P3[Pod: 10.0.3.30:8080]
            end

            TG1 --> NP1
            TG2 --> NP2
            TG3 --> NP3

            NP1 --> P1
            NP2 --> P2
            NP3 --> P3
        end
    end

    INTERNET --> NLB
```

### LoadBalancer YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-loadbalancer
  namespace: ecommerce-prod
  annotations:
    # Use Network Load Balancer (default is Classic Load Balancer)
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"

    # Internal LB (private subnets)
    service.beta.kubernetes.io/aws-load-balancer-internal: "true"

    # Cross-zone load balancing
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"

    # SSL/TLS termination at LB
    service.beta.kubernetes.io/aws-load-balancer-ssl-cert: "arn:aws:acm:us-east-1:123456789012:certificate/abc123"
    service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"
    service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "http"

    # Connection draining
    service.beta.kubernetes.io/aws-load-balancer-connection-draining-enabled: "true"
    service.beta.kubernetes.io/aws-load-balancer-connection-draining-timeout: "60"

    # Health check
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-path: "/health"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-port: "8080"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-interval: "10"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-timeout: "5"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-healthy-threshold: "2"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-unhealthy-threshold: "2"

    # Subnet selection (for internal LBs)
    service.beta.kubernetes.io/aws-load-balancer-subnets: "subnet-abc123,subnet-def456,subnet-ghi789"

    # EIP allocation (for public NLB)
    service.beta.kubernetes.io/aws-load-balancer-eip-allocations: "eipalloc-abc123,eipalloc-def456"

    # Proxy protocol v2
    service.beta.kubernetes.io/aws-load-balancer-proxy-protocol: "*"

spec:
  type: LoadBalancer

  selector:
    app: api-service

  ports:
  - name: https
    port: 443
    targetPort: 8080
    protocol: TCP
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP

  # Preserve client source IP
  externalTrafficPolicy: Local  # or Cluster (default)
```

## Ingress with AWS Load Balancer Controller

```mermaid
graph TB
    INTERNET((Internet))

    subgraph "AWS Application Load Balancer"
        ALB[ALB<br/>api.example.com]
        R1[Rule: /orders → order-service]
        R2[Rule: /products → product-service]
        R3[Rule: /users → user-service]

        ALB --> R1
        ALB --> R2
        ALB --> R3
    end

    subgraph "Kubernetes Services"
        S1[Service: order-service<br/>ClusterIP]
        S2[Service: product-service<br/>ClusterIP]
        S3[Service: user-service<br/>ClusterIP]

        R1 --> S1
        R2 --> S2
        R3 --> S3
    end

    subgraph "Pods"
        P1[order-service-1<br/>10.0.1.10:8080]
        P2[order-service-2<br/>10.0.2.20:8080]
        P3[product-service-1<br/>10.0.1.30:8080]
        P4[user-service-1<br/>10.0.2.40:8080]

        S1 --> P1
        S1 --> P2
        S2 --> P3
        S3 --> P4
    end

    INTERNET -->|HTTPS| ALB

    style ALB fill:#FFD700
```

### Ingress YAML

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: ecommerce-prod
  annotations:
    # Ingress class
    kubernetes.io/ingress.class: alb

    # Scheme
    alb.ingress.kubernetes.io/scheme: internet-facing  # or internal

    # Target type
    alb.ingress.kubernetes.io/target-type: ip  # or instance (use ip for Fargate)

    # Listen ports
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'

    # SSL redirect
    alb.ingress.kubernetes.io/ssl-redirect: '443'

    # Certificate
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456789012:certificate/abc-123

    # Health check
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: '15'
    alb.ingress.kubernetes.io/healthcheck-timeout-seconds: '5'
    alb.ingress.kubernetes.io/healthy-threshold-count: '2'
    alb.ingress.kubernetes.io/unhealthy-threshold-count: '2'

    # Target group attributes
    alb.ingress.kubernetes.io/target-group-attributes: stickiness.enabled=true,stickiness.lb_cookie.duration_seconds=3600

    # WAF
    alb.ingress.kubernetes.io/wafv2-acl-arn: arn:aws:wafv2:us-east-1:123456789012:global/webacl/prod/abc-123

    # Security groups
    alb.ingress.kubernetes.io/security-groups: sg-abc123,sg-def456

    # Subnets
    alb.ingress.kubernetes.io/subnets: subnet-abc123,subnet-def456,subnet-ghi789

    # Tags
    alb.ingress.kubernetes.io/tags: Environment=prod,Team=platform

    # Actions (for advanced routing)
    alb.ingress.kubernetes.io/actions.ssl-redirect: '{"Type": "redirect", "RedirectConfig": { "Protocol": "HTTPS", "Port": "443", "StatusCode": "HTTP_301"}}'

spec:
  rules:
  # Host-based routing
  - host: api.example.com
    http:
      paths:
      # Path-based routing
      - path: /orders
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80

      - path: /products
        pathType: Prefix
        backend:
          service:
            name: product-service
            port:
              number: 80

      - path: /users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80

  # Multiple hosts
  - host: admin.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: admin-service
            port:
              number: 80

  # TLS configuration
  tls:
  - hosts:
    - api.example.com
    - admin.example.com
    secretName: tls-secret  # Optional, can use ACM cert from annotations
```

## DNS and Service Discovery

```mermaid
graph TB
    subgraph "Pod: client-app"
        APP[Application]
    end

    subgraph "DNS Resolution"
        COREDNS[CoreDNS<br/>Cluster DNS]
    end

    subgraph "Service Discovery Methods"
        M1["order-service<br/>(same namespace)"]
        M2["order-service.ecommerce-prod<br/>(specific namespace)"]
        M3["order-service.ecommerce-prod.svc.cluster.local<br/>(FQDN)"]
    end

    APP -->|DNS Query| COREDNS
    COREDNS -->|Returns ClusterIP| M1
    COREDNS -->|Returns ClusterIP| M2
    COREDNS -->|Returns ClusterIP| M3

    M1 & M2 & M3 --> SVC[Service: order-service<br/>ClusterIP: 10.100.200.50]

    subgraph "Pods"
        P1[Pod 1: 10.0.1.47]
        P2[Pod 2: 10.0.2.89]
    end

    SVC --> P1
    SVC --> P2
```

### DNS Records

```bash
# Service DNS format
<service-name>.<namespace>.svc.cluster.local

# Examples
order-service.ecommerce-prod.svc.cluster.local
postgres.ecommerce-prod.svc.cluster.local

# Headless service (StatefulSet) - returns pod IPs
postgres-0.postgres.ecommerce-prod.svc.cluster.local
postgres-1.postgres.ecommerce-prod.svc.cluster.local

# Pod DNS (if enabled)
<pod-ip-with-dashes>.<namespace>.pod.cluster.local
10-0-1-47.ecommerce-prod.pod.cluster.local
```

## Network Policies (Firewall Rules)

```mermaid
graph LR
    subgraph "Namespace: ecommerce-prod"
        API[api-gateway]
        ORDER[order-service]
        PAYMENT[payment-service]
        DB[(postgres)]
    end

    subgraph "Namespace: monitoring"
        PROM[prometheus]
    end

    INTERNET((Internet)) -->|Allowed| API
    API -->|Allowed| ORDER
    ORDER -->|Allowed| PAYMENT
    ORDER -->|Allowed| DB
    PAYMENT -->|Allowed| DB

    PROM -.Allowed on :9090.-> ORDER
    PROM -.Allowed on :9090.-> PAYMENT

    INTERNET -.Denied.-> ORDER
    INTERNET -.Denied.-> DB

    style API fill:#90EE90
    style ORDER fill:#87CEEB
    style DB fill:#FFD700
```

### Network Policy: Default Deny

```yaml
# Deny all ingress traffic by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ecommerce-prod
spec:
  podSelector: {}  # Applies to all pods
  policyTypes:
  - Ingress

---
# Deny all egress traffic by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: ecommerce-prod
spec:
  podSelector: {}
  policyTypes:
  - Egress
```

### Network Policy: Allow Specific Traffic

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service-netpol
  namespace: ecommerce-prod
spec:
  # Apply to these pods
  podSelector:
    matchLabels:
      app: order-service

  policyTypes:
  - Ingress
  - Egress

  # Ingress rules (who can connect TO this service)
  ingress:
  # Allow from api-gateway
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 8080

  # Allow from prometheus (different namespace)
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
      podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 9090  # Metrics port

  # Egress rules (where this service can connect TO)
  egress:
  # Allow DNS (kube-system namespace)
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53

  # Allow postgres
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432

  # Allow payment service
  - to:
    - podSelector:
        matchLabels:
          app: payment-service
    ports:
    - protocol: TCP
      port: 8080

  # Allow external HTTPS (for APIs)
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

### Network Policy: Advanced Scenarios

```yaml
# Allow traffic from specific IP blocks (external services)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external-ips
  namespace: ecommerce-prod
spec:
  podSelector:
    matchLabels:
      app: webhook-receiver
  policyTypes:
  - Ingress
  ingress:
  - from:
    - ipBlock:
        cidr: 192.168.1.0/24
        except:
        - 192.168.1.5/32
    ports:
    - protocol: TCP
      port: 8080

---
# Allow traffic based on namespace labels
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-production
  namespace: shared-services
spec:
  podSelector:
    matchLabels:
      tier: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          environment: production
    ports:
    - protocol: TCP
      port: 8080
```

## Service Mesh (AWS App Mesh / Istio)

```mermaid
graph TB
    subgraph "Service Mesh Architecture"
        subgraph "Control Plane"
            ISTIOD[Istio Control Plane<br/>or<br/>App Mesh Controller]
        end

        subgraph "Data Plane"
            subgraph "Pod: order-service"
                APP1[Container:<br/>order-service:8080]
                PROXY1[Envoy Sidecar Proxy<br/>:15001]

                PROXY1 --> APP1
            end

            subgraph "Pod: payment-service"
                APP2[Container:<br/>payment-service:8080]
                PROXY2[Envoy Sidecar Proxy<br/>:15001]

                PROXY2 --> APP2
            end
        end

        ISTIOD -.Configures.-> PROXY1
        ISTIOD -.Configures.-> PROXY2

        CLIENT[Client Request] --> PROXY1
        PROXY1 -.mTLS.-> PROXY2
    end

    style PROXY1 fill:#FFD700
    style PROXY2 fill:#FFD700
```

### Service Mesh Features

```mermaid
graph LR
    subgraph "Traffic Management"
        TM1[Load Balancing]
        TM2[Circuit Breaking]
        TM3[Retries & Timeouts]
        TM4[Traffic Splitting<br/>Canary/Blue-Green]
    end

    subgraph "Security"
        S1[mTLS Encryption]
        S2[Authentication]
        S3[Authorization]
    end

    subgraph "Observability"
        O1[Distributed Tracing]
        O2[Metrics Collection]
        O3[Access Logs]
    end

    style TM4 fill:#90EE90
    style S1 fill:#87CEEB
    style O1 fill:#FFD700
```

### AWS App Mesh Example

```yaml
# Virtual Node (represents a microservice)
apiVersion: appmesh.k8s.aws/v1beta2
kind: VirtualNode
metadata:
  name: order-service
  namespace: ecommerce-prod
spec:
  podSelector:
    matchLabels:
      app: order-service

  listeners:
  - portMapping:
      port: 8080
      protocol: http
    healthCheck:
      protocol: http
      path: /health
      healthyThreshold: 2
      unhealthyThreshold: 3
      timeoutMillis: 2000
      intervalMillis: 5000

  serviceDiscovery:
    dns:
      hostname: order-service.ecommerce-prod.svc.cluster.local

  backends:
  - virtualService:
      virtualServiceRef:
        name: payment-service

---
# Virtual Service (routing rules)
apiVersion: appmesh.k8s.aws/v1beta2
kind: VirtualService
metadata:
  name: order-service
  namespace: ecommerce-prod
spec:
  provider:
    virtualRouter:
      virtualRouterRef:
        name: order-service-router

---
# Virtual Router (traffic distribution)
apiVersion: appmesh.k8s.aws/v1beta2
kind: VirtualRouter
metadata:
  name: order-service-router
  namespace: ecommerce-prod
spec:
  listeners:
  - portMapping:
      port: 8080
      protocol: http

  routes:
  - name: order-service-route
    httpRoute:
      match:
        prefix: /
      action:
        weightedTargets:
        - virtualNodeRef:
            name: order-service-v1
          weight: 90
        - virtualNodeRef:
            name: order-service-v2
          weight: 10  # 10% canary traffic
      retryPolicy:
        maxRetries: 3
        perRetryTimeout:
          unit: ms
          value: 2000
        httpRetryEvents:
        - server-error
        - gateway-error
```

## Traffic Flow Summary

```mermaid
sequenceDiagram
    participant Client
    participant DNS as CoreDNS
    participant Service
    participant kube-proxy
    participant Pod1
    participant Pod2

    Client->>DNS: Resolve order-service
    DNS-->>Client: ClusterIP: 10.100.200.50

    Client->>Service: Request to 10.100.200.50:80
    Service->>kube-proxy: iptables rules

    alt Round-robin to Pod1
        kube-proxy->>Pod1: Forward to 10.0.1.47:8080
        Pod1-->>Client: Response
    else Round-robin to Pod2
        kube-proxy->>Pod2: Forward to 10.0.2.89:8080
        Pod2-->>Client: Response
    end
```

## Common Networking Patterns

| Pattern | Use Case | Implementation |
|---------|----------|----------------|
| **ClusterIP** | Internal microservice communication | Default service type |
| **Headless Service** | StatefulSet, direct pod access | `clusterIP: None` |
| **NodePort** | Development, debugging | Expose on node IP:port |
| **LoadBalancer** | Single-service external access | AWS ELB/NLB |
| **Ingress** | Multi-service HTTP(S) routing | ALB with path/host rules |
| **Service Mesh** | Advanced traffic management, security | Istio, App Mesh |

## Next Steps

- **[04-storage-volumes.md](./04-storage-volumes.md)**: Persistent storage with EBS and EFS
- **[05-secrets-management.md](./05-secrets-management.md)**: Configuration and secrets
- **[06-monitoring-observability.md](./06-monitoring-observability.md)**: Metrics, logs, traces
