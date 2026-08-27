"""SQL Data Analyst Agent with Safety Guardrails.

Demonstrates an agent converting natural language into safe, read-only SQL queries,
inspecting schemas, and generating executive summaries.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

TABLE_SCHEMAS: dict[str, list[str]] = {
    "subscriptions": [
        "id INTEGER PRIMARY KEY",
        "customer_id VARCHAR(50)",
        "plan VARCHAR(20)",
        "mrr_usd NUMERIC(10,2)",
        "created_at TIMESTAMP",
    ],
    "churn_events": [
        "id INTEGER PRIMARY KEY",
        "subscription_id INTEGER",
        "reason TEXT",
        "churn_date DATE",
    ],
}

MOCK_QUERY_RESULTS: list[dict[str, Any]] = [
    {"plan": "enterprise", "total_mrr": 45000.0, "active_count": 15},
    {"plan": "pro", "total_mrr": 18200.0, "active_count": 91},
    {"plan": "starter", "total_mrr": 3400.0, "active_count": 170},
]


def list_tables(ctx: RunContext[None]) -> list[str]:
    """List available tables in the analytical warehouse."""
    return list(TABLE_SCHEMAS.keys())


def get_table_schema(ctx: RunContext[None], table_name: str) -> dict[str, Any]:
    """Inspect column definitions and primary keys for a specific table."""
    columns = TABLE_SCHEMAS.get(table_name.lower())
    if columns is None:
        return {"error": f"Table '{table_name}' does not exist"}
    return {"table": table_name, "columns": columns}


def execute_read_only_query(ctx: RunContext[None], sql_query: str) -> dict[str, Any]:
    """Safely execute a verified read-only SQL SELECT query against the analytical replica."""
    normalized = sql_query.strip().upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return {"error": "Guardrail violation: Only SELECT queries are permitted"}

    return {"rows": MOCK_QUERY_RESULTS, "row_count": len(MOCK_QUERY_RESULTS)}


def create_sql_analyst_agent(model: Any = None) -> Agent[None, str]:
    """Factory creating the SQL analyst agent."""
    selected_model = model or TestModel(
        call_tools=["list_tables", "get_table_schema", "execute_read_only_query"]
    )

    return Agent(
        selected_model,
        system_prompt=(
            "You are an expert SQL data analyst. "
            "When answering questions about business metrics: "
            "1. List available tables to locate relevant data. "
            "2. Inspect the schemas of relevant tables. "
            "3. Generate and execute a read-only SQL query. "
            "4. Provide a clear summary with key findings."
        ),
        tools=[list_tables, get_table_schema, execute_read_only_query],
    )


if __name__ == "__main__":
    analyst = create_sql_analyst_agent()
    result = analyst.run_sync(
        "What is our current Monthly Recurring Revenue (MRR) breakdown by tier?"
    )
    print(result.output)
