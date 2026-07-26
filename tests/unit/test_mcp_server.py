"""Servidor MCP `prumo-review` (stdio) — tools do ciclo de revisão.

Task 1 da Fase 3 da ponte
(`docs/superpowers/plans/2026-07-24-ponte-fase3-mcp-reconciliador.md`):
as fixtures constroem um "ciclo pós-ingest sintético" gravando
`reviews/<slug>/{review.md,events.yaml,review-comments.yaml}` à mão via
`init_project`/`write_review_artifacts` (fixtures compartilhadas de
`tests/unit/conftest.py` — simulam a saída de `review.ingest()` sem rodar o
pipeline docx/adeu de verdade), porque as 3 tools read-only só LEEM esses
artefatos, nunca o docx original.

Task 2 acrescenta `propose_prose_edit` — a ÚNICA tool de ESCRITA do
servidor (fachada fina sobre `domains.write.review.propose_prose_edit`; a
lógica/guardas I1/I3b são testadas em unidade em
`tests/unit/write/test_review_apply.py` — aqui só a delegação/tradução de
Path/tipos e erros da fachada).

As tools são chamadas como FUNÇÕES Python diretas (`mcp_server.review_status(...)`):
o decorator `@server.tool()` do FastMCP registra a tool como efeito colateral
e devolve a função original inalterada — chamar direto pula inteiramente o
transporte MCP/validação de schema, que este módulo não testa em unidade
(per plano: "transporte stdio não é testado em unidade").
"""

from __future__ import annotations

import asyncio

import pytest
from typer.testing import CliRunner

from prumo_assist import mcp_server
from prumo_assist.cli import app
from prumo_assist.domains.write.schemas.v1 import ReviewComment, ReviewEvent
from tests.unit.conftest import InitProject, WriteReviewArtifacts

runner = CliRunner()


# --- 1. review_status: counts certos de um ciclo pós-ingest sintético ------


