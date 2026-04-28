"""
CodePipeline Tools — real-time pipeline status via AWS CodePipeline API.
"""

import os
import json

import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


@tool
def list_pipelines():
    """
    List all AWS CodePipelines in the account and region.

    Returns:
        JSON list of pipeline names and last updated timestamps.
    """
    client = boto3.client("codepipeline", region_name=AWS_REGION)
    try:
        paginator = client.get_paginator("list_pipelines")
        pipelines = []
        for page in paginator.paginate():
            for p in page.get("pipelines", []):
                pipelines.append({
                    "name": p["name"],
                    "version": p.get("version"),
                    "updated": str(p.get("updated", "")),
                })
        return json.dumps(pipelines, indent=2)
    except Exception as e:
        return f"CodePipeline list error: {e}"


@tool
def get_pipeline_status(pipeline_name):
    """
    Get the current real-time status of a specific AWS CodePipeline,
    including each stage and action state.

    Args:
        pipeline_name: The exact name of the CodePipeline.

    Returns:
        JSON with pipeline state per stage and action.
    """
    client = boto3.client("codepipeline", region_name=AWS_REGION)
    try:
        response = client.get_pipeline_state(name=pipeline_name)
        stages = []
        for stage in response.get("stageStates", []):
            actions = []
            for action in stage.get("actionStates", []):
                latest = action.get("latestExecution", {})
                actions.append({
                    "action": action.get("actionName"),
                    "status": latest.get("status"),
                    "summary": latest.get("summary", "")[:200],
                    "last_status_change": str(latest.get("lastStatusChange", "")),
                })
            stages.append({
                "stage": stage.get("stageName"),
                "status": stage.get("latestExecution", {}).get("status"),
                "actions": actions,
            })
        return json.dumps({
            "pipeline": pipeline_name,
            "updated": str(response.get("updated", "")),
            "stages": stages,
        }, indent=2)
    except Exception as e:
        return f"CodePipeline status error: {e}"


@tool
def get_pipeline_executions(pipeline_name, max_results=10):
    """
    Get recent execution history for a CodePipeline.

    Args:
        pipeline_name: The CodePipeline name.
        max_results: Max executions to return (default 10, max 100).

    Returns:
        JSON list of execution summaries.
    """
    client = boto3.client("codepipeline", region_name=AWS_REGION)
    try:
        response = client.list_pipeline_executions(
            pipelineName=pipeline_name,
            maxResults=min(max_results, 100),
        )
        executions = []
        for ex in response.get("pipelineExecutionSummaries", []):
            trigger = ex.get("trigger", {})
            executions.append({
                "execution_id": ex.get("pipelineExecutionId"),
                "status": ex.get("status"),
                "start_time": str(ex.get("startTime", "")),
                "last_update": str(ex.get("lastUpdateTime", "")),
                "trigger_type": trigger.get("triggerType"),
                "trigger_detail": trigger.get("triggerDetail", "")[:100],
            })
        return json.dumps(executions, indent=2)
    except Exception as e:
        return f"CodePipeline executions error: {e}"
