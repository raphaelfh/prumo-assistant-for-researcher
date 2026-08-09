"""Resolvedores de projeto e de escopo — a base de todo caminho do layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core import pj_layout as L


def _mk_project(root: Path, *scopes: str) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs" / "references" / "papers").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "pdfs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "_references.bib").write_text("", encoding="utf-8")
    for slug in scopes or ("principal",):
        for sub in L.SCOPE_DIRS:
            (root / "docs" / "studies" / slug / sub).mkdir(parents=True, exist_ok=True)
    return root


def test_find_pj_root_sobe_ate_o_marcador(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    deep = root / "docs" / "studies" / "principal" / "writing"
    assert L.find_pj_root(deep) == root


def test_find_pj_root_aceita_arquivo(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    page = root / "docs" / "studies" / "principal" / "writing" / "paper.md"
    page.write_text("x", encoding="utf-8")
    assert L.find_pj_root(page) == root


def test_find_pj_root_levanta_com_mensagem_acionavel(tmp_path: Path) -> None:
    with pytest.raises(L.PjRootNotFoundError) as exc:
        L.find_pj_root(tmp_path)
    assert "prumo init" in str(exc.value)


def test_find_scope_root_devolve_o_filho_de_studies(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "a", "b")
    page = root / "docs" / "studies" / "b" / "writing" / "paper.md"
    page.write_text("x", encoding="utf-8")
    assert L.find_scope_root(page) == root / "docs" / "studies" / "b"


def test_find_scope_root_nao_confunde_escopos_irmaos(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "a", "b")
    a = L.find_scope_root(root / "docs" / "studies" / "a" / "notes")
    b = L.find_scope_root(root / "docs" / "studies" / "b" / "notes")
    assert a != b
    assert a.name == "a"
    assert b.name == "b"


def test_find_scope_root_fora_de_studies_levanta(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    with pytest.raises(L.PjRootNotFoundError) as exc:
        L.find_scope_root(root / "docs" / "references")
    assert "prumo add study" in str(exc.value)


def test_iter_scopes_ordena_e_ignora_arquivo(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "b", "a")
    (root / "docs" / "studies" / "leia-me.md").write_text("x", encoding="utf-8")
    assert [s.name for s in L.iter_scopes(root)] == ["a", "b"]


def test_iter_scopes_sem_studies_devolve_vazio(tmp_path: Path) -> None:
    root = tmp_path / "pj_x"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    assert L.iter_scopes(root) == []


def test_caminhos_do_projeto_e_do_escopo(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    scope = root / "docs" / "studies" / "principal"
    refs = root / "docs" / "references"
    assert L.references_dir(root) == refs
    assert L.bib_path(root) == refs / "_references.bib"
    assert L.papers_dir(root) == refs / "papers"
    assert L.paper_dir(root, "silva2020") == refs / "papers" / "silva2020"
    assert L.pdfs_dir(root) == refs / "pdfs"
    assert L.note_template_path(root) == refs / "_note_template.md"
    assert L.notes_dir(scope) == scope / "notes"
    assert L.writing_dir(scope) == scope / "writing"
    assert L.decisions_dir(scope) == scope / "decisions"


def test_is_legacy_layout_detecta_references_na_raiz(tmp_path: Path) -> None:
    legado = tmp_path / "pj_legado"
    (legado / "references").mkdir(parents=True)
    (legado / "references" / "_references.bib").write_text("", encoding="utf-8")
    (legado / "docs").mkdir()
    assert L.is_legacy_layout(legado) is True
    assert L.is_legacy_layout(_mk_project(tmp_path / "pj_novo")) is False


def test_assert_current_layout_convida_a_adequacao(tmp_path: Path) -> None:
    legado = tmp_path / "pj_legado"
    (legado / "references").mkdir(parents=True)
    (legado / "docs").mkdir()
    with pytest.raises(L.LegacyLayoutError) as exc:
        L.assert_current_layout(legado)
    assert "adeque este projeto" in str(exc.value)
