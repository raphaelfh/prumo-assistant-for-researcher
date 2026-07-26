"""Fixtures compartilhadas de `tests/unit` (achado do /simplify, 2026-07-25).

`_init_project` era VERBATIM em `test_review_ingest.py`/`test_review_apply.py`/
`test_mcp_server.py` (cada cópia citava "mesmo padrão de..." na docstring), e
os builders de sidecar sintético (`_write_sidecars` no ingest,
`_write_review_dir` no apply, `_write_review_artifacts` no mcp) sobrepunham o
mesmo bloco citemap/"deadbee"/span-map-vazio ou review.md+events.yaml —
consolidados aqui num único builder parametrizado por quais artefatos emitir.

A convenção "cada arquivo de teste tem seu próprio builder" SEGUE VALENDO
para os builders de docx-zip (`_write_docx`/`_write_docx_with_fields`/...),
genuinamente diferentes por módulo — campos de citação, regiões estruturais,
comentários; só `W_XMLNS`, idêntico em todos, mora aqui (constante importável,
não fixture: é usado em nível de módulo, ex. `test_review_guards._DOC_XMLNS`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import pytest
import yaml

from prumo_assist.domains.write.export import slugify
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
    ReviewEventsFile,
    SpanMapFile,
)

W_XMLNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


class InitProject(Protocol):
    """Tipo do factory devolvido pela fixture `init_project` (mypy --strict)."""

    def __call__(self, *, body: str = ...) -> tuple[Path, Path]: ...


@pytest.fixture
def init_project(tmp_path: Path) -> InitProject:
    """Monta `project_root` mínimo (`references/_references.bib`, invariante
    exigido por `export.detect_project_root`) + `pagina.md` com `body`;
    devolve `(project_root, page)`. `project_root` é o próprio `tmp_path` do
    teste — caminhos auxiliares (docx sintético etc.) podem continuar usando
    `tmp_path` diretamente."""

    def _init(*, body: str = "Corpo da pagina de teste.") -> tuple[Path, Path]:
        project_root = tmp_path
        (project_root / "references").mkdir(parents=True, exist_ok=True)
        (project_root / "references" / "_references.bib").write_text("")
        page = project_root / "pagina.md"
        page.write_text(body)
        return project_root, page

    return _init


class WriteReviewArtifacts(Protocol):
    """Tipo do builder devolvido por `write_review_artifacts` (mypy --strict)."""

    def __call__(
        self,
        project_root: Path,
        page: Path,
        *,
        review_md: str | None = ...,
        events: list[ReviewEvent] | None = ...,
        comments: list[ReviewComment] | None = ...,
        occurrences: list[CiteOccurrence] | None = ...,
        source_text: str = ...,
        docx_sha256: str = ...,
    ) -> Path: ...


@pytest.fixture
def write_review_artifacts() -> WriteReviewArtifacts:
    """Grava `reviews/<slug>/` sintético à mão, parametrizado por quais
    artefatos emitir — nunca roda pandoc/BBT/adeu de verdade:

    - `citemap.json` + `span-map.json`: SEMPRE (simulam a saída de
      `export._emit_review_sidecars`). `span_map.fragments` fica vazio de
      propósito: `ingest()` recalcula `norm_text`/`span_frags` na hora via
      `normalize_markdown_with_map` (mesma chamada do export) e `apply_review`
      nunca reinverte offsets (I5) — os sidecars só precisam de
      `source_sha256`/`docx_sha256` para os preflights.
    - `review.md` + `events.yaml`: quando `review_md` é passado (simulam a
      saída de `review.ingest()` — worklist pós-ingest).
    - `review-comments.yaml`: quando `comments` é passado (lista vazia conta).

    `page` é resolvido antes do slug (mesmo comportamento do builder original
    de `test_mcp_server.py` — as tools MCP resolvem o path recebido como str).
    """

    def _write(
        project_root: Path,
        page: Path,
        *,
        review_md: str | None = None,
        events: list[ReviewEvent] | None = None,
        comments: list[ReviewComment] | None = None,
        occurrences: list[CiteOccurrence] | None = None,
        source_text: str = "irrelevante para apply_review",
        docx_sha256: str = "cd" * 32,
    ) -> Path:
        page_resolved = page.resolve()
        rel_page = str(page_resolved.relative_to(project_root))
        review_dir = project_root / "reviews" / slugify(page_resolved, project_root)
        review_dir.mkdir(parents=True, exist_ok=True)

        citemap = CiteMapFile(
            page=rel_page,
            export_git_sha="deadbee",
            bib_sha256="ab" * 32,
            docx_sha256=docx_sha256,
            occurrences=occurrences or [],
        )
        (review_dir / "citemap.json").write_text(citemap.model_dump_json())

        span_map = SpanMapFile(
            page=rel_page,
            source_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            fragments=[],
        )
        (review_dir / "span-map.json").write_text(span_map.model_dump_json())

        if review_md is not None:
            (review_dir / "review.md").write_text(review_md, encoding="utf-8")
        if review_md is not None or events is not None:
            events_file = ReviewEventsFile(page=rel_page, events=events or [])
            (review_dir / "events.yaml").write_text(
                yaml.safe_dump(
                    events_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False
                ),
                encoding="utf-8",
            )
        if comments is not None:
            comments_file = ReviewCommentsFile(page=rel_page, comments=comments)
            (review_dir / "review-comments.yaml").write_text(
                yaml.safe_dump(
                    comments_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False
                ),
                encoding="utf-8",
            )
        return review_dir

    return _write
