# AWS Deployment and Infrastructure

This document covers the AWS infrastructure, deployment strategies, and Infrastructure as Code (IaC) for the URL shortener system.

---

## Infrastructure Overview

```mermaid
flowchart TB
    subgraph Global["Global Services"]
        R53["Route 53 (DNS)"]
        CF["CloudFront (CDN)"]
        WAF["WAF (Firewall)"]
        Shield["Shield Advanced (DDoS)"]
    end
    
    subgraph US["US-EAST-1 (Primary)"]
        US_VPC["VPC"]
        US_ALB["ALB"]
        US_EKS["EKS Cluster"]
        US_Redis["ElastiCache"]
        US_NAT["NAT Gateway"]
    end
    
    subgraph EU["EU-WEST-1"]
        EU_VPC["VPC"]
        EU_ALB["ALB"]
        EU_EKS["EKS Cluster"]
        EU_Redis["ElastiCache"]
        EU_NAT["NAT Gateway"]
    end
    
    subgraph AP["AP-SOUTH-1"]
        AP_VPC["VPC"]
        AP_ALB["ALB"]
        AP_EKS["EKS Cluster"]
        AP_Redis["ElastiCache"]
        AP_NAT["NAT Gateway"]
    end
    
    subgraph DataLayer["Global Data Layer"]
        DDB["DynamoDB Global Tables"]
        Kinesis["Kinesis (Events)"]
        Timestream["Timestream (Analytics)"]
        S3["S3 (Audit Logs)"]
    end
    
    subgraph Mgmt["Management & Observability"]
        CW["CloudWatch"]
        XRay["X-Ray"]
        Secrets["Secrets Manager"]
        KMS["KMS"]
    end
    
    Global --> US
    Global --> EU
    Global --> AP
    
    US --> DataLayer
    EU --> DataLayer
    AP --> DataLayer
```

---

## Terraform Project Structure

```mermaid
flowchart TB
    subgraph Modules["terraform/modules/"]
        VPC["vpc/"]
        EKS["eks/"]
        DynamoDB["dynamodb/"]
        ElastiCache["elasticache/"]
        CloudFront["cloudfront/"]
        WAF["waf/"]
        Observability["observability/"]
    end
    
    subgraph Environments["terraform/environments/"]
        Dev["dev/"]
        Staging["staging/"]
        Production["production/"]
    end
    
    subgraph GlobalRes["terraform/global/"]
        Route53["route53/"]
        IAM["iam/"]
        S3Global["s3/"]
    end
    
    Modules --> Environments
    GlobalRes --> Environments
```

---

## Core Infrastructure Modules

### VPC Architecture

```mermaid
flowchart TB
    subgraph VPC["VPC (10.0.0.0/16)"]
        subgraph Public["Public Subnets"]
            Pub_A["10.0.0.0/20<br/>AZ-a (ALB)"]
            Pub_B["10.0.16.0/20<br/>AZ-b (ALB)"]
            Pub_C["10.0.32.0/20<br/>AZ-c (ALB)"]
        end
        
        subgraph Private["Private Subnets (EKS)"]
            Pri_A["10.0.64.0/20<br/>AZ-a"]
            Pri_B["10.0.80.0/20<br/>AZ-b"]
            Pri_C["10.0.96.0/20<br/>AZ-c"]
        end
        
        subgraph Data["Data Subnets (Redis)"]
            Data_A["10.0.128.0/20<br/>AZ-a"]
            Data_B["10.0.144.0/20<br/>AZ-b"]
            Data_C["10.0.160.0/20<br/>AZ-c"]
        end
    end
    
    IGW["Internet Gateway"]
    NAT_A["NAT Gateway A"]
    NAT_B["NAT Gateway B"]
    NAT_C["NAT Gateway C"]
    
    IGW --> Public
    Public --> NAT_A
    Public --> NAT_B
    Public --> NAT_C
    NAT_A --> Pri_A
    NAT_B --> Pri_B
    NAT_C --> Pri_C
    
    subgraph Endpoints["VPC Endpoints"]
        DDB_EP["DynamoDB Endpoint"]
        S3_EP["S3 Endpoint"]
    end
    
    Private --> Endpoints
```

### EKS Cluster Architecture

