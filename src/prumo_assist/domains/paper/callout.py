"""Render do callout estruturado escrito pelo modo ``paper extract``.

Migrado de ``paper_extract.py``. **Importante:** este módulo NÃO chama LLM.
Ele só:

- Parseia o template ``.claude/paper_extraction.md`` em seções.
- Renderiza um callout Markdown delimitado a partir de ``dict[seção, texto]``.
- Escreve o callout em ``references/notes/<key>/_extract.md`` (arquivo dedicado,
  layout α) e atualiza ``extracted_*`` no ``_meta.md``.

A extração propriamente dita (PDF → ``dict[seção, texto]``) acontece na skill,
executada pelo agent-host. Esse módulo é a "metade Python" do contrato.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from prumo_assist.core.provenance import build_meta, hash_input
from prumo_assist.domains.paper.errors import PaperError
from prumo_assist.domains.paper.schemas.v1 import Locator, PaperCallout
from prumo_assist.domains.paper.sync import FRONTMATTER_RE, read_nota_yaml, write_nota

EXTRACT_BEGIN = "<!-- paper-extract:begin -->"
EXTRACT_END = "<!-- paper-extract:end -->"


@dataclass(frozen=True)
class ExtractionSection:
    """Uma seção parseada do ``paper_extraction.md`` template."""

    name: str
    instruction: str  # texto dentro de <!-- ... --> após o header


def parse_extraction_template(text: str) -> list[ExtractionSection]:
    """Parseia ``paper_extraction.md`` em lista ordenada de seções."""
    sections: list[ExtractionSection] = []
    parts = re.split(r"(?m)^### (.+)$", text)
    # parts[0] = topo; depois alternam (nome, corpo, nome, corpo, ...)
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        raw = parts[i + 1] if i + 1 < len(parts) else ""
        instruction = _extract_instruction(raw)
        sections.append(ExtractionSection(name=name, instruction=instruction))
    return sections


def _extract_instruction(raw: str) -> str:
    """Pega o texto dentro de ``<!-- ... -->`` que vier logo após um header."""
    m = re.search(r"<!--(.*?)-->", raw, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_extract_payload(raw: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separa ``(seções, locators)`` do JSON que o agente manda ao ``prumo paper extract``.

    Aceita as duas formas: a legada, plana (``{"TL;DR": "..."}``), e a estruturada
    (``{"sections": {...}, "locators": {...}}``). A validação de tipos acontece em
    :func:`apply_extraction`, por ``PaperCallout``.
    """
    if isinstance(raw.get("sections"), dict):
        locators = raw.get("locators")
        return dict(raw["sections"]), dict(locators) if isinstance(locators, dict) else {}
    return dict(raw), {}


def _format_locator(loc: Locator) -> str:
    return f'p. {loc.page} — "{loc.quote}"' if loc.page else f'"{loc.quote}"'


def render_callout(
    sections: list[ExtractionSection],
    content: Mapping[str, str],
    model: str,
    date: str,
    locators: Mapping[str, Sequence[Locator]] | None = None,
) -> str:
    """Renderiza o callout Markdown com 1 subsection por seção.

    Locators, quando houver, saem numa linha ``**Onde:**`` ao fim da seção; extract
    sem locators renderiza igual ao de antes (idempotência preservada).
    """
    lines = [
        EXTRACT_BEGIN,
        "> [!note]- Auto-extraído do PDF (revisar antes de confiar)",
        f"> **Gerado em:** {date} · **Modelo:** {model}",
        ">",
    ]
    for sec in sections:
        body = content.get(sec.name, "").strip() or "_(pendente)_"
        lines.append(f"> ### {sec.name}")
        for ln in body.splitlines():
            lines.append(f"> {ln}" if ln else ">")
        locs = (locators or {}).get(sec.name) or []
        if locs:
            lines.append(">")
            lines.append("> **Onde:** " + "; ".join(_format_locator(loc) for loc in locs))
        lines.append(">")
    while lines and lines[-1] == ">":
        lines.pop()
    lines.append(EXTRACT_END)
    return "\n".join(lines)


def hash_template(path: Path) -> str:
    """sha256[:12] do conteúdo do template — pra detectar staleness do callout."""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h[:12]


def _validation_summary(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:3]
    )


