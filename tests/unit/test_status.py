"""`prumo status` — onde o estudo está e qual a próxima frase (spec 2026-09-12, D5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from par.cli import app
from par.core.paths import resolve_resource
from par.core.skills import SkillRef, SkillRegistry, load_skill_registry
from par.domains.paper.callout import hash_template
from par.domains.protocol.picot_io import write_picot
from par.domains.protocol.schemas.v1 import Hypothesis, PicotSpec
from par.status import ProjectStatus, project_status, render_status, status_to_dict

runner = CliRunner()


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    reg, _ = load_skill_registry(resolve_resource("skills"))
    return reg


def _init(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    res = runner.invoke(app, ["init", str(pj), "--json"])
    assert res.exit_code == 0, res.output
    return pj


def _bib(pj: Path, *keys: str) -> None:
    text = "".join(f"@article{{{k},\n  title = {{T {k}}},\n  year = {{2024}}\n}}\n\n" for k in keys)
    (pj / "docs" / "references" / "_references.bib").write_text(text, encoding="utf-8")


def _paper(pj: Path, key: str, *, pdf: bool = True, extract: bool = False, hash_: str = "") -> None:
    d = pj / "docs" / "references" / "papers" / key
    d.mkdir(parents=True, exist_ok=True)
    extra = f"extracted_template_hash: '{hash_}'\n" if hash_ else ""
    (d / "_meta.md").write_text(f"---\ncitekey: {key}\n{extra}---\n", encoding="utf-8")
    if extract:
        (d / "_extract.md").write_text("---\npaper: x\n---\n", encoding="utf-8")
    if pdf:
        pdfs = pj / "docs" / "references" / "pdfs"
        pdfs.mkdir(parents=True, exist_ok=True)
        (pdfs / f"{key}.pdf").write_bytes(b"%PDF-1.4")


def _current_hash(pj: Path) -> str:
    return hash_template(pj / ".claude" / "paper_extraction.md")


def _picot(pj: Path) -> None:
    write_picot(
        pj,
        PicotSpec(
            type="clinical",
            created_at="2026-09-12",
            last_updated="2026-09-12",
            version=1,
            population="adultos",
            intervention="modelo",
            comparison="escore",
            outcome="AUROC",
            time="retrospectivo",
            hypothesis=Hypothesis(statement="s", rationale="r", metrics=["AUROC"]),
        ),
    )


def _ready_for_writing(pj: Path) -> None:
    _bib(pj, "a")
    _paper(pj, "a", extract=True, hash_=_current_hash(pj))
    _picot(pj)


def _draft(pj: Path, scope: str = "principal") -> None:
    writing = pj / "docs" / "studies" / scope / "writing"
    writing.mkdir(parents=True, exist_ok=True)
    (writing / "paper-2026-09-12-x.md").write_text("# draft\n", encoding="utf-8")


def _review(pj: Path, kinds: tuple[str, ...], marks: str, scope: str = "principal") -> None:
    d = pj / "reviews" / f"studies__{scope}__writing__paper-2026-09-12-x"
    d.mkdir(parents=True)
    events: dict[str, Any] = {
        "schema_version": "ReviewEventsFile/v1",
        "page": "docs/studies/principal/writing/paper-2026-09-12-x.md",
        "events": [{"kind": k, "detail": "d"} for k in kinds],
    }
    (d / "events.yaml").write_text(yaml.safe_dump(events), encoding="utf-8")
    (d / "review.md").write_text(marks, encoding="utf-8")


def _states(st: ProjectStatus) -> dict[str, str]:
    """``{id: state}``; etapas de escopo viram ``id:<slug>``."""
    return {(f"{s.id}:{s.scope}" if s.scope else s.id): s.state for s in st.stages}


def _init_protocol(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    res = runner.invoke(app, ["init", str(pj), "--with", "protocol", "--no-git", "--json"])
    assert res.exit_code == 0, res.output
    return pj


def _first_phrase(registry: SkillRegistry, skill: str, mode: str) -> str:
    found = registry.find_mode(SkillRef(skill, mode))
    assert found is not None
    return found.phrases[0]


def test_projeto_recem_criado_pede_a_pergunta(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    st = project_status(pj, registry=registry)
    assert st.library.placeholder is True
    assert st.next is not None
    assert (st.next.skill, st.next.mode) == ("protocol", "question")
    assert st.next.say == _first_phrase(registry, "protocol", "question")


def test_pergunta_fechada_e_bib_placeholder_pede_a_bibliografia(
    tmp_path: Path, registry: SkillRegistry
) -> None:
    pj = _init(tmp_path)
    _picot(pj)
    st = project_status(pj, registry=registry)
    assert _states(st)["question"] == "done"
    assert _states(st)["library"] == "current"
    assert st.next is not None and (st.next.skill, st.next.mode) == ("paper", "library")


def test_paper_com_pdf_sem_extract_pede_extract(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _picot(pj)
    _bib(pj, "a", "b")
    _paper(pj, "a")
    _paper(pj, "b", pdf=False)
    st = project_status(pj, registry=registry)
    assert (st.library.entries, st.library.placeholder) == (2, False)
    assert (st.extracts.papers, st.extracts.pending, st.extracts.without_pdf) == (2, 1, 1)
    assert st.next is not None and (st.next.skill, st.next.mode) == ("paper", "extract")
    assert "1 paper" in st.next.why


def test_extract_com_template_antigo_conta_como_stale(
    tmp_path: Path, registry: SkillRegistry
) -> None:
    pj = _init(tmp_path)
    _bib(pj, "a")
    _paper(pj, "a", extract=True, hash_="000000000000")
    st = project_status(pj, registry=registry)
    assert (st.extracts.pending, st.extracts.stale) == (0, 1)


def test_sem_pergunta_pede_question(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _bib(pj, "a")
    _paper(pj, "a", extract=True, hash_=_current_hash(pj))
    st = project_status(pj, registry=registry)
    assert st.picot.closed is False and st.picot.error is None
    assert st.next is not None and (st.next.skill, st.next.mode) == ("protocol", "question")


def test_picot_invalida_reporta_erro(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    (pj / ".claude" / "picot.toml").write_text('[picot]\ntype = "clinical"\n', encoding="utf-8")
    st = project_status(pj, registry=registry)
    assert st.picot.closed is False
    assert st.picot.error


def test_picot_fechada_sem_draft_pede_manuscript(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _ready_for_writing(pj)
    st = project_status(pj, registry=registry)
    assert st.picot.closed is True
    assert st.next is not None
    assert (st.next.skill, st.next.mode, st.next.scope) == ("write", "manuscript", "principal")


def test_evento_ambiguo_pede_reconcile(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _ready_for_writing(pj)
    _draft(pj)
    _review(pj, ("unanchored-mark", "applied"), "texto {++novo++} e {--velho--}\n")
    st = project_status(pj, registry=registry)
    review = st.scopes[0].reviews[0]
    assert (review.reconcile_events, review.pending_marks) == (1, 2)
    assert st.next is not None
    assert (st.next.skill, st.next.mode, st.next.scope) == ("review", "reconcile", "principal")


def test_eventos_nao_bloqueantes_nao_pedem_reconcile(
    tmp_path: Path, registry: SkillRegistry
) -> None:
    pj = _init(tmp_path)
    _ready_for_writing(pj)
    _draft(pj)
    _review(pj, ("applied", "citation-drop"), "texto limpo\n")
    st = project_status(pj, registry=registry)
    assert st.scopes[0].drafts == ("paper-2026-09-12-x.md",)
    assert _states(st)["review:principal"] == "done"
    assert st.next is not None and (st.next.skill, st.next.mode) == ("write", "export")


def test_multi_escopo_lista_todos_e_scope_filtra(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    (pj / "docs" / "studies" / "outro" / "writing").mkdir(parents=True)
    assert [s.slug for s in project_status(pj, registry=registry).scopes] == ["outro", "principal"]
    only = project_status(pj, scope="outro", registry=registry)
    assert [s.slug for s in only.scopes] == ["outro"]


def test_subdiretorio_do_projeto_acha_a_raiz(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    st = project_status(pj / "docs" / "studies" / "principal", registry=registry)
    assert st.project == pj.resolve()


def test_status_sem_registry_usa_a_invocacao(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    st = project_status(pj)
    assert st.next is not None and st.next.say == "/par:protocol question"


def test_cli_json_tem_schema_e_invocacao(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    assert payload["schema_version"] == "ProjectStatus/v1"
    assert payload["next"]["invocation"] == "/par:protocol question"
    assert payload["stages"][0]["id"] == "question"
    assert payload["stages"][0]["next"]["invocation"] == "/par:protocol question"
    assert payload["scopes"][0]["slug"] == "principal"
    assert payload["library"] == status_to_dict(project_status(pj))["library"]


def test_cli_texto_mostra_a_frase(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj)])
    assert res.exit_code == 0, res.output
    assert _first_phrase(registry, "protocol", "question") in res.output


def test_cli_escopo_inexistente_falha_com_instrucao(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj), "--scope", "nada"])
    assert res.exit_code != 0
    assert "prumo add study" in res.output


def test_esqueletos_do_protocol_nao_contam_como_draft(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    res = runner.invoke(app, ["init", str(pj), "--with", "protocol", "--json"])
    assert res.exit_code == 0, res.output
    st = project_status(pj)
    assert st.scopes and all(scope.drafts == () for scope in st.scopes)


# --- etapas (spec 2026-11-14, painel de etapas do projeto) -------------------


def test_recem_criado_tem_pergunta_atual_e_o_resto_depois(tmp_path: Path) -> None:
    st = project_status(_init(tmp_path))
    assert _states(st) == {
        "question": "current",
        "library": "todo",
        "reading": "todo",
        "writing:principal": "todo",
    }


def test_etapa_feita_depois_da_atual_aparece_feita(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    _bib(pj, "a")
    _paper(pj, "a", extract=True)
    states = _states(project_status(pj))
    assert states["question"] == "current"
    assert states["library"] == "done"
    assert states["reading"] == "done"
    assert states["writing:principal"] == "todo"


def test_leitura_sem_paper_no_acervo_nao_esta_feita(
    tmp_path: Path, registry: SkillRegistry
) -> None:
    pj = _init(tmp_path)
    _picot(pj)
    _bib(pj, "a")
    st = project_status(pj, registry=registry)
    reading = next(s for s in st.stages if s.id == "reading")
    assert reading.state == "current" and reading.summary == "nenhum paper no acervo"
    assert st.next is not None and (st.next.skill, st.next.mode) == ("paper", "library")


def test_bibliografia_mostra_a_colecao_do_zotero_gravada(tmp_path: Path) -> None:
    from par.domains.paper import link
    from par.domains.paper.schemas.v1 import ZoteroLink

    pj = _init(tmp_path)
    _bib(pj, "a")
    library = next(s for s in project_status(pj).stages if s.id == "library")
    assert "›" not in library.summary

    link.write_link(
        pj,
        ZoteroLink(
            library="My Library",
            library_id=1,
            collection="Pesquisa/Colecao do estudo piloto1",
            collection_key="BBB",
            linked_at="2026-11-16",
            source="connect",
        ),
    )
    st = project_status(pj)
    library = next(s for s in st.stages if s.id == "library")
    assert library.summary.startswith("My Library › Pesquisa/Colecao do estudo piloto1 · 1 entrada")
    payload = status_to_dict(st)["library"]["zotero"]
    assert payload["collection_key"] == "BBB"
    assert payload["select_uri"] == "zotero://select/library/collections/BBB"


def test_pasta_oculta_em_studies_nao_vira_etapa(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    (pj / "docs" / "studies" / ".claude").mkdir()
    st = project_status(pj)
    assert [s.slug for s in st.scopes] == ["principal"]
    assert all(s.scope != ".claude" for s in st.stages)


def test_extract_desatualizado_vira_atencao_sem_bloquear(
    tmp_path: Path, registry: SkillRegistry
) -> None:
    pj = _init(tmp_path)
    _picot(pj)
    _bib(pj, "a")
    _paper(pj, "a", extract=True, hash_="000000000000")
    st = project_status(pj, registry=registry)
    reading = next(s for s in st.stages if s.id == "reading")
    assert reading.state == "attention"
    assert reading.next is not None and reading.next.mode == "extract"
    assert _states(st)["writing:principal"] == "current"
    assert "Atenção:" in render_status(st)


def test_protocol_recem_criado_e_a_etapa_atual(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init_protocol(tmp_path)
    _ready_for_writing(pj)
    st = project_status(pj, registry=registry)
    protocol = next(s for s in st.stages if s.id == "protocol")
    assert protocol.state == "current" and protocol.scope == "principal"
    assert "projeto-cep.md" in protocol.summary
    assert "statistical_analysis_plan_skeleton.md" in protocol.summary
    assert st.next is not None and (st.next.skill, st.next.mode) == ("protocol", "sap")


def test_protocol_preenchido_fica_feito(tmp_path: Path) -> None:
    pj = _init_protocol(tmp_path)
    _ready_for_writing(pj)
    writing = pj / "docs" / "studies" / "principal" / "writing"
    for name in ("protocol.md", "projeto-cep.md", "statistical_analysis_plan_skeleton.md"):
        with (writing / name).open("a", encoding="utf-8") as f:
            f.write("\nPreenchido pela pesquisadora.\n")
    st = project_status(pj)
    assert _states(st)["protocol:principal"] == "done"
    assert _states(st)["writing:principal"] == "current"


def test_sem_modulo_protocol_nao_ha_etapa_protocol(tmp_path: Path) -> None:
    st = project_status(_init(tmp_path))
    assert all(s.id != "protocol" for s in st.stages)


def test_entrega_atual_ate_existir_o_docx(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _ready_for_writing(pj)
    _draft(pj)
    st = project_status(pj, registry=registry)
    assert _states(st)["delivery:principal"] == "current"
    assert st.next is not None and (st.next.skill, st.next.mode) == ("write", "export")
    exports = pj / "build" / "exports"
    exports.mkdir(parents=True)
    (exports / "studies__principal__writing__paper-2026-09-12-x.docx").write_bytes(b"PK")
    st = project_status(pj, registry=registry)
    assert _states(st)["delivery:principal"] == "done"
    assert st.next is None


def test_next_do_json_e_o_da_etapa_atual(tmp_path: Path) -> None:
    payload = status_to_dict(project_status(_init(tmp_path)))
    current = [s for s in payload["stages"] if s["state"] == "current"]
    assert len(current) == 1
    assert payload["next"] == current[0]["next"]
    assert {"library", "extracts", "question", "picot", "scopes", "next"} <= payload.keys()


def test_texto_tem_uma_linha_por_etapa(tmp_path: Path) -> None:
    st = project_status(_init(tmp_path))
    text = render_status(st)
    assert "● Pergunta: ainda aberta" in text
    assert "○ Escrita (principal): sem draft" in text
    assert text.index("Pergunta") < text.index("Próximo passo")
