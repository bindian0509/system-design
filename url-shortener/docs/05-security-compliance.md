# Security and Compliance

This document covers security architecture, threat mitigation, and compliance with GDPR, CCPA, SOC 2, and HIPAA regulations for the URL shortener system.

---

## Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY LAYERS                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Layer 1: Edge Protection                                                        │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  AWS Shield Advanced │ AWS WAF │ CloudFront Signed URLs │ Rate Limiting   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                     │
│  Layer 2: Network Security                 ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  VPC │ Private Subnets │ Security Groups │ NACLs │ VPC Endpoints          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                     │
│  Layer 3: Application Security             ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  TLS 1.3 │ API Authentication │ Input Validation │ CORS │ CSP Headers     │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                     │
│  Layer 4: Data Security                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  Encryption at Rest │ Encryption in Transit │ Key Management │ Secrets    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                     │
│  Layer 5: Identity & Access                ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  IAM Roles │ RBAC │ API Keys │ JWT Tokens │ SSO/SAML │ MFA                │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                     │
│  Layer 6: Audit & Monitoring               ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  CloudTrail │ Audit Logs │ SIEM │ Anomaly Detection │ Incident Response   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Threat Model

### STRIDE Analysis

| Threat | Description | Mitigation |
|--------|-------------|------------|
| **Spoofing** | Attacker impersonates legitimate user | API key auth, JWT with RS256, IP validation |
| **Tampering** | Modification of URLs or analytics | Input validation, checksums, audit logs |
| **Repudiation** | User denies actions | Immutable audit logs, request signing |
| **Information Disclosure** | Exposure of sensitive data | Encryption, access controls, data masking |
| **Denial of Service** | Service unavailability | Rate limiting, WAF, auto-scaling, Shield |
| **Elevation of Privilege** | Unauthorized access escalation | RBAC, least privilege, input validation |

### Attack Vectors and Mitigations

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ATTACK SURFACE                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1. URL Creation Endpoint (/api/v1/urls)                                        │
│     ┌─────────────────────────────────────────────────────────────────────────┐ │
│     │ Attack: Malicious URL injection (phishing, malware)                     │ │
│     │ Mitigation:                                                              │ │
│     │   • URL validation (scheme, domain, path)                               │ │
│     │   • Integration with Google Safe Browsing API                           │ │
│     │   • Domain reputation checking                                          │ │
│     │   • Rate limiting per user/IP                                           │ │
│     │   • Content-Type validation                                             │ │
│     └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  2. Redirect Endpoint (/:code)                                                  │
│     ┌─────────────────────────────────────────────────────────────────────────┐ │
│     │ Attack: Open redirect vulnerability                                      │ │
│     │ Mitigation:                                                              │ │
│     │   • Validate stored URLs on redirect                                    │ │
│     │   • No user-controlled redirect parameters                              │ │
│     │   • Log suspicious redirect patterns                                    │ │
│     │   • Interstitial warning page option                                    │ │
│     └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  3. Authentication                                                              │
│     ┌─────────────────────────────────────────────────────────────────────────┐ │
│     │ Attack: API key theft, brute force                                      │ │
│     │ Mitigation:                                                              │ │
│     │   • API keys hashed with Argon2id                                       │ │
│     │   • Key rotation policies                                               │ │
│     │   • IP allowlisting option                                              │ │
│     │   • Failed attempt lockout                                              │ │
│     │   • Anomaly detection for unusual patterns                              │ │
│     └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  4. DDoS Attacks                                                                │
│     ┌─────────────────────────────────────────────────────────────────────────┐ │
│     │ Attack: Volumetric, protocol, application-layer attacks                 │ │
│     │ Mitigation:                                                              │ │
│     │   • AWS Shield Advanced (DDoS protection)                               │ │
│     │   • CloudFront (absorbs attack traffic)                                 │ │
│     │   • WAF rate limiting rules                                             │ │
│     │   • Geographic blocking for attack sources                              │ │
│     │   • Auto-scaling for legitimate traffic spikes                          │ │
│     └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Authentication and Authorization

