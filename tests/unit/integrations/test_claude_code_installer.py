"""Installer do Claude Code: a skill vai inteira, com modos e material de apoio."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.core.skills import load_skill_registry
from par.integrations.claude_code.installer import ClaudeCodeIntegration


def test_install_copia_modos_references_e_templates(tmp_path: Path) -> None:
    src = tmp_path / "skills" / "write"
    (src / "modes").mkdir(parents=True)
    (src / "templates").mkdir()
    (src / "SKILL.md").write_text("---\nname: write\ndescription: w\n---\n", encoding="utf-8")
    (src / "modes" / "section.md").write_text(
        "---\nname: section\ndescription: s\nprumo:\n  phrases: [x]\n---\n", encoding="utf-8"
    )
    (src / "templates" / "section.md").write_text("# t\n", encoding="utf-8")
    registry, _ = load_skill_registry(tmp_path / "skills")

    report = ClaudeCodeIntegration().install(tmp_path / "pj", registry)

    dest = tmp_path / "pj" / ".claude" / "skills" / "write"
    assert report.installed == ["write"]
    assert report.skipped == []
    assert (dest / "SKILL.md").is_file()
    assert (dest / "modes" / "section.md").is_file()
    assert (dest / "templates" / "section.md").is_file()


def test_reinstalar_sobrescreve_sem_erro(tmp_path: Path) -> None:
    src = tmp_path / "skills" / "start"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: start\ndescription: s\n---\nv1\n", encoding="utf-8")
    registry, _ = load_skill_registry(tmp_path / "skills")
    ClaudeCodeIntegration().install(tmp_path / "pj", registry)
    (src / "SKILL.md").write_text("---\nname: start\ndescription: s\n---\nv2\n", encoding="utf-8")
    registry, _ = load_skill_registry(tmp_path / "skills")

    report = ClaudeCodeIntegration().install(tmp_path / "pj", registry)

    assert report.installed == ["start"]
    installed = tmp_path / "pj" / ".claude" / "skills" / "start" / "SKILL.md"
    assert installed.read_text(encoding="utf-8").endswith("v2\n")


def test_install_copia_agents_para_claude_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "reader.md").write_text("---\nname: reader\n---\ncorpo\n", encoding="utf-8")
    monkeypatch.setattr(
        "par.integrations.claude_code.installer.find_resource",
        lambda name: agents if name == "agents" else None,
    )
    registry, _ = load_skill_registry(tmp_path / "sem-skills")

    ClaudeCodeIntegration().install(tmp_path / "pj", registry)

    assert (
        (tmp_path / "pj" / ".claude" / "agents" / "reader.md")
        .read_text(encoding="utf-8")
        .endswith("corpo\n")
    )
