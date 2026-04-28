"""Response and tool-call formatting helpers."""
import json
from typing import Any


def format_agent_response(result: dict) -> str:
    """Extract the response text from the agent result dict."""
    return result.get("response", str(result))


def format_tool_calls(tool_calls: list[dict]) -> str:
    """Pretty-print tool call list as JSON."""
    if not tool_calls:
        return "[]"
    try:
        return json.dumps(tool_calls, indent=2, default=str)
    except Exception:
        return str(tool_calls)