### API Key Authentication

```rust
use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier};
use rand::Rng;

/// API Key structure
/// Format: prefix_randomBytes
/// Example: urlsh_sk_a1b2c3d4e5f6g7h8i9j0
pub struct ApiKey {
    /// Visible prefix for identification (first 8 chars)
    pub prefix: String,
    /// Argon2id hash of the full key
    pub hash: String,
    /// Associated user ID
    pub user_id: String,
    /// Scopes: ["read", "write", "delete", "admin"]
    pub scopes: Vec<String>,
    /// Rate limit override (requests per hour)
    pub rate_limit: Option<u32>,
    /// IP allowlist (empty = all allowed)
    pub allowed_ips: Vec<String>,
    /// Expiration timestamp
    pub expires_at: Option<DateTime<Utc>>,
}

impl ApiKey {
    /// Generate a new API key
    pub fn generate(user_id: &str, scopes: Vec<String>) -> (String, Self) {
        let mut rng = rand::thread_rng();

        // Generate random bytes
        let random_bytes: [u8; 24] = rng.gen();
        let encoded = base62::encode(&random_bytes);

        // Full key format: urlsh_sk_<encoded>
        let full_key = format!("urlsh_sk_{}", encoded);
        let prefix = full_key[..16].to_string();

        // Hash with Argon2id
        let salt = argon2::password_hash::SaltString::generate(&mut rng);
        let argon2 = Argon2::default();
        let hash = argon2
            .hash_password(full_key.as_bytes(), &salt)
            .unwrap()
            .to_string();

        let api_key = Self {
            prefix,
            hash,
            user_id: user_id.to_string(),
            scopes,
            rate_limit: None,
            allowed_ips: vec![],
            expires_at: None,
        };

        // Return full key (only shown once) and the stored key object
        (full_key, api_key)
    }

    /// Verify an API key
    pub fn verify(&self, provided_key: &str) -> bool {
        let parsed_hash = PasswordHash::new(&self.hash).unwrap();
        Argon2::default()
            .verify_password(provided_key.as_bytes(), &parsed_hash)
            .is_ok()
    }
}
```

### JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-2024-01"
  },
  "payload": {
    "sub": "user_uuid",
    "iss": "https://api.shortener.io",
    "aud": "https://api.shortener.io",
    "iat": 1704067200,
    "exp": 1704153600,
    "scope": ["read", "write"],
    "tier": "premium",
    "workspace_id": "ws_uuid",
    "roles": ["admin", "member"]
  }
}
```

### Role-Based Access Control (RBAC)

```yaml
roles:
  viewer:
    description: "Read-only access"
    permissions:
      - urls:read
      - analytics:read

  member:
    description: "Standard user access"
    permissions:
      - urls:read
      - urls:create
      - urls:update
      - analytics:read

  admin:
    description: "Full workspace access"
    permissions:
      - urls:*
      - analytics:*
      - members:read
      - members:invite
      - members:remove
      - settings:read
      - settings:update

  owner:
    description: "Workspace owner"
    permissions:
      - "*"  # All permissions

  super_admin:
    description: "Platform administrator"
    permissions:
      - "*"
      - platform:*
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

