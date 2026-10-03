"""Tests do gerador de perfil de export do Zettlr (defaults file)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from par.domains.write.zettlr import (
    FILTER_RELPATH,
    PROFILE_RELPATH,
    generate_profile,
    profile_issues,
)


def _pj(tmp_path: Path) -> Path:
    """Marca ``tmp_path`` como raiz de pj_* (o gerador exige o ``.bib``)."""
    (tmp_path / "docs" / "references").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "references" / "_references.bib").write_text("")
    return tmp_path


def _gen(tmp_path: Path) -> Any:
    _pj(tmp_path)
    with patch(
        "par.domains.write.zettlr.resolve_csl",
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
    # A lista é usada porque é o único mecanismo com ordem garantida pelo
    # manual, não porque `citeproc: true` rodaria depois.
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
    from par.core.csl import CslNotFoundError

    _pj(tmp_path)
    with patch(
        "par.domains.write.zettlr.resolve_csl",
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


def test_generate_profile_rejects_non_pj_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        generate_profile(tmp_path)
    msg = str(exc.value)
    assert "docs/references/_references.bib" in msg
    assert "--path" in msg


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


def test_profile_issues_flags_non_mapping_yaml(tmp_path: Path) -> None:
    p = tmp_path / PROFILE_RELPATH
    p.parent.mkdir(parents=True)
    p.write_text("just a string\n", encoding="utf-8")
    issues = profile_issues(tmp_path)
    assert issues
    assert "prumo write zettlr-profile" in issues[0]


_GITIGNORE_LINE = "docs/templates/prumo-docx.yaml"
_GITIGNORE_COMMENT = (
    "# perfil do Zettlr: caminhos absolutos desta máquina; "
    "regenere com `prumo write zettlr-profile`"
)


def _assert_one_gitignore_line(pj: Path) -> None:
    lines = (pj / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert [ln.strip() for ln in lines].count(_GITIGNORE_LINE) == 1
    idx = [ln.strip() for ln in lines].index(_GITIGNORE_LINE)
    assert lines[idx - 1] == _GITIGNORE_COMMENT


def test_perfil_copia_o_filtro_para_o_projeto(tmp_path: Path) -> None:
    from par.domains.write.export import _zotero_live_docx_filter

    data = _gen(tmp_path)
    copia = tmp_path / FILTER_RELPATH
    assert copia == tmp_path / "docs" / "templates" / "zotero_live_docx.lua"
    assert copia.read_bytes() == _zotero_live_docx_filter().read_bytes()
    assert data["filters"] == ["citeproc", str((tmp_path / FILTER_RELPATH).resolve())]


def test_perfil_cria_gitignore_com_a_linha(tmp_path: Path) -> None:
    assert not (tmp_path / ".gitignore").exists()
    _gen(tmp_path)
    _assert_one_gitignore_line(tmp_path)


def test_perfil_acrescenta_linha_ao_gitignore_existente(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".venv/\n.prumo/", encoding="utf-8")
    _gen(tmp_path)
    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines[:2] == [".venv/", ".prumo/"]
    _assert_one_gitignore_line(tmp_path)


def test_perfil_rodado_duas_vezes_deixa_uma_linha(tmp_path: Path) -> None:
    _gen(tmp_path)
    _gen(tmp_path)
    _assert_one_gitignore_line(tmp_path)


def _write_profile(pj: Path, filtro: str) -> None:
    p = pj / PROFILE_RELPATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump({"reader": "markdown", "writer": "docx", "filters": ["citeproc", filtro]}),
        encoding="utf-8",
    )


def test_profile_issues_filtro_fora_do_projeto(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    pj.mkdir()
    fora = tmp_path / "outro" / "zotero_live_docx.lua"
    fora.parent.mkdir()
    fora.write_text("-- lua", encoding="utf-8")
    _write_profile(pj, str(fora))
    assert profile_issues(pj) == [
        f"Perfil Zettlr aponta filtro fora do projeto: {fora}. "
        "Regenere: `prumo write zettlr-profile`"
    ]


def test_profile_issues_copia_divergente(tmp_path: Path) -> None:
    _gen(tmp_path)
    (tmp_path / FILTER_RELPATH).write_text("-- alterado", encoding="utf-8")
    assert profile_issues(tmp_path) == [
        "A cópia do filtro em docs/templates/zotero_live_docx.lua está diferente da "
        "desta versão do PAR. Regenere: `prumo write zettlr-profile`"
    ]


def test_profile_issues_filtro_inexistente(tmp_path: Path) -> None:
    _write_profile(tmp_path, "/caminho/que/nao/existe.lua")
    assert profile_issues(tmp_path) == [
        "Perfil Zettlr aponta filtro inexistente: /caminho/que/nao/existe.lua. "
        "Regenere: `prumo write zettlr-profile`."
    ]


def test_perfil_recem_gerado_nao_tem_issue(tmp_path: Path) -> None:
    _gen(tmp_path)
    assert profile_issues(tmp_path) == []
