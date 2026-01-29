"""Request and response models for the DSAR Query Generator API."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class DSARRequest(BaseModel):
    """Request model for DSAR query generation."""

    request_id: str = Field(..., description="Unique identifier for the DSAR request")
    user_id: str = Field(..., description="ID of the user whose data is being requested")
    natural_language_request: str = Field(
        ..., description="Natural language description of the data request"
    )
    requester_email: EmailStr = Field(..., description="Email of the support agent making request")


class GeneratedQuery(BaseModel):
    """A single generated SQL query."""

    sql: str = Field(..., description="The generated SQL query with parameterized placeholders")
    params: list[str] = Field(..., description="Parameter values for the query")
    tables_accessed: list[str] = Field(..., description="List of tables accessed by the query")
    columns_returned: list[str] = Field(..., description="List of columns in the SELECT clause")


class DSARResponse(BaseModel):
    """Successful response with generated query."""

    request_id: str
    generated_query: GeneratedQuery | None = None
    generated_queries: list[GeneratedQuery] | None = None
    confidence: Literal["high", "medium", "low"]
    requires_review: bool = True
    warnings: list[str] = Field(default_factory=list)
    note: str | None = None


class ClarificationResponse(BaseModel):
    """Response when request needs clarification."""

    status: Literal["clarification_needed"] = "clarification_needed"
    message: str
    suggestions: list[str]


class OutOfScopeResponse(BaseModel):
    """Response when request is outside the system's scope."""

    status: Literal["out_of_scope"] = "out_of_scope"
    message: str
    escalation_path: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    request_id: str | None = None
