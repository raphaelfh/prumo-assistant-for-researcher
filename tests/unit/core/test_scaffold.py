"""Unit tests para core/scaffold.py (overlay + descoberta de módulos)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import PrumoError
from prumo_assist.core import scaffold


def test_overlay_copies_into_empty_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "docs").mkdir(parents=True)
    (src / "docs" / "a.md").write_text("A")
    (src / "root.txt").write_text("R")
    target = tmp_path / "tgt"
    target.mkdir()

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "docs" / "a.md").read_text() == "A"
    assert (target / "root.txt").read_text() == "R"
    assert sorted(copied) == ["docs/a.md", "root.txt"]
    assert skipped == []


def test_overlay_does_not_clobber_existing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.txt").write_text("FROM SRC")
    target = tmp_path / "tgt"
    target.mkdir()
    (target / "keep.txt").write_text("USER OWN")

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "keep.txt").read_text() == "USER OWN"
    assert copied == []
    assert skipped == ["keep.txt"]


def test_overlay_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("X")
    target = tmp_path / "tgt"
    target.mkdir()

    scaffold.overlay(src, target)
    copied, skipped = scaffold.overlay(src, target)  # segunda vez

    assert copied == []
    assert skipped == ["x.txt"]


def test_apply_project_name_replaces_placeholders(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    (target / "docs").mkdir(parents=True)
    (target / "pyproject.toml").write_text('[project]\nname = "pj-NOME"\n', encoding="utf-8")
    (target / "docs" / "_index.md").write_text("# Wiki do projeto — pj_<NOME>\n", encoding="utf-8")
    (target / "notes.md").write_text("sem placeholder\n", encoding="utf-8")
    # Fora da lista de copiados (arquivo do usuário em --merge): intocável.
    (target / "user.md").write_text("meu pj-NOME literal\n", encoding="utf-8")

    changed = scaffold.apply_project_name(
        target, "pj_demo", ["pyproject.toml", "docs/_index.md", "notes.md"]
    )

    assert sorted(changed) == ["docs/_index.md", "pyproject.toml"]
    assert 'name = "pj_demo"' in (target / "pyproject.toml").read_text(encoding="utf-8")
    index = (target / "docs" / "_index.md").read_text(encoding="utf-8")
    assert "pj_demo" in index
    assert "NOME" not in index
    assert (target / "notes.md").read_text(encoding="utf-8") == "sem placeholder\n"
    assert (target / "user.md").read_text(encoding="utf-8") == "meu pj-NOME literal\n"


def test_apply_project_name_tolerates_binary_files(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    target.mkdir()
    payload = b"\x89PNG\xff\xfe\x00bin"
    (target / "img.png").write_bytes(payload)

    changed = scaffold.apply_project_name(target, "pj_demo", ["img.png"])

    assert changed == []
    assert (target / "img.png").read_bytes() == payload


@pytest.fixture
def fake_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cria templates/modules/<m>/_module.toml fake e aponta scaffold para ele."""
    root = tmp_path / "templates" / "modules"
    clin = root / "clinical"
    clin.mkdir(parents=True)
    (clin / "_module.toml").write_text(
        'description = "Camada clínica"\n'
        'when_to_use = "Estudo clínico"\n'
        'anchor = "docs/protocol.md"\n'
    )
    (clin / "docs").mkdir()
    (clin / "docs" / "protocol.md").write_text("# protocolo")
    bare = root / "bare"  # módulo sem _module.toml
    bare.mkdir()
    monkeypatch.setattr(scaffold, "_modules_root", lambda: root)
    return root


def test_discover_modules_reads_metadata(fake_modules: Path) -> None:
    mods = scaffold.discover_modules()
    names = [m.name for m in mods]
    assert names == ["bare", "clinical"]  # ordenado
    clin = scaffold.get_module("clinical")
    assert clin is not None
    assert clin.description == "Camada clínica"
    assert clin.anchor == "docs/protocol.md"


def test_discover_modules_tolerates_missing_metadata(fake_modules: Path) -> None:
    bare = scaffold.get_module("bare")
    assert bare is not None
    assert bare.description == ""
    assert bare.anchor is None


def test_get_module_unknown_returns_none(fake_modules: Path) -> None:
    assert scaffold.get_module("nope") is None


def test_is_applied_true_when_anchor_exists(tmp_path: Path) -> None:
    m = scaffold.ModuleInfo("clinical", "", "", "docs/protocol.md", tmp_path)
    target = tmp_path / "pj"
    (target / "docs").mkdir(parents=True)
    (target / "docs" / "protocol.md").write_text("x")
    assert scaffold.is_applied(target, m) is True


