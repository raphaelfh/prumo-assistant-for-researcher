"""``PaperCallout/v1`` — schema do output da skill ``paper-extract``.

A skill produz um JSON estruturado conforme este schema. O Python valida com
Pydantic e renderiza o callout via ``domains.paper.callout.render_callout``.

Versionamento: nunca remover campos; novos campos sempre opcionais. ``v2`` lê
``v1`` adicionando defaults. Migrações em ``schemas/migrations.py`` (ainda
não criado — só quando ``v2`` existir).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PaperCallout(BaseModel):
    """Output estruturado do ``paper-extract``.

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
