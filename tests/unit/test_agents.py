"""Subagents do plugin: read-only, despachados por algum modo e empacotados (spec D3/D4)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

from par.core.paths import resolve_resource

REPO = Path(__file__).resolve().parents[2]
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _front(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    data = yaml.safe_load(text.split("---", 2)[1])
    assert isinstance(data, dict), path
    return data


def test_os_tres_agents_existem_e_sao_read_only() -> None:
    agents = sorted((REPO / "agents").glob("*.md"))
    assert [a.stem for a in agents] == ["reader", "reviewer", "verifier"]
    for agent in agents:
        fm = _front(agent)
        assert fm["name"] == agent.stem
        assert str(fm["description"]).strip()
        tools = {t.strip().split("(")[0] for t in str(fm["tools"]).split(",") if t.strip()}
        assert tools, agent.name
        assert not tools & _WRITE_TOOLS, (agent.name, tools & _WRITE_TOOLS)


def test_todo_agent_eh_despachado_por_algum_modo() -> None:
    bodies = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "skills").rglob("modes/*.md"))
    for agent in (REPO / "agents").glob("*.md"):
        assert f"agents/{agent.name}" in bodies, agent.name


def test_wheel_force_inclui_agents() -> None:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    force = data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force["agents"] == "par/_agents"


def test_resolve_resource_acha_agents() -> None:
    assert (resolve_resource("agents") / "reader.md").is_file()
