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


def test_find_scope_root_fora_de_studies_resolve_o_escopo_unico(tmp_path: Path) -> None:
    """Fora de `docs/studies/` (a raiz do pj_* é o cwd do agente), um escopo só
    resolve sozinho — mesma política de `cli._resolve_module_scope`. Sem isso,
    toda invocação bare das skills (`prumo write prep`, `prumo wiki finding`)
    saía com exit 1 num projeto recém-criado."""
    root = _mk_project(tmp_path / "pj_x")
    assert L.find_scope_root(root) == root / "docs" / "studies" / "principal"
    assert (
        L.find_scope_root(root / "docs" / "references") == root / "docs" / "studies" / "principal"
    )


def test_find_scope_root_sem_escopo_nenhum_levanta_com_add_study(tmp_path: Path) -> None:
    root = tmp_path / "pj_x"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    with pytest.raises(L.PjRootNotFoundError) as exc:
        L.find_scope_root(root)
    assert "prumo add study" in str(exc.value)


def test_find_scope_root_com_varios_escopos_exige_escolha_e_lista_slugs(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "artigo-a", "artigo-b")
    with pytest.raises(L.PjRootNotFoundError) as exc:
        L.find_scope_root(root)
    message = str(exc.value)
    assert "artigo-a" in message
    assert "artigo-b" in message
    assert "docs/studies/" in message


def test_find_scope_root_caminho_explicito_tem_precedencia(tmp_path: Path) -> None:
    """Contrato de quem já passa escopo explícito: POSIÇÃO ganha do fallback."""
    root = _mk_project(tmp_path / "pj_x", "a", "b")
    assert L.find_scope_root(root / "docs" / "studies" / "b") == root / "docs" / "studies" / "b"


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


# --- layout legado de PROSA (ADR-0022/0025) --------------------------------


def test_legacy_prose_dirs_detects_studies_na_raiz(tmp_path: Path) -> None:
    (tmp_path / "studies" / "01_x").mkdir(parents=True)
    assert L.legacy_prose_dirs(tmp_path) == ["studies/"]


def test_legacy_prose_dirs_detects_diretorios_de_tipo(tmp_path: Path) -> None:
    for name in ("findings", "concepts", "entities", "sources"):
        (tmp_path / "docs" / name).mkdir(parents=True)
    assert L.legacy_prose_dirs(tmp_path) == [
        "docs/concepts/",
        "docs/entities/",
        "docs/findings/",
        "docs/sources/",
    ]


def test_legacy_prose_dirs_inclui_references_na_raiz_sem_docs_references(
    tmp_path: Path,
) -> None:
    (tmp_path / "references").mkdir()
    assert L.legacy_prose_dirs(tmp_path) == ["references/"]


def test_legacy_prose_dirs_nao_reclama_de_references_ressuscitado(tmp_path: Path) -> None:
    # Os dois existindo é assinatura de autoexport do BBT apontando pro
    # caminho antigo: remédio DIFERENTE, issue própria. Não entra aqui.
    (tmp_path / "references").mkdir()
    (tmp_path / "docs" / "references").mkdir(parents=True)
    assert L.legacy_prose_dirs(tmp_path) == []


def test_legacy_prose_dirs_vazio_em_projeto_no_padrao(tmp_path: Path) -> None:
    (tmp_path / "docs" / "studies" / "principal" / "notes").mkdir(parents=True)
    (tmp_path / "docs" / "references").mkdir(parents=True)
    assert L.legacy_prose_dirs(tmp_path) == []
