"""``extract_prep`` — valida pré-requisitos de extração + lê config, num só passo.

Absorve o snippet inline ``load_project_config`` e os aborts de pré-requisito
que viviam na prosa de ``paper-extract`` (spec Fase A: comando *prep* compõe
validação + leitura de contexto). Tudo determinístico (checagem de path + config).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.config import load_project_config


@dataclass(frozen=True)
class ExtractPrep:
    """Contexto pronto pra extração: idioma + caminhos validados."""

    language: str
    template_path: Path
    pdf_path: Path
    meta_path: Path


def extract_prep(pj_path: Path, citekey: str) -> ExtractPrep:
    """Valida os pré-requisitos de extração de ``citekey`` e devolve idioma + caminhos.

    Levanta ``FileNotFoundError`` (pré-req ausente, com comando de correção) ou
    ``ConfigError`` (``paper_extract.language`` inválido).
    """
    template_path = pj_path / ".claude" / "paper_extraction.md"
    bib_path = pj_path / "references" / "_references.bib"
    pdf_path = pj_path / "references" / "pdfs" / f"{citekey}.pdf"
    meta_path = pj_path / "references" / "notes" / citekey / "_meta.md"

    checks: list[tuple[str, Path, str]] = [
        ("template .claude/paper_extraction.md", template_path, "rode o scaffold do pj_*"),
        ("references/_references.bib", bib_path, "exporte pelo BBT"),
        (f"PDF references/pdfs/{citekey}.pdf", pdf_path, "rode `make sync-pdfs`"),
        (f"_meta.md de {citekey}", meta_path, "rode `prumo paper sync`"),
    ]
    # `.exists()` é False para symlink quebrado — intencional: as dicas de
    # correção (ex.: `make sync-pdfs`) recriam o link, então tratamos como ausente.
    for label, p, fix in checks:
        if not p.exists():
            raise FileNotFoundError(f"pré-requisito ausente: {label} ({p}); {fix}.")

    config = load_project_config(pj_path)  # valida paper_extract.language
    language = str(config["paper_extract"]["language"])
    return ExtractPrep(
        language=language, template_path=template_path, pdf_path=pdf_path, meta_path=meta_path
    )