def test_is_applied_false_when_anchor_missing_or_none(tmp_path: Path) -> None:
    target = tmp_path / "pj"
    target.mkdir()
    with_anchor = scaffold.ModuleInfo("clinical", "", "", "docs/protocol.md", tmp_path)
    no_anchor = scaffold.ModuleInfo("x", "", "", None, tmp_path)
    assert scaffold.is_applied(target, with_anchor) is False
    assert scaffold.is_applied(target, no_anchor) is False


# ---------------------------------------------------------------------------
# Nome de pacote e marcador `__pkg__` (ADR-0027)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("projeto", "esperado"),
    [
        ("pj_piloto_genetica", "piloto_genetica"),
        ("pj_piloto_rwd", "piloto_rwd"),
        ("pj_piloto_ml", "piloto_ml"),
    ],
)
def test_pkg_name_remove_o_prefixo_pj(projeto: str, esperado: str) -> None:
    """O `pj_` marca diretório de projeto; em import é ruído (ADR-0027, D2)."""
    assert scaffold.pkg_name(projeto) == esperado


def test_pkg_name_recusa_resultado_que_nao_e_identificador() -> None:
    with pytest.raises(PrumoError, match="não é um nome de pacote Python válido"):
        scaffold.pkg_name("pj_2024")


def test_pkg_name_recusa_projeto_que_vira_vazio() -> None:
    with pytest.raises(PrumoError, match="não é um nome de pacote Python válido"):
        scaffold.pkg_name("pj_")


@pytest.mark.parametrize(
    ("slug", "esperado"),
    [
        ("01_estudo", "estudo"),
        ("mortalidade-uti", "mortalidade_uti"),
        ("principal", "principal"),
        ("02-triage-cohort", "triage_cohort"),
    ],
)
def test_scope_pkg_name_normaliza_slug_de_escopo(slug: str, esperado: str) -> None:
    """Slug de escrita é bom slug e não é identificador Python (ADR-0027, D3)."""
    assert scaffold.scope_pkg_name(slug) == esperado


def test_scope_pkg_name_recusa_slug_so_numerico() -> None:
    with pytest.raises(PrumoError, match="não vira um nome de pacote Python válido"):
        scaffold.scope_pkg_name("2024")


def test_overlay_substitui_marcador_de_pacote_no_caminho(tmp_path: Path) -> None:
    template = tmp_path / "tpl"
    (template / "src" / scaffold.PKG_MARKER).mkdir(parents=True)
    (template / "src" / scaffold.PKG_MARKER / "__init__.py").write_text("")
    target = tmp_path / "tgt"
    target.mkdir()

    copied, _ = scaffold.overlay(template, target, pkg="piloto_genetica")

    assert copied == ["src/piloto_genetica/__init__.py"]
    assert (target / "src" / "piloto_genetica" / "__init__.py").is_file()
    assert not (target / "src" / scaffold.PKG_MARKER).exists()


def test_overlay_sem_pkg_falha_alto_quando_o_template_usa_o_marcador(tmp_path: Path) -> None:
    """Defeito do chamador nunca vira arquivo `__pkg__` órfão no projeto."""
    template = tmp_path / "tpl"
    (template / "src" / scaffold.PKG_MARKER).mkdir(parents=True)
    (template / "src" / scaffold.PKG_MARKER / "__init__.py").write_text("")
    target = tmp_path / "tgt"
    target.mkdir()

    with pytest.raises(PrumoError, match=scaffold.PKG_MARKER):
        scaffold.overlay(template, target)


def test_overlay_substitui_marcador_de_pacote_no_conteudo(tmp_path: Path) -> None:
    """`[tool.hatch.build.targets.wheel] packages` precisa do nome real."""
    template = tmp_path / "tpl"
    template.mkdir()
    (template / "pyproject.toml").write_text(
        f'[tool.hatch.build.targets.wheel]\npackages = ["src/{scaffold.PKG_MARKER}"]\n'
    )
    target = tmp_path / "tgt"
    target.mkdir()

    copied, _ = scaffold.overlay(template, target, pkg="piloto_genetica")
    scaffold.apply_pkg_name(target, "piloto_genetica", copied)

    text = (target / "pyproject.toml").read_text()
    assert 'packages = ["src/piloto_genetica"]' in text
    assert scaffold.PKG_MARKER not in text