def test_review_status_counts_from_synthetic_post_ingest_cycle(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project()
    review_md = "Texto {++inserido++} e outro {--removido--} trecho."
    events = [
        ReviewEvent(kind="citation-drop", detail="d1", occ_id="00000001", citekeys=["smith2020"]),
        ReviewEvent(kind="citation-drop", detail="d2", occ_id="00000002", citekeys=["jones2021"]),
        ReviewEvent(kind="unanchored-mark", detail="d3"),
    ]
    comments = [
        ReviewComment(id="0", author="Alice", text="comentario 1"),
        ReviewComment(id="1", author="Bob", text="comentario 2"),
    ]
    write_review_artifacts(
        project_root, page, review_md=review_md, events=events, comments=comments
    )

    status = mcp_server.review_status(str(page))

    assert status["pending_marks"] == 2
    assert status["events_by_kind"] == {"citation-drop": 2, "unanchored-mark": 1}
    assert status["comments"] == 2
    assert status["pending_drops"] == 2


# --- 2. review_events: lista completa, kinds na ordem do events.yaml -------


def test_review_events_lists_kinds(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project()
    events = [
        ReviewEvent(kind="citation-drop", detail="d1", occ_id="00000001", citekeys=["smith2020"]),
        ReviewEvent(kind="non-identity-span", detail="d2"),
    ]
    write_review_artifacts(
        project_root, page, review_md="conteudo qualquer", events=events, comments=[]
    )

    result = mcp_server.review_events(str(page))

    assert [event["kind"] for event in result] == ["citation-drop", "non-identity-span"]
    assert result[0]["occ_id"] == "00000001"
    assert result[0]["citekeys"] == ["smith2020"]


# --- 3. review_worklist: conteúdo == review.md gravado ----------------------


def test_review_worklist_returns_review_md_content(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project()
    review_md = "---\ntitle: X\n---\n\nCorpo com {++marca++} pendente."
    write_review_artifacts(project_root, page, review_md=review_md, events=[], comments=[])

    assert mcp_server.review_worklist(str(page)) == review_md


# --- 4. sem sidecars (ingest nunca rodou) → ValueError pt-BR ----------------


def test_review_tools_without_ingest_raise_value_error_pt_br(init_project: InitProject) -> None:
    _project_root, page = init_project()

    for tool in (mcp_server.review_status, mcp_server.review_events, mcp_server.review_worklist):
        with pytest.raises(ValueError) as exc:
            tool(str(page))
        message = str(exc.value)
        assert "prumo write review ingest" in message


# --- 4b. events.yaml fora do schema → ValueError pt-BR "sidecar corrompido" -
#         (MUST-DO da review da Task 1: `pydantic.ValidationError` cru não --
#         tinha o polimento pt-BR+comando das demais mensagens) -------------


def test_review_events_with_malformed_events_yaml_raises_corrupt_sidecar_error(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project()
    review_dir = write_review_artifacts(
        project_root, page, review_md="conteudo qualquer", events=[], comments=[]
    )
    # `detail` é obrigatório em `ReviewEvent` (schemas/v1.py) — evento sem
    # ele viola o schema (`pydantic.ValidationError`), simulando um
    # events.yaml corrompido/editado à mão incorretamente.
    (review_dir / "events.yaml").write_text(
        "schema_version: ReviewEventsFile/v1\n"
        "page: pagina.md\n"
        "events:\n"
        "  - kind: unanchored-mark\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        mcp_server.review_events(str(page))

    message = str(exc.value)
    assert "sidecar corrompido" in message
    assert "events.yaml" in message
    assert "prumo write review ingest" in message


# --- 5. server registra exatamente as tools read-only + a de proposta ------


def test_server_registers_exactly_the_read_only_and_proposal_tools() -> None:
    tools = asyncio.run(mcp_server.server.list_tools())
    assert {tool.name for tool in tools} == {
        "review_status",
        "review_events",
        "review_worklist",
        "propose_prose_edit",
    }


# --- 6. CLI `prumo mcp serve` chama run_stdio (fachada) ---------------------


def test_mcp_serve_command_calls_run_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def _fake_run_stdio() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(mcp_server, "run_stdio", _fake_run_stdio)

    result = runner.invoke(app, ["mcp", "serve"])

    assert result.exit_code == 0, result.output
    assert called


# --- 7. propose_prose_edit: fachada delega ao domínio e traduz Path/tipos --


def test_propose_prose_edit_delegates_to_domain_and_writes_pending_mark(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project(body="Frase-alvo para a proposta aqui.")
    review_dir = write_review_artifacts(
        project_root,
        page,
        review_md="Frase-alvo para a proposta aqui.",
        events=[],
        comments=[],
    )

    result = mcp_server.propose_prose_edit(
        str(page),
        anchor_excerpt="Frase-alvo",
        position="after",
        kind="ins",
        b=" extra",
    )

    assert result == {
        "review_md": str(review_dir / "review.md"),
        "inserted_mark_index": 0,
    }
    review_md_text = (review_dir / "review.md").read_text()
    assert review_md_text == "Frase-alvo{++ extra++}{>>prumo-autor: agente<<} para a proposta aqui."


# --- 8. propose_prose_edit propaga as guardas I1/I3b do domínio (fachada não
#         reimplementa nada, só repassa o ValueError) ----------------------


def test_propose_prose_edit_propagates_domain_citation_guard_error(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    project_root, page = init_project(body="Frase-alvo para a proposta aqui.")
    write_review_artifacts(
        project_root,
        page,
        review_md="Frase-alvo para a proposta aqui.",
        events=[],
        comments=[],
    )

    with pytest.raises(ValueError) as exc:
        mcp_server.propose_prose_edit(
            str(page),
            anchor_excerpt="Frase-alvo",
            position="after",
            kind="ins",
            b=" conforme [@smith2020]",
        )

    assert "I3b" in str(exc.value)


# --- 9. propose_prose_edit sem ingest → ValueError pt-BR (mesma disciplina -
#        das 3 tools read-only) ---------------------------------------------


def test_propose_prose_edit_without_ingest_raises_value_error_pt_br(
    init_project: InitProject,
) -> None:
    _project_root, page = init_project()

    with pytest.raises(ValueError) as exc:
        mcp_server.propose_prose_edit(
            str(page),
            anchor_excerpt="qualquer coisa",
            position="after",
            kind="ins",
            b=" x",
        )

    assert "prumo write review ingest" in str(exc.value)


# --- 10. Fix pós-review (Crítico 1): fachada propaga a recusa do round-trip
#         guard (injeção de delimitador via `author`) sem reescrever nada --


def test_propose_prose_edit_propagates_author_injection_guard_error(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Mesma disciplina do teste 8 (guardas do domínio atravessam a fachada
    sem reimplementação): o repro do reviewer (`author` hostil fechando a
    âncora prematuramente e soltando `[[@injetado]]` livre no worklist)
    chega aqui como `ValueError` pt-BR ("author inválido"), e `review.md`
    permanece intocado."""
    project_root, page = init_project(body="Frase-alvo para a proposta aqui.")
    review_dir = write_review_artifacts(
        project_root,
        page,
        review_md="Frase-alvo para a proposta aqui.",
        events=[],
        comments=[],
    )

    with pytest.raises(ValueError) as exc:
        mcp_server.propose_prose_edit(
            str(page),
            anchor_excerpt="Frase-alvo",
            position="after",
            kind="ins",
            b=" extra",
            author="agente<<} [[@injetado]] {>>x",
        )

    assert "author inválido" in str(exc.value)
    assert (review_dir / "review.md").read_text() == "Frase-alvo para a proposta aqui."