```mermaid
flowchart TB
    subgraph EKS["EKS Cluster"]
        ControlPlane["Control Plane<br/>(AWS Managed)"]
        
        subgraph NodeGroup["Node Group"]
            Node1["Node 1<br/>t3.medium"]
            Node2["Node 2<br/>t3.medium"]
            Node3["Node 3<br/>t3.medium"]
            NodeN["Node N..."]
        end
        
        subgraph Pods["Application Pods"]
            Pod1["url-shortener Pod 1"]
            Pod2["url-shortener Pod 2"]
            Pod3["url-shortener Pod N"]
        end
    end
    
    subgraph IAM["IAM Configuration"]
        ClusterRole["Cluster IAM Role"]
        NodeRole["Node IAM Role<br/>+ DynamoDB, Kinesis, Secrets, X-Ray"]
        OIDC["OIDC Provider (IRSA)"]
    end
    
    subgraph Security["Security"]
        SG["Security Groups"]
        KMSKey["KMS Key (Secrets encryption)"]
    end
    
    ControlPlane --> NodeGroup --> Pods
    IAM --> EKS
    Security --> EKS
```

### DynamoDB Global Tables

```mermaid
flowchart TB
    subgraph GlobalTable["DynamoDB Global Table: url-shortener-urls"]
        subgraph US_Table["US-EAST-1 Replica"]
            US_DDB["Primary"]
        end
        
        subgraph EU_Table["EU-WEST-1 Replica"]
            EU_DDB["Replica"]
        end
        
        subgraph AP_Table["AP-SOUTH-1 Replica"]
            AP_DDB["Replica"]
        end
        
        US_DDB <-->|"~1s replication"| EU_DDB
        EU_DDB <-->|"~1s replication"| AP_DDB
        AP_DDB <-->|"~1s replication"| US_DDB
    end
    
    subgraph Features["Table Features"]
        TTL["TTL: expires_at"]
        PITR["Point-in-Time Recovery"]
        Encryption["Server-side Encryption"]
        GSI["GSIs: user-urls, expires-at"]
    end
    
    GlobalTable --> Features
```

### CloudFront Distribution

```mermaid
flowchart TB
    subgraph CloudFront["CloudFront Distribution"]
        subgraph Origins["Origins"]
            ALB_Origin["ALB Origin<br/>• HTTPS only<br/>• Custom headers"]
        end
        
        subgraph Behaviors["Cache Behaviors"]
            Default["Default (API)<br/>• No caching<br/>• Lambda@Edge auth"]
            Redirect["/:code (Redirect)<br/>• 24h cache<br/>• Lambda@Edge redirect"]
            Health["/health*<br/>• No caching"]
        end
        
        subgraph Edge["Edge Functions"]
            EdgeAuth["edge-auth<br/>Auth/Rate limiting"]
            EdgeRedirect["edge-redirect<br/>Cached redirects"]
        end
        
        subgraph Security["Security"]
            WAF_ACL["WAF ACL"]
            GeoRestrict["Geo Restriction<br/>Block: KP, IR, SY, CU"]
            TLS["TLS 1.2+"]
        end
    end
    
    Origins --> Behaviors
    Behaviors --> Edge
    CloudFront --> Security
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```mermaid
flowchart TB
    subgraph Trigger["Trigger"]
        Push["Push to main"]
        PR["Pull Request"]
    end
    
    subgraph Test["Test Job"]
        Checkout["Checkout"]
        InstallRust["Install Rust"]
        RunTests["cargo test"]
        Clippy["cargo clippy"]
        Fmt["cargo fmt --check"]
    end
    
    subgraph Build["Build Job"]
        AWSCreds["Configure AWS"]
        ECRLogin["Login to ECR"]
        DockerBuild["Build Docker Image"]
        DockerPush["Push to ECR"]
    end
    
    subgraph DeployStaging["Deploy Staging (PR only)"]
        UpdateKubeStaging["kubectl set image"]
        RolloutStaging["kubectl rollout status"]
    end
    
    subgraph DeployProd["Deploy Production (main only)"]
        Canary["Deploy Canary (10%)"]
        Wait["Wait 5 minutes"]
        CheckMetrics["Check canary metrics"]
        FullDeploy["Full deployment"]
        InvalidateCF["Invalidate CloudFront"]
    end
    
    Trigger --> Test --> Build
    Build -->|"PR"| DeployStaging
    Build -->|"main"| DeployProd
```

### Canary Deployment Strategy

```mermaid
flowchart LR
    subgraph Before["Before Deployment"]
        Stable100["Stable: 100%<br/>Canary: 0%"]
    end
    
    subgraph Canary["Canary Phase"]
        Stable90["Stable: 90%<br/>Canary: 10%"]
        Validation["5 min validation<br/>Check error rate"]
    end
    
    subgraph After["After Validation"]
        Stable0["Stable: 0%<br/>New: 100%"]
    end
    
    Before -->|"Deploy canary"| Canary
    Canary -->|"Metrics OK"| After
    Canary -->|"Metrics BAD"| Rollback["Rollback"]
