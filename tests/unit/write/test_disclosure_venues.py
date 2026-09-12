"""Testes dos perfis de declaração de uso de IA por periódico."""

from __future__ import annotations

from pathlib import Path

import pytest

from par import PrumoError
from par.domains.write.disclosure import generate_disclosure, load_venue_profiles


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


@pytest.mark.parametrize(
    ("venue", "key", "present", "absent", "placement"),
    [
        (
            "ICMJE",
            "icmje",
            [
                "claude-opus-4",
                "responsibility",
                "Complete before submitting: prompts used, where applicable.",
            ],
            ["between"],
            "Placement (ICMJE Recommendations): cover letter / Acknowledgments / Methods.",
        ),
        (
            "jama",
            "jama",
            ["between 2026-05-01 and 2026-06-15.", "tool manufacturer"],
            [],
            "Placement (JAMA): Methods / Acknowledgments.",
        ),
        (
            "bmj",
            "bmj",
            ["why the tool was used"],
            ["between"],
            "Placement (BMJ): contributorship statement / Methods.",
        ),
    ],
)
def test_perfil_de_periodico(
    tmp_path: Path,
    venue: str,
    key: str,
    present: list[str],
    absent: list[str],
    placement: str,
) -> None:
    disc = generate_disclosure(root=_project(tmp_path), venue=venue)
    assert disc.venue is not None and disc.venue.key == key
    en = disc.statement_en
    for text in present:
        assert text in en
    for text in absent:
        assert text not in en
    assert en.endswith(placement)
    assert en.count("Placement") == 1


def test_jama_em_portugues(tmp_path: Path) -> None:
    pt = generate_disclosure(root=_project(tmp_path), venue="jama").statement_pt
    assert "Local (JAMA): Métodos / Agradecimentos." in pt
    assert "entre 2026-05-01 e 2026-06-15." in pt


def test_bmj_exige_autoria_humana(tmp_path: Path) -> None:
    disc = generate_disclosure(root=_project(tmp_path), venue="bmj")
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


_VALID_PROFILE = {
    "name": '"X"',
    "source_url": '"https://x.org"',
    "accessed": '"2026-09-12"',
    "required": '["tool"]',
    "placement": '["methods"]',
    "authorship": '"no"',
}


def _profile_toml(**overrides: str | None) -> str:
    fields = {**_VALID_PROFILE, **overrides}
    body = "\n".join(f"{k} = {v}" for k, v in fields.items() if v is not None)
    return f"[venues.x]\n{body}\n"


def test_perfil_valido_carrega() -> None:
    assert set(load_venue_profiles(_profile_toml())) == {"x"}


@pytest.mark.parametrize("missing", ["source_url", "accessed"])
def test_perfil_sem_fonte_ou_data_falha(missing: str) -> None:
    with pytest.raises(PrumoError, match="source_url e accessed"):
        load_venue_profiles(_profile_toml(**{missing: None}))


@pytest.mark.parametrize(
    ("field", "value"), [("required", '["horoscope"]'), ("placement", '["horoscope"]')]
)
def test_chave_desconhecida_falha(field: str, value: str) -> None:
    with pytest.raises(PrumoError, match="horoscope"):
        load_venue_profiles(_profile_toml(**{field: value}))


def test_cli_venue(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from par.domains.write.cli import write_app

    result = CliRunner().invoke(
        write_app, ["disclosure", str(_project(tmp_path)), "--venue", "jama"]
    )
    assert result.exit_code == 0
    assert "Placement (JAMA)" in result.stdout
