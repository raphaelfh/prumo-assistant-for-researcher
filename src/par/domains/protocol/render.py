"""Renderiza ``QuestionSpec`` em blocos Markdown delimitados pros destinos.

Bloco padrão::

    <!-- question:begin v=N hash=sha8 -->
    ... conteúdo ...
    <!-- question:end -->

O bloco ``picot:begin``/``picot:end`` antigo é reconhecido e trocado pelo novo.

``v`` e ``hash`` permitem detectar drift sem reabrir o TOML canônico.
"""

from __future__ import annotations

import re

from par.domains.protocol.schemas.v1 import ELEMENT_LABELS, QuestionSpec

QUESTION_BEGIN_PREFIX = "<!-- question:begin "
QUESTION_END = "<!-- question:end -->"
#: Formato anterior (ADR-0041): ainda reconhecido e substituído pelo novo.
PICOT_BEGIN_PREFIX = "<!-- picot:begin "
PICOT_END = "<!-- picot:end -->"

BLOCK_BEGIN_RE = re.compile(
    r"<!--\s*(?:question|picot):begin\s+v=(?P<version>\d+)\s+hash=(?P<hash>[a-f0-9]{8})\s*-->",
)
BLOCK_FULL_RE = re.compile(
    r"<!--\s*(?:question|picot):begin\s+v=\d+\s+hash=[a-f0-9]{8}\s*-->.*?"
    r"<!--\s*(?:question|picot):end\s*-->",
    flags=re.DOTALL,
)

TYPE_LABELS: dict[str, str] = {
    "clinical": "clínico de intervenção",
    "experimental": "experimental (animal, bancada ou in vitro)",
    "observational": "observacional",
    "prediction": "de predição (diagnóstico ou prognóstico)",
    "review": "revisão",
    "qualitative": "qualitativo",
    "mixed_methods": "métodos mistos",
    "economic": "avaliação econômica",
    "computational": "computacional",
    "theoretical": "teórico",
    "methodological": "metodológico",
    "case_report": "relato de caso",
    "other": "outro",
}


#: Rótulos de elemento que mudam de sentido conforme o tipo.
_LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "clinical": {"intervention": "Intervenção (sob teste)"},
    "experimental": {"intervention": "Intervenção (sob teste)"},
    "prediction": {
        "intervention": "Preditor (index)",
        "outcome": "Desfecho previsto",
        "time": "Horizonte temporal",
    },
}


def element_label(spec: QuestionSpec, key: str) -> str:
    """Rótulo pt-BR do elemento ``key`` no tipo de ``spec``."""
    return _LABEL_OVERRIDES.get(spec.type, {}).get(key) or ELEMENT_LABELS.get(key, key)


def _type_line(spec: QuestionSpec) -> str:
    label = TYPE_LABELS[spec.type]
    return f"{label} ({spec.design})" if spec.design else label


def _header(spec: QuestionSpec, hash8: str) -> str:
    return f"{QUESTION_BEGIN_PREFIX}v={spec.version} hash={hash8} -->"


def render_protocol_block(spec: QuestionSpec, *, hash8: str) -> str:
    """Render operacional pra ``protocol.md`` (concreto, conferível)."""
    lines = [
        _header(spec, hash8),
        "",
        f"**Tipo de estudo.** {_type_line(spec)}",
        "",
        f"**Pergunta do estudo.** {spec.question}",
        "",
    ]
    if spec.objective:
        lines += [f"**Objetivo.** {spec.objective}", ""]
    if spec.framework and spec.elements:
        lines += [f"**Estrutura ({spec.framework}).**", ""]
        lines += [f"- **{element_label(spec, k)}.** {v}" for k, v in spec.elements.items()]
        lines.append("")
    if spec.contribution:
        lines += [f"**Contribuição.** {spec.contribution}", ""]
    if spec.hypothesis_validity_condition:
        lines += [f"**Condição de validade.** {spec.hypothesis_validity_condition}", ""]
    if spec.hypothesis:
        lines += [
            f"**Hipótese formal.** {spec.hypothesis.statement}",
            "",
            f"*Métricas: {', '.join(spec.hypothesis.metrics)}.*",
            "",
        ]
    lines.append(QUESTION_END)
    return "\n".join(lines)


def render_project_block(spec: QuestionSpec, *, hash8: str) -> str:
    """Render acadêmico pra ``project_guide.md`` (prosa formal)."""
    lines = [_header(spec, hash8), "", "## Pergunta do estudo", "", spec.question, ""]
    lines += [f"Estudo {_type_line(spec)}.", ""]
    if spec.objective:
        lines += [f"**Objetivo:** {spec.objective}", ""]
    if spec.contribution:
        lines += [f"**Contribuição:** {spec.contribution}", ""]
    if spec.hypothesis_validity_condition:
        lines += [f"**Condição de validade:** {spec.hypothesis_validity_condition}", ""]
    if spec.hypothesis:
        lines += [
            "## Hipótese central",
            "",
            spec.hypothesis.statement.rstrip(".") + ".",
            "",
            spec.hypothesis.rationale,
            "",
        ]
    lines.append(QUESTION_END)
    return "\n".join(lines)


def replace_or_insert_block(text: str, new_block: str, *, anchor_pattern: str) -> str:
    """Substitui bloco existente; se ausente, insere logo após ``anchor_pattern``.

    ``anchor_pattern`` é regex multiline (ex.: ``r'^## Contexto.*$'``). Se nenhum
    bloco (question ou picot) existir e o anchor não casar, append no final.
    """
    if BLOCK_FULL_RE.search(text):
        return BLOCK_FULL_RE.sub(new_block, text, count=1)
    anchor = re.compile(anchor_pattern, flags=re.MULTILINE)
    m = anchor.search(text)
    if m:
        end = m.end()
        return text[:end] + "\n\n" + new_block + "\n" + text[end:]
    sep = "" if text.endswith("\n") else "\n"
    return text + sep + "\n" + new_block + "\n"
