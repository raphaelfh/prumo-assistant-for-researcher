"""Tests pro parser de SKILL.md e o registry de descoberta."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import ManifestError
from prumo_assist.core.skills import load_skill_registry, parse_skill_file


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_minimal_skill(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: A demo skill.\n---\n\nBody here.\n",
    )
    m = parse_skill_file(skill)
    assert m.name == "demo"
    assert m.description == "A demo skill."
    assert m.version == "0.0.0"
    assert m.determinism == "agentic"
    assert m.body.startswith("Body here.")


def test_parses_full_prumo_block(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "extract" / "SKILL.md",
        (
            "---\n"
            "name: paper-extract\n"
            "description: Extract.\n"
            "prumo:\n"
            "  version: 1.2.0\n"
            "  schema: PaperCallout/v1\n"
            "  determinism: agentic\n"
            "  agent_compat: [claude-code, cursor]\n"
            "  cost_estimate: ~4k tokens\n"
            "  inputs:\n"
            "    citekey: required\n"
            "  custom_field: kept\n"
            "---\n"
            "Prompt body.\n"
        ),
    )
    m = parse_skill_file(skill)
    assert m.version == "1.2.0"
    assert m.schema == "PaperCallout/v1"
    assert m.agent_compat == ("claude-code", "cursor")
    assert m.cost_estimate == "~4k tokens"
    assert m.inputs == {"citekey": "required"}
    assert m.extra == {"custom_field": "kept"}


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "no frontmatter here\n")
    with pytest.raises(ManifestError, match="frontmatter YAML ausente"):
        parse_skill_file(skill)


def test_missing_name_raises(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "---\ndescription: x\n---\nbody\n")
    with pytest.raises(ManifestError, match="'name' obrigatório"):
        parse_skill_file(skill)


def test_invalid_determinism_raises(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "x" / "SKILL.md",
        "---\nname: x\ndescription: y\nprumo:\n  determinism: magical\n---\nbody\n",
    )
    with pytest.raises(ManifestError, match="determinism="):
        parse_skill_file(skill)


def test_registry_indexes_by_name(tmp_path: Path) -> None:
    _write(
        tmp_path / "alpha" / "SKILL.md",
        "---\nname: alpha\ndescription: A\n---\nbody\n",
    )
    _write(
        tmp_path / "beta" / "SKILL.md",
        "---\nname: beta\ndescription: B\n---\nbody\n",
    )
    reg, _ = load_skill_registry(tmp_path)
    assert reg.names() == ["alpha", "beta"]
    assert reg.get("alpha").description == "A"


def test_registry_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    _write(
        tmp_path / "real" / "SKILL.md",
        "---\nname: real\ndescription: r\n---\nbody\n",
    )
    (tmp_path / "empty").mkdir()
    reg, _ = load_skill_registry(tmp_path)
    assert reg.names() == ["real"]


def test_registry_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    reg, _ = load_skill_registry(tmp_path / "absent")
    assert reg.names() == []


def test_registry_rejects_duplicate_names(tmp_path: Path) -> None:
    _write(
        tmp_path / "a" / "SKILL.md",
        "---\nname: dup\ndescription: A\n---\nbody\n",
    )
    _write(
        tmp_path / "b" / "SKILL.md",
        "---\nname: dup\ndescription: B\n---\nbody\n",
    )
    with pytest.raises(ManifestError, match="duplicada"):
        load_skill_registry(tmp_path)


def test_registry_tolerant_mode_skips_malformed(tmp_path: Path) -> None:
    _write(
        tmp_path / "good" / "SKILL.md",
        "---\nname: good\ndescription: ok\n---\nbody\n",
    )
    # Frontmatter quebrado: tabs em vez de espaços + colon em valor unquoted
    _write(
        tmp_path / "bad" / "SKILL.md",
        "---\n: invalid yaml\n---\nbody\n",
    )
    reg, warnings = load_skill_registry(tmp_path, strict=False)
    assert reg.names() == ["good"]
    assert len(warnings) == 1


def test_registry_strict_mode_aborts_on_malformed(tmp_path: Path) -> None:
    _write(tmp_path / "bad" / "SKILL.md", "---\n: invalid\n---\nbody\n")
    with pytest.raises(ManifestError):
        load_skill_registry(tmp_path, strict=True)
