"""Tests for the SQL validator."""

import pytest

from dsar_query_generator.models.llm import LLMGeneratedQuery
from dsar_query_generator.models.schema import SchemaRegistry, TableSchema
from dsar_query_generator.services.sql_validator import SQLValidator, ValidationResult


class TestSQLValidator:
    """Tests for SQL validation."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "users": TableSchema(
                    description="User data",
                    allowed_columns=["id", "email", "name", "phone", "created_at"],
                    excluded_columns=["password_hash", "internal_flags"],
                ),
                "payments": TableSchema(
                    description="Payment data",
                    allowed_columns=["id", "user_id", "amount", "currency", "created_at"],
                    excluded_columns=["card_token", "fraud_score"],
                ),
            },
            blocked_tables=["audit_logs", "security_events"],
        )

    @pytest.fixture
    def validator(self, schema_registry: SchemaRegistry) -> SQLValidator:
        """Create a validator instance."""
        return SQLValidator(schema_registry, max_tables=5)

    def test_valid_select_query_passes(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id, amount, currency FROM payments WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id", "amount", "currency"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is True
        assert result.errors == []

    def test_insert_query_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="INSERT INTO payments (user_id, amount) VALUES ($1, $2)",
            params=["user123", "100"],
            tables_accessed=["payments"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("INSERT" in error or "SELECT" in error for error in result.errors)

    def test_update_query_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="UPDATE payments SET amount = $2 WHERE user_id = $1",
            params=["user123", "100"],
            tables_accessed=["payments"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("UPDATE" in error or "SELECT" in error for error in result.errors)

    def test_delete_query_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="DELETE FROM payments WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("DELETE" in error or "SELECT" in error for error in result.errors)

    def test_blocked_table_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT * FROM audit_logs WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["audit_logs"],
            columns_returned=["id", "action"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("audit_logs" in error.lower() or "blocked" in error.lower() for error in result.errors)

    def test_unknown_table_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id FROM unknown_table WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["unknown_table"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("unknown" in error.lower() for error in result.errors)

    def test_select_star_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT * FROM payments WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id", "amount"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("SELECT *" in error for error in result.errors)

    def test_missing_parameter_placeholder_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id, amount FROM payments WHERE user_id = 'literal_user_id'",
            params=[],
            tables_accessed=["payments"],
            columns_returned=["id", "amount"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("literal" in error.lower() or "parameter" in error.lower() for error in result.errors)

    def test_union_query_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1 UNION SELECT id FROM users",
            params=["user123"],
            tables_accessed=["payments", "users"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("UNION" in error for error in result.errors)

    def test_sql_comment_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1 -- comment",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("comment" in error.lower() for error in result.errors)

    def test_subquery_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id IN (SELECT id FROM users)",
            params=[],
            tables_accessed=["payments", "users"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("subquer" in error.lower() for error in result.errors)

    def test_too_many_tables_fails(self, validator: SQLValidator):
        # Create validator with max_tables=2
        strict_validator = SQLValidator(validator._schema, max_tables=2)
        query = LLMGeneratedQuery(
            sql="SELECT p.id FROM payments p JOIN users u ON p.user_id = u.id JOIN ratings r ON r.user_id = u.id WHERE p.user_id = $1",
            params=["user123"],
            tables_accessed=["payments", "users", "ratings"],
            columns_returned=["id"],
            confidence="high",
        )
        result = strict_validator.validate(query)
        assert result.valid is False
        assert any("too many tables" in error.lower() for error in result.errors)

    def test_parameter_count_mismatch_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1 AND created_at >= $2",
            params=["user123"],  # Missing second param
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("mismatch" in error.lower() or "param" in error.lower() for error in result.errors)

    def test_valid_query_with_multiple_params(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id, amount FROM payments WHERE user_id = $1 AND created_at >= $2 AND created_at < $3",
            params=["user123", "2024-01-01", "2025-01-01"],
            tables_accessed=["payments"],
            columns_returned=["id", "amount"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is True

    def test_excluded_column_fails(self, validator: SQLValidator):
        query = LLMGeneratedQuery(
            sql="SELECT id, password_hash FROM users WHERE id = $1",
            params=["user123"],
            tables_accessed=["users"],
            columns_returned=["id", "password_hash"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("password_hash" in error or "excluded" in error.lower() for error in result.errors)
