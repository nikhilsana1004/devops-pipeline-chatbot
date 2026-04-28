"""
CloudWatch Tools — pull pipeline metrics and alarms from AWS CloudWatch.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@tool
def get_cloudwatch_metrics(
    pipeline_name: str,
    metric_name: str = "SucceededBuilds",
    hours: int = 24,
    period_seconds: int = 3600,
) -> str:
    """
    Retrieve CloudWatch metrics for a CodePipeline or CodeBuild project.

    Useful metrics:
      - SucceededBuilds   (CodeBuild)
      - FailedBuilds      (CodeBuild)
      - Duration          (CodeBuild, in seconds)
      - PipelineExecutionFailure  (CodePipeline)
      - PipelineExecutionSuccess  (CodePipeline)

    Args:
        pipeline_name: Name of the pipeline or build project.
        metric_name: CloudWatch metric name (default: SucceededBuilds).
        hours: Look-back window in hours (default: 24).
        period_seconds: Aggregation period in seconds (default: 3600 = 1 hour).

    Returns:
        JSON with metric datapoints or an error message.
    """
    client = boto3.client("cloudwatch", region_name=AWS_REGION)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Try CodeBuild namespace first, then CodePipeline
    namespaces = ["AWS/CodeBuild", "AWS/CodePipeline"]
    dimension_keys = {
        "AWS/CodeBuild": "ProjectName",
        "AWS/CodePipeline": "PipelineName",
    }

    for namespace in namespaces:
        dim_key = dimension_keys[namespace]
        try:
            response = client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{"Name": dim_key, "Value": pipeline_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_seconds,
                Statistics=["Sum", "Average", "Maximum"],
            )
            datapoints = sorted(
                response.get("Datapoints", []),
                key=lambda x: x["Timestamp"],
            )
            if datapoints:
                result = {
                    "pipeline": pipeline_name,
                    "metric": metric_name,
                    "namespace": namespace,
                    "period_hours": hours,
                    "datapoints": [
                        {
                            "timestamp": dp["Timestamp"].isoformat(),
                            "sum": dp.get("Sum"),
                            "average": dp.get("Average"),
                            "maximum": dp.get("Maximum"),
                        }
                        for dp in datapoints
                    ],
                }
                return json.dumps(result, indent=2)
        except Exception:
            continue

    return json.dumps({"message": f"No metric data found for '{pipeline_name}' / '{metric_name}'"})


@tool
def get_cloudwatch_alarms(pipeline_name: Optional[str] = None) -> str:
    """
    List CloudWatch alarms related to DevOps pipelines.
    Returns alarm names, states, and threshold conditions.

    Args:
        pipeline_name: Optional filter — only return alarms mentioning this pipeline.

    Returns:
        JSON list of alarm states.
    """
    client = boto3.client("cloudwatch", region_name=AWS_REGION)

    try:
        paginator = client.get_paginator("describe_alarms")
        alarms = []
        for page in paginator.paginate(AlarmTypes=["MetricAlarm"]):
            for alarm in page.get("MetricAlarms", []):
                name = alarm.get("AlarmName", "")
                if pipeline_name and pipeline_name.lower() not in name.lower():
                    continue
                alarms.append({
                    "name": name,
                    "state": alarm.get("StateValue"),
                    "reason": alarm.get("StateReason", "")[:200],
                    "metric": alarm.get("MetricName"),
                    "threshold": alarm.get("Threshold"),
                    "comparison": alarm.get("ComparisonOperator"),
                    "updated": alarm.get("StateUpdatedTimestamp", "").isoformat()
                    if hasattr(alarm.get("StateUpdatedTimestamp", ""), "isoformat")
                    else str(alarm.get("StateUpdatedTimestamp", "")),
                })

        if not alarms:
            return json.dumps({"message": "No alarms found matching the filter."})
        return json.dumps(alarms, indent=2)
    except Exception as e:
        return f"CloudWatch alarms error: {e}"