def _validated_callout(
    *,
    citekey: str,
    sections: list[ExtractionSection],
    template_path: Path,
    content: Mapping[str, Any],
    locators: Mapping[str, Any],
    model: str,
    date: str,
) -> PaperCallout:
    """Fail-closed: seção fora do template ou tipo errado não chega ao disco."""
    names = [s.name for s in sections]
    unknown = sorted({k for k in (*content, *locators) if k not in names})
    if unknown:
        raise PaperError(
            f"seção(ões) fora do template .claude/paper_extraction.md: {', '.join(unknown)}. "
            f"Seções esperadas: {', '.join(names)}. Corrija as chaves do JSON e rode "
            "`prumo paper extract` de novo."
        )
    try:
        return PaperCallout(
            citekey=citekey,
            sections=dict(content),
            model=model,
            extracted_at=date,
            template_hash=hash_template(template_path),
            locators=dict(locators),
        )
    except ValidationError as exc:
        raise PaperError(
            f"extract de {citekey} não valida contra PaperCallout/v1 ({_validation_summary(exc)}). "
            "Corrija o JSON — seção → texto; locators → lista de {page, quote} — e rode "
            "`prumo paper extract` de novo."
        ) from exc


def _provenance(callout: PaperCallout) -> dict[str, Any]:
    """Bloco ``_meta`` do extract (Princípio V), sem ``human_reviewed``.

    A flag de revisão é do humano, no frontmatter do ``_meta.md``; carimbá-la aqui
    com ``False`` a sombrearia na declaração de uso de IA.
    """
    payload = json.dumps(
        {
            "sections": callout.sections,
            "locators": {k: [loc.model_dump() for loc in v] for k, v in callout.locators.items()},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    meta = build_meta(
        schema="PaperCallout/v1",
        skill="paper/extract",
        model=callout.model,
        input_hash=hash_input(payload),
    ).to_dict()
    meta.pop("human_reviewed", None)
    return meta


def apply_extraction(
    pj_path: Path,
    citekey: str,
    template_path: Path,
    content: Mapping[str, Any],
    model: str,
    date: str,
    locators: Mapping[str, Any] | None = None,
) -> bool:
    """Aplica extração: renderiza callout em ``_extract.md``, atualiza YAML do ``_meta.md``.

    Valida o conteúdo por ``PaperCallout/v1`` antes de escrever (levanta ``PaperError``).
    Retorna ``True`` se algum dos dois arquivos mudou; ``False`` se conteúdo idêntico.
    Só atualiza ``extracted_*`` e o ``_meta`` de proveniência quando o callout muda.
    """
    from prumo_assist.core.note_paths import extract_path, meta_path

    sections = parse_extraction_template(template_path.read_text())
    callout = _validated_callout(
        citekey=citekey,
        sections=sections,
        template_path=template_path,
        content=content,
        locators=locators or {},
        model=model,
        date=date,
    )
    new_callout = render_callout(sections, callout.sections, model, date, callout.locators)

    extract_file = extract_path(pj_path, citekey)
    extract_file.parent.mkdir(parents=True, exist_ok=True)

    new_extract_text = _compose_extract_file(citekey, new_callout, date)

    if extract_file.exists():
        existing = extract_file.read_text()
        if _extract_body_equal(existing, new_extract_text):
            return False
    extract_file.write_text(new_extract_text)

    # Update extracted_* fields in _meta.md (if it exists)
    meta_file = meta_path(pj_path, citekey)
    if meta_file.exists():
        yaml_dict = read_nota_yaml(meta_file)
        text = meta_file.read_text()
        m = FRONTMATTER_RE.match(text)
        body = text[m.end() :] if m else text
        yaml_dict["extracted_at"] = date
        yaml_dict["extracted_model"] = model
        yaml_dict["extracted_template_hash"] = callout.template_hash
        yaml_dict["_meta"] = _provenance(callout)
        write_nota(meta_file, yaml_dict, body)
    return True


def _compose_extract_file(citekey: str, callout: str, date: str) -> str:
    """Monta o conteúdo de _extract.md: YAML mínimo + callout."""
    fm = f"---\npaper: {citekey}\nsource: prumo-paper-extract\ngenerated_at: '{date}'\n---\n\n"
    return fm + callout + "\n"


def _extract_body_equal(a: str, b: str) -> bool:
    """Compara dois _extract.md ignorando linhas voláteis (`generated_at`, `Gerado em`)."""

    def strip_volatile(s: str) -> str:
        s = re.sub(r"^generated_at:.*\n", "", s, flags=re.MULTILINE)
        s = re.sub(r"> \*\*Gerado em:\*\*[^\n]*\n", "", s)
        return s

    return strip_volatile(a) == strip_volatile(b)
