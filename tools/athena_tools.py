"""
Athena Tools — query CI/CD pipeline data stored in AWS Athena.

This matches the real pipeline_executions table schema from the original app:

  account       STRING   — AWS account ID
  time          TIMESTAMP — event time
  region        STRING   — AWS region
  pipeline      STRING   — CodePipeline name
  execution_id  STRING   — unique execution UUID
  start_time    TIMESTAMP — execution start time
  stage         STRING   — pipeline stage (Source / Build / Deploy / Approval)
  action        STRING   — action name within the stage
  state         STRING   — STARTED | SUCCEEDED | FAILED | STOPPED
"""

from __future__ import annotations

import os
import time as time_module
import json
import boto3
from typing import Optional

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn


ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "devops_metrics")
ATHENA_TABLE = os.getenv("ATHENA_TABLE", "pipeline_executions")
ATHENA_OUTPUT_BUCKET = os.getenv("ATHENA_OUTPUT_BUCKET", "s3://your-bucket/athena-output/")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


def _run_query(sql: str, region: str = AWS_REGION) -> list[dict]:
    """Execute an Athena query and return rows as list-of-dicts."""
    client = boto3.client("athena", region_name=region)

    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_BUCKET},
    )
    execution_id = response["QueryExecutionId"]

    for _ in range(120):
        result = client.get_query_execution(QueryExecutionId=execution_id)
        state = result["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = result["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Athena query {state}: {reason}")
        time_module.sleep(1)

    paginator = client.get_paginator("get_query_results")
    rows: list[dict] = []
    headers: list[str] = []

    for page in paginator.paginate(QueryExecutionId=execution_id):
        result_rows = page["ResultSet"]["Rows"]
        if not headers:
            headers = [col["VarCharValue"] for col in result_rows[0]["Data"]]
            result_rows = result_rows[1:]
        for row in result_rows:
            values = [col.get("VarCharValue", "") for col in row["Data"]]
            rows.append(dict(zip(headers, values)))

    return rows


@tool
def query_athena(sql: str) -> str:
    """
    Run a SQL SELECT query against the pipeline_executions table in AWS Athena.

    Table columns: account, time, region, pipeline, execution_id,
    start_time, stage, action, state (STARTED/SUCCEEDED/FAILED/STOPPED).

    Always ORDER BY start_time DESC for latest results. Always include LIMIT.

    Args:
        sql: A valid Athena/Presto SQL SELECT statement.

    Returns:
        JSON string with query results, or an error message.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + " LIMIT 100"
    try:
        rows = _run_query(sql)
        if not rows:
            return "Query returned no results."
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return f"Athena query error: {e}"


@tool
def get_table_schema() -> str:
    """
    Return the schema of the pipeline_executions Athena table.

    Returns:
        Markdown table describing each column.
    """
    try:
        rows = _run_query(f"DESCRIBE {ATHENA_DATABASE}.{ATHENA_TABLE}")
        lines = ["| Column | Type | Description |", "|--------|------|-------------|"]
        for row in rows:
            col = row.get("col_name", "")
            typ = row.get("data_type", "")
            comment = row.get("comment", "")
            lines.append(f"| {col} | {typ} | {comment} |")
        return "\n".join(lines)
    except Exception:
        return """
## pipeline_executions schema

| Column | Type | Description |
|---|---|---|
| account | STRING | AWS account ID |
| time | TIMESTAMP | Event timestamp |
| region | STRING | AWS region (e.g. us-west-2) |
| pipeline | STRING | CodePipeline name |
| execution_id | STRING | Unique execution UUID |
| start_time | TIMESTAMP | Execution start time (UTC) |
| stage | STRING | Stage: Source / Build / Deploy / Approval |
| action | STRING | Action name within the stage |
| state | STRING | STARTED / SUCCEEDED / FAILED / STOPPED |
"""


@tool
def get_pipeline_summary() -> str:
    """
    Generate a high-level summary of all pipeline data:
    total events, unique pipelines, executions, state breakdown,
    regions, accounts, and latest/earliest execution times.

    Returns:
        JSON summary object.
    """
    sql = f"""
    SELECT
        COUNT(*)                                              AS total_events,
        COUNT(DISTINCT pipeline)                              AS unique_pipelines,
        COUNT(DISTINCT execution_id)                          AS unique_executions,
        COUNT(DISTINCT region)                                AS region_count,
        COUNT(DISTINCT account)                               AS account_count,
        MIN(CAST(start_time AS VARCHAR))                      AS earliest_execution,
        MAX(CAST(start_time AS VARCHAR))                      AS latest_execution,
        SUM(CASE WHEN state = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded,
        SUM(CASE WHEN state = 'FAILED'    THEN 1 ELSE 0 END) AS failed,
        SUM(CASE WHEN state = 'STARTED'   THEN 1 ELSE 0 END) AS started,
        SUM(CASE WHEN state = 'STOPPED'   THEN 1 ELSE 0 END) AS stopped
    FROM {ATHENA_TABLE}
    """
    try:
        rows = _run_query(sql)
        return json.dumps(rows[0] if rows else {}, indent=2, default=str)
    except Exception as e:
        return f"Summary query error: {e}"


@tool
def get_failed_pipelines(hours: int = 24) -> str:
    """
    List pipelines with FAILED state in the last N hours,
    including the stage and action where the failure occurred.

    Args:
        hours: Look-back window in hours (default: 24).

    Returns:
        JSON list of failed executions, most recent first.
    """
    sql = f"""
    SELECT
        pipeline,
        execution_id,
        stage,
        action,
        CAST(start_time AS VARCHAR) AS start_time,
        region,
        account
    FROM {ATHENA_TABLE}
    WHERE state = 'FAILED'
      AND start_time >= current_timestamp - INTERVAL '{hours}' HOUR
    ORDER BY start_time DESC
    LIMIT 50
    """
    try:
        rows = _run_query(sql)
        if not rows:
            return f"No failed pipelines in the last {hours} hours."
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return f"Failed pipeline query error: {e}"
