"""A local STDIO MCP bridge. Never expose it as an unauthenticated HTTP server."""
from __future__ import annotations
from typing import Literal

# Works both as python local_mcp/server.py (Codex stdio command)
# and python -m local_mcp.server from repository root.
try:
    from .core import machine_status, repository_status, check_plan, run_check
except ImportError:
    from core import machine_status, repository_status, check_plan, run_check

from mcp.server.mcpserver import MCPServer  # official MCP Python SDK v2

mcp = MCPServer(
    "acquisition-local-compute",
    version="0.1.0",
    instructions=(
        "Only fixed local diagnostics and verification checks are exposed. "
        "There is no arbitrary shell access, Upwork access, file-editing, "
        "outreach or autonomous agent execution. Checks require local opt-in."
    ),
)


@mcp.tool()
def get_machine_status() -> dict:
    """Read non-sensitive OS, CPU, free disk and Codex/Kilo availability."""
    return machine_status()


@mcp.tool()
def get_repository_status() -> dict:
    """Read Git branch and working-tree status in the fixed acquisition repository."""
    return repository_status()


@mcp.tool()
def preview_check(name: Literal["tests", "audit"]) -> dict:
    """Show exactly which fixed local check would run; execute nothing."""
    return check_plan(name)


@mcp.tool()
def execute_check(name: Literal["tests", "audit"], execute: bool = False) -> dict:
    """Execute an allowlisted test/audit check only when locally enabled and explicitly requested."""
    return run_check(name, execute=execute)


if __name__ == "__main__":
    mcp.run(transport="stdio")
