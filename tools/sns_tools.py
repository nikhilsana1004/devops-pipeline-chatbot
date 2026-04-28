"""
SNS Tools — publish pipeline alerts via AWS SNS.
"""

import os

import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")


@tool
def send_sns_alert(pipeline_name, message, severity="WARNING"):
    """
    Send an SNS notification alert about a pipeline issue.

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
    body = f"Pipeline: {pipeline_name}\nSeverity: {severity}\nMessage: {message}"
    try:
        response = client.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=body)
        return f"Alert sent. SNS MessageId: {response['MessageId']}"
    except Exception as e:
        return f"SNS publish error: {e}"
