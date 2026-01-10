//! Compliance modules for GDPR, CCPA, SOC2, HIPAA

pub mod gdpr;
pub mod audit;

pub use gdpr::GdprService;
pub use audit::AuditLogger;
