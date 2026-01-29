"""Security tests for SQL injection and unauthorized access attempts."""

import pytest

from dsar_query_generator.models.llm import LLMGeneratedQuery
from dsar_query_generator.models.schema import SchemaRegistry, TableSchema
from dsar_query_generator.services.sql_validator import SQLValidator


class TestSQLInjectionPrevention:
    """Tests to verify SQL injection attempts are blocked."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "users": TableSchema(
                    description="User data",
                    allowed_columns=["id", "email", "name"],
                    excluded_columns=["password_hash"],
                ),
                "payments": TableSchema(
                    description="Payment data",
                    allowed_columns=["id", "user_id", "amount"],
                    excluded_columns=["card_token"],
                ),
            },
            blocked_tables=["admin_users", "secrets"],
        )

    @pytest.fixture
    def validator(self, schema_registry: SchemaRegistry) -> SQLValidator:
        """Create a validator instance."""
        return SQLValidator(schema_registry, max_tables=5)

    def test_union_injection_blocked(self, validator: SQLValidator):
        """UNION injection should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1 UNION SELECT password_hash FROM users",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("UNION" in e for e in result.errors)

    def test_comment_injection_blocked(self, validator: SQLValidator):
        """SQL comment injection should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1 -- AND admin_only = false",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("comment" in e.lower() for e in result.errors)

    def test_block_comment_injection_blocked(self, validator: SQLValidator):
        """Block comment injection should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments /* comment */ WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("comment" in e.lower() for e in result.errors)

    def test_stacked_query_blocked(self, validator: SQLValidator):
        """Stacked queries (multiple statements) should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = $1; DROP TABLE users;",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_subquery_injection_blocked(self, validator: SQLValidator):
        """Subquery injection should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = (SELECT admin_id FROM admin_users)",
            params=[],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False
        assert any("subquer" in e.lower() for e in result.errors)

    def test_drop_statement_blocked(self, validator: SQLValidator):
        """DROP statements should be blocked."""
        query = LLMGeneratedQuery(
            sql="DROP TABLE users",
            params=[],
            tables_accessed=["users"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_truncate_statement_blocked(self, validator: SQLValidator):
        """TRUNCATE statements should be blocked."""
        query = LLMGeneratedQuery(
            sql="TRUNCATE TABLE payments",
            params=[],
            tables_accessed=["payments"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_alter_statement_blocked(self, validator: SQLValidator):
        """ALTER statements should be blocked."""
        query = LLMGeneratedQuery(
            sql="ALTER TABLE users ADD COLUMN admin BOOLEAN",
            params=[],
            tables_accessed=["users"],
            columns_returned=[],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False


class TestUnauthorizedTableAccess:
    """Tests to verify unauthorized table access is blocked."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "payments": TableSchema(
                    description="Payment data",
                    allowed_columns=["id", "user_id", "amount"],
                    excluded_columns=["card_token"],
                ),
            },
            blocked_tables=["admin_users", "secrets", "audit_logs"],
        )

    @pytest.fixture
    def validator(self, schema_registry: SchemaRegistry) -> SQLValidator:
        """Create a validator instance."""
        return SQLValidator(schema_registry, max_tables=5)

    def test_blocked_table_access_denied(self, validator: SQLValidator):
        """Access to blocked tables should be denied."""
        for blocked_table in ["admin_users", "secrets", "audit_logs"]:
            query = LLMGeneratedQuery(
                sql=f"SELECT * FROM {blocked_table} WHERE user_id = $1",
                params=["user123"],
                tables_accessed=[blocked_table],
                columns_returned=["id"],
                confidence="high",
            )
            result = validator.validate(query)
            assert result.valid is False, f"Access to {blocked_table} should be blocked"

    def test_unknown_table_access_denied(self, validator: SQLValidator):
        """Access to unknown tables should be denied."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM unknown_table WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["unknown_table"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_join_with_blocked_table_denied(self, validator: SQLValidator):
        """JOINs with blocked tables should be denied."""
        query = LLMGeneratedQuery(
            sql="SELECT p.id FROM payments p JOIN admin_users a ON p.user_id = a.id WHERE p.user_id = $1",
            params=["user123"],
            tables_accessed=["payments", "admin_users"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False


class TestExcludedColumnAccess:
    """Tests to verify excluded columns are not accessible."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "users": TableSchema(
                    description="User data",
                    allowed_columns=["id", "email", "name"],
                    excluded_columns=["password_hash", "mfa_secret", "internal_flags"],
                ),
            },
            blocked_tables=[],
        )

    @pytest.fixture
    def validator(self, schema_registry: SchemaRegistry) -> SQLValidator:
        """Create a validator instance."""
        return SQLValidator(schema_registry, max_tables=5)

    def test_excluded_column_in_select_denied(self, validator: SQLValidator):
        """Selecting excluded columns should be denied."""
        for excluded_col in ["password_hash", "mfa_secret", "internal_flags"]:
            query = LLMGeneratedQuery(
                sql=f"SELECT id, {excluded_col} FROM users WHERE id = $1",
                params=["user123"],
                tables_accessed=["users"],
                columns_returned=["id", excluded_col],
                confidence="high",
            )
            result = validator.validate(query)
            assert result.valid is False, f"Access to {excluded_col} should be blocked"


class TestLiteralValuePrevention:
    """Tests to verify literal values are not allowed in queries."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "payments": TableSchema(
                    description="Payment data",
                    allowed_columns=["id", "user_id", "amount"],
                    excluded_columns=[],
                ),
            },
            blocked_tables=[],
        )

    @pytest.fixture
    def validator(self, schema_registry: SchemaRegistry) -> SQLValidator:
        """Create a validator instance."""
        return SQLValidator(schema_registry, max_tables=5)

    def test_literal_user_id_in_single_quotes_blocked(self, validator: SQLValidator):
        """Literal user IDs in single quotes should be blocked."""
        query = LLMGeneratedQuery(
            sql="SELECT id FROM payments WHERE user_id = 'user123'",
            params=[],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_literal_user_id_in_double_quotes_blocked(self, validator: SQLValidator):
        """Literal user IDs in double quotes should be blocked."""
        query = LLMGeneratedQuery(
            sql='SELECT id FROM payments WHERE user_id = "user123"',
            params=[],
            tables_accessed=["payments"],
            columns_returned=["id"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is False

    def test_parameterized_query_allowed(self, validator: SQLValidator):
        """Properly parameterized queries should be allowed."""
        query = LLMGeneratedQuery(
            sql="SELECT id, amount FROM payments WHERE user_id = $1",
            params=["user123"],
            tables_accessed=["payments"],
            columns_returned=["id", "amount"],
            confidence="high",
        )
        result = validator.validate(query)
        assert result.valid is True
