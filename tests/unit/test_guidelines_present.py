"""Guard: as skills clínicas devem nomear os guidelines de reporting atuais.

Conteúdo de skill é prose; este teste impede que uma edição futura derrube
silenciosamente TRIPOD-LLM / DECIDE-AI / CONSORT 2025.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from par.core.paths import resolve_resource

_SKILLS = Path(__file__).resolve().parents[2] / "skills"


def _read(rel: str) -> str:
    return (_SKILLS / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("guideline", ["TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025"])
def test_peer_review_names_current_guidelines(guideline: str) -> None:
    assert guideline in _read("review/modes/critique.md")


def test_peer_review_reference_card_exists_and_covers_all() -> None:
    card = _read("review/references/reporting-guidelines.md")
    for g in ("TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025", "TRIPOD+AI", "CLAIM", "STROBE"):
        assert g in card


def test_write_statistics_mentions_tripod_llm_and_consort2025() -> None:
    text = _read("protocol/modes/sap.md")
    assert "TRIPOD-LLM" in text
    assert "CONSORT 2025" in text


def test_templates_de_escrita_apontam_a_bibliografia_do_escopo() -> None:
    esperado = "bibliography: ../../../references/_references.bib"
    for rel in (
        "write/templates/manuscript.md",
        "write/templates/section.md",
        "protocol/templates/sap.md",
        "protocol/templates/cep.md",
    ):
        texto = (resolve_resource("skills") / rel).read_text(encoding="utf-8")
        assert esperado in texto, rel


def test_nenhuma_skill_cita_o_caminho_antigo() -> None:
    for skill in (resolve_resource("skills")).rglob("*.md"):
        texto = skill.read_text(encoding="utf-8")
        assert "references/notes/" not in texto, skill.name
        assert "docs/wiki/findings" not in texto, skill.name


# Taxonomia plana pré-ADR-0022/0023: `docs/{concepts,entities,findings,sources}/`
# como diretórios de primeiro nível. Toda página virou nota de
# `docs/studies/<escopo>/notes/`, distinguida pelo `type:` do frontmatter.
# São dois padrões porque a mesma pasta aparece em três formas: com o prefixo
# (`docs/concepts/`), na forma de chaves do glob (`docs/{concepts,entities}/`) e
# sem prefixo nenhum nos templates do `pj_base`, que já moram em `docs/`
# (``[`concepts/`](concepts/)``) ou num wikilink (`[[concepts/curvas-roc]]`).
_TAXONOMIA_PLANA = (
    re.compile(r"docs/\{?[\w,]*\b(concepts|entities|findings|sources)\b"),
    re.compile(r"\b(concepts|entities|findings|sources)/"),
)


def _sem_taxonomia_plana(raiz: Path, docs: list[Path]) -> None:
    for doc in docs:
        texto = doc.read_text(encoding="utf-8")
        for padrao in _TAXONOMIA_PLANA:
            achado = padrao.search(texto)
            assert not achado, f"{doc.relative_to(raiz).as_posix()}: {achado.group(0)!r}"


def test_nenhuma_skill_cita_a_taxonomia_plana() -> None:
    raiz = resolve_resource("skills")
    _sem_taxonomia_plana(raiz, sorted(raiz.rglob("*.md")))


def test_pj_base_nao_promete_pasta_de_taxonomia_plana() -> None:
    raiz = resolve_resource("templates") / "pj_base"
    _sem_taxonomia_plana(raiz, sorted(raiz.rglob("*.md")))
