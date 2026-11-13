"""Schemas canônicos da pergunta do estudo.

- ``QuestionSpec/v1`` (ADR-0041) — vive em ``.claude/question.toml`` e é a fonte
  única de verdade. A pergunta em uma frase é o centro; PICOT, PECO, PCC e os
  demais frameworks são decomposição opcional (``framework`` + ``elements``).
- ``PicotSpec/v1`` — formato anterior (``.claude/picot.toml``), só lido e
  convertido por :func:`question_from_picot`.

Os destinos (``protocol.md``, ``project_guide.md``, ADRs) são renders.

Versionamento forward-only: nunca remover ou renomear campos; novos campos
sempre opcionais com default. ``v2`` lê ``v1``.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator


class Hypothesis(BaseModel):
    """Hipótese formal única do projeto."""

    statement: str = Field(..., min_length=1, description="Frase declarativa formal.")
    rationale: str = Field(..., min_length=1, description="Por que esperar — ok citar literatura.")
    metrics: list[str] = Field(..., min_length=1, description="Como testar — ex.: AUROC, ECE.")


#: Campos P/I/C/O/T obrigatórios por ``type``; ``methodological`` não usa nenhum.
_REQUIRED_PICOT: dict[str, tuple[str, ...]] = {
    "clinical": ("population", "intervention", "comparison", "outcome", "time"),
    "prediction": ("population", "intervention", "outcome", "time"),
}


class PicotSpec(BaseModel):
    """Schema canônico de PICOT por projeto.

    Em ``type = 'clinical'``, P/I/C/O/T são obrigatórios.
    Em ``type = 'prediction'`` (modelo/escore/biomarcador prognóstico ou
    diagnóstico), P/I/O/T são obrigatórios e ``comparison`` é opcional:
    ``intervention`` guarda o index (preditor, teste, escore) e ``time`` o
    horizonte de predição.
    Em ``type = 'methodological'``, ``contribution`` + ``hypothesis_validity_condition``
    são obrigatórios; P/I/C/O/T podem ser ``None`` (omitidos do TOML).
    """

    schema_version: Literal["PicotSpec/v1"] = "PicotSpec/v1"
    type: Literal["clinical", "methodological", "prediction"]
    created_at: str = Field(..., description="ISO date YYYY-MM-DD da primeira escrita.")
    last_updated: str = Field(..., description="ISO date YYYY-MM-DD da última escrita.")
    version: int = Field(..., ge=1, description="Bump em mudança estrutural.")

    population: str | None = Field(default=None, description="P: população, paciente ou problema.")
    intervention: str | None = Field(
        default=None,
        description="I: intervenção sob teste ou, em ``prediction``, o index/preditor.",
    )
    comparison: str | None = Field(
        default=None, description="C: comparador; opcional em ``prediction``."
    )
    outcome: str | None = Field(
        default=None, description="O: desfecho (o evento previsto em ``prediction``)."
    )
    time: str | None = Field(
        default=None, description="T: janela temporal ou horizonte de predição."
    )

    contribution: str | None = None
    hypothesis_validity_condition: str | None = None

    hypothesis: Hypothesis

    @model_validator(mode="after")
    def _validate_required_by_type(self) -> PicotSpec:
        if self.type in _REQUIRED_PICOT:
            for field in _REQUIRED_PICOT[self.type]:
                value = getattr(self, field)
                if not value:
                    raise ValueError(
                        f"type='{self.type}': campo '{field}' é obrigatório (não-vazio)."
                    )
        elif self.type == "methodological":
            for field in ("contribution", "hypothesis_validity_condition"):
                value = getattr(self, field)
                if not value:
                    raise ValueError(
                        f"type='methodological': campo '{field}' é obrigatório (não-vazio)."
                    )
        return self


QuestionType = Literal[
    "clinical",
    "experimental",
    "observational",
    "prediction",
    "review",
    "qualitative",
    "mixed_methods",
    "economic",
    "computational",
    "theoretical",
    "methodological",
    "case_report",
    "other",
]
QUESTION_TYPES: tuple[str, ...] = get_args(QuestionType)

Framework = Literal[
    "PICOT",
    "PICO",
    "PICOS",
    "PECO",
    "PECOT",
    "PEO",
    "PCC",
    "PICo",
    "SPIDER",
    "PIRD",
    "CoCoPop",
]

#: Elementos de cada framework: (obrigatórios, opcionais).
FRAMEWORK_ELEMENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "PICOT": (("population", "intervention", "outcome", "time"), ("comparison",)),
    "PICO": (("population", "intervention", "outcome"), ("comparison",)),
    "PICOS": (("population", "intervention", "outcome", "study_design"), ("comparison",)),
    "PECO": (("population", "exposure", "outcome"), ("comparison",)),
    "PECOT": (("population", "exposure", "outcome", "time"), ("comparison",)),
    "PEO": (("population", "exposure", "outcome"), ()),
    "PCC": (("population", "concept", "context"), ()),
    "PICo": (("population", "phenomenon", "context"), ()),
    "SPIDER": (("sample", "phenomenon", "design", "evaluation", "research_type"), ()),
    "PIRD": (("population", "index_test", "reference_standard", "diagnosis"), ()),
    "CoCoPop": (("condition", "context", "population"), ()),
}

#: Rótulo pt-BR de cada elemento, usado nos renders.
ELEMENT_LABELS: dict[str, str] = {
    "population": "População",
    "intervention": "Intervenção ou index",
    "exposure": "Exposição",
    "comparison": "Comparador",
    "outcome": "Desfecho",
    "time": "Tempo ou horizonte",
    "study_design": "Desenho dos estudos",
    "concept": "Conceito",
    "context": "Contexto",
    "phenomenon": "Fenômeno de interesse",
    "sample": "Amostra",
    "design": "Desenho",
    "evaluation": "Avaliação",
    "research_type": "Tipo de pesquisa",
    "index_test": "Teste index",
    "reference_standard": "Padrão de referência",
    "diagnosis": "Diagnóstico-alvo",
    "condition": "Condição",
}

#: Tipos confirmatórios: hipótese formal obrigatória.
_NEEDS_HYPOTHESIS = frozenset({"clinical", "experimental", "prediction", "methodological"})
#: Tipos sem teste de hipótese por natureza: objetivo obrigatório.
_NEEDS_OBJECTIVE = frozenset({"qualitative", "case_report", "theoretical"})
#: Frameworks em que ``clinical`` exige comparador (regra herdada da PICOT).
_COMPARATIVE = frozenset({"PICOT", "PICO", "PICOS"})


class QuestionSpec(BaseModel):
    """Pergunta do estudo (ADR-0041).

    ``question`` é sempre obrigatória. ``framework``/``elements`` são opcionais;
    quando há framework, ``elements`` precisa das chaves obrigatórias dele e só
    aceita as conhecidas. Hipótese e objetivo seguem o ``type``: confirmatórios
    (``clinical``, ``experimental``, ``prediction``, ``methodological``) exigem
    hipótese; ``qualitative``, ``case_report`` e ``theoretical`` exigem objetivo;
    os demais aceitam um dos dois.
    """

    schema_version: Literal["QuestionSpec/v1"] = "QuestionSpec/v1"
    type: QuestionType
    question: str = Field(..., min_length=1, description="A pergunta do estudo em uma frase.")
    design: str | None = Field(
        default=None, description="Subdesenho livre: 'coorte retrospectiva', 'revisão de escopo'."
    )
    objective: str | None = Field(default=None, description="Objetivo geral do estudo.")
    created_at: str = Field(..., description="ISO date YYYY-MM-DD da primeira escrita.")
    last_updated: str = Field(..., description="ISO date YYYY-MM-DD da última escrita.")
    version: int = Field(..., ge=1, description="Bump em mudança estrutural.")

    framework: Framework | None = None
    elements: dict[str, str] | None = None

    contribution: str | None = None
    hypothesis_validity_condition: str | None = None

    hypothesis: Hypothesis | None = None

    @model_validator(mode="after")
    def _validate(self) -> QuestionSpec:
        self._validate_framework()
        t = self.type
        if t in _NEEDS_HYPOTHESIS and self.hypothesis is None:
            raise ValueError(
                f"type='{t}': campo 'hypothesis' é obrigatório "
                '(ex.: {"statement": "...", "rationale": "...", "metrics": ["..."]}).'
            )
        if t in _NEEDS_OBJECTIVE and not self.objective:
            raise ValueError(f"type='{t}': campo 'objective' é obrigatório (não-vazio).")
        if not self.objective and self.hypothesis is None:
            raise ValueError(
                f"type='{t}': informe 'objective' ou 'hypothesis' (ao menos um dos dois)."
            )
        if t in ("theoretical", "methodological") and not self.contribution:
            raise ValueError(f"type='{t}': campo 'contribution' é obrigatório (não-vazio).")
        if t == "methodological" and not self.hypothesis_validity_condition:
            raise ValueError(
                "type='methodological': campo 'hypothesis_validity_condition' é obrigatório."
            )
        return self

    def _validate_framework(self) -> None:
        if self.framework is None:
            if self.elements:
                raise ValueError(
                    "'elements' exige 'framework' (ex.: \"framework\": \"PECO\"); "
                    f"opções: {', '.join(FRAMEWORK_ELEMENTS)}."
                )
            return
        required, optional = FRAMEWORK_ELEMENTS[self.framework]
        elements = self.elements or {}
        missing = [k for k in required if not elements.get(k)]
        needs_comparison = self.type == "clinical" and self.framework in _COMPARATIVE
        if needs_comparison and not elements.get("comparison"):
            missing.append("comparison")
        if missing:
            raise ValueError(
                f"framework='{self.framework}': faltam os elementos {', '.join(missing)} "
                f"(obrigatórios: {', '.join(required)})."
            )
        unknown = sorted(set(elements) - set(required) - set(optional))
        if unknown:
            raise ValueError(
                f"framework='{self.framework}': elementos desconhecidos {', '.join(unknown)}; "
                f"aceitos: {', '.join(required + optional)}."
            )


_PICOT_KEYS = ("population", "intervention", "comparison", "outcome", "time")


def picot_question_sentence(spec: PicotSpec) -> str:
    """A frase da pergunta que o render acadêmico da PICOT já produzia."""
    if spec.type == "clinical":
        return (
            f"Em {spec.population}, a aplicação de {spec.intervention} comparada a "
            f"{spec.comparison} produz {spec.outcome}, no horizonte de {spec.time}?"
        )
    if spec.type == "prediction":
        compared = f", comparado a {spec.comparison}," if spec.comparison else ""
        return (
            f"Em {spec.population}, {spec.intervention}{compared} prevê "
            f"{spec.outcome} no horizonte de {spec.time}?"
        )
    return f"{spec.contribution} se sustenta quando {spec.hypothesis_validity_condition}?"


def question_from_picot(spec: PicotSpec) -> QuestionSpec:
    """Converte ``PicotSpec/v1`` em ``QuestionSpec/v1`` sem perda (ADR-0041)."""
    elements = {k: v for k in _PICOT_KEYS if (v := getattr(spec, k))}
    framework: Framework | None = "PICOT" if spec.type != "methodological" else None
    return QuestionSpec(
        type=spec.type,
        question=picot_question_sentence(spec),
        created_at=spec.created_at,
        last_updated=spec.last_updated,
        version=spec.version,
        framework=framework,
        elements=elements if framework else None,
        contribution=spec.contribution,
        hypothesis_validity_condition=spec.hypothesis_validity_condition,
        hypothesis=spec.hypothesis,
    )
