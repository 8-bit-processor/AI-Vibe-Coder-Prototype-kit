"""
Stdio Client for Model Context Protocol (MCP) servers.
Communicates with MCP subprocesses via standard input/output using JSON-RPC 2.0.
"""

import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional
from core.mcp.protocol import MCPNotification, MCPRequest, MCPResponse, MCPToolSchema


class StdioMCPClient:
    """Client managing connection to a single stdio-based MCP server."""

    def __init__(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self.is_connected = False
        self.tools: List[MCPToolSchema] = []

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def connect(self, timeout: int = 15) -> bool:
        """Start the server subprocess and perform MCP initialize handshake."""
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)

        full_cmd = [self.command] + self.args

        try:
            # On Windows, if command is 'npx' or 'npm', use shell=True or npx.cmd
            use_shell = sys.platform == "win32" and (self.command.lower() in ("npx", "npm", "uvx"))

            self.process = subprocess.Popen(
                full_cmd if not use_shell else " ".join(full_cmd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=full_env,
                cwd=self.cwd,
                shell=use_shell,
                bufsize=0
            )

            # 1. Send initialize request
            init_req = MCPRequest(
                id=self._next_id(),
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "LocalVibeCoder",
                        "version": "1.0.0"
                    }
                }
            )
            init_res = self._send_request(init_req, timeout=timeout)
            if not init_res or init_res.error:
                return False

            # 2. Send initialized notification
            init_notif = MCPNotification(method="notifications/initialized")
            self._send_notification(init_notif)

            # 3. Discover available tools
            self.tools = self.list_tools(timeout=timeout)
            self.is_connected = True
            return True

        except Exception as e:
            self.close()
            return False

    def list_tools(self, timeout: int = 10) -> List[MCPToolSchema]:
        """Query server for list of supported tools (tools/list)."""
        req = MCPRequest(id=self._next_id(), method="tools/list", params={})
        res = self._send_request(req, timeout=timeout)
        if not res or not res.result:
            return []

        tools_data = res.result.get("tools", [])
        tool_schemas = []
        for t in tools_data:
            tool_schemas.append(
                MCPToolSchema(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    inputSchema=t.get("inputSchema", {"type": "object", "properties": {}})
                )
            )
        self.tools = tool_schemas
        return tool_schemas

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: int = 60) -> str:
        """Invoke a tool on the MCP server (tools/call)."""
        if not self.is_connected or not self.process:
            return f"Error: MCP server '{self.name}' is not connected."

        req = MCPRequest(
            id=self._next_id(),
            method="tools/call",
            params={"name": tool_name, "arguments": arguments}
        )
        res = self._send_request(req, timeout=timeout)
        if not res:
            return f"Error: No response from MCP server '{self.name}' for tool '{tool_name}'."
        if res.error:
            return f"MCP Error [{self.name}]: {res.error.get('message', str(res.error))}"

        result = res.result or {}
        content_items = result.get("content", [])

        # Extract text from content array
        text_outputs = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                text_outputs.append(item.get("text", ""))
            elif isinstance(item, str):
                text_outputs.append(item)

        if text_outputs:
            return "\n".join(text_outputs)

        return json.dumps(result, indent=2)

    def _send_request(self, req: MCPRequest, timeout: int = 15) -> Optional[MCPResponse]:
        """Send JSON-RPC request and wait for line response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            return None

        line = req.model_dump_json(exclude_none=True) + "\n"
        try:
            self.process.stdin.write(line)
            self.process.stdin.flush()

            # Read response line
            resp_line = self.process.stdout.readline()
            if not resp_line:
                return None

            data = json.loads(resp_line.strip())
            return MCPResponse(**data)
        except Exception:
            return None

    def _send_notification(self, notif: MCPNotification):
        """Send JSON-RPC notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return

        line = notif.model_dump_json(exclude_none=True) + "\n"
        try:
            self.process.stdin.write(line)
            self.process.stdin.flush()
        except Exception:
            pass

    def close(self):
        """Terminate the server subprocess gracefully and close pipes."""
        self.is_connected = False
        if self.process:
            try:
                if self.process.stdin:
                    try:
                        self.process.stdin.close()
                    except Exception:
                        pass
                if self.process.stdout:
                    try:
                        self.process.stdout.close()
                    except Exception:
                        pass
                if self.process.stderr:
                    try:
                        self.process.stderr.close()
                    except Exception:
                        pass
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
