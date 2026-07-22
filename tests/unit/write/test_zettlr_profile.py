"""Tests do gerador de perfil de export do Zettlr (defaults file)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from prumo_assist.domains.write.zettlr import PROFILE_RELPATH, generate_profile, profile_issues


def _gen(tmp_path: Path) -> Any:
    with patch(
        "prumo_assist.domains.write.zettlr.resolve_csl",
        return_value=Path("/fake/styles/apa.csl"),
    ):
        out = generate_profile(tmp_path)
    assert out == tmp_path / PROFILE_RELPATH
    return yaml.safe_load(out.read_text(encoding="utf-8"))


def test_profile_has_reader_writer_required_by_zettlr(tmp_path: Path) -> None:
    data = _gen(tmp_path)
    assert data["reader"].startswith("markdown")
    assert data["writer"] == "docx"


def test_profile_runs_citeproc_before_lua_filter(tmp_path: Path) -> None:
    # Num defaults file, `citeproc: true` rodaria DEPOIS dos lua filters
    # e quebraria o zotero_live_docx.lua — a ordem TEM que vir da lista.
    data = _gen(tmp_path)
    filters = data["filters"]
    assert filters[0] == "citeproc"
    assert filters[1].endswith("zotero_live_docx.lua")
    assert Path(filters[1]).is_file()


def test_profile_carries_style_metadata_and_csl(tmp_path: Path) -> None:
    data = _gen(tmp_path)
    assert data["metadata"]["zotero_csl_style"] == "apa"
    assert data["csl"] == "/fake/styles/apa.csl"


def test_profile_omits_csl_when_style_unavailable(tmp_path: Path) -> None:
    from prumo_assist.core.csl import CslNotFoundError

    with patch(
        "prumo_assist.domains.write.zettlr.resolve_csl",
        side_effect=CslNotFoundError("sem estilo"),
    ):
        out = generate_profile(tmp_path)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "csl" not in data


def test_profile_includes_reference_doc_when_present(tmp_path: Path) -> None:
    ref = tmp_path / "docs" / "templates" / "reference.docx"
    ref.parent.mkdir(parents=True)
    ref.write_bytes(b"PK\x03\x04fake")
    data = _gen(tmp_path)
    assert data["reference-doc"] == str(ref.resolve())


def test_profile_is_idempotent(tmp_path: Path) -> None:
    assert _gen(tmp_path) == _gen(tmp_path)


def test_profile_issues_empty_when_absent(tmp_path: Path) -> None:
    assert profile_issues(tmp_path) == []


def test_profile_issues_flags_broken_filter_with_fix_command(tmp_path: Path) -> None:
    p = tmp_path / PROFILE_RELPATH
    p.parent.mkdir(parents=True)
    p.write_text(
        yaml.safe_dump(
            {
                "reader": "markdown",
                "writer": "docx",
                "filters": ["citeproc", "/caminho/que/nao/existe.lua"],
            }
        ),
        encoding="utf-8",
    )
    issues = profile_issues(tmp_path)
    assert issues
    assert "prumo write zettlr-profile" in issues[0]
