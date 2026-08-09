"""Guard: as skills clínicas devem nomear os guidelines de reporting atuais.

Conteúdo de skill é prose; este teste impede que uma edição futura derrube
silenciosamente TRIPOD-LLM / DECIDE-AI / CONSORT 2025.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core.paths import resolve_resource

_SKILLS = Path(__file__).resolve().parents[2] / "skills"


def _read(rel: str) -> str:
    return (_SKILLS / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("guideline", ["TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025"])
def test_peer_review_names_current_guidelines(guideline: str) -> None:
    assert guideline in _read("peer-review/SKILL.md")


def test_peer_review_reference_card_exists_and_covers_all() -> None:
    card = _read("peer-review/references/reporting-guidelines.md")
    for g in ("TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025", "TRIPOD+AI", "CLAIM", "STROBE"):
        assert g in card


def test_write_statistics_mentions_tripod_llm_and_consort2025() -> None:
    text = _read("write-statistics/SKILL.md")
    assert "TRIPOD-LLM" in text
    assert "CONSORT 2025" in text


def test_templates_de_escrita_apontam_a_bibliografia_do_escopo() -> None:
    esperado = "bibliography: ../../../references/_references.bib"
    for nome in ("write-paper", "write-scientific", "write-statistics", "write-projeto-cep"):
        texto = (resolve_resource("skills") / nome / "template.md").read_text(encoding="utf-8")
        assert esperado in texto, nome


def test_nenhuma_skill_cita_o_caminho_antigo() -> None:
    for skill in (resolve_resource("skills")).glob("*/SKILL.md"):
        texto = skill.read_text(encoding="utf-8")
        assert "references/notes/" not in texto, skill.name
        assert "docs/wiki/findings" not in texto, skill.name
