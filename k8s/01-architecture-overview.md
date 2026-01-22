# Kubernetes Architecture Overview

## High-Level Architecture

```mermaid
graph TB
    subgraph "EKS Control Plane (AWS Managed)"
        API[API Server]
        ETCD[(etcd)]
        SCHED[Scheduler]
        CM[Controller Manager]
        CCM[Cloud Controller Manager]
    end

    subgraph "Worker Nodes (Your EC2/Fargate)"
        subgraph "Node 1 - us-east-1a"
            KUBELET1[kubelet]
            PROXY1[kube-proxy]
            RUNTIME1[containerd]
            POD1A[Pod: order-service-1]
            POD1B[Pod: postgres-1]
        end

        subgraph "Node 2 - us-east-1b"
            KUBELET2[kubelet]
            PROXY2[kube-proxy]
            RUNTIME2[containerd]
            POD2A[Pod: order-service-2]
            POD2B[Pod: payment-service-1]
        end

        subgraph "Node 3 - us-east-1c"
            KUBELET3[kubelet]
            PROXY3[kube-proxy]
            RUNTIME3[containerd]
            POD3A[Pod: order-service-3]
            POD3B[Pod: inventory-service-1]
        end
    end

    subgraph "AWS Services"
        ELB[Elastic Load Balancer]
        EBS[EBS Volumes]
        EFS[EFS File System]
        ECR[ECR Registry]
        SM[Secrets Manager]
        CW[CloudWatch]
    end

    API --> KUBELET1
    API --> KUBELET2
    API --> KUBELET3

    KUBELET1 --> RUNTIME1
    KUBELET2 --> RUNTIME2
    KUBELET3 --> RUNTIME3

    RUNTIME1 --> POD1A
    RUNTIME1 --> POD1B
    RUNTIME2 --> POD2A
    RUNTIME2 --> POD2B
    RUNTIME3 --> POD3A
    RUNTIME3 --> POD3B

    CCM --> ELB
    CCM --> EBS
    CCM --> EFS

    RUNTIME1 --> ECR
    RUNTIME2 --> ECR
    RUNTIME3 --> ECR

    POD1A --> SM
    POD2A --> SM
    POD3A --> SM

    POD1A --> CW
    POD2A --> CW
    POD3A --> CW
```

## Control Plane Components

### API Server
- **Role**: Central hub for all cluster operations
- **Responsibilities**:
  - Validates and processes API requests
  - Only component that talks to etcd
  - Authentication and authorization
  - Admission control
- **In EKS**: Fully managed by AWS, multi-AZ by default

### etcd
- **Role**: Distributed key-value store for cluster state
- **What it stores**:
  - All resource definitions (Pods, Services, ConfigMaps, etc.)
  - Cluster configuration
  - State of all objects
- **In EKS**: Managed, backed up, and highly available

### Scheduler
- **Role**: Assigns pods to nodes
- **Decision factors**:
  - Resource requirements (CPU, memory)
  - Node affinity/anti-affinity
  - Taints and tolerations
  - Data locality
  - Pod topology spread constraints
- **Process**:
  1. Watches for unscheduled pods
  2. Filters nodes (feasibility)
  3. Scores nodes (best fit)
  4. Binds pod to highest-scored node

### Controller Manager
- **Role**: Runs control loops to maintain desired state
- **Key controllers**:
  - **Deployment Controller**: Manages ReplicaSets for deployments
  - **ReplicaSet Controller**: Ensures correct number of pod replicas
  - **Service Controller**: Creates/updates load balancers
  - **Node Controller**: Monitors node health
  - **Job Controller**: Manages batch jobs
  - **PersistentVolume Controller**: Binds PVCs to PVs

### Cloud Controller Manager
- **Role**: AWS-specific integrations
- **Responsibilities**:
  - Provisions ELB/NLB/ALB for LoadBalancer services
  - Manages EBS volume lifecycle
  - Updates node metadata from EC2
  - Removes nodes when EC2 instances are terminated

## Worker Node Components

### kubelet
- **Role**: Node agent ensuring containers are running
- **Responsibilities**:
  - Watches API server for pod assignments
  - Pulls container images from registry
  - Starts/stops containers via container runtime
  - Reports pod and node status to API server
  - Executes liveness/readiness probes
  - Mounts volumes

### kube-proxy
- **Role**: Network proxy implementing Service abstraction
- **Modes**:
  - **iptables** (default): Uses Linux iptables rules for load balancing
  - **IPVS**: More efficient for large clusters
- **Responsibilities**:
  - Maintains network rules on nodes
  - Enables service discovery and load balancing
  - Forwards traffic to correct pods

