"""Renderiza ``PicotSpec`` em blocos Markdown delimitados pros 3 destinos.

Bloco padrão::

    <!-- picot:begin v=N hash=sha8 -->
    ... conteúdo ...
    <!-- picot:end -->

``v`` e ``hash`` permitem detectar drift sem reabrir o TOML canônico.
"""

from __future__ import annotations

import re

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

PICOT_BEGIN_PREFIX = "<!-- picot:begin "
PICOT_END = "<!-- picot:end -->"

BLOCK_BEGIN_RE = re.compile(
    r"<!--\s*picot:begin\s+v=(?P<version>\d+)\s+hash=(?P<hash>[a-f0-9]{8})\s*-->",
)
BLOCK_FULL_RE = re.compile(
    r"<!--\s*picot:begin\s+v=\d+\s+hash=[a-f0-9]{8}\s*-->.*?<!--\s*picot:end\s*-->",
    flags=re.DOTALL,
)


def render_protocol_block(spec: PicotSpec, *, hash8: str) -> str:
    """Render operacional pra ``docs/protocol.md`` (concreto, conferível)."""
    header = f"{PICOT_BEGIN_PREFIX}v={spec.version} hash={hash8} -->"
    lines = [header, ""]
    if spec.type == "clinical":
        lines += [
            f"**População operacional.** {spec.population}",
            "",
            f"**Intervenção (sob teste).** {spec.intervention}",
            "",
            f"**Comparação (baseline).** {spec.comparison}",
            "",
            f"**Desfecho primário.** {spec.outcome}",
            "",
            f"**Janela temporal.** {spec.time}",
            "",
        ]
    else:
        lines += [
            f"**Contribuição.** {spec.contribution}",
            "",
            f"**Condição de validade.** {spec.hypothesis_validity_condition}",
            "",
        ]
    lines += [
        f"**Hipótese formal.** {spec.hypothesis.statement}",
        "",
        f"*Métricas: {', '.join(spec.hypothesis.metrics)}.*",
        "",
        PICOT_END,
    ]
    return "\n".join(lines)


def render_project_block(spec: PicotSpec, *, hash8: str) -> str:
    """Render acadêmico pra ``docs/project.md`` (prosa formal)."""
    header = f"{PICOT_BEGIN_PREFIX}v={spec.version} hash={hash8} -->"
    lines = [header, "", "## Pergunta de pesquisa", ""]
    if spec.type == "clinical":
        lines.append(
            f"Em **{spec.population}**, a aplicação de **{spec.intervention}** comparada a "
            f"**{spec.comparison}** produz **{spec.outcome}**, no horizonte de **{spec.time}**?"
        )
    else:
        lines += [
            f"**Contribuição teórica:** {spec.contribution}.",
            "",
            f"**Condição de validade:** {spec.hypothesis_validity_condition}.",
        ]
    lines += [
        "",
        "## Hipótese central",
        "",
        spec.hypothesis.statement + ".",
        "",
        spec.hypothesis.rationale,
        "",
        PICOT_END,
    ]
    return "\n".join(lines)


def replace_or_insert_block(text: str, new_block: str, *, anchor_pattern: str) -> str:
    """Substitui bloco existente; se ausente, insere logo após ``anchor_pattern``.

    ``anchor_pattern`` é regex multiline (ex.: ``r'^## Contexto.*$'``). Se nenhum
    bloco picot existir e o anchor não casar, append no final.
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
