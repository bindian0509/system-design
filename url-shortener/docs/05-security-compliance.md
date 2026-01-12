# Security and Compliance

This document covers security architecture, threat mitigation, and compliance with GDPR, CCPA, SOC 2, and HIPAA regulations for the URL shortener system.

---

## Security Architecture Overview

```mermaid
flowchart TB
    subgraph Layer1["Layer 1: Edge Protection"]
        Shield["AWS Shield Advanced"]
        WAF["AWS WAF"]
        SignedURLs["CloudFront Signed URLs"]
        EdgeRate["Rate Limiting"]
    end

    subgraph Layer2["Layer 2: Network Security"]
        VPC["VPC"]
        PrivateSub["Private Subnets"]
        SG["Security Groups"]
        NACLs["NACLs"]
        Endpoints["VPC Endpoints"]
    end

    subgraph Layer3["Layer 3: Application Security"]
        TLS["TLS 1.3"]
        APIAuth["API Authentication"]
        InputVal["Input Validation"]
        CORS["CORS"]
        CSP["CSP Headers"]
    end

    subgraph Layer4["Layer 4: Data Security"]
        EncryptRest["Encryption at Rest"]
        EncryptTransit["Encryption in Transit"]
        KMS["Key Management"]
        Secrets["Secrets Manager"]
    end

    subgraph Layer5["Layer 5: Identity & Access"]
        IAM["IAM Roles"]
        RBAC["RBAC"]
        APIKeys["API Keys"]
        JWT["JWT Tokens"]
        SSO["SSO/SAML"]
        MFA["MFA"]
    end

    subgraph Layer6["Layer 6: Audit & Monitoring"]
        CloudTrail["CloudTrail"]
        AuditLogs["Audit Logs"]
        SIEM["SIEM"]
        Anomaly["Anomaly Detection"]
        IR["Incident Response"]
    end

    Layer1 --> Layer2 --> Layer3 --> Layer4 --> Layer5 --> Layer6
```

---

## Threat Model

### STRIDE Analysis

```mermaid
flowchart LR
    subgraph Threats["STRIDE Threats"]
        S["Spoofing<br/>Impersonate user"]
        T["Tampering<br/>Modify URLs/analytics"]
        R["Repudiation<br/>Deny actions"]
        I["Information Disclosure<br/>Data exposure"]
        D["Denial of Service<br/>Unavailability"]
        E["Elevation of Privilege<br/>Unauthorized access"]
    end

    subgraph Mitigations["Mitigations"]
        S --> M1["API key auth, JWT, IP validation"]
        T --> M2["Input validation, checksums, audit logs"]
        R --> M3["Immutable audit logs, request signing"]
        I --> M4["Encryption, access controls, data masking"]
        D --> M5["Rate limiting, WAF, auto-scaling, Shield"]
        E --> M6["RBAC, least privilege, input validation"]
    end
```

### Attack Vectors and Mitigations

```mermaid
flowchart TB
    subgraph URLCreation["1. URL Creation (/api/v1/urls)"]
        Attack1["Malicious URL injection"]
        Mit1["• URL validation<br/>• Google Safe Browsing API<br/>• Domain reputation<br/>• Rate limiting"]
        Attack1 --> Mit1
    end

    subgraph Redirect["2. Redirect Endpoint (/:code)"]
        Attack2["Open redirect vulnerability"]
        Mit2["• Validate stored URLs<br/>• No user-controlled params<br/>• Log suspicious patterns<br/>• Interstitial warning option"]
        Attack2 --> Mit2
    end

    subgraph Auth["3. Authentication"]
        Attack3["API key theft, brute force"]
        Mit3["• Argon2id hashing<br/>• Key rotation<br/>• IP allowlisting<br/>• Lockout policy<br/>• Anomaly detection"]
        Attack3 --> Mit3
    end

    subgraph DDoS["4. DDoS Attacks"]
        Attack4["Volumetric, protocol, app-layer"]
        Mit4["• AWS Shield Advanced<br/>• CloudFront absorption<br/>• WAF rate rules<br/>• Geo blocking<br/>• Auto-scaling"]
        Attack4 --> Mit4
    end
```

---

## Authentication and Authorization

### API Key Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Auth as Auth Service
    participant DB

    User->>API: Request with API Key
    API->>Auth: Validate Key
    Auth->>Auth: Extract prefix
    Auth->>DB: Lookup by prefix
    DB-->>Auth: Key hash + metadata
    Auth->>Auth: Verify Argon2id hash

    alt Valid Key
        Auth->>Auth: Check expiration
        Auth->>Auth: Verify scopes
        Auth-->>API: Authenticated
        API-->>User: 200 OK
    else Invalid Key
        Auth-->>API: Unauthorized
        API-->>User: 401 Unauthorized
    end
```

### Role-Based Access Control (RBAC)

```mermaid
flowchart TB
    subgraph Roles["RBAC Hierarchy"]
        Viewer["Viewer<br/>urls:read, analytics:read"]
        Member["Member<br/>+ urls:create, urls:update"]
        Admin["Admin<br/>+ urls:*, analytics:*, members:*, settings:*"]
        Owner["Owner<br/>All permissions"]
        SuperAdmin["Super Admin<br/>+ platform:*"]
    end

    Viewer --> Member --> Admin --> Owner --> SuperAdmin
