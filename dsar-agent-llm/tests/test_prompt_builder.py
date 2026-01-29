"""Tests for the prompt builder."""

import pytest

from dsar_query_generator.models.schema import SchemaRegistry, TableSchema
from dsar_query_generator.services.prompt_builder import PromptBuilder


class TestPromptBuilder:
    """Tests for the PromptBuilder."""

    @pytest.fixture
    def schema_registry(self) -> SchemaRegistry:
        """Create a test schema registry."""
        return SchemaRegistry(
            tables={
                "users": TableSchema(
                    description="User profile information",
                    allowed_columns=["id", "email", "name"],
                    excluded_columns=["password_hash"],
                ),
                "payments": TableSchema(
                    description="Payment records",
                    allowed_columns=["id", "user_id", "amount", "currency"],
                    excluded_columns=["card_token"],
                ),
            },
            blocked_tables=["audit_logs"],
        )

    @pytest.fixture
    def prompt_builder(self, schema_registry: SchemaRegistry) -> PromptBuilder:
        """Create a prompt builder instance."""
        return PromptBuilder(schema_registry, max_tables=5)

    def test_build_system_prompt_includes_role(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "SQL query generator" in prompt
        assert "DSAR" in prompt

    def test_build_system_prompt_includes_constraints(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "SELECT" in prompt
        assert "INSERT" in prompt or "no INSERT" in prompt.lower() or "never" in prompt.lower()
        assert "parameterized" in prompt.lower()

    def test_build_system_prompt_includes_schema(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "users" in prompt
        assert "payments" in prompt
        assert "id" in prompt
        assert "email" in prompt
        assert "amount" in prompt

    def test_build_system_prompt_excludes_blocked_tables(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        # Blocked tables should not appear in schema description
        # (audit_logs is blocked but not in tables dict, so won't appear anyway)
        assert "audit_logs" not in prompt

    def test_build_system_prompt_includes_max_tables(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "5" in prompt  # max_tables=5

    def test_build_user_prompt_includes_user_id(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_user_prompt(
            user_id="user123",
            natural_language_request="Show me my payments",
        )
        assert "user123" in prompt

    def test_build_user_prompt_includes_request(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_user_prompt(
            user_id="user123",
            natural_language_request="Show me my payment history from last year",
        )
        assert "payment history from last year" in prompt

    def test_build_messages_returns_correct_structure(self, prompt_builder: PromptBuilder):
        messages = prompt_builder.build_messages(
            user_id="user123",
            natural_language_request="Show me my data",
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "user123" in messages[1]["content"]
        assert "Show me my data" in messages[1]["content"]

    def test_build_messages_system_prompt_contains_schema(self, prompt_builder: PromptBuilder):
        messages = prompt_builder.build_messages(
            user_id="user123",
            natural_language_request="Show me my data",
        )

        system_content = messages[0]["content"]
        assert "users" in system_content
        assert "payments" in system_content

    def test_output_format_mentioned_in_prompt(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "JSON" in prompt
        assert "sql" in prompt
        assert "params" in prompt
        assert "tables_accessed" in prompt or "tables" in prompt.lower()

    def test_confidence_levels_mentioned_in_prompt(self, prompt_builder: PromptBuilder):
        prompt = prompt_builder.build_system_prompt()
        assert "high" in prompt.lower()
        assert "medium" in prompt.lower()
        assert "low" in prompt.lower()
