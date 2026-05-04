"""Render do callout estruturado escrito pela skill ``paper-extract``.

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
import re
from dataclasses import dataclass
from pathlib import Path

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


def hash_template(path: Path) -> str:
    """sha256[:12] do conteúdo do template — pra detectar staleness do callout."""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h[:12]


def apply_extraction(
    pj_path: Path,
    citekey: str,
    template_path: Path,
    content: dict[str, str],
    model: str,
    date: str,
) -> bool:
    """Aplica extração: renderiza callout em ``_extract.md``, atualiza YAML do ``_meta.md``.

    Retorna ``True`` se algum dos dois arquivos mudou; ``False`` se conteúdo idêntico.
    Só atualiza ``extracted_at`` no `_meta.md` quando o callout efetivamente muda.
    """
    from prumo_assist.core.note_paths import extract_path, meta_path

    sections = parse_extraction_template(template_path.read_text())
    new_callout = render_callout(sections, content, model, date)

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
        yaml_dict["extracted_template_hash"] = hash_template(template_path)
        write_nota(meta_file, yaml_dict, body)
    return True


def _compose_extract_file(citekey: str, callout: str, date: str) -> str:
    """Monta o conteúdo de _extract.md: YAML mínimo + callout."""
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"source: prumo-paper-extract\n"
        f"generated_at: '{date}'\n"
        f"---\n\n"
    )
    return fm + callout + "\n"


def _extract_body_equal(a: str, b: str) -> bool:
    """Compara dois _extract.md ignorando linhas voláteis (`generated_at`, `Gerado em`)."""

    def strip_volatile(s: str) -> str:
        s = re.sub(r"^generated_at:.*\n", "", s, flags=re.MULTILINE)
        s = re.sub(r"> \*\*Gerado em:\*\*[^\n]*\n", "", s)
        return s

    return strip_volatile(a) == strip_volatile(b)