```

---

## Data Protection

### Encryption Standards

| Data Type | At Rest | In Transit | Key Management |
|-----------|---------|------------|----------------|
| URL Mappings | AES-256 (DynamoDB) | TLS 1.3 | AWS managed |
| User Data | AES-256 | TLS 1.3 | AWS KMS |
| API Keys | Argon2id hash | TLS 1.3 | N/A (hashed) |
| Analytics | AES-256 | TLS 1.3 | AWS managed |
| Audit Logs | AES-256 (S3 SSE-KMS) | TLS 1.3 | Customer CMK |
| Secrets | AES-256 (Secrets Manager) | TLS 1.3 | AWS KMS |

### Sensitive Data Handling

```mermaid
flowchart LR
    subgraph Raw["Raw Data"]
        IP["IP Address"]
        UA["User Agent"]
        Geo["Geolocation"]
        Ref["Referrer URL"]
    end

    subgraph Transform["Privacy Transformations"]
        IP --> Hash["Hash with daily salt"]
        UA --> Generalize["Generalize (device/browser only)"]
        Geo --> Limit["Country/region only"]
        Ref --> Domain["Domain only (strip params)"]
    end

    subgraph Stored["Stored Data"]
        Hash --> SafeIP["ip_hash: sha256(...)"]
        Generalize --> SafeUA["device_type: mobile"]
        Limit --> SafeGeo["country: US"]
        Domain --> SafeRef["referrer_domain: twitter.com"]
    end
```

---

## Compliance Frameworks

### GDPR (General Data Protection Regulation)

```mermaid
flowchart TB
    subgraph Principles["Article 5: Principles"]
        Lawfulness["Lawfulness<br/>Explicit consent, documented basis"]
        Purpose["Purpose limitation<br/>Data only for stated purposes"]
        Minimization["Data minimization<br/>Only necessary data, IP hashing"]
        Accuracy["Accuracy<br/>Profile update APIs"]
        Storage["Storage limitation<br/>Automatic TTL, cleanup policies"]
        Integrity["Integrity<br/>Encryption, access controls"]
        Accountability["Accountability<br/>DPO, documentation, DPIA"]
    end

    subgraph Rights["Articles 15-22: Data Subject Rights"]
        Access["Right of Access<br/>GET /compliance/gdpr/data<br/>SLA: 30 days"]
        Rectification["Rectification<br/>PUT /users/:id<br/>SLA: 72 hours"]
        Erasure["Erasure<br/>DELETE /compliance/gdpr/*<br/>SLA: 72 hours"]
        Portability["Portability<br/>GET /compliance/gdpr/export<br/>SLA: 30 days"]
        Objection["Objection<br/>POST /compliance/gdpr/object<br/>SLA: Immediate"]
    end
```

### CCPA (California Consumer Privacy Act)

```mermaid
flowchart LR
    subgraph Categories["Data Categories Collected"]
        Identifiers["Identifiers<br/>email, IP hash, API keys"]
        Internet["Internet Activity<br/>URLs, click analytics"]
        Geolocation["Geolocation<br/>Country, region from IP"]
        Inferences["Inferences<br/>Device type, browser, bot detection"]
    end

    subgraph Rights["Consumer Rights"]
        Know["Right to Know<br/>45 days response"]
        Delete["Right to Delete<br/>45 days response"]
        OptOut["Right to Opt-Out<br/>We don't sell PI"]
        NonDiscrim["Non-Discrimination<br/>Equal service for all"]
    end
```

### SOC 2 Trust Principles

```mermaid
flowchart TB
    subgraph Security["Security (Required)"]
        AC["Access Control: RBAC, API keys, MFA"]
        LA["Logical Access: VPC, Security Groups"]
        Enc["Encryption: AES-256, TLS 1.3"]
        Mon["Monitoring: CloudWatch, GuardDuty"]
        IR["Incident Response: Runbooks, PagerDuty"]
        CM["Change Management: GitOps, PR reviews"]
        RA["Risk Assessment: Quarterly reviews, pen testing"]
    end

    subgraph Availability["Availability"]
        SLA["SLA: 99.95% uptime"]
        MultiRegion["Multi-region with auto failover"]
        DR["DR: RPO < 1 min, RTO < 15 min"]
    end

    subgraph ProcessingIntegrity["Processing Integrity"]
        Validation["Input validation on all endpoints"]
        Idempotency["Idempotent API operations"]
        Testing["Automated testing: unit, integration, e2e"]
    end

    subgraph Confidentiality["Confidentiality"]
        Classification["Data classification"]
        NeedToKnow["Need-to-know access"]
        Disposal["Secure data disposal"]
    end

    subgraph Privacy["Privacy"]
        Notice["Privacy notice at collection"]
        PurposeLimitation["Purpose limitation"]
        SubjectRights["Data subject rights (GDPR/CCPA)"]
    end
