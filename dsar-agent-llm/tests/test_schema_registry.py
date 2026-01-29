"""Tests for the schema registry."""

import pytest

from dsar_query_generator.models.schema import SchemaRegistry, TableSchema


class TestSchemaRegistry:
    """Tests for SchemaRegistry model."""

    @pytest.fixture
    def registry(self) -> SchemaRegistry:
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
                    allowed_columns=["id", "amount", "currency"],
                    excluded_columns=["card_token"],
                ),
            },
            blocked_tables=["audit_logs"],
        )

    def test_is_table_allowed_returns_true_for_allowed_table(self, registry: SchemaRegistry):
        assert registry.is_table_allowed("users") is True
        assert registry.is_table_allowed("payments") is True

    def test_is_table_allowed_returns_false_for_blocked_table(self, registry: SchemaRegistry):
        assert registry.is_table_allowed("audit_logs") is False

    def test_is_table_allowed_returns_false_for_unknown_table(self, registry: SchemaRegistry):
        assert registry.is_table_allowed("unknown_table") is False

    def test_is_column_allowed_returns_true_for_allowed_column(self, registry: SchemaRegistry):
        assert registry.is_column_allowed("users", "id") is True
        assert registry.is_column_allowed("users", "email") is True
        assert registry.is_column_allowed("payments", "amount") is True

    def test_is_column_allowed_returns_false_for_unknown_column(self, registry: SchemaRegistry):
        assert registry.is_column_allowed("users", "unknown_column") is False

    def test_is_column_allowed_returns_false_for_blocked_table(self, registry: SchemaRegistry):
        assert registry.is_column_allowed("audit_logs", "id") is False

    def test_get_allowed_columns_returns_columns_for_valid_table(self, registry: SchemaRegistry):
        columns = registry.get_allowed_columns("users")
        assert columns == ["id", "email", "name"]

    def test_get_allowed_columns_returns_empty_for_blocked_table(self, registry: SchemaRegistry):
        columns = registry.get_allowed_columns("audit_logs")
        assert columns == []

    def test_get_all_table_names_excludes_blocked_tables(self, registry: SchemaRegistry):
        tables = registry.get_all_table_names()
        assert "users" in tables
        assert "payments" in tables
        assert "audit_logs" not in tables

    def test_get_schema_description_formats_correctly(self, registry: SchemaRegistry):
        description = registry.get_schema_description()
        assert "users(id, email, name): User data" in description
        assert "payments(id, amount, currency): Payment data" in description
        assert "audit_logs" not in description