```rust
/// Personal data categories and handling
pub enum PersonalDataCategory {
    /// IP addresses - hash before storage
    IpAddress,
    /// User agent strings - truncate and generalize
    UserAgent,
    /// Geographic data - city-level only, no precise location
    GeoLocation,
    /// Referrer URLs - domain only, strip query params
    Referrer,
}

/// Privacy-preserving data transformation
pub fn sanitize_click_event(event: RawClickEvent) -> SanitizedClickEvent {
    SanitizedClickEvent {
        short_code: event.short_code,
        timestamp: event.timestamp,

        // Hash IP with daily salt (prevents long-term tracking)
        ip_hash: hash_with_daily_salt(&event.ip_address),

        // Generalize location to country/region only
        country: event.country,
        region: event.region,
        city: None,  // Don't store city for privacy

        // Extract only domain from referrer
        referrer_domain: extract_domain(&event.referrer),

        // Generalize user agent
        device_type: parse_device_type(&event.user_agent),
        browser_family: parse_browser_family(&event.user_agent),
        os_family: parse_os_family(&event.user_agent),

        // Don't store raw user agent
        user_agent: None,
    }
}

/// Hash IP with rotating daily salt
fn hash_with_daily_salt(ip: &str) -> String {
    let today = Utc::now().format("%Y-%m-%d").to_string();
    let salt = get_daily_salt(&today);  // Retrieved from Secrets Manager

    let mut hasher = Sha256::new();
    hasher.update(ip.as_bytes());
    hasher.update(salt.as_bytes());

    hex::encode(hasher.finalize())
}
```

---

## Compliance Frameworks

