"""Testes dos perfis de declaração de uso de IA por periódico."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import PrumoError
from prumo_assist.domains.write.disclosure import generate_disclosure, load_venue_profiles


def _project(tmp_path: Path) -> Path:
    for slug, day in (("a", "2026-05-01"), ("b", "2026-06-15")):
        p = tmp_path / "docs/references/papers" / slug / "_meta.md"
        p.parent.mkdir(parents=True)
        p.write_text(
            f"---\nextracted_model: claude-opus-4\nextracted_at: {day}\n---\n", encoding="utf-8"
        )
    return tmp_path


def test_perfis_empacotados_tem_fonte_e_data() -> None:
    profiles = load_venue_profiles()
    assert set(profiles) == {"icmje", "jama", "bmj"}
    for prof in profiles.values():
        assert prof.source_url.startswith("https://")
        assert prof.accessed == "2026-09-12"


def test_icmje(tmp_path: Path) -> None:
    disc = generate_disclosure(root=_project(tmp_path), venue="ICMJE")
    assert disc.venue is not None and disc.venue.key == "icmje"
    en = disc.statement_en
    assert "claude-opus-4" in en and "responsibility" in en
    assert "Complete before submitting: prompts used, where applicable." in en
    assert en.endswith(
        "Placement (ICMJE Recommendations): cover letter / Acknowledgments / Methods."
    )
    assert en.count("Placement") == 1


def test_jama(tmp_path: Path) -> None:
    disc = generate_disclosure(root=_project(tmp_path), venue="jama")
    en = disc.statement_en
    assert "between 2026-05-01 and 2026-06-15." in en
    assert "tool manufacturer" in en
    assert en.endswith("Placement (JAMA): Methods / Acknowledgments.")
    assert "Local (JAMA): Métodos / Agradecimentos." in disc.statement_pt
    assert "entre 2026-05-01 e 2026-06-15." in disc.statement_pt


def test_bmj(tmp_path: Path) -> None:
    disc = generate_disclosure(root=_project(tmp_path), venue="bmj")
    en = disc.statement_en
    assert "between" not in en
    assert "why the tool was used" in en
    assert en.endswith("Placement (BMJ): contributorship statement / Methods.")
    assert disc.venue is not None and "author" in disc.venue.authorship


def test_venue_desconhecido_mantem_generico_e_pede_conferir(tmp_path: Path) -> None:
    root = _project(tmp_path)
    generic = generate_disclosure(root=root)
    disc = generate_disclosure(root=root, venue="periodico_x")
    assert disc.venue is None
    first, line = disc.statement_en.split("\n\n")
    assert first == generic.statement_en
    assert line.startswith("No prumo profile for 'periodico_x' (profiles: bmj, icmje, jama)")
    assert "política de IA do periódico" in disc.statement_pt


def test_sem_venue_saida_identica_a_de_hoje(tmp_path: Path) -> None:
    disc = generate_disclosure(root=_project(tmp_path))
    assert disc.venue is None
    assert "\n" not in disc.statement_en


@pytest.mark.parametrize("missing", ["source_url", "accessed"])
def test_perfil_sem_fonte_ou_data_falha(missing: str) -> None:
    lines = {
        "name": 'name = "X"',
        "source_url": 'source_url = "https://x.org"',
        "accessed": 'accessed = "2026-09-12"',
        "required": 'required = ["tool"]',
        "placement": 'placement = ["methods"]',
        "authorship": 'authorship = "no"',
    }
    del lines[missing]
    body = "\n".join(lines.values())
    with pytest.raises(PrumoError, match="source_url e accessed"):
        load_venue_profiles(f"[venues.x]\n{body}\n")


def test_elemento_desconhecido_falha() -> None:
    text = (
        '[venues.x]\nname = "X"\nsource_url = "https://x.org"\naccessed = "2026-09-12"\n'
        'required = ["horoscope"]\nplacement = ["methods"]\nauthorship = "no"\n'
    )
    with pytest.raises(PrumoError, match="horoscope"):
        load_venue_profiles(text)


def test_cli_venue(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from prumo_assist.domains.write.cli import write_app

    result = CliRunner().invoke(
        write_app, ["disclosure", str(_project(tmp_path)), "--venue", "jama"]
    )
    assert result.exit_code == 0
    assert "Placement (JAMA)" in result.stdout
