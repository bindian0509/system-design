"""Audit logger for DSAR query generation compliance."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from dsar_query_generator.config.settings import Settings, get_settings

logger = structlog.get_logger()


class AuditEntry:
    """Represents a single audit log entry."""

    def __init__(
        self,
        request_id: str,
        agent_id: str,
        agent_email: str,
        subject_user_id: str,
        original_request: str,
        generated_sql: str | None = None,
        params: list[str] | None = None,
        tables_accessed: list[str] | None = None,
        columns_returned: list[str] | None = None,
        confidence: str | None = None,
        model_version: str | None = None,
        validation_passed: bool | None = None,
        validation_errors: list[str] | None = None,
        response_status: str = "success",
        error_message: str | None = None,
    ):
        self.timestamp = datetime.now(timezone.utc)
        self.request_id = request_id
        self.agent_id = agent_id
        self.agent_email = agent_email
        self.subject_user_id = subject_user_id
        self.original_request = original_request
        self.generated_sql = generated_sql
        self.params = params or []
        self.tables_accessed = tables_accessed or []
        self.columns_returned = columns_returned or []
        self.confidence = confidence
        self.model_version = model_version
        self.validation_passed = validation_passed
        self.validation_errors = validation_errors or []
        self.response_status = response_status
        self.error_message = error_message

    def to_dict(self) -> dict[str, Any]:
        """Convert audit entry to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "agent_email": self.agent_email,
            "subject_user_id": self.subject_user_id,
            "original_request": self.original_request,
            "generated_sql": self.generated_sql,
            "params": self.params,
            "tables_accessed": self.tables_accessed,
            "columns_returned": self.columns_returned,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "response_status": self.response_status,
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        """Convert audit entry to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """Audit logger for compliance logging of all DSAR requests."""

    def __init__(self, log_path: Path | None = None, settings: Settings | None = None):
        """Initialize audit logger.

        Args:
            log_path: Path to the audit log file. If None, uses settings.
            settings: Application settings. If None, loads from environment.
        """
        if settings is None:
            settings = get_settings()

        self._log_path = log_path or settings.audit_log_path
        self._ensure_log_directory()

    def _ensure_log_directory(self) -> None:
        """Ensure the log directory exists."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(self, entry: AuditEntry) -> None:
        """Write an audit entry to the log file.

        This is an append-only operation for compliance purposes.

        Args:
            entry: The audit entry to log.
        """
        try:
            # Append to JSONL file (one JSON object per line)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")

            logger.info(
                "audit_logged",
                request_id=entry.request_id,
                agent_id=entry.agent_id,
                subject_user_id=entry.subject_user_id,
                response_status=entry.response_status,
            )
        except Exception as e:
            # Never fail the main request due to audit logging issues
            # but do log the error
            logger.error(
                "audit_log_failed",
                request_id=entry.request_id,
                error=str(e),
            )

    async def log_request(
        self,
        request_id: str,
        agent_id: str,
        agent_email: str,
        subject_user_id: str,
        original_request: str,
        generated_sql: str | None = None,
        params: list[str] | None = None,
        tables_accessed: list[str] | None = None,
        columns_returned: list[str] | None = None,
        confidence: str | None = None,
        model_version: str | None = None,
        validation_passed: bool | None = None,
        validation_errors: list[str] | None = None,
        response_status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Convenience method to log a request directly.

        Args:
            request_id: Unique request identifier.
            agent_id: ID of the support agent making the request.
            agent_email: Email of the support agent.
            subject_user_id: ID of the user whose data is being requested.
            original_request: The natural language request text.
            generated_sql: The generated SQL query (if successful).
            params: Query parameters.
            tables_accessed: Tables accessed by the query.
            columns_returned: Columns in the SELECT clause.
            confidence: Confidence level of the generation.
            model_version: LLM model version used.
            validation_passed: Whether validation passed.
            validation_errors: List of validation errors (if any).
            response_status: Status of the response (success, error, etc.).
            error_message: Error message (if any).
        """
        entry = AuditEntry(
            request_id=request_id,
            agent_id=agent_id,
            agent_email=agent_email,
            subject_user_id=subject_user_id,
            original_request=original_request,
            generated_sql=generated_sql,
            params=params,
            tables_accessed=tables_accessed,
            columns_returned=columns_returned,
            confidence=confidence,
            model_version=model_version,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            response_status=response_status,
            error_message=error_message,
        )
        await self.log(entry)


# Singleton instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
