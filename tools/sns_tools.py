"""
SNS Tools — publish pipeline alerts via AWS SNS.
"""

from __future__ import annotations

import os
import json

import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")


@tool
def send_sns_alert(pipeline_name: str, message: str, severity: str = "WARNING") -> str:
    """
    Send an SNS notification alert about a pipeline issue.
    Use this when the user asks to alert the team or when a critical issue is detected.

    Severity levels: INFO | WARNING | CRITICAL

    Args:
        pipeline_name: Name of the affected pipeline.
        message: Alert message describing the issue.
        severity: Severity level (INFO / WARNING / CRITICAL).

    Returns:
        Confirmation string with SNS MessageId or error.
    """
    if not SNS_TOPIC_ARN:
        return "Error: SNS_TOPIC_ARN environment variable not set."

    client = boto3.client("sns", region_name=AWS_REGION)
    subject = f"[{severity}] Pipeline Alert: {pipeline_name}"
    body = f"""Pipeline Alert
==================
Pipeline : {pipeline_name}
Severity : {severity}
Message  : {message}
"""
    try:
        response = client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=body,
        )
        return f"Alert sent. SNS MessageId: {response['MessageId']}"
    except Exception as e:
        return f"SNS publish error: {e}"
