"""Layout do plugin: o que o `.mcp.json` distribui aos consumidores."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_mcp_json_nao_declara_qmd() -> None:
    """O qmd é CLI opcional; o plugin não distribui servidor MCP de terceiro (A9)."""
    servers = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert "qmd" not in servers
