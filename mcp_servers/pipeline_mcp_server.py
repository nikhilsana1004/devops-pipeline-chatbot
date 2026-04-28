"""
DevOps Pipeline MCP Server
==========================
Exposes pipeline tools as an MCP server so any MCP-compatible
client (Claude Desktop, Kiro, Amazon Q CLI, etc.) can query
your CI/CD data directly.

Usage:
    python mcp_servers/pipeline_mcp_server.py

Then add to your MCP client config (e.g. ~/.aws/amazonq/mcp.json):
{
  "mcpServers": {
    "devops-pipeline": {
      "command": "python",
      "args": ["mcp_servers/pipeline_mcp_server.py"],
      "env": {
        "AWS_REGION": "us-east-1",
        "ATHENA_DATABASE": "devops_metrics",
        "ATHENA_TABLE": "pipeline_executions",
        "ATHENA_OUTPUT_BUCKET": "s3://your-bucket/athena-output/"
      }
    }
  }
}
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: 'mcp' package not installed. Run: pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

from tools.athena_tools import query_athena as _query_athena, get_table_schema as _get_table_schema
from tools.cloudwatch_tools import get_cloudwatch_metrics as _get_cw_metrics, get_cloudwatch_alarms as _get_cw_alarms
from tools.codepipeline_tools import (
    get_pipeline_status as _get_status,
    list_pipelines as _list_pipelines,
    get_pipeline_executions as _get_executions,
)

# ── MCP Server ─────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="DevOps Pipeline MCP Server",
    description="Query CI/CD pipeline data from AWS Athena, CloudWatch, and CodePipeline via MCP.",
)


@mcp.tool()
def query_athena(sql: str) -> str:
    """Run a SQL SELECT query against the pipeline_executions Athena table."""
    return _query_athena(sql)


@mcp.tool()
def get_table_schema() -> str:
    """Return the schema of the pipeline_executions Athena table."""
    return _get_table_schema()


@mcp.tool()
def get_cloudwatch_metrics(
    pipeline_name: str,
    metric_name: str = "SucceededBuilds",
    hours: int = 24,
) -> str:
    """Get CloudWatch metrics for a pipeline or build project."""
    return _get_cw_metrics(pipeline_name=pipeline_name, metric_name=metric_name, hours=hours)


@mcp.tool()
def get_cloudwatch_alarms(pipeline_name: str = "") -> str:
    """List CloudWatch alarms for pipeline monitoring."""
    return _get_cw_alarms(pipeline_name=pipeline_name or None)


@mcp.tool()
def get_pipeline_status(pipeline_name: str) -> str:
    """Get real-time status of a specific AWS CodePipeline."""
    return _get_status(pipeline_name=pipeline_name)


@mcp.tool()
def list_pipelines() -> str:
    """List all AWS CodePipelines in the account."""
    return _list_pipelines()


@mcp.tool()
def get_pipeline_executions(pipeline_name: str, max_results: int = 10) -> str:
    """Get recent execution history for a CodePipeline."""
    return _get_executions(pipeline_name=pipeline_name, max_results=max_results)


if __name__ == "__main__":
    mcp.run()
