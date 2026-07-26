"""``ComposeInputs/v1`` + ``WriteOutput/v1`` — schemas pra família ``write-*``.

Versionamento forward-only (vN+1 lê vN; nunca remove campo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec


class PaperSummary(BaseModel):
    """Resumo de 1 paper do acervo (metadata + extract callout)."""

    citekey: str = Field(..., min_length=1)
    title: str
    year: int | None = None
    authors: str = ""
    extract_content: str | None = None


class FindingSummary(BaseModel):
    """Achado canônico (``docs/wiki/findings/*.md`` ou ``docs/findings/*.md``)."""

    path: Path
    title: str
    body: str


class ComposeInputs(BaseModel):
    """Tudo que skill ``write-*`` precisa pra gerar prose."""

    schema_version: Literal["ComposeInputs/v1"] = "ComposeInputs/v1"
    picot: PicotSpec | None = None
    citekeys: list[str] = []
    papers: dict[str, PaperSummary] = {}
    protocol: str | None = None
    project: str | None = None
    findings: list[FindingSummary] = []


WriteKind = Literal["paper", "projeto-cep", "statistics", "scientific"]
WriteMode = Literal["drafts", "into", "out"]


class WriteOutput(BaseModel):
    """Resultado da geração — reportado e usável programaticamente."""

    schema_version: Literal["WriteOutput/v1"] = "WriteOutput/v1"
    output_path: Path
    mode: WriteMode
    kind: WriteKind
    sections_filled: list[str]
    sections_skipped: list[str]
    citations_used: list[str]
    references_missing: list[str]
    words_generated: int


class SpanFragmentModel(BaseModel):
    """Um fragmento de mapeamento de intervalo (source → normalized)."""

    source_start: int
    source_end: int
    norm_start: int
    norm_end: int
    kind: str


class SpanMapFile(BaseModel):
    """Arquivo sidecar que mapeia spans de texto-fonte para texto normalizado."""

    schema_version: Literal["SpanMapFile/v1"] = "SpanMapFile/v1"
    page: str
    source_sha256: str
    fragments: list[SpanFragmentModel]


class CiteOccurrence(BaseModel):
    """Uma ocorrência de citação com identidade, citekeys e metadados de formatação."""

    occ_id: str
    citation_id: str
    citekeys: list[str]
    fingerprints: dict[str, str]
    formatted: str
    norm_start: int
    norm_end: int


class CiteMapFile(BaseModel):
    """Arquivo sidecar que mapeia ocorrências de citações com suas posições normalizadas."""

    schema_version: Literal["CiteMapFile/v1"] = "CiteMapFile/v1"
    page: str
    export_git_sha: str
    bib_sha256: str
    docx_sha256: str
    occurrences: list[CiteOccurrence]


class AIToolUse(BaseModel):
    """Um uso agregado de ferramenta de IA (uma skill + um modelo)."""

    tool: str
    model: str | None = None
    task: str
    count: int = 1
    human_reviewed: bool = False


class AIDisclosure(BaseModel):
    """AIDisclosure/v1 — declaração de uso de IA derivada da proveniência."""

    schema_version: Literal["AIDisclosure/v1"] = "AIDisclosure/v1"
    generated_at: str
    date_from: str | None = None
    date_to: str | None = None
    tools: list[AIToolUse] = Field(default_factory=list)
    statement_pt: str
    statement_en: str


class ReviewComment(BaseModel):
    """Comentário extraído de um docx revisado."""

    id: str
    author: str
    date: str | None = None
    text: str
    anchor_text: str | None = None
    reply_of: str | None = None


class ReviewCommentsFile(BaseModel):
    """Arquivo sidecar que mapeia comentários extraídos de um docx revisado."""

    schema_version: Literal["ReviewCommentsFile/v1"] = "ReviewCommentsFile/v1"
    page: str
    comments: list[ReviewComment] = []


class ReviewEvent(BaseModel):
    """Um evento de revisão capturado durante ingest/apply."""

    kind: str
    detail: str
    occ_id: str | None = None
    citekeys: list[str] = []
    author: str | None = None
    mark_excerpt: str | None = None


class ReviewEventsFile(BaseModel):
    """Arquivo sidecar que mapeia eventos de revisão durante processamento."""

    schema_version: Literal["ReviewEventsFile/v1"] = "ReviewEventsFile/v1"
    page: str
    events: list[ReviewEvent] = []