### Container Runtime
- **Current**: containerd (Docker deprecated since K8s 1.24)
- **Role**: Pulls images and runs containers
- **Interface**: Communicates with kubelet via CRI (Container Runtime Interface)

## Request Flow Example

```mermaid
sequenceDiagram
    participant User
    participant kubectl
    participant API as API Server
    participant Auth as Authentication/Authorization
    participant Admission as Admission Controllers
    participant ETCD as etcd
    participant Scheduler
    participant Kubelet
    participant Runtime as Container Runtime
    participant Pod

    User->>kubectl: kubectl apply -f deployment.yaml
    kubectl->>API: HTTP POST /apis/apps/v1/deployments
    API->>Auth: Authenticate & Authorize
    Auth-->>API: Approved
    API->>Admission: Run admission controllers
    Admission-->>API: Validated & Mutated
    API->>ETCD: Store deployment
    ETCD-->>API: Stored
    API-->>kubectl: Deployment created

    Note over API,Scheduler: Deployment Controller creates ReplicaSet
    Note over API,Scheduler: ReplicaSet Controller creates Pods

    Scheduler->>API: Watch for unscheduled pods
    API-->>Scheduler: Pod pending
    Scheduler->>Scheduler: Filter & Score nodes
    Scheduler->>API: Bind pod to node-1
    API->>ETCD: Update pod (node: node-1)

    Kubelet->>API: Watch for pods on node-1
    API-->>Kubelet: New pod assigned
    Kubelet->>Runtime: Pull image & create container
    Runtime->>Pod: Start container
    Pod-->>Runtime: Running
    Runtime-->>Kubelet: Container started
    Kubelet->>API: Update pod status (Running)
    API->>ETCD: Store pod status
```

## Deployment Flow

```mermaid
graph LR
    A[Deployment] --> B[ReplicaSet v1]
    B --> C1[Pod 1]
    B --> C2[Pod 2]
    B --> C3[Pod 3]

    A --> D[ReplicaSet v2]
    D --> E1[Pod 4]
    D --> E2[Pod 5]
    D --> E3[Pod 6]

    style D fill:#90EE90
    style E1 fill:#90EE90
    style E2 fill:#90EE90
    style E3 fill:#90EE90

    style B fill:#FFB6C1
    style C1 fill:#FFB6C1
    style C2 fill:#FFB6C1
    style C3 fill:#FFB6C1
```

## Kubernetes Objects Hierarchy

```mermaid
graph TD
    Cluster[Cluster]
    Cluster --> NS1[Namespace: ecommerce-prod]
    Cluster --> NS2[Namespace: ecommerce-staging]
    Cluster --> NS3[Namespace: monitoring]

    NS1 --> Deploy[Deployment: order-service]
    Deploy --> RS[ReplicaSet: order-service-7d8f9c]
    RS --> Pod1[Pod: order-service-7d8f9c-abc]
    RS --> Pod2[Pod: order-service-7d8f9c-def]
    RS --> Pod3[Pod: order-service-7d8f9c-ghi]

    Pod1 --> C1[Container: order-service]
    Pod1 --> C2[Container: fluent-bit sidecar]

    NS1 --> SVC[Service: order-service]
    SVC -.Load Balances.-> Pod1
    SVC -.Load Balances.-> Pod2
    SVC -.Load Balances.-> Pod3

    NS1 --> ING[Ingress: api-ingress]
    ING --> SVC

    NS1 --> CM[ConfigMap: order-service-config]
    NS1 --> SEC[Secret: order-service-secrets]
    NS1 --> PVC[PVC: postgres-data]

    Pod1 -.Uses.-> CM
    Pod1 -.Uses.-> SEC
    Pod1 -.Uses.-> PVC
```

## Multi-AZ High Availability

```mermaid
graph TB
    subgraph "AWS Region: us-east-1"
        subgraph "Control Plane (Multi-AZ)"
            CP1[API Server AZ-1]
            CP2[API Server AZ-2]
            CP3[API Server AZ-3]
        end

        ELB[Network Load Balancer]
        ELB --> CP1
        ELB --> CP2
        ELB --> CP3

        subgraph "us-east-1a"
            N1[Worker Node 1]
            P1A[order-service-1]
            P1B[postgres-1]
            EBS1[(EBS Volume)]
            N1 --> P1A
            N1 --> P1B
            P1B --> EBS1
        end

        subgraph "us-east-1b"
            N2[Worker Node 2]
            P2A[order-service-2]
            P2B[payment-service-1]
            EBS2[(EBS Volume)]
            N2 --> P2A
            N2 --> P2B
        end

        subgraph "us-east-1c"
            N3[Worker Node 3]
            P3A[order-service-3]
            P3B[inventory-service-1]
            EBS3[(EBS Volume)]
            N3 --> P3A
            N3 --> P3B
        end

        EFS[(EFS - Shared Storage)]
        P1A -.ReadWriteMany.-> EFS
        P2A -.ReadWriteMany.-> EFS
        P3A -.ReadWriteMany.-> EFS
    end

    Internet[Internet Users] --> ALB[Application Load Balancer]
    ALB --> P1A
    ALB --> P2A
    ALB --> P3A
```

