"""
PipelineAgent — Strands-based orchestrator for the DevOps Pipeline Chatbot.

Upgrades over the original app.py:
  - Strands Agent replaces the single bedrock.invoke_model call
  - Agent picks tools automatically based on the question
  - Conversation memory persists across turns
  - 8 tools available (vs Athena-only original)
  - Falls back to raw boto3 converse if Strands SDK not installed
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from strands import Agent
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False

from tools.athena_tools import (
    query_athena, get_table_schema,
    get_pipeline_summary, get_failed_pipelines,
)
from tools.cloudwatch_tools import get_cloudwatch_metrics, get_cloudwatch_alarms
from tools.codepipeline_tools import get_pipeline_status, list_pipelines, get_pipeline_executions
from tools.s3_tools import list_s3_artifacts
from tools.sns_tools import send_sns_alert

# ── System prompt (preserves the spirit of your original context injection) ────
SYSTEM_PROMPT = """You are an expert DevOps assistant specializing in CI/CD pipeline analysis.
You have access to AWS tools to answer questions about pipelines.

The primary data source is an Athena table called pipeline_executions with these columns:
  account, time, region, pipeline, execution_id, start_time, stage, action, state

state values: STARTED | SUCCEEDED | FAILED | STOPPED

Available tools:
1. query_athena          — run arbitrary SQL against pipeline_executions
2. get_table_schema      — see column names/types before writing SQL
3. get_pipeline_summary  — overall counts: events, pipelines, executions, states
4. get_failed_pipelines  — recent failures with stage/action breakdown
5. get_cloudwatch_metrics — CloudWatch build/pipeline metrics
6. get_cloudwatch_alarms  — active CloudWatch alarms
7. get_pipeline_status   — real-time CodePipeline stage state
8. list_pipelines        — all pipelines in account
9. get_pipeline_executions — execution history for a pipeline
10. list_s3_artifacts    — browse S3 build artifacts
11. send_sns_alert       — notify the team via SNS

Guidelines:
- Provide concise, data-driven answers. Do not show code or explain how to analyze.
- For time-based questions, default to last 24 hours unless specified.
- Format responses with markdown: bullet points, tables, bold key numbers.
- For failure analysis, always include stage and action where possible.
- If data is empty, say so clearly and suggest what to check.
- Format durations in human-readable form (e.g. "2m 34s").
"""


class PipelineAgent:
    """Wraps a Strands Agent with DevOps pipeline tools."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.region = config.get("aws_region", os.getenv("AWS_REGION", "us-west-2"))
        self.model_id = config.get("model_id", os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"))
        self.chat_history = config.get("chat_history", [])
        self.active_tools = self._build_tool_list()
        self.agent = self._build_agent()

    def _build_tool_list(self) -> list:
        tools = []
        if self.config.get("use_athena", True):
            tools += [query_athena, get_table_schema, get_pipeline_summary, get_failed_pipelines]
        if self.config.get("use_cloudwatch", True):
            tools += [get_cloudwatch_metrics, get_cloudwatch_alarms]
        if self.config.get("use_codepipeline", True):
            tools += [get_pipeline_status, list_pipelines, get_pipeline_executions]
        if self.config.get("use_s3", False):
            tools += [list_s3_artifacts]
        if self.config.get("use_sns", False):
            tools += [send_sns_alert]
        return tools

    def _build_agent(self):
        if STRANDS_AVAILABLE:
            model = BedrockModel(model_id=self.model_id, region_name=self.region)
            return Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=self.active_tools)
        return None

    def run(self, user_message: str) -> dict[str, Any]:
        if STRANDS_AVAILABLE and self.agent:
            return self._run_strands(user_message)
        return self._run_fallback(user_message)

    def _run_strands(self, user_message: str) -> dict[str, Any]:
        tool_calls: list[dict] = []
        response = self.agent(user_message)
        response_text = str(response)

        if hasattr(response, "metrics") and response.metrics:
            for usage in response.metrics.get("tool_use", []):
                tool_calls.append({
                    "tool": usage.get("name"),
                    "input": usage.get("input", {}),
                    "output_preview": str(usage.get("output", ""))[:300],
                })

        return {"response": response_text, "tool_calls": tool_calls}

    def _run_fallback(self, user_message: str) -> dict[str, Any]:
        """
        Direct boto3 Bedrock converse — mirrors the original app's invoke_model
        but uses the converse API so tool use works without Strands.
        """
        import boto3

        client = boto3.client("bedrock-runtime", region_name=self.region)

        # Build conversation with history (same pattern as original st.session_state.messages)
        messages = list(self.chat_history) + [
            {"role": "user", "content": [{"text": user_message}]}
        ]

        tool_defs = self._build_bedrock_tool_defs()
        kwargs: dict = {
            "modelId": self.model_id,
            "system": [{"text": SYSTEM_PROMPT}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": 2000, "temperature": 0.1},
        }
        if tool_defs:
            kwargs["toolConfig"] = {"tools": tool_defs}

        response = client.converse(**kwargs)
        tool_calls: list[dict] = []
        output_text = ""

        for block in response.get("output", {}).get("message", {}).get("content", []):
            if block.get("text"):
                output_text += block["text"]
            elif block.get("toolUse"):
                tu = block["toolUse"]
                tool_result = self._invoke_tool(tu["name"], tu.get("input", {}))
                tool_calls.append({
                    "tool": tu["name"],
                    "toolUseId": tu.get("toolUseId", tu["name"]),
                    "input": tu.get("input", {}),
                    "output_preview": str(tool_result)[:300],
                    "raw_output": tool_result,
                })

        # Second pass: feed tool results back
        if tool_calls:
            output_text = self._second_pass(client, messages, response, tool_calls, kwargs)

        return {
            "response": output_text or "Analysis complete. See tool outputs above.",
            "tool_calls": tool_calls,
        }

    def _build_bedrock_tool_defs(self) -> list[dict]:
        specs = []
        for fn in self.active_tools:
            doc = (fn.__doc__ or "").strip()
            first_line = doc.split("\n")[0] if doc else fn.__name__
            specs.append({
                "toolSpec": {
                    "name": fn.__name__,
                    "description": first_line[:500],
                    "inputSchema": {
                        "json": getattr(fn, "_input_schema", {
                            "type": "object",
                            "properties": {},
                        })
                    },
                }
            })
        return specs

    def _invoke_tool(self, name: str, inputs: dict) -> Any:
        tool_map = {t.__name__: t for t in self.active_tools}
        fn = tool_map.get(name)
        if fn:
            try:
                return fn(**inputs)
            except Exception as e:
                return f"Tool error: {e}"
        return f"Unknown tool: {name}"

    def _second_pass(self, client, messages, first_response, tool_calls, kwargs) -> str:
        assistant_msg = first_response["output"]["message"]
        tool_results = [
            {
                "toolResult": {
                    "toolUseId": tc["toolUseId"],
                    "content": [{"text": str(tc["raw_output"])[:2000]}],
                }
            }
            for tc in tool_calls
        ]
        new_messages = messages + [
            assistant_msg,
            {"role": "user", "content": tool_results},
        ]
        kwargs2 = dict(kwargs)
        kwargs2["messages"] = new_messages
        resp2 = client.converse(**kwargs2)
        text = ""
        for block in resp2.get("output", {}).get("message", {}).get("content", []):
            if block.get("text"):
                text += block["text"]
        return text