def test_module_requires_pkg(tmp_path: Path) -> None:
    com_pkg = tmp_path / "com"
    (com_pkg / "src" / scaffold.PKG_MARKER).mkdir(parents=True)
    (com_pkg / "src" / scaffold.PKG_MARKER / "__init__.py").write_text("")
    sem_pkg = tmp_path / "sem"
    (sem_pkg / "notebooks").mkdir(parents=True)
    (sem_pkg / "notebooks" / ".gitkeep").write_text("")

    assert scaffold.module_requires_pkg(_module_info(com_pkg))
    assert not scaffold.module_requires_pkg(_module_info(sem_pkg))


def _module_info(path: Path) -> scaffold.ModuleInfo:
    return scaffold.ModuleInfo(
        name=path.name, description="", when_to_use="", anchor=None, path=path
    )


# --- drift do template vs projeto vivo (Princípio VIII) ---------------------


def _fake_base(root: Path) -> Path:
    """Mini `pj_base`: um core doc, uma rule, e a árvore de escopo."""
    base = root / "pj_base"
    (base / ".claude" / "rules").mkdir(parents=True)
    (base / ".claude" / "rules" / "documentation.md").write_text("REGRA v2", encoding="utf-8")
    (base / "docs").mkdir(parents=True)
    (base / "docs" / "project_guide.md").write_text("GUIA", encoding="utf-8")
    (base / "docs" / "studies" / "principal" / "notes").mkdir(parents=True)
    (base / "docs" / "studies" / "principal" / "notes" / ".gitkeep").write_text("")
    return base


def test_template_drift_reporta_arquivo_do_nucleo_ausente(tmp_path: Path) -> None:
    base = _fake_base(tmp_path)
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v2", encoding="utf-8")
    (pj / "docs").mkdir(parents=True)

    drift = scaffold.template_drift(pj, base)

    assert drift.missing == ("docs/project_guide.md",)
    assert drift.diverged == ()


def test_template_drift_ignora_a_arvore_de_escopo(tmp_path: Path) -> None:
    # O slug é escolha do pesquisador: recopiar o `principal` do template
    # injetaria um escopo órfão e faria `find_scope_root` exigir --scope.
    base = _fake_base(tmp_path)
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v2", encoding="utf-8")
    (pj / "docs" / "studies" / "01_outro").mkdir(parents=True)
    (pj / "docs" / "project_guide.md").write_text("GUIA", encoding="utf-8")

    drift = scaffold.template_drift(pj, base)

    assert drift.missing == ()
    assert "docs/studies/principal/notes/.gitkeep" not in drift.missing


def test_template_drift_compara_conteudo_so_das_rules(tmp_path: Path) -> None:
    base = _fake_base(tmp_path)
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v1", encoding="utf-8")
    (pj / "docs").mkdir(parents=True)
    # project_guide.md diverge por CONSTRUÇÃO (placeholder de nome trocado
    # no init); comparar conteúdo dele reportaria drift em todo projeto.
    (pj / "docs" / "project_guide.md").write_text("GUIA do pj_real", encoding="utf-8")

    drift = scaffold.template_drift(pj, base)

    assert drift.diverged == (".claude/rules/documentation.md",)
    assert drift.missing == ()


def test_standard_issues_junta_tudo_numa_mensagem_so(tmp_path: Path) -> None:
    base = _fake_base(tmp_path)
    pj = tmp_path / "pj_x"
    (pj / "docs").mkdir(parents=True)
    (pj / "studies").mkdir()  # layout legado de prosa
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v1", encoding="utf-8")

    issues = scaffold.standard_issues(pj, base)

    assert len(issues) == 1
    (msg,) = issues
    assert msg.startswith("[fora_do_padrao]")
    assert "studies/" in msg
    assert "docs/project_guide.md" in msg
    assert ".claude/rules/documentation.md" in msg
    assert "prumo update" in msg


def test_standard_issues_silencioso_em_projeto_no_padrao(tmp_path: Path) -> None:
    base = _fake_base(tmp_path)
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v2", encoding="utf-8")
    (pj / "docs" / "studies" / "principal" / "notes").mkdir(parents=True)
    (pj / "docs" / "project_guide.md").write_text("GUIA", encoding="utf-8")

    assert scaffold.standard_issues(pj, base) == []


