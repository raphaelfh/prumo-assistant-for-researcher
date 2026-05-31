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
