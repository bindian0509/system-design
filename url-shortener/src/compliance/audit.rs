//! Audit logging for compliance

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::instrument;
use uuid::Uuid;

/// Audit event types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuditEventType {
    // URL events
    UrlCreated,
    UrlUpdated,
    UrlDeleted,
    UrlAccessed,

    // User events
    UserCreated,
    UserUpdated,
    UserDeleted,
    UserLogin,
    UserLogout,

    // API key events
    ApiKeyCreated,
    ApiKeyRevoked,

    // Compliance events
    GdprExportRequested,
    GdprErasureRequested,
    GdprErasureCompleted,

    // Admin events
    ConfigChanged,
    SystemEvent,
}

/// Audit event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub event_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub event_type: AuditEventType,

    // Actor information
    pub actor_type: ActorType,
    pub actor_id: Option<String>,
    pub actor_ip: Option<String>,

    // Resource information
    pub resource_type: String,
    pub resource_id: Option<String>,

    // Request context
    pub request_id: Option<String>,

    // Event details
    pub action: String,
    pub outcome: Outcome,
    pub changes: Option<serde_json::Value>,
    pub metadata: Option<serde_json::Value>,

    // Compliance flags
    pub gdpr_relevant: bool,
    pub pii_accessed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ActorType {
    User,
    ApiKey,
    Service,
    System,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Outcome {
    Success,
    Failure,
    Denied,
}

/// Audit logger
pub struct AuditLogger {
    // In production, this would write to Kinesis/S3
    // For development, we use an in-memory buffer
    buffer: Arc<RwLock<VecDeque<AuditEvent>>>,
    max_buffer_size: usize,
}

impl AuditLogger {
    pub fn new(max_buffer_size: usize) -> Self {
        Self {
            buffer: Arc::new(RwLock::new(VecDeque::with_capacity(max_buffer_size))),
            max_buffer_size,
        }
    }

    /// Log an audit event
    #[instrument(skip(self, event))]
    pub async fn log(&self, event: AuditEvent) {
        let mut buffer = self.buffer.write().await;

        // Remove oldest events if buffer is full
        while buffer.len() >= self.max_buffer_size {
            buffer.pop_front();
        }

        tracing::info!(
            event_id = %event.event_id,
            event_type = ?event.event_type,
            actor_id = ?event.actor_id,
            resource_type = %event.resource_type,
            resource_id = ?event.resource_id,
            outcome = ?event.outcome,
            "Audit event logged"
        );

        buffer.push_back(event);
    }

    /// Get recent audit events
    pub async fn get_recent(&self, limit: usize) -> Vec<AuditEvent> {
        let buffer = self.buffer.read().await;
        buffer.iter().rev().take(limit).cloned().collect()
    }

    /// Get audit events for a specific resource
    pub async fn get_for_resource(
        &self,
        resource_type: &str,
        resource_id: &str,
    ) -> Vec<AuditEvent> {
        let buffer = self.buffer.read().await;
        buffer
            .iter()
            .filter(|e| {
                e.resource_type == resource_type
                    && e.resource_id.as_deref() == Some(resource_id)
            })
            .cloned()
            .collect()
    }

    /// Get audit events for a specific actor
    pub async fn get_for_actor(&self, actor_id: &str) -> Vec<AuditEvent> {
        let buffer = self.buffer.read().await;
        buffer
            .iter()
            .filter(|e| e.actor_id.as_deref() == Some(actor_id))
            .cloned()
            .collect()
    }
}

impl Default for AuditLogger {
    fn default() -> Self {
        Self::new(10000)
    }
}

/// Builder for creating audit events
pub struct AuditEventBuilder {
    event_type: AuditEventType,
    actor_type: ActorType,
    actor_id: Option<String>,
    actor_ip: Option<String>,
    resource_type: String,
    resource_id: Option<String>,
    request_id: Option<String>,
    action: String,
    outcome: Outcome,
    changes: Option<serde_json::Value>,
    metadata: Option<serde_json::Value>,
    gdpr_relevant: bool,
    pii_accessed: bool,
}

impl AuditEventBuilder {
    pub fn new(event_type: AuditEventType, resource_type: &str, action: &str) -> Self {
        Self {
            event_type,
            actor_type: ActorType::System,
            actor_id: None,
            actor_ip: None,
            resource_type: resource_type.to_string(),
            resource_id: None,
            request_id: None,
            action: action.to_string(),
            outcome: Outcome::Success,
            changes: None,
            metadata: None,
            gdpr_relevant: false,
            pii_accessed: false,
        }
    }

    pub fn actor(mut self, actor_type: ActorType, actor_id: Option<String>) -> Self {
        self.actor_type = actor_type;
        self.actor_id = actor_id;
        self
    }

    pub fn actor_ip(mut self, ip: String) -> Self {
        self.actor_ip = Some(ip);
        self
    }

    pub fn resource_id(mut self, id: String) -> Self {
        self.resource_id = Some(id);
        self
    }

    pub fn request_id(mut self, id: String) -> Self {
        self.request_id = Some(id);
        self
    }

    pub fn outcome(mut self, outcome: Outcome) -> Self {
        self.outcome = outcome;
        self
    }

    pub fn changes(mut self, changes: serde_json::Value) -> Self {
        self.changes = Some(changes);
        self
    }

    pub fn metadata(mut self, metadata: serde_json::Value) -> Self {
        self.metadata = Some(metadata);
        self
    }

    pub fn gdpr_relevant(mut self) -> Self {
        self.gdpr_relevant = true;
        self
    }

    pub fn pii_accessed(mut self) -> Self {
        self.pii_accessed = true;
        self
    }

    pub fn build(self) -> AuditEvent {
        AuditEvent {
            event_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            event_type: self.event_type,
            actor_type: self.actor_type,
            actor_id: self.actor_id,
            actor_ip: self.actor_ip,
            resource_type: self.resource_type,
            resource_id: self.resource_id,
            request_id: self.request_id,
            action: self.action,
            outcome: self.outcome,
            changes: self.changes,
            metadata: self.metadata,
            gdpr_relevant: self.gdpr_relevant,
            pii_accessed: self.pii_accessed,
        }
    }
}