```

---

## Disaster Recovery

### Multi-Region Failover

```mermaid
flowchart TB
    subgraph Route53["Route 53"]
        DNS["Latency-based routing<br/>+ Health checks"]
    end
    
    subgraph NormalState["Normal State (All Healthy)"]
        US_OK["US-EAST-1 ✓"]
        EU_OK["EU-WEST-1 ✓"]
        AP_OK["AP-SOUTH-1 ✓"]
    end
    
    subgraph FailoverState["Failover State (US Down)"]
        US_DOWN["US-EAST-1 ✗"]
        EU_ACTIVE["EU-WEST-1 ✓<br/>(Absorbs traffic)"]
        AP_ACTIVE["AP-SOUTH-1 ✓<br/>(Absorbs traffic)"]
    end
    
    DNS -->|"Healthy"| NormalState
    DNS -->|"US fails health check"| FailoverState
    
    subgraph Metrics["Recovery Metrics"]
        RTO["RTO: < 60 seconds<br/>(DNS TTL)"]
        RPO["RPO: < 1 second<br/>(DynamoDB Global Tables)"]
    end
```

### Health Check Configuration

```mermaid
sequenceDiagram
    participant R53 as Route 53
    participant ALB as ALB
    participant App as Application
    
    loop Every 30 seconds
        R53->>ALB: Health check request
        ALB->>App: GET /health
        
        alt Healthy
            App-->>ALB: 200 OK
            ALB-->>R53: Healthy
        else Unhealthy (3 consecutive)
            App-->>ALB: 5xx / Timeout
            ALB-->>R53: Unhealthy
            R53->>R53: Remove from DNS
            Note over R53: Failover to healthy regions
        end
    end
```

### Backup Strategy

```mermaid
flowchart TB
    subgraph DynamoDB_Backup["DynamoDB"]
        PITR["Point-in-Time Recovery<br/>35 days retention"]
        OnDemand["On-demand backups<br/>Daily, 90 day retention"]
    end
    
    subgraph Redis_Backup["ElastiCache"]
        Snapshots["Hourly snapshots<br/>24 hour retention"]
        DailyBackup["Daily backups<br/>7 day retention"]
    end
    
    subgraph S3_Backup["S3 Audit Logs"]
        CrossRegion["Cross-region replication<br/>US → EU"]
    end
    
    subgraph Secrets_Backup["Secrets Manager"]
        SecretReplication["Multi-region replication<br/>US, EU, AP"]
    end
```

---

## Cost Optimization

### Estimated Monthly Costs (Tier 5 - 500M URLs/month)

```mermaid
pie title Monthly Cost Distribution
    "DynamoDB" : 15000
    "EC2/EKS Nodes" : 5500
    "ElastiCache" : 4500
    "CloudFront" : 1500
    "WAF + Shield" : 6000
    "Kinesis + Timestream" : 3500
    "Data Transfer" : 3000
    "Other (S3, etc)" : 1000
```

| Service | Configuration | Estimated Cost |
|---------|--------------|----------------|
| CloudFront | 1.5TB data transfer | $1,500 |
| EKS | 15 nodes (3 regions) | $3,000 |
| EC2 (Nodes) | t3.large x 15 | $2,500 |
| DynamoDB | 500M writes, 50B reads | $15,000 |
| ElastiCache | r6g.large x 9 | $4,500 |
| Kinesis | 50 shards | $1,500 |
| Timestream | Storage + queries | $2,000 |
| S3 | Audit logs + exports | $500 |
| Data Transfer | Inter-region | $3,000 |
| WAF + Shield | Advanced | $6,000 |
| **Total** | | **~$40,000/month** |

### Cost Optimization Strategies

```mermaid
flowchart LR
    subgraph Strategies["Cost Optimization"]
        Reserved["Reserved Capacity<br/>30-40% savings on EC2/ElastiCache"]
        OnDemand["DynamoDB On-Demand<br/>Pay per request, auto-scale"]
        Caching["CloudFront Caching<br/>Higher hit rate = lower origin costs"]
        Spot["Spot Instances<br/>Non-critical workloads"]
        Lifecycle["Data Lifecycle<br/>Move old data to Glacier"]
    end
```