def _context(pj: Path, corpo: str) -> Path:
    (pj / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    alvo = pj / ".claude" / "rules" / "project_context.md"
    alvo.write_text(corpo, encoding="utf-8")
    return alvo


def test_empty_context_fields_reconhece_as_duas_formas_do_template(tmp_path: Path) -> None:
    """O template usa DUAS formas de campo, e a v0.68.0 só via a primeira.

    `- **Rótulo:**` põe os dois-pontos DENTRO do negrito; `- **Rótulo** (dica):`
    põe fora, depois de um parêntese. O `doctor` acusava 2 campos vazios num
    `pj_*` recém-criado que tem 5 — sub-reportando em silêncio justamente o
    arquivo cujo esquecimento ele existe para pegar.
    """
    pj = tmp_path / "pj_x"
    _context(
        pj,
        "- **Objetivo principal:**\n"
        "- **Hipótese:** reduzir mortalidade\n"
        "- **Entidades principais** (datasets, ferramentas):\n"
        "- **Conceitos centrais** (métodos): curvas ROC\n"
        "- **Decisões já tomadas** (viram ADR):   \n",
    )
    assert scaffold.empty_context_fields(pj) == [
        "Decisões já tomadas",
        "Entidades principais",
        "Objetivo principal",
    ]


def test_context_untouched_quando_nenhum_campo_foi_preenchido(tmp_path: Path) -> None:
    pj = tmp_path / "pj_x"
    _context(pj, "- **Objetivo principal:**\n- **Entidades principais** (dica):\n")
    assert scaffold.context_is_untouched(pj) is True


def test_context_untouched_falso_no_preenchimento_parcial(tmp_path: Path) -> None:
    pj = tmp_path / "pj_x"
    _context(pj, "- **Objetivo principal:** prever o desfecho\n- **Hipótese:**\n")
    assert scaffold.context_is_untouched(pj) is False


def test_context_untouched_falso_quando_tudo_preenchido(tmp_path: Path) -> None:
    pj = tmp_path / "pj_x"
    _context(pj, "- **Objetivo principal:** prever o desfecho\n")
    assert scaffold.context_is_untouched(pj) is False


def test_context_untouched_em_arquivo_ausente(tmp_path: Path) -> None:
    # Ausência tem dono próprio (`[fora_do_padrao]`); aqui não há campo
    # preenchido nenhum, então "intocado" é a resposta honesta.
    assert scaffold.context_is_untouched(tmp_path) is True


def test_empty_context_fields_lista_campos_em_branco(tmp_path: Path) -> None:
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "project_context.md").write_text(
        "## Estudo\n"
        "- **Objetivo principal:**\n"
        "- **Hipótese:** reduzir mortalidade\n"
        "- **Coorte:**   \n",
        encoding="utf-8",
    )
    assert scaffold.empty_context_fields(pj) == ["Coorte", "Objetivo principal"]


def test_empty_context_fields_vazio_quando_arquivo_ausente(tmp_path: Path) -> None:
    assert scaffold.empty_context_fields(tmp_path) == []


def test_empty_context_fields_vazio_quando_tudo_preenchido(tmp_path: Path) -> None:
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "project_context.md").write_text(
        "- **Objetivo principal:** prever o desfecho\n", encoding="utf-8"
    )
    assert scaffold.empty_context_fields(pj) == []


def test_template_drift_nao_trata_project_context_preenchido_como_drift(
    tmp_path: Path,
) -> None:
    """Bug do v0.68.0: `project_context.md` mora em `.claude/rules/`, que é
    comparado por CONTEÚDO — então PREENCHER o arquivo, que é exatamente o que
    o `init` manda fazer, acusava "rule desatualizada" e marcava o projeto como
    fora do padrão. Pior: `prumo update --yes` o listava como divergente e
    sobrescrevia o contexto do pesquisador com o template em branco.

    Ele é FORMULÁRIO, não regra: divergir do template é o estado correto.
    """
    base = _fake_base(tmp_path)
    (base / scaffold.CONTEXT_RELPATH).parent.mkdir(parents=True, exist_ok=True)
    (base / scaffold.CONTEXT_RELPATH).write_text("- **Objetivo principal:**\n", encoding="utf-8")

    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "rules" / "documentation.md").write_text("REGRA v2", encoding="utf-8")
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "project_guide.md").write_text("GUIA", encoding="utf-8")
    _context(pj, "- **Objetivo principal:** prever o desfecho\n")

    drift = scaffold.template_drift(pj, base)

    assert drift.diverged == ()
    assert scaffold.standard_issues(pj, base) == []
