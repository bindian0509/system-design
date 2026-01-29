"""SQL validator for generated queries."""

import re
from dataclasses import dataclass, field

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, Token, Where
from sqlparse.tokens import Keyword, DML

from dsar_query_generator.models.llm import LLMGeneratedQuery
from dsar_query_generator.models.schema import SchemaRegistry


@dataclass
class ValidationResult:
    """Result of SQL validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SQLValidationError(Exception):
    """Exception raised when SQL validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


class SQLValidator:
    """Validates generated SQL queries against security constraints."""

    def __init__(self, schema_registry: SchemaRegistry, max_tables: int = 5):
        """Initialize validator.

        Args:
            schema_registry: Schema registry with allowed tables/columns.
            max_tables: Maximum number of tables allowed per query.
        """
        self._schema = schema_registry
        self._max_tables = max_tables

        # Patterns that indicate literal values (potential security issue)
        self._literal_patterns = [
            r"user_id\s*=\s*'[^']+'" ,  # user_id = 'literal'
            r"user_id\s*=\s*\"[^\"]+\"",  # user_id = "literal"
            r"user_id\s*=\s*[a-zA-Z0-9_-]{5,}(?!\s*\$)",  # user_id = literal (not param)
        ]

    def validate(self, query: LLMGeneratedQuery) -> ValidationResult:
        """Validate a generated query against all security constraints.

        Args:
            query: The generated query to validate.

        Returns:
            ValidationResult with valid flag and any errors/warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        sql = query.sql.strip()

        # 1. Parse SQL
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                errors.append("Empty or invalid SQL")
                return ValidationResult(valid=False, errors=errors)
            stmt = parsed[0]
        except Exception as e:
            errors.append(f"SQL parse error: {e}")
            return ValidationResult(valid=False, errors=errors)

        # 2. Check statement type (SELECT only)
        stmt_type = stmt.get_type()
        if stmt_type != "SELECT":
            errors.append(f"Only SELECT statements allowed, got: {stmt_type or 'UNKNOWN'}")

        # 3. Check for dangerous keywords
        dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]
        sql_upper = sql.upper()
        for keyword in dangerous_keywords:
            if re.search(rf"\b{keyword}\b", sql_upper):
                errors.append(f"Dangerous keyword detected: {keyword}")

        # 4. Extract and validate tables
        tables = self._extract_tables(stmt)
        declared_tables = set(query.tables_accessed)

        # Check if tables match what was declared
        if tables != declared_tables:
            undeclared = tables - declared_tables
            if undeclared:
                warnings.append(f"Undeclared tables in query: {undeclared}")

        # Check against blocked tables
        for table in tables:
            if table in self._schema.blocked_tables:
                errors.append(f"Blocked table: {table}")
            elif table not in self._schema.tables:
                errors.append(f"Unknown table: {table}")

        # 5. Check table count limit
        if len(tables) > self._max_tables:
            errors.append(f"Too many tables: {len(tables)} (max {self._max_tables})")

        # 6. Validate columns
        for table in tables:
            if table in self._schema.tables:
                table_schema = self._schema.tables[table]
                for col in query.columns_returned:
                    # Handle qualified column names (table.column)
                    col_name = col.split(".")[-1] if "." in col else col
                    if col_name in table_schema.excluded_columns:
                        errors.append(f"Excluded column: {table}.{col_name}")

        # 7. Check for SELECT *
        if re.search(r"\bSELECT\s+\*", sql_upper):
            errors.append("SELECT * is not allowed; must specify explicit columns")

        # 8. Check parameterization
        param_errors = self._check_parameterization(sql, query.params)
        errors.extend(param_errors)

        # 9. Check for SQL injection patterns
        injection_errors = self._check_injection_patterns(sql)
        errors.extend(injection_errors)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _extract_tables(self, stmt: sqlparse.sql.Statement) -> set[str]:
        """Extract table names from a SQL statement."""
        tables: set[str] = set()

        # Look for FROM and JOIN clauses
        from_seen = False
        join_seen = False

        for token in stmt.tokens:
            if token.ttype is Keyword:
                word = token.value.upper()
                if word == "FROM":
                    from_seen = True
                    join_seen = False
                elif "JOIN" in word:
                    join_seen = True
                    from_seen = False
                elif word in ("WHERE", "GROUP", "ORDER", "LIMIT", "HAVING"):
                    from_seen = False
                    join_seen = False

            elif from_seen or join_seen:
                if isinstance(token, Identifier):
                    # Could be "table" or "table alias"
                    table_name = self._get_table_name(token)
                    if table_name:
                        tables.add(table_name)
                    from_seen = False
                    join_seen = False
                elif isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        if isinstance(identifier, Identifier):
                            table_name = self._get_table_name(identifier)
                            if table_name:
                                tables.add(table_name)
                    from_seen = False

        return tables

    def _get_table_name(self, identifier: Identifier) -> str | None:
        """Extract table name from an identifier, handling aliases."""
        # Get the real name (first identifier, not alias)
        real_name = identifier.get_real_name()
        if real_name:
            return real_name.lower()

        # Fallback: get first word
        for token in identifier.tokens:
            if token.ttype is not None and not token.is_whitespace:
                return str(token.value).lower()

        return None

    def _check_parameterization(self, sql: str, params: list[str]) -> list[str]:
        """Check that query uses parameterized placeholders correctly."""
        errors: list[str] = []

        # Count parameter placeholders
        placeholder_pattern = r"\$(\d+)"
        placeholders = re.findall(placeholder_pattern, sql)
        placeholder_nums = [int(p) for p in placeholders]

        if not placeholder_nums:
            # Check if there should be a user_id filter
            if "user_id" in sql.lower():
                errors.append("Query references user_id but has no parameter placeholders")
        else:
            # Check that placeholder numbers are sequential starting from 1
            expected = list(range(1, max(placeholder_nums) + 1))
            if sorted(set(placeholder_nums)) != expected:
                errors.append(f"Parameter placeholders should be sequential: found {sorted(set(placeholder_nums))}")

            # Check that number of params matches placeholders
            if len(params) != len(set(placeholder_nums)):
                errors.append(
                    f"Parameter count mismatch: {len(params)} params provided, "
                    f"{len(set(placeholder_nums))} placeholders in query"
                )

        # Check for literal user IDs
        for pattern in self._literal_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                errors.append("Query contains literal user_id value; must use parameter placeholder")
                break

        return errors

    def _check_injection_patterns(self, sql: str) -> list[str]:
        """Check for potential SQL injection patterns."""
        errors: list[str] = []

        # Check for comments (could be used to bypass validation)
        if "--" in sql or "/*" in sql:
            errors.append("SQL comments are not allowed")

        # Check for multiple statements
        # Note: sqlparse.split() separates by semicolons
        statements = sqlparse.split(sql)
        if len(statements) > 1:
            errors.append("Multiple SQL statements are not allowed")

        # Check for UNION (could be used to access other data)
        if re.search(r"\bUNION\b", sql, re.IGNORECASE):
            errors.append("UNION is not allowed in generated queries")

        # Check for subqueries (could bypass table restrictions)
        # This is a simple check; complex subqueries might need more analysis
        if sql.upper().count("SELECT") > 1:
            errors.append("Subqueries are not allowed in generated queries")

        return errors


def validate_query(
    query: LLMGeneratedQuery,
    schema_registry: SchemaRegistry,
    max_tables: int = 5,
) -> ValidationResult:
    """Convenience function to validate a query.

    Args:
        query: The generated query to validate.
        schema_registry: Schema registry with allowed tables/columns.
        max_tables: Maximum number of tables allowed.

    Returns:
        ValidationResult with valid flag and any errors.
    """
    validator = SQLValidator(schema_registry, max_tables)
    return validator.validate(query)
