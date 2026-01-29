"""Schema registry service for loading and accessing table schemas."""

from functools import lru_cache
from pathlib import Path

import yaml

from dsar_query_generator.config.settings import get_settings
from dsar_query_generator.models.schema import SchemaRegistry, TableSchema


class SchemaRegistryService:
    """Service for loading and accessing schema registry."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """Initialize schema registry service.

        Args:
            schema_path: Path to schema registry YAML file.
                        If None, uses path from settings.
        """
        if schema_path is None:
            settings = get_settings()
            schema_path = settings.schema_registry_path

        self._schema_path = schema_path
        self._registry: SchemaRegistry | None = None

    def load(self) -> SchemaRegistry:
        """Load schema registry from YAML file."""
        if self._registry is not None:
            return self._registry

        with open(self._schema_path) as f:
            data = yaml.safe_load(f)

        tables = {}
        for table_name, table_data in data.get("tables", {}).items():
            tables[table_name] = TableSchema(
                description=table_data.get("description", ""),
                allowed_columns=table_data.get("allowed_columns", []),
                excluded_columns=table_data.get("excluded_columns", []),
            )

        self._registry = SchemaRegistry(
            tables=tables,
            blocked_tables=data.get("blocked_tables", []),
        )
        return self._registry

    @property
    def registry(self) -> SchemaRegistry:
        """Get the loaded schema registry."""
        return self.load()


@lru_cache
def get_schema_registry_service() -> SchemaRegistryService:
    """Get cached schema registry service instance."""
    return SchemaRegistryService()
