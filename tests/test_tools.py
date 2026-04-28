"""
Unit tests — uses your real schema: account, time, region, pipeline,
execution_id, start_time, stage, action, state
Run: pytest tests/ -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ── Athena Tool Tests ──────────────────────────────────────────────────────────
class TestQueryAthena:
    def test_rejects_non_select(self):
        from tools.athena_tools import query_athena
        result = query_athena("DROP TABLE pipeline_executions")
        assert "Only SELECT" in result

    def test_adds_limit_when_missing(self):
        import tools.athena_tools as mod
        calls = []
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: calls.append(sql) or []
        try:
            query_athena("SELECT * FROM pipeline_executions")
            assert any("LIMIT" in c.upper() for c in calls)
        finally:
            mod._run_query = orig

    def test_returns_json_with_real_columns(self):
        import tools.athena_tools as mod
        fake_row = {
            "account": "123456789012",
            "time": "2025-04-01T10:00:00Z",
            "region": "us-west-2",
            "pipeline": "api-deploy",
            "execution_id": "abc-123",
            "start_time": "2025-04-01T09:58:00Z",
            "stage": "Build",
            "action": "CodeBuild",
            "state": "SUCCEEDED",
        }
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: [fake_row]
        try:
            result = query_athena("SELECT * FROM pipeline_executions LIMIT 1")
            parsed = json.loads(result)
            assert parsed[0]["pipeline"] == "api-deploy"
            assert parsed[0]["state"] == "SUCCEEDED"
            assert parsed[0]["stage"] == "Build"
        finally:
            mod._run_query = orig

    def test_empty_result(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: []
        try:
            result = query_athena("SELECT * FROM pipeline_executions LIMIT 1")
            assert "no results" in result.lower()
        finally:
            mod._run_query = orig


class TestGetFailedPipelines:
    def test_returns_no_failures_message(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: []
        try:
            from tools.athena_tools import get_failed_pipelines
            result = get_failed_pipelines(hours=24)
            assert "no failed" in result.lower()
        finally:
            mod._run_query = orig

    def test_returns_failure_rows(self):
        import tools.athena_tools as mod
        fake_row = {
            "pipeline": "prod-deploy",
            "execution_id": "exec-999",
            "stage": "Deploy",
            "action": "ECS",
            "start_time": "2025-04-01T08:00:00Z",
            "region": "us-east-1",
            "account": "111122223333",
        }
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: [fake_row]
        try:
            from tools.athena_tools import get_failed_pipelines
            result = get_failed_pipelines(hours=24)
            parsed = json.loads(result)
            assert parsed[0]["pipeline"] == "prod-deploy"
            assert parsed[0]["stage"] == "Deploy"
        finally:
            mod._run_query = orig


class TestGetPipelineSummary:
    def test_summary_returns_json(self):
        import tools.athena_tools as mod
        fake = {
            "total_events": "500",
            "unique_pipelines": "12",
            "unique_executions": "95",
            "succeeded": "88",
            "failed": "7",
        }
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: [fake]
        try:
            from tools.athena_tools import get_pipeline_summary
            result = get_pipeline_summary()
            parsed = json.loads(result)
            assert parsed["total_events"] == "500"
            assert parsed["failed"] == "7"
        finally:
            mod._run_query = orig


# ── CloudWatch Tests ───────────────────────────────────────────────────────────
class TestCloudWatch:
    @patch("tools.cloudwatch_tools.boto3.client")
    def test_metrics_returns_json(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_metrics
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_metric_statistics.return_value = {
            "Datapoints": [{
                "Timestamp": datetime(2025, 4, 1, 12, 0, tzinfo=timezone.utc),
                "Sum": 10.0, "Average": 5.0, "Maximum": 10.0,
            }]
        }
        result = get_cloudwatch_metrics("api-deploy", "SucceededBuilds", hours=24)
        data = json.loads(result)
        assert data["pipeline"] == "api-deploy"
        assert len(data["datapoints"]) == 1

    @patch("tools.cloudwatch_tools.boto3.client")
    def test_alarms_empty(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_alarms
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [{"MetricAlarms": []}]
        result = get_cloudwatch_alarms()
        data = json.loads(result)
        assert "message" in data


# ── CodePipeline Tests ─────────────────────────────────────────────────────────
class TestCodePipeline:
    @patch("tools.codepipeline_tools.boto3.client")
    def test_list_pipelines(self, mock_boto):
        from tools.codepipeline_tools import list_pipelines
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [
            {"pipelines": [{"name": "api-deploy", "version": 2, "updated": "2025-04-01"}]}
        ]
        result = list_pipelines()
        data = json.loads(result)
        assert data[0]["name"] == "api-deploy"


# ── Formatter Tests ────────────────────────────────────────────────────────────
class TestFormatters:
    def test_format_response(self):
        from utils.formatters import format_agent_response
        assert format_agent_response({"response": "hello"}) == "hello"

    def test_format_tool_calls_empty(self):
        from utils.formatters import format_tool_calls
        assert format_tool_calls([]) == "[]"

    def test_format_tool_calls_json(self):
        from utils.formatters import format_tool_calls
        calls = [{"tool": "query_athena", "input": {"sql": "SELECT 1"}, "output_preview": "ok"}]
        parsed = json.loads(format_tool_calls(calls))
        assert parsed[0]["tool"] == "query_athena"
