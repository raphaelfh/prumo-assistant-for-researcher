"""``PicotSpec/v1`` — schema canônico da PICOT do projeto.

Vive em ``.claude/picot.toml`` e é a fonte única de verdade. Os 3 destinos
(``docs/protocol.md``, ``docs/project_guide.md``, ADRs) são renders.

Versionamento forward-only: nunca remover ou renomear campos; novos campos
sempre opcionais com default. ``v2`` lê ``v1``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Hypothesis(BaseModel):
    """Hipótese formal única do projeto."""

    statement: str = Field(..., min_length=1, description="Frase declarativa formal.")
    rationale: str = Field(..., min_length=1, description="Por que esperar — ok citar literatura.")
    metrics: list[str] = Field(..., min_length=1, description="Como testar — ex.: AUROC, ECE.")


class PicotSpec(BaseModel):
    """Schema canônico de PICOT por projeto.

    Em ``type = 'clinical'``, P/I/C/O/T são obrigatórios.
    Em ``type = 'methodological'``, ``contribution`` + ``hypothesis_validity_condition``
    são obrigatórios; P/I/C/O/T podem ser ``None`` (omitidos do TOML).
    """

    schema_version: Literal["PicotSpec/v1"] = "PicotSpec/v1"
    type: Literal["clinical", "methodological"]
    created_at: str = Field(..., description="ISO date YYYY-MM-DD da primeira escrita.")
    last_updated: str = Field(..., description="ISO date YYYY-MM-DD da última escrita.")
    version: int = Field(..., ge=1, description="Bump em mudança estrutural.")

    population: str | None = None
    intervention: str | None = None
    comparison: str | None = None
    outcome: str | None = None
    time: str | None = None

    contribution: str | None = None
    hypothesis_validity_condition: str | None = None

    hypothesis: Hypothesis

    @model_validator(mode="after")
    def _validate_required_by_type(self) -> PicotSpec:
        if self.type == "clinical":
            for field in ("population", "intervention", "comparison", "outcome", "time"):
                value = getattr(self, field)
                if not value:
                    raise ValueError(f"type='clinical': campo '{field}' é obrigatório (não-vazio).")
        elif self.type == "methodological":
            for field in ("contribution", "hypothesis_validity_condition"):
                value = getattr(self, field)
                if not value:
                    raise ValueError(
                        f"type='methodological': campo '{field}' é obrigatório (não-vazio)."
                    )
        return self
