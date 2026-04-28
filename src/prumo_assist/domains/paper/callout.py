"""Render e parse do callout estruturado escrito pela skill ``paper-extract``.

Migrado de ``paper_extract.py``. **Importante:** este módulo NÃO chama LLM.
Ele só:

- Parseia o template ``.claude/paper_extraction.md`` em seções.
- Renderiza um callout Markdown delimitado a partir de ``dict[seção, texto]``.
- Insere/atualiza o callout dentro de uma nota existente preservando o body.

A extração propriamente dita (PDF → ``dict[seção, texto]``) acontece na skill,
executada pelo agent-host. Esse módulo é a "metade Python" do contrato.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from prumo_assist.domains.paper.sync import FRONTMATTER_RE, read_nota_yaml, write_nota

EXTRACT_BEGIN = "<!-- paper-extract:begin -->"
EXTRACT_END = "<!-- paper-extract:end -->"
CALLOUT_RE = re.compile(
    rf"{re.escape(EXTRACT_BEGIN)}.*?{re.escape(EXTRACT_END)}",
    flags=re.DOTALL,
)


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


def render_callout(
    sections: list[ExtractionSection],
    content: dict[str, str],
    model: str,
    date: str,
) -> str:
    """Renderiza o callout Markdown com 1 subsection por seção."""
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
        lines.append(">")
    while lines and lines[-1] == ">":
        lines.pop()
    lines.append(EXTRACT_END)
    return "\n".join(lines)


def read_callout(text: str) -> str | None:
    """Retorna o bloco do callout (BEGIN..END) ou ``None`` se ausente."""
    m = CALLOUT_RE.search(text)
    return m.group(0) if m else None


def write_callout(text: str, new_callout: str) -> str:
    """Substitui o bloco existente ou insere logo após o frontmatter."""
    if CALLOUT_RE.search(text):
        return CALLOUT_RE.sub(new_callout, text, count=1)
    fm = FRONTMATTER_RE.match(text)
    if fm:
        head = text[: fm.end()]
        tail = text[fm.end() :]
        return f"{head}\n{new_callout}\n{tail}"
    return f"{new_callout}\n\n{text}"


def hash_template(path: Path) -> str:
    """sha256[:12] do conteúdo do template — pra detectar staleness do callout."""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h[:12]


def apply_extraction(
    nota_path: Path,
    template_path: Path,
    content: dict[str, str],
    model: str,
    date: str,
) -> bool:
    """Aplica extração: renderiza callout, escreve na nota, atualiza YAML.

    Retorna ``True`` se o arquivo de fato mudou, ``False`` se conteúdo idêntico.
    Só atualiza ``extracted_at`` quando o conteúdo do callout efetivamente muda.
    """
    sections = parse_extraction_template(template_path.read_text())
    new_callout = render_callout(sections, content, model, date)

    text = nota_path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{nota_path} sem frontmatter.")
    body = text[m.end() :]

    old_callout = read_callout(body)
    if old_callout is not None and _callout_body_equal(old_callout, new_callout):
        return False

    new_body = write_callout(body, new_callout)
    yaml_dict = read_nota_yaml(nota_path)
    yaml_dict["extracted_at"] = date
    yaml_dict["extracted_model"] = model
    yaml_dict["extracted_template_hash"] = hash_template(template_path)
    write_nota(nota_path, yaml_dict, new_body)
    return True


def _callout_body_equal(a: str, b: str) -> bool:
    """Compara 2 callouts ignorando linha ``> **Gerado em:** ...`` (metadata).

    Justificativa: callout só deve ser considerado "mudou" se conteúdo
    estrutural (seções) diferir — não se só a data do metadata mudou.
    """

    def strip_generated(s: str) -> str:
        return re.sub(r"> \*\*Gerado em:\*\*[^\n]*\n", "", s)

    return strip_generated(a) == strip_generated(b)