### GDPR (General Data Protection Regulation)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          GDPR COMPLIANCE                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Article 5: Principles                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ Principle              │ Implementation                                     ││
│  ├────────────────────────┼────────────────────────────────────────────────────┤│
│  │ Lawfulness            │ Explicit consent collection, documented basis      ││
│  │ Purpose limitation    │ Data only used for stated purposes                 ││
│  │ Data minimization     │ Only collect necessary data, IP hashing            ││
│  │ Accuracy              │ User profile update APIs, correction requests      ││
│  │ Storage limitation    │ Automatic TTL, cleanup policies                    ││
│  │ Integrity             │ Encryption, access controls, audit logs            ││
│  │ Accountability        │ DPO appointment, documentation, DPIA               ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Article 15-22: Data Subject Rights                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ Right                  │ API Endpoint              │ SLA                    ││
│  ├────────────────────────┼───────────────────────────┼────────────────────────┤│
│  │ Access (Art 15)        │ GET /compliance/gdpr/data │ 30 days               ││
│  │ Rectification (Art 16) │ PUT /users/:id            │ 72 hours              ││
│  │ Erasure (Art 17)       │ DELETE /compliance/gdpr/* │ 72 hours              ││
│  │ Portability (Art 20)   │ GET /compliance/gdpr/export│ 30 days              ││
│  │ Objection (Art 21)     │ POST /compliance/gdpr/object│ Immediate           ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Data Residency Requirements                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • EU user data stays in EU region (eu-west-1)                               ││
│  │ • DynamoDB Global Tables with regional filtering                            ││
│  │ • Analytics data processed in same region as user                           ││
│  │ • Cross-border transfer only with SCCs or adequacy decision                 ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### GDPR Implementation

```rust
/// GDPR compliance module

pub struct GdprService {
    dynamo: DynamoClient,
    s3: S3Client,
    kinesis: KinesisClient,
}

impl GdprService {
    /// Article 15: Right of Access
    /// Returns all personal data associated with a user
    pub async fn get_user_data(&self, user_id: &str) -> Result<UserDataExport, Error> {
        let mut export = UserDataExport::new(user_id);

        // 1. User profile
        export.profile = self.get_user_profile(user_id).await?;

        // 2. All URLs created by user
        export.urls = self.get_user_urls(user_id).await?;

        // 3. API keys (metadata only, not secrets)
        export.api_keys = self.get_user_api_keys(user_id).await?;

        // 4. Analytics data (aggregated)
        export.analytics = self.get_user_analytics(user_id).await?;

        // 5. Audit log entries
        export.audit_logs = self.get_user_audit_logs(user_id).await?;

        Ok(export)
    }

    /// Article 17: Right to Erasure ("Right to be Forgotten")
    /// Complete deletion within 72 hours
    pub async fn erasure_request(
        &self,
        user_id: &str,
        request_id: &str,
    ) -> Result<ErasureConfirmation, Error> {
        // 1. Validate request
        let user = self.get_user_profile(user_id).await?;

        // 2. Check for legal holds or legitimate interest exceptions
        if self.has_legal_hold(user_id).await? {
            return Err(Error::LegalHoldActive);
        }

        // 3. Create immutable audit record (retained for compliance)
        let audit_entry = AuditEntry {
            action: "gdpr_erasure_initiated",
            user_id: user_id.to_string(),
            request_id: request_id.to_string(),
            timestamp: Utc::now(),
            metadata: serde_json::json!({
                "data_categories": ["profile", "urls", "analytics", "api_keys"],
                "requested_by": "data_subject",
            }),
        };
        self.create_audit_log(audit_entry).await?;

        // 4. Delete all user data
        let deletion_tasks = vec![
            self.delete_user_urls(user_id),
            self.delete_user_analytics(user_id),
            self.delete_user_api_keys(user_id),
            self.delete_user_profile(user_id),
        ];

        futures::future::try_join_all(deletion_tasks).await?;

        // 5. Invalidate all caches globally
        self.invalidate_user_caches(user_id).await?;

        // 6. Create confirmation
        Ok(ErasureConfirmation {
            request_id: request_id.to_string(),
            user_id: user_id.to_string(),
            completed_at: Utc::now(),
            data_categories_deleted: vec![
                "profile", "urls", "analytics", "api_keys", "sessions"
            ],
            retention_exceptions: vec![
                "audit_logs (7 year legal retention)"
            ],
        })
    }

    /// Article 20: Right to Data Portability
    /// Export data in machine-readable format
    pub async fn export_data(
        &self,
        user_id: &str,
        format: ExportFormat,
    ) -> Result<ExportResult, Error> {
        let data = self.get_user_data(user_id).await?;

        let (content, content_type) = match format {
            ExportFormat::Json => (
                serde_json::to_string_pretty(&data)?,
                "application/json"
            ),
            ExportFormat::Csv => (
                self.to_csv(&data)?,
                "text/csv"
            ),
        };

        // Upload to S3 with 7-day expiration
        let key = format!("exports/{}/{}.{}",
            user_id,
            Uuid::new_v4(),
            format.extension()
        );

        self.s3.put_object()
            .bucket("url-shortener-exports")
            .key(&key)
            .body(content.into())
            .content_type(content_type)
            .expires(Utc::now() + Duration::days(7))
            .send()
            .await?;

        // Generate pre-signed URL
        let download_url = self.generate_presigned_url(&key, Duration::hours(24))?;

        Ok(ExportResult {
            download_url,
            expires_at: Utc::now() + Duration::hours(24),
            format,
            size_bytes: content.len(),
        })
    }
}
```

### CCPA (California Consumer Privacy Act)

```yaml
ccpa_compliance:
  # Categories of personal information collected
  data_categories:
    - identifiers: "email, IP address (hashed), API keys"
    - internet_activity: "URLs created, click analytics, referrers"
    - geolocation: "Country, region (derived from IP)"
    - inferences: "Device type, browser, bot detection"

  # Consumer rights implementation
  rights:
    right_to_know:
      endpoint: "GET /compliance/ccpa/disclosures"
      description: "Disclose categories and specific pieces of PI"
      response_time: "45 days"

    right_to_delete:
      endpoint: "DELETE /compliance/ccpa/data"
      description: "Delete consumer's personal information"
      response_time: "45 days"
      exceptions:
        - "Legal obligations"
        - "Security incident detection"
        - "Contract fulfillment"

    right_to_opt_out:
      endpoint: "POST /compliance/ccpa/opt-out"
      description: "Opt out of sale of personal information"
      note: "We do not sell personal information"

    right_to_non_discrimination:
      description: "Equal service regardless of privacy choices"
      implementation: "No feature restrictions for opt-out users"

  # Required disclosures
  disclosures:
    privacy_policy:
      location: "https://shortener.io/privacy"
      update_frequency: "Annual minimum"

    collection_notice:
      display: "At or before point of collection"
      content: "Categories of PI, purposes, rights"

    do_not_sell_link:
      location: "Footer of all pages"
      text: "Do Not Sell My Personal Information"
```

### SOC 2 Type II

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SOC 2 TRUST PRINCIPLES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Security (Required)                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ Control              │ Implementation                     │ Evidence        ││
│  ├──────────────────────┼────────────────────────────────────┼─────────────────┤│
│  │ Access Control       │ RBAC, API keys, MFA               │ IAM policies    ││
│  │ Logical Access       │ VPC, Security Groups, NACLs       │ VPC Flow Logs   ││
│  │ Encryption           │ AES-256 at rest, TLS 1.3 transit  │ Config docs     ││
│  │ Monitoring           │ CloudWatch, GuardDuty, X-Ray      │ Alert history   ││
│  │ Incident Response    │ Runbooks, PagerDuty, postmortems  │ Incident logs   ││
│  │ Change Management    │ GitOps, PR reviews, CI/CD         │ Git history     ││
│  │ Risk Assessment      │ Quarterly reviews, pen testing    │ Reports         ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Availability                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • SLA: 99.95% uptime (22 min/month downtime)                               ││
│  │ • Multi-region deployment with automatic failover                           ││
│  │ • Disaster recovery: RPO < 1 min, RTO < 15 min                             ││
│  │ • Capacity planning and auto-scaling                                        ││
│  │ • Regular DR drills (quarterly)                                             ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Processing Integrity                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • Input validation on all endpoints                                         ││
│  │ • Idempotency for API operations                                            ││
│  │ • Checksums for data integrity                                              ││
│  │ • Automated testing: unit, integration, e2e                                 ││
│  │ • Error handling and retry logic                                            ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Confidentiality                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • Data classification (Public, Internal, Confidential, Restricted)         ││
│  │ • Need-to-know access policies                                              ││
│  │ • NDA requirements for employees and contractors                            ││
│  │ • Secure data disposal procedures                                           ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Privacy                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • Privacy notice at data collection                                         ││
│  │ • Purpose limitation for data use                                           ││
│  │ • Data subject rights implementation (GDPR/CCPA)                            ││
│  │ • Third-party data processing agreements                                    ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### HIPAA (Health Insurance Portability and Accountability Act)

```yaml
hipaa_compliance:
  applicability:
    description: "Only applies to Enterprise tier customers handling PHI"
    note: "URL shortener does NOT store PHI in URL content by design"

  administrative_safeguards:
    security_officer: "Designated Security Officer"
    risk_analysis: "Annual risk assessment"
    workforce_training: "Annual HIPAA training"
    access_management: "Unique user IDs, automatic logoff"
    incident_response: "60-day breach notification"

  physical_safeguards:
    facility_access: "AWS data centers (SOC 2 certified)"
    workstation_security: "AWS managed"
    device_media_controls: "Encrypted EBS, secure disposal"

  technical_safeguards:
    access_control:
      - "Unique user identification"
      - "Emergency access procedures"
      - "Automatic logoff (session timeout)"
      - "Encryption and decryption"

    audit_controls:
      - "All access logged to S3"
      - "7-year retention"
      - "Tamper-evident storage"

    integrity:
      - "Input validation"
      - "Checksums for data at rest"

    transmission_security:
      - "TLS 1.3 for all transmission"
      - "No unencrypted channels"

  business_associate_agreement:
    requirement: "BAA required for Enterprise customers with PHI"
    template: "Available upon request"
    aws_baa: "AWS BAA in place for underlying infrastructure"

  minimum_necessary:
    implementation: |
      URL shortener by design does not access or store URL content.
      Analytics data is aggregated and does not contain PHI.
      Audit logs capture access metadata only.
```

---

## Security Controls Implementation

### AWS WAF Rules

```json
{
  "Name": "URLShortenerWAFRules",
  "Rules": [
    {
      "Name": "RateLimitRule",
      "Priority": 1,
      "Statement": {
        "RateBasedStatement": {
          "Limit": 2000,
          "AggregateKeyType": "IP"
        }
      },
      "Action": { "Block": {} }
    },
    {
      "Name": "SQLInjectionRule",
      "Priority": 2,
      "Statement": {
        "SqliMatchStatement": {
          "FieldToMatch": { "AllQueryArguments": {} },
          "TextTransformations": [
            { "Priority": 0, "Type": "URL_DECODE" },
            { "Priority": 1, "Type": "HTML_ENTITY_DECODE" }
          ]
        }
      },
      "Action": { "Block": {} }
    },
    {
      "Name": "XSSRule",
      "Priority": 3,
      "Statement": {
        "XssMatchStatement": {
          "FieldToMatch": { "Body": {} },
          "TextTransformations": [
            { "Priority": 0, "Type": "URL_DECODE" },
            { "Priority": 1, "Type": "HTML_ENTITY_DECODE" }
          ]
        }
      },
      "Action": { "Block": {} }
    },
    {
      "Name": "GeoBlockRule",
      "Priority": 4,
      "Statement": {
        "GeoMatchStatement": {
          "CountryCodes": ["KP", "IR", "SY", "CU"]
        }
      },
      "Action": { "Block": {} }
    },
    {
      "Name": "AWSManagedRulesCommonRuleSet",
      "Priority": 5,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesCommonRuleSet"
        }
      },
      "OverrideAction": { "None": {} }
    },
    {
      "Name": "AWSManagedRulesBotControlRuleSet",
      "Priority": 6,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesBotControlRuleSet"
        }
      },
      "OverrideAction": { "None": {} }
    }
  ]
}
```

### Input Validation

```rust
use validator::{Validate, ValidationError};
use url::Url;

#[derive(Debug, Validate)]
pub struct CreateUrlRequest {
    #[validate(url, length(max = 4096))]
    pub url: String,

    #[validate(custom = "validate_custom_alias")]
    pub custom_alias: Option<String>,

    #[validate(range(min = 60, max = 31536000))]  // 1 min to 1 year
    pub ttl_seconds: Option<i64>,

    #[validate(length(max = 10))]
    pub tags: Option<Vec<String>>,
}

fn validate_custom_alias(alias: &str) -> Result<(), ValidationError> {
    // Must be 4-20 characters
    if alias.len() < 4 || alias.len() > 20 {
        return Err(ValidationError::new("alias_length"));
    }

    // Only alphanumeric and hyphens
    if !alias.chars().all(|c| c.is_alphanumeric() || c == '-') {
        return Err(ValidationError::new("alias_characters"));
    }

    // Cannot start or end with hyphen
    if alias.starts_with('-') || alias.ends_with('-') {
        return Err(ValidationError::new("alias_format"));
    }

    // Block reserved words
    let reserved = ["api", "admin", "health", "metrics", "login", "signup"];
    if reserved.contains(&alias.to_lowercase().as_str()) {
        return Err(ValidationError::new("alias_reserved"));
    }

    Ok(())
}

/// URL safety check
pub async fn is_url_safe(url: &str) -> Result<bool, Error> {
    let parsed = Url::parse(url)?;

    // 1. Scheme validation (only http/https)
    if parsed.scheme() != "http" && parsed.scheme() != "https" {
        return Ok(false);
    }

    // 2. Block localhost and private IPs
    if let Some(host) = parsed.host_str() {
        if is_private_host(host) {
            return Ok(false);
        }
    }

    // 3. Check Google Safe Browsing API
    let is_safe = google_safe_browsing_check(url).await?;
    if !is_safe {
        return Ok(false);
    }

    // 4. Check domain reputation (optional)
    let reputation = check_domain_reputation(parsed.host_str().unwrap()).await?;
    if reputation.score < 0.5 {
        return Ok(false);
    }

    Ok(true)
}
```

### Audit Logging

```rust
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Debug, Serialize, Deserialize)]
pub struct AuditEvent {
    pub event_id: String,
    pub timestamp: DateTime<Utc>,
    pub event_type: AuditEventType,

    // Actor
    pub actor: Actor,

    // Resource
    pub resource_type: String,
    pub resource_id: Option<String>,

    // Request context
    pub request_id: String,
    pub source_ip: String,
    pub user_agent: Option<String>,

    // Changes
    pub action: String,
    pub outcome: Outcome,
    pub changes: Option<Changes>,

    // Compliance flags
    pub gdpr_relevant: bool,
    pub pii_accessed: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Actor {
    pub actor_type: ActorType,
    pub user_id: Option<String>,
    pub api_key_prefix: Option<String>,
    pub service_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum ActorType {
    User,
    ApiKey,
    Service,
    System,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Changes {
    pub before: Option<serde_json::Value>,
    pub after: Option<serde_json::Value>,
    pub fields_changed: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum Outcome {
    Success,
    Failure { reason: String },
    Denied { reason: String },
}

/// Audit logger implementation
pub struct AuditLogger {
    kinesis: KinesisClient,
    stream_name: String,
}

impl AuditLogger {
    pub async fn log(&self, event: AuditEvent) -> Result<(), Error> {
        let data = serde_json::to_vec(&event)?;

        self.kinesis.put_record()
            .stream_name(&self.stream_name)
            .partition_key(&event.actor.user_id.unwrap_or_else(|| event.request_id.clone()))
            .data(Blob::new(data))
            .send()
            .await?;

        Ok(())
    }
}

// Example audit events
impl AuditEvent {
    pub fn url_created(url: &Url, actor: &Actor, request_id: &str) -> Self {
        Self {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            event_type: AuditEventType::DataAccess,
            actor: actor.clone(),
            resource_type: "url".to_string(),
            resource_id: Some(url.short_code.clone()),
            request_id: request_id.to_string(),
            source_ip: "masked".to_string(),  // PII protection
            user_agent: None,
            action: "create".to_string(),
            outcome: Outcome::Success,
            changes: Some(Changes {
                before: None,
                after: Some(serde_json::json!({
                    "short_code": url.short_code,
                    "tier": url.tier,
                })),
                fields_changed: vec!["short_code".to_string()],
            }),
            gdpr_relevant: true,
            pii_accessed: false,
        }
    }

    pub fn gdpr_erasure(user_id: &str, request_id: &str) -> Self {
        Self {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            event_type: AuditEventType::Compliance,
            actor: Actor {
                actor_type: ActorType::System,
                user_id: None,
                api_key_prefix: None,
                service_name: Some("gdpr-service".to_string()),
            },
            resource_type: "user".to_string(),
            resource_id: Some(user_id.to_string()),
            request_id: request_id.to_string(),
            source_ip: "internal".to_string(),
            user_agent: None,
            action: "gdpr_erasure".to_string(),
            outcome: Outcome::Success,
            changes: None,  // Don't log PII in audit
            gdpr_relevant: true,
            pii_accessed: true,
        }
    }
}
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

### Incident Response Runbook

```yaml
incident_response:
  detection:
    sources:
      - GuardDuty findings
      - WAF block events
      - Anomaly detection alerts
      - User reports

  triage:
    steps:
      - Assess scope and severity
      - Identify affected systems/data
      - Determine if breach occurred
      - Classify incident severity

  containment:
    immediate:
      - Isolate affected systems
      - Revoke compromised credentials
      - Block malicious IPs/patterns
      - Enable enhanced logging

  eradication:
    steps:
      - Remove malicious artifacts
      - Patch vulnerabilities
      - Reset affected credentials
      - Verify system integrity

  recovery:
    steps:
      - Restore from clean backups
      - Validate system functionality
      - Monitor for recurrence
      - Gradually restore access

  post_incident:
    steps:
      - Conduct postmortem
      - Update runbooks
      - Implement preventive measures
      - Notify affected parties (if required)

  notification_requirements:
    gdpr:
      timeline: "72 hours to DPA"
      threshold: "Risk to individuals"

    hipaa:
      timeline: "60 days to HHS"
      threshold: "500+ individuals affected"

    ccpa:
      timeline: "Most expedient time possible"
      threshold: "Any breach of unencrypted PI"
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
