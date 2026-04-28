"""
Athena Tools — query CI/CD pipeline data stored in AWS Athena.

Table schema (pipeline_executions):
  account       STRING    — AWS account ID
  time          TIMESTAMP — event timestamp
  region        STRING    — AWS region
  pipeline      STRING    — CodePipeline name
  execution_id  STRING    — unique execution UUID
  start_time    TIMESTAMP — execution start time (sort by this)
  stage         STRING    — Source / Build / Deploy / Approval
  action        STRING    — action name within the stage
  state         STRING    — STARTED / SUCCEEDED / FAILED / STOPPED
"""

import os
import time as time_module
import json
import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn


ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "devops_metrics")
ATHENA_TABLE = os.getenv("ATHENA_TABLE", "pipeline_executions")
ATHENA_OUTPUT_BUCKET = os.getenv("ATHENA_OUTPUT_BUCKET", "s3://your-bucket/athena-output/")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


def _run_query(sql, region=AWS_REGION):
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
    rows = []
    headers = []
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
def query_athena(sql):
    """
    Run a SQL SELECT query against the pipeline_executions table in Athena.

    Columns: account, time, region, pipeline, execution_id,
    start_time, stage, action, state (STARTED/SUCCEEDED/FAILED/STOPPED).

    Always ORDER BY start_time DESC. Always include LIMIT.

    Args:
        sql: A valid Athena/Presto SQL SELECT statement.

    Returns:
        JSON string with results, or an error message.
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
def get_table_schema():
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
        return (
            "## pipeline_executions schema\n\n"
            "| Column | Type | Description |\n"
            "|---|---|---|\n"
            "| account | STRING | AWS account ID |\n"
            "| time | TIMESTAMP | Event timestamp |\n"
            "| region | STRING | AWS region |\n"
            "| pipeline | STRING | CodePipeline name |\n"
            "| execution_id | STRING | Unique execution UUID |\n"
            "| start_time | TIMESTAMP | Execution start time (UTC) |\n"
            "| stage | STRING | Source / Build / Deploy / Approval |\n"
            "| action | STRING | Action name within the stage |\n"
            "| state | STRING | STARTED / SUCCEEDED / FAILED / STOPPED |\n"
        )


@tool
def get_pipeline_summary():
    """
    Generate a high-level summary: total events, unique pipelines,
    executions, state breakdown, region/account counts, time range.

    Returns:
        JSON summary object.
    """
    sql = (
        f"SELECT COUNT(*) AS total_events,"
        f" COUNT(DISTINCT pipeline) AS unique_pipelines,"
        f" COUNT(DISTINCT execution_id) AS unique_executions,"
        f" COUNT(DISTINCT region) AS region_count,"
        f" COUNT(DISTINCT account) AS account_count,"
        f" MIN(CAST(start_time AS VARCHAR)) AS earliest_execution,"
        f" MAX(CAST(start_time AS VARCHAR)) AS latest_execution,"
        f" SUM(CASE WHEN state = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded,"
        f" SUM(CASE WHEN state = 'FAILED' THEN 1 ELSE 0 END) AS failed,"
        f" SUM(CASE WHEN state = 'STARTED' THEN 1 ELSE 0 END) AS started,"
        f" SUM(CASE WHEN state = 'STOPPED' THEN 1 ELSE 0 END) AS stopped"
        f" FROM {ATHENA_TABLE}"
    )
    try:
        rows = _run_query(sql)
        return json.dumps(rows[0] if rows else {}, indent=2, default=str)
    except Exception as e:
        return f"Summary query error: {e}"


@tool
def get_failed_pipelines(hours=24):
    """
    List pipelines with FAILED state in the last N hours,
    including the stage and action where the failure occurred.

    Args:
        hours: Look-back window in hours (default: 24).

    Returns:
        JSON list of failed executions, most recent first.
    """
    sql = (
        f"SELECT pipeline, execution_id, stage, action,"
        f" CAST(start_time AS VARCHAR) AS start_time, region, account"
        f" FROM {ATHENA_TABLE}"
        f" WHERE state = 'FAILED'"
        f" AND start_time >= current_timestamp - INTERVAL '{hours}' HOUR"
        f" ORDER BY start_time DESC LIMIT 50"
    )
    try:
        rows = _run_query(sql)
        if not rows:
            return f"No failed pipelines in the last {hours} hours."
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return f"Failed pipeline query error: {e}"