```

### HIPAA Compliance

```mermaid
flowchart TB
    subgraph Applicability["Applicability"]
        Note["Only for Enterprise tier<br/>handling PHI"]
    end

    subgraph Administrative["Administrative Safeguards"]
        SO["Security Officer"]
        RA["Annual Risk Analysis"]
        Training["Annual HIPAA Training"]
        Access["Access Management"]
        IR["60-day Breach Notification"]
    end

    subgraph Physical["Physical Safeguards"]
        Facility["AWS Data Centers (SOC 2)"]
        Workstation["AWS managed"]
        Device["Encrypted EBS, Secure disposal"]
    end

    subgraph Technical["Technical Safeguards"]
        UniqueID["Unique user identification"]
        AutoLogoff["Automatic logoff"]
        AuditControls["All access logged to S3"]
        TLS["TLS 1.3 for all transmission"]
    end

    subgraph BAA["Business Associate Agreement"]
        Required["BAA required for Enterprise"]
        AWS["AWS BAA in place"]
    end
```

---

## AWS WAF Rules

```mermaid
flowchart TB
    subgraph WAFRules["WAF Rule Set"]
        Rule1["Priority 1: Rate Limit<br/>2000 req/IP"]
        Rule2["Priority 2: SQL Injection<br/>Block SQLi patterns"]
        Rule3["Priority 3: XSS<br/>Block XSS patterns"]
        Rule4["Priority 4: Geo Block<br/>KP, IR, SY, CU"]
        Rule5["Priority 5: AWS Common Rules<br/>Managed ruleset"]
        Rule6["Priority 6: Bot Control<br/>Managed ruleset"]
    end

    Request["Incoming Request"] --> Rule1
    Rule1 --> Rule2 --> Rule3 --> Rule4 --> Rule5 --> Rule6 --> Allow["Allow"]

    Rule1 -->|"Block"| Blocked["403 Forbidden"]
    Rule2 -->|"Block"| Blocked
    Rule3 -->|"Block"| Blocked
    Rule4 -->|"Block"| Blocked
```

---

## Incident Response

### Security Incident Classification

| Severity | Description | Response Time | Example |
|----------|-------------|---------------|---------|
| P1 - Critical | Active breach, data exposure | 15 minutes | Data exfiltration detected |
| P2 - High | Potential breach, vulnerability exploited | 1 hour | Unauthorized access attempt |
| P3 - Medium | Security concern, no breach | 4 hours | Suspicious activity pattern |
| P4 - Low | Minor issue, no immediate risk | 24 hours | Failed login attempts |

### Incident Response Workflow

```mermaid
flowchart TB
    Detection["Detection<br/>GuardDuty, WAF, Anomaly alerts, User reports"]

    Triage["Triage<br/>• Assess scope/severity<br/>• Identify affected systems<br/>• Determine if breach occurred"]

    Containment["Containment<br/>• Isolate affected systems<br/>• Revoke compromised credentials<br/>• Block malicious IPs<br/>• Enable enhanced logging"]

    Eradication["Eradication<br/>• Remove malicious artifacts<br/>• Patch vulnerabilities<br/>• Reset affected credentials"]

    Recovery["Recovery<br/>• Restore from clean backups<br/>• Validate functionality<br/>• Monitor for recurrence"]

    PostIncident["Post-Incident<br/>• Conduct postmortem<br/>• Update runbooks<br/>• Implement preventive measures<br/>• Notify affected parties"]

    Detection --> Triage --> Containment --> Eradication --> Recovery --> PostIncident
```

### Notification Requirements

```mermaid
flowchart LR
    subgraph Breach["Data Breach"]
        Detected["Breach Detected"]
    end

    subgraph GDPR["GDPR"]
        GDPR_Timeline["72 hours to DPA"]
        GDPR_Threshold["Risk to individuals"]
    end

    subgraph HIPAA["HIPAA"]
        HIPAA_Timeline["60 days to HHS"]
        HIPAA_Threshold["500+ individuals affected"]
    end

    subgraph CCPA["CCPA"]
        CCPA_Timeline["Most expedient time"]
        CCPA_Threshold["Any unencrypted PI breach"]
    end

    Breach --> GDPR
    Breach --> HIPAA
    Breach --> CCPA
```

---

## Security Compliance Checklist

### Pre-Launch Security Review

- [ ] Threat model documented and reviewed
- [ ] Penetration test completed (no critical/high findings)
- [ ] Security architecture review completed
- [ ] All dependencies scanned for vulnerabilities
- [ ] Secrets management implemented (no hardcoded secrets)
- [ ] Encryption at rest and in transit verified
- [ ] Access controls tested and documented
- [ ] Audit logging functional and verified
- [ ] Incident response runbook documented
- [ ] Security monitoring and alerting configured

### Ongoing Security Operations

- [ ] Weekly vulnerability scans
- [ ] Monthly access review
- [ ] Quarterly penetration testing
- [ ] Annual security training
- [ ] Annual risk assessment
- [ ] Continuous dependency monitoring
- [ ] Regular backup and recovery testing
