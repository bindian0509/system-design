"""
Common utilities shared across services.
"""
import uuid
from datetime import datetime


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.utcnow()
