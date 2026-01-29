"""Schema registry models."""

from pydantic import BaseModel


class TableSchema(BaseModel):
    """Schema definition for a single table."""

    description: str
    allowed_columns: list[str]
    excluded_columns: list[str] = []


class SchemaRegistry(BaseModel):
    """Complete schema registry with allowed and blocked tables."""

    tables: dict[str, TableSchema]
    blocked_tables: list[str] = []

    def is_table_allowed(self, table_name: str) -> bool:
        """Check if a table is allowed for querying."""
        return table_name in self.tables and table_name not in self.blocked_tables

    def is_column_allowed(self, table_name: str, column_name: str) -> bool:
        """Check if a column is allowed for a given table."""
        if not self.is_table_allowed(table_name):
            return False
        table = self.tables[table_name]
        return column_name in table.allowed_columns

    def get_allowed_columns(self, table_name: str) -> list[str]:
        """Get list of allowed columns for a table."""
        if not self.is_table_allowed(table_name):
            return []
        return self.tables[table_name].allowed_columns

    def get_all_table_names(self) -> list[str]:
        """Get list of all allowed table names."""
        return [t for t in self.tables.keys() if t not in self.blocked_tables]

    def get_schema_description(self) -> str:
        """Generate a text description of the schema for LLM prompts."""
        lines = []
        for table_name, table in self.tables.items():
            if table_name in self.blocked_tables:
                continue
            columns = ", ".join(table.allowed_columns)
            lines.append(f"- {table_name}({columns}): {table.description}")
        return "\n".join(lines)
