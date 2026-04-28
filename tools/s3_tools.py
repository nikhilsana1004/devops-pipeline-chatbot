"""
S3 Tools — browse pipeline artifacts stored in S3.
"""

from __future__ import annotations

import os
import json
from typing import Optional

import boto3

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ARTIFACT_BUCKET = os.getenv("ARTIFACT_BUCKET", "")


@tool
def list_s3_artifacts(pipeline_name: str, prefix: Optional[str] = None, max_keys: int = 20) -> str:
    """
    List artifacts stored in S3 for a given pipeline.
    Useful for finding build outputs, test reports, and deployment packages.

    Args:
        pipeline_name: Pipeline name used to filter the S3 prefix.
        prefix: Optional additional S3 prefix to narrow the search.
        max_keys: Maximum number of objects to return (default 20).

    Returns:
        JSON list of S3 objects with key, size, and last_modified.
    """
    if not ARTIFACT_BUCKET:
        return "Error: ARTIFACT_BUCKET environment variable not set."

    client = boto3.client("s3", region_name=AWS_REGION)
    search_prefix = f"{pipeline_name}/{prefix or ''}"

    try:
        response = client.list_objects_v2(
            Bucket=ARTIFACT_BUCKET,
            Prefix=search_prefix,
            MaxKeys=max_keys,
        )
        objects = [
            {
                "key": obj["Key"],
                "size_kb": round(obj["Size"] / 1024, 1),
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in response.get("Contents", [])
        ]
        if not objects:
            return json.dumps({"message": f"No artifacts found for prefix: {search_prefix}"})
        return json.dumps(objects, indent=2)
    except Exception as e:
        return f"S3 artifacts error: {e}"
