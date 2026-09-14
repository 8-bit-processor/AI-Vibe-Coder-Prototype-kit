"""
JSON-RPC 2.0 & Model Context Protocol (MCP) data models and serializers.
"""

import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    """JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    id: Union[int, str]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPNotification(BaseModel):
    """JSON-RPC 2.0 Notification (no id, does not expect a response)."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """JSON-RPC 2.0 Response."""
    jsonrpc: str = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class MCPToolSchema(BaseModel):
    """MCP Tool definition returned by tools/list."""
    name: str
    description: Optional[str] = ""
    inputSchema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
