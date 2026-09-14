"""
MCP Manager: Loads mcp_config.json, manages server lifecycles, and bridges tools into ToolRegistry.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.mcp.client import StdioMCPClient
from core.mcp.protocol import MCPToolSchema
from core.tools.base import Tool, ToolRegistry


class DynamicMCPTool(Tool):
    """Wraps an MCP server tool dynamically into a Local Vibe Coder Tool."""

    def __init__(self, client: StdioMCPClient, schema: MCPToolSchema, prefix: str = ""):
        self.client = client
        self.original_name = schema.name
        self.name = f"{prefix}{schema.name}" if prefix else schema.name
        self.description = (
            f"[MCP: {client.name}] {schema.description or 'No description provided.'}"
        )
        self.parameters = schema.inputSchema or {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> str:
        return self.client.call_tool(self.original_name, kwargs)


class MCPManager:
    """Manages all configured MCP servers and bridges their tools to the agent."""

    def __init__(self, workspace_dir: str, config_path: Optional[str] = None):
        self.workspace_dir = workspace_dir
        self.config_path = config_path or os.path.join(workspace_dir, "mcp_config.json")
        self.clients: Dict[str, StdioMCPClient] = {}

    def load_config(self) -> Dict[str, Any]:
        """Load mcp_config.json if it exists."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def start_all(self) -> Dict[str, bool]:
        """Start and connect all configured MCP servers."""
        config = self.load_config()
        servers = config.get("mcpServers", {})
        results = {}

        for name, s_cfg in servers.items():
            command = s_cfg.get("command")
            args = s_cfg.get("args", [])
            env = s_cfg.get("env")
            cwd = s_cfg.get("cwd", self.workspace_dir)

            if not command:
                results[name] = False
                continue

            client = StdioMCPClient(
                name=name,
                command=command,
                args=args,
                env=env,
                cwd=cwd
            )
            connected = client.connect()
            self.clients[name] = client
            results[name] = connected

        return results

    def register_tools_into(self, registry: ToolRegistry):
        """Register all discovered MCP tools into the agent's ToolRegistry."""
        for server_name, client in self.clients.items():
            if client.is_connected:
                for schema in client.tools:
                    # Clean tool registration with prefix
                    mcp_tool = DynamicMCPTool(
                        client=client,
                        schema=schema,
                        prefix=f"mcp__{server_name}__"
                    )
                    registry.register(mcp_tool)

    def get_status(self) -> List[Dict[str, Any]]:
        """Return status and tool list for all managed servers."""
        status_list = []
        for name, client in self.clients.items():
            status_list.append({
                "name": name,
                "command": client.command,
                "connected": client.is_connected,
                "tool_count": len(client.tools),
                "tools": [t.name for t in client.tools]
            })
        return status_list

    def stop_all(self):
        """Shut down all running MCP servers."""
        for client in self.clients.values():
            client.close()
        self.clients.clear()