## Key Concepts Summary

| Component | Scope | Purpose | Managed by |
|-----------|-------|---------|------------|
| **Cluster** | Global | Complete Kubernetes deployment | You + AWS |
| **Namespace** | Cluster | Virtual cluster for isolation | You |
| **Node** | Cluster | Worker machine (EC2/Fargate) | AWS (hardware), You (registration) |
| **Pod** | Namespace | Smallest deployable unit (1+ containers) | Kubernetes |
| **Deployment** | Namespace | Declarative pod management | Kubernetes |
| **Service** | Namespace | Stable network endpoint | Kubernetes |
| **Ingress** | Namespace | HTTP(S) routing | AWS Load Balancer Controller |
| **ConfigMap** | Namespace | Non-sensitive configuration | You |
| **Secret** | Namespace | Sensitive data | You + AWS Secrets Manager |
| **PersistentVolume** | Cluster | Storage resource | AWS (EBS/EFS) |
| **PersistentVolumeClaim** | Namespace | Request for storage | You |

## EKS-Specific Architecture

```mermaid
graph TB
    subgraph "Your AWS Account"
        subgraph "EKS Control Plane VPC (AWS Managed)"
            API[API Server<br/>Multi-AZ]
            ETCD[(etcd<br/>Multi-AZ)]
        end

        subgraph "Your VPC"
            subgraph "Private Subnet 1a"
                NG1[Node Group 1]
                POD1[Pods]
                NG1 --> POD1
            end

            subgraph "Private Subnet 1b"
                NG2[Node Group 2]
                POD2[Pods]
                NG2 --> POD2
            end

            subgraph "Public Subnet 1a"
                NAT1[NAT Gateway]
            end

            subgraph "Public Subnet 1b"
                NAT2[NAT Gateway]
            end

            ALB[Application LB<br/>Public Subnets]
        end

        IAM[IAM Roles<br/>IRSA]
        ECR[ECR Registry]
        SM[Secrets Manager]
        CW[CloudWatch]

        API -.Control.-> NG1
        API -.Control.-> NG2

        NG1 --> NAT1
        NG2 --> NAT2

        POD1 -.IRSA.-> IAM
        POD2 -.IRSA.-> IAM

        IAM --> SM
        IAM --> CW

        NG1 --> ECR
        NG2 --> ECR

        ALB --> POD1
        ALB --> POD2
    end

    Internet((Internet)) --> ALB
    NAT1 --> Internet
    NAT2 --> Internet
```

## Scalability Model

```mermaid
graph LR
    subgraph "Application Scaling"
        HPA[Horizontal Pod Autoscaler]
        HPA -->|Increases replicas| Pods[More Pods]
        Metrics[Metrics: CPU, Memory, Custom] --> HPA
    end

    subgraph "Cluster Scaling"
        CA[Cluster Autoscaler<br/>or<br/>Karpenter]
        Pods -->|Need more resources| CA
        CA -->|Provisions| Nodes[More EC2 Nodes]
    end

    subgraph "Storage Scaling"
        PVC[PersistentVolumeClaim]
        PVC -->|Volume expansion| Larger[Larger EBS Volume]
    end

    style HPA fill:#90EE90
    style CA fill:#87CEEB
    style PVC fill:#FFD700
```

## Next Steps

- **[02-structure-and-components.md](./02-structure-and-components.md)**: Deep dive into Pods, Deployments, StatefulSets
- **[03-networking.md](./03-networking.md)**: Services, Ingress, Network Policies
- **[04-storage-volumes.md](./04-storage-volumes.md)**: Persistent storage with EBS and EFS
- **[05-secrets-management.md](./05-secrets-management.md)**: Secrets, ConfigMaps, AWS integration
- **[06-monitoring-observability.md](./06-monitoring-observability.md)**: Prometheus, CloudWatch, logging
- **[07-complete-example.md](./07-complete-example.md)**: Full e-commerce microservices example
- **[08-best-practices.md](./08-best-practices.md)**: Production best practices and patterns
