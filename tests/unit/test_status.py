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
from par.status import project_status, status_to_dict

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


def _first_phrase(registry: SkillRegistry, skill: str, mode: str) -> str:
    found = registry.find_mode(SkillRef(skill, mode))
    assert found is not None
    return found.phrases[0]


def test_projeto_recem_criado_pede_a_bibliografia(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    st = project_status(pj, registry=registry)
    assert st.library.placeholder is True
    assert st.next is not None
    assert (st.next.skill, st.next.mode) == ("paper", "library")
    assert st.next.say == _first_phrase(registry, "paper", "library")


def test_paper_com_pdf_sem_extract_pede_extract(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
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


def test_sem_picot_pede_picot(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _bib(pj, "a")
    _paper(pj, "a", extract=True, hash_=_current_hash(pj))
    st = project_status(pj, registry=registry)
    assert st.picot.closed is False and st.picot.error is None
    assert st.next is not None and (st.next.skill, st.next.mode) == ("protocol", "picot")


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


def test_eventos_nao_bloqueantes_nao_pedem_nada(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    _ready_for_writing(pj)
    _draft(pj)
    _review(pj, ("applied", "citation-drop"), "texto limpo\n")
    st = project_status(pj, registry=registry)
    assert st.scopes[0].drafts == ("paper-2026-09-12-x.md",)
    assert st.next is None


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
    assert st.next is not None and st.next.say == "/par:paper library"


def test_cli_json_tem_schema_e_invocacao(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    assert payload["schema_version"] == "ProjectStatus/v1"
    assert payload["next"]["invocation"] == "/par:paper library"
    assert payload["scopes"][0]["slug"] == "principal"
    assert payload["library"] == status_to_dict(project_status(pj))["library"]


def test_cli_texto_mostra_a_frase(tmp_path: Path, registry: SkillRegistry) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj)])
    assert res.exit_code == 0, res.output
    assert _first_phrase(registry, "paper", "library") in res.output


def test_cli_escopo_inexistente_falha_com_instrucao(tmp_path: Path) -> None:
    pj = _init(tmp_path)
    res = runner.invoke(app, ["status", str(pj), "--scope", "nada"])
    assert res.exit_code != 0
    assert "prumo add study" in res.output
