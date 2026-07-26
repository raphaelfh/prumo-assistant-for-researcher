"""Leitores read-side dos artefatos de ingest (`reviews/<slug>/`).

Consolidação do achado do /simplify (agente de altitude, 2026-07-25): a
fachada MCP (`mcp_server.py`) re-implementava — com WORDING DIVERGENTE do
domínio — a leitura de `review.md` e `review-comments.yaml`. Aqui ficam os
testes de unidade dos leitores de domínio (`read_comments_file`/
`read_worklist`), siblings de :func:`review.read_events_file` (testado em
`test_cli.py`, onde o fix Important #3 da Fase 3 nasceu), com contratos
idênticos: `FileNotFoundError` pt-BR (comando de ingest embutido) para
artefato ausente, `ValueError` pt-BR ("sidecar corrompido") para YAML
malformado ou fora do schema.

Fixtures gravam `reviews/<slug>/` À MÃO (ciclo pós-ingest sintético, mesmo
espírito de `test_mcp_server.py`); builders LOCAIS deste arquivo (convenção
do repo — ver docstring de `test_review_ingest.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from prumo_assist.domains.write import review
from prumo_assist.domains.write.export import slugify
from prumo_assist.domains.write.schemas.v1 import (
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
    ReviewEventsFile,
)

# --- builders locais ---------------------------------------------------------


def _init_project(tmp_path: Path) -> tuple[Path, Path]:
    """Projeto mínimo (`references/_references.bib`, exigido por
    `export.detect_project_root`) + página `.md`."""
    project_root = tmp_path
    (project_root / "references").mkdir(parents=True, exist_ok=True)
    (project_root / "references" / "_references.bib").write_text("")
    page = project_root / "pagina.md"
    page.write_text("Corpo da pagina de teste.")
    return project_root, page


def _review_dir(project_root: Path, page: Path) -> Path:
    review_dir = project_root / "reviews" / slugify(page.resolve(), project_root)
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir


def _write_comments_yaml(review_dir: Path, page: Path, comments: list[ReviewComment]) -> None:
    comments_file = ReviewCommentsFile(page=page.name, comments=comments)
    (review_dir / "review-comments.yaml").write_text(
        yaml.safe_dump(comments_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


# --- read_comments_file ------------------------------------------------------


def test_read_comments_file_returns_validated_model(tmp_path: Path) -> None:
    project_root, page = _init_project(tmp_path)
    review_dir = _review_dir(project_root, page)
    _write_comments_yaml(
        review_dir,
        page,
        [
            ReviewComment(id="0", author="Alice", text="comentario 1"),
            ReviewComment(id="1", author="Bob", text="comentario 2"),
        ],
    )

    # `project_root` explícito pula `detect_project_root` — mesma assinatura
    # opcional de `read_events_file`.
    result = review.read_comments_file(page.resolve(), project_root)

    assert isinstance(result, ReviewCommentsFile)
    assert [c.author for c in result.comments] == ["Alice", "Bob"]


def test_read_comments_file_missing_raises_file_not_found_pt_br(tmp_path: Path) -> None:
    _project_root, page = _init_project(tmp_path)

    with pytest.raises(FileNotFoundError) as exc:
        review.read_comments_file(page.resolve())

    message = str(exc.value)
    assert "Sidecar de review ausente em" in message
    assert "review-comments.yaml" in message
    assert "prumo write review ingest" in message


def test_read_comments_file_out_of_schema_raises_corrupt_sidecar_value_error(
    tmp_path: Path,
) -> None:
    project_root, page = _init_project(tmp_path)
    review_dir = _review_dir(project_root, page)
    # `text` é obrigatório em `ReviewComment` (schemas/v1.py) — ausência viola
    # o schema (`pydantic.ValidationError`), simulando sidecar corrompido.
    (review_dir / "review-comments.yaml").write_text(
        "schema_version: ReviewCommentsFile/v1\n"
        "page: pagina.md\n"
        "comments:\n"
        "  - id: '0'\n"
        "    author: Alice\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        review.read_comments_file(page.resolve())

    message = str(exc.value)
    assert "sidecar corrompido" in message
    assert "review-comments.yaml" in message
    assert "prumo write review ingest" in message
    assert "validation error" not in message.lower()


def test_read_comments_file_malformed_yaml_raises_corrupt_sidecar_value_error(
    tmp_path: Path,
) -> None:
    project_root, page = _init_project(tmp_path)
    review_dir = _review_dir(project_root, page)
    (review_dir / "review-comments.yaml").write_text("{invalid: yaml: [", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        review.read_comments_file(page.resolve())

    message = str(exc.value)
    assert "sidecar corrompido" in message
    assert "review-comments.yaml" in message


# --- read_worklist -----------------------------------------------------------


def test_read_worklist_returns_raw_review_md(tmp_path: Path) -> None:
    project_root, page = _init_project(tmp_path)
    review_dir = _review_dir(project_root, page)
    review_md = "---\ntitle: X\n---\n\nCorpo com {++marca++} pendente."
    (review_dir / "review.md").write_text(review_md, encoding="utf-8")

    assert review.read_worklist(page.resolve()) == review_md


def test_read_worklist_missing_raises_file_not_found_pt_br(tmp_path: Path) -> None:
    _project_root, page = _init_project(tmp_path)

    with pytest.raises(FileNotFoundError) as exc:
        review.read_worklist(page.resolve())

    message = str(exc.value)
    assert "Sidecar de review ausente em" in message
    assert "review.md" in message
    assert "prumo write review ingest" in message


# --- count_pending_drops / status -------------------------------------------


def test_count_pending_drops_counts_only_citation_drop_events() -> None:
    events = [
        ReviewEvent(kind="citation-drop", detail="d1", occ_id="00000001"),
        ReviewEvent(kind="unanchored-mark", detail="d2"),
        ReviewEvent(kind="citation-drop", detail="d3", occ_id="00000002"),
        ReviewEvent(kind="applied", detail="d4"),
    ]

    assert review.count_pending_drops(events) == 2
    assert review.count_pending_drops([]) == 0


def test_status_aggregates_counts_from_the_three_artifacts(tmp_path: Path) -> None:
    project_root, page = _init_project(tmp_path)
    review_dir = _review_dir(project_root, page)
    (review_dir / "review.md").write_text(
        "Texto {++inserido++} e outro {--removido--} trecho.", encoding="utf-8"
    )
    events_file = ReviewEventsFile(
        page="pagina.md",
        events=[
            ReviewEvent(kind="citation-drop", detail="d1", occ_id="00000001"),
            ReviewEvent(kind="citation-drop", detail="d2", occ_id="00000002"),
            ReviewEvent(kind="unanchored-mark", detail="d3"),
        ],
    )
    (review_dir / "events.yaml").write_text(
        yaml.safe_dump(events_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_comments_yaml(
        review_dir,
        page,
        [
            ReviewComment(id="0", author="Alice", text="comentario 1"),
            ReviewComment(id="1", author="Bob", text="comentario 2"),
        ],
    )

    result = review.status(page.resolve())

    assert result == {
        "page": "pagina.md",
        "pending_marks": 2,
        "events_by_kind": {"citation-drop": 2, "unanchored-mark": 1},
        "comments": 2,
        "pending_drops": 2,
    }


def test_status_without_ingest_propagates_missing_sidecar_error(tmp_path: Path) -> None:
    _project_root, page = _init_project(tmp_path)

    with pytest.raises(FileNotFoundError) as exc:
        review.status(page.resolve())

    message = str(exc.value)
    assert "Sidecar de review ausente em" in message
    assert "prumo write review ingest" in message
