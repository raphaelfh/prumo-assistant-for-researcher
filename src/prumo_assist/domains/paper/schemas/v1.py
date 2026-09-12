"""``PaperCallout/v1`` — schema do output do modo ``paper extract``.

A skill produz um JSON estruturado conforme este schema. O Python valida com
Pydantic e renderiza o callout via ``domains.paper.callout.render_callout``.

Versionamento: nunca remover campos; novos campos sempre opcionais. ``v2`` lê
``v1`` adicionando defaults. Migrações em ``schemas/migrations.py`` (ainda
não criado — só quando ``v2`` existir).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Locator(BaseModel):
    """Onde, no PDF, está o que uma seção do extract afirma (spec 2026-09-12, D3).

    Só orienta o ``verifier``: o veredito sai da leitura do PDF, nunca do locator.
    """

    page: int | None = Field(None, ge=1, description="Página do PDF (1-based), se conhecida")
    quote: str = Field(..., min_length=1, max_length=400, description="Trecho literal do PDF")


class PaperCallout(BaseModel):
    """Output estruturado do ``paper extract``.

    ``sections`` mapeia nome de seção → texto Markdown. As seções são definidas
    no template ``.claude/paper_extraction.md`` do projeto (TL;DR, PICOT, Método,
    Resultados, Limitações por padrão).
    """

    schema_version: Literal["PaperCallout/v1"] = "PaperCallout/v1"
    citekey: str = Field(..., min_length=1, description="Citekey BBT do paper")
    sections: dict[str, str] = Field(default_factory=dict, description="seção → texto Markdown")
    model: str = Field(..., min_length=1, description="Modelo LLM que gerou")
    extracted_at: str = Field(..., description="ISO date YYYY-MM-DD")
    template_hash: str = Field(..., min_length=1, description="sha256[:12] do template")
    extra: dict[str, Any] = Field(default_factory=dict, description="campos adicionais")
    locators: dict[str, list[Locator]] = Field(
        default_factory=dict, description="seção → trechos do PDF que a sustentam (opcional)"
    )


SupportVerdictKind = Literal["fully", "partially", "unsubstantiated", "no-source"]


class SupportVerdict(BaseModel):
    """Veredito do ``verifier``: a fonte sustenta a frase que a cita?

    ``fully``/``partially`` exigem o trecho literal do PDF que sustenta — veredito
    positivo sem evidência é exatamente a confirmação ativa que o modo evita.
    ``no-source`` = PDF indisponível; nunca vira veredito positivo.
    """

    sentence: str = Field(..., min_length=1)
    citekey: str = Field(..., min_length=1)
    verdict: SupportVerdictKind
    justification: str = Field(..., min_length=1)
    quote: str | None = None
    page: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _positivo_exige_trecho(self) -> SupportVerdict:
        if self.verdict in ("fully", "partially") and not (self.quote and self.quote.strip()):
            raise ValueError(f"verdict='{self.verdict}' exige quote (trecho literal do PDF).")
        return self


class SupportReport(BaseModel):
    """Relatório do modo ``paper support`` para uma página."""

    schema_version: Literal["SupportReport/v1"] = "SupportReport/v1"
    page: str = Field(..., min_length=1)
    verdicts: list[SupportVerdict] = Field(default_factory=list)
