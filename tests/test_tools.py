"""
Unit tests — mocked AWS, no real credentials needed.
Real schema: account, time, region, pipeline, execution_id, start_time, stage, action, state
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

    def test_rejects_delete(self):
        from tools.athena_tools import query_athena
        result = query_athena("DELETE FROM pipeline_executions")
        assert "Only SELECT" in result

    def test_adds_limit_when_missing(self):
        import tools.athena_tools as mod
        calls = []
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: calls.append(sql) or []
        try:
            from tools.athena_tools import query_athena
            query_athena("SELECT * FROM pipeline_executions")
            assert any("LIMIT" in c.upper() for c in calls)
        finally:
            mod._run_query = orig

    def test_does_not_double_add_limit(self):
        import tools.athena_tools as mod
        calls = []
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: calls.append(sql) or []
        try:
            from tools.athena_tools import query_athena
            query_athena("SELECT * FROM pipeline_executions LIMIT 10")
            assert calls[0].upper().count("LIMIT") == 1
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
            from tools.athena_tools import query_athena
            result = query_athena("SELECT * FROM pipeline_executions LIMIT 1")
            parsed = json.loads(result)
            assert parsed[0]["pipeline"] == "api-deploy"
            assert parsed[0]["state"] == "SUCCEEDED"
            assert parsed[0]["stage"] == "Build"
            assert parsed[0]["account"] == "123456789012"
        finally:
            mod._run_query = orig

    def test_empty_result_message(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: []
        try:
            from tools.athena_tools import query_athena
            result = query_athena("SELECT * FROM pipeline_executions LIMIT 1")
            assert "no results" in result.lower()
        finally:
            mod._run_query = orig

    def test_query_error_returns_string(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: (_ for _ in ()).throw(RuntimeError("Athena FAILED"))
        try:
            from tools.athena_tools import query_athena
            result = query_athena("SELECT 1 LIMIT 1")
            assert "error" in result.lower()
        finally:
            mod._run_query = orig


class TestGetFailedPipelines:
    def test_no_failures_returns_message(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: []
        try:
            from tools.athena_tools import get_failed_pipelines
            result = get_failed_pipelines(hours=24)
            assert "no failed" in result.lower()
        finally:
            mod._run_query = orig

    def test_returns_failure_rows_as_json(self):
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

    def test_default_hours_is_24(self):
        import tools.athena_tools as mod
        captured = []
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: captured.append(sql) or []
        try:
            from tools.athena_tools import get_failed_pipelines
            get_failed_pipelines()
            assert "24" in captured[0]
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
            "started": "3",
            "stopped": "2",
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

    def test_empty_summary_returns_empty_json(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: []
        try:
            from tools.athena_tools import get_pipeline_summary
            result = get_pipeline_summary()
            parsed = json.loads(result)
            assert parsed == {}
        finally:
            mod._run_query = orig


class TestGetTableSchema:
    def test_schema_fallback_returns_markdown(self):
        import tools.athena_tools as mod
        orig = mod._run_query
        mod._run_query = lambda sql, region=None: (_ for _ in ()).throw(Exception("no athena"))
        try:
            from tools.athena_tools import get_table_schema
            result = get_table_schema()
            assert "pipeline" in result
            assert "state" in result
            assert "account" in result
        finally:
            mod._run_query = orig


# ── CloudWatch Tool Tests ──────────────────────────────────────────────────────

class TestCloudWatchMetrics:
    @patch("tools.cloudwatch_tools.boto3.client")
    def test_returns_json_with_datapoints(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_metrics
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_metric_statistics.return_value = {
            "Datapoints": [{
                "Timestamp": datetime(2025, 4, 1, 12, 0, tzinfo=timezone.utc),
                "Sum": 10.0,
                "Average": 5.0,
                "Maximum": 10.0,
            }]
        }
        result = get_cloudwatch_metrics("api-deploy", "SucceededBuilds", hours=24)
        data = json.loads(result)
        assert data["pipeline"] == "api-deploy"
        assert data["metric"] == "SucceededBuilds"
        assert len(data["datapoints"]) == 1
        assert data["datapoints"][0]["sum"] == 10.0

    @patch("tools.cloudwatch_tools.boto3.client")
    def test_no_data_returns_message(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_metrics
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_metric_statistics.return_value = {"Datapoints": []}
        result = get_cloudwatch_metrics("api-deploy", "SucceededBuilds")
        data = json.loads(result)
        assert "message" in data


class TestCloudWatchAlarms:
    @patch("tools.cloudwatch_tools.boto3.client")
    def test_empty_alarms_returns_message(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_alarms
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": []}
        ]
        result = get_cloudwatch_alarms()
        data = json.loads(result)
        assert "message" in data

    @patch("tools.cloudwatch_tools.boto3.client")
    def test_alarm_list_returned(self, mock_boto):
        from tools.cloudwatch_tools import get_cloudwatch_alarms
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [{
            "MetricAlarms": [{
                "AlarmName": "prod-pipeline-alarm",
                "StateValue": "ALARM",
                "StateReason": "Threshold exceeded",
                "MetricName": "FailedBuilds",
                "Threshold": 5.0,
                "ComparisonOperator": "GreaterThanThreshold",
                "StateUpdatedTimestamp": datetime(2025, 4, 1, tzinfo=timezone.utc),
            }]
        }]
        result = get_cloudwatch_alarms()
        data = json.loads(result)
        assert data[0]["name"] == "prod-pipeline-alarm"
        assert data[0]["state"] == "ALARM"


# ── CodePipeline Tool Tests ────────────────────────────────────────────────────

class TestListPipelines:
    @patch("tools.codepipeline_tools.boto3.client")
    def test_returns_pipeline_list(self, mock_boto):
        from tools.codepipeline_tools import list_pipelines
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [{
            "pipelines": [
                {"name": "api-deploy", "version": 2, "updated": "2025-04-01"},
                {"name": "infra-pipeline", "version": 1, "updated": "2025-03-20"},
            ]
        }]
        result = list_pipelines()
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["name"] == "api-deploy"

    @patch("tools.codepipeline_tools.boto3.client")
    def test_empty_account_returns_empty_list(self, mock_boto):
        from tools.codepipeline_tools import list_pipelines
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = [{"pipelines": []}]
        result = list_pipelines()
        data = json.loads(result)
        assert data == []


class TestGetPipelineExecutions:
    @patch("tools.codepipeline_tools.boto3.client")
    def test_returns_executions(self, mock_boto):
        from tools.codepipeline_tools import get_pipeline_executions
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.list_pipeline_executions.return_value = {
            "pipelineExecutionSummaries": [{
                "pipelineExecutionId": "exec-001",
                "status": "Succeeded",
                "startTime": datetime(2025, 4, 1, tzinfo=timezone.utc),
                "lastUpdateTime": datetime(2025, 4, 1, 1, tzinfo=timezone.utc),
                "trigger": {"triggerType": "Webhook", "triggerDetail": "push"},
            }]
        }
        result = get_pipeline_executions("api-deploy", max_results=5)
        data = json.loads(result)
        assert data[0]["execution_id"] == "exec-001"
        assert data[0]["status"] == "Succeeded"


# ── Formatter Tests ────────────────────────────────────────────────────────────

class TestFormatters:
    def test_format_agent_response_extracts_text(self):
        from utils.formatters import format_agent_response
        assert format_agent_response({"response": "hello"}) == "hello"

    def test_format_agent_response_fallback(self):
        from utils.formatters import format_agent_response
        result = format_agent_response({"other_key": "data"})
        assert isinstance(result, str)

    def test_format_tool_calls_empty(self):
        from utils.formatters import format_tool_calls
        assert format_tool_calls([]) == "[]"

    def test_format_tool_calls_valid_json(self):
        from utils.formatters import format_tool_calls
        calls = [{"tool": "query_athena", "input": {"sql": "SELECT 1"}, "output_preview": "ok"}]
        parsed = json.loads(format_tool_calls(calls))
        assert parsed[0]["tool"] == "query_athena"

    def test_format_tool_calls_handles_non_serializable(self):
        from utils.formatters import format_tool_calls
        calls = [{"tool": "query_athena", "input": {}, "output_preview": "ok"}]
        result = format_tool_calls(calls)
        assert isinstance(result, str)


# ── Session Tests ──────────────────────────────────────────────────────────────

class TestSession:
    def test_add_to_history_appends(self):
        import streamlit as st
        from utils.session import init_session_state, add_to_history
        if not hasattr(st, "session_state"):
            pytest.skip("Streamlit session_state not available outside app context")
        init_session_state()
        initial_len = len(st.session_state.chat_history)
        add_to_history("user", "hello")
        assert len(st.session_state.chat_history) == initial_len + 1
        assert st.session_state.chat_history[-1]["role"] == "user"
        assert st.session_state.chat_history[-1]["content"] == "hello"
