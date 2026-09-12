"""Tests pro parser de SKILL.md e o registry de descoberta."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from par import ManifestError
from par.core.skills import (
    SkillRef,
    load_modes,
    load_skill_registry,
    parse_skill_file,
    stale_guideline_warnings,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_minimal_skill(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: A demo skill.\n---\n\nBody here.\n",
    )
    m = parse_skill_file(skill)
    assert m.name == "demo"
    assert m.description == "A demo skill."
    assert m.version == "0.0.0"
    assert m.determinism == "agentic"
    assert m.body.startswith("Body here.")


def test_parses_full_prumo_block(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "extract" / "SKILL.md",
        (
            "---\n"
            "name: paper-extract\n"
            "description: Extract.\n"
            "prumo:\n"
            "  version: 1.2.0\n"
            "  schema: PaperCallout/v1\n"
            "  determinism: agentic\n"
            "  agent_compat: [claude-code, cursor]\n"
            "  cost_estimate: ~4k tokens\n"
            "  inputs:\n"
            "    citekey: required\n"
            "  custom_field: kept\n"
            "---\n"
            "Prompt body.\n"
        ),
    )
    m = parse_skill_file(skill)
    assert m.version == "1.2.0"
    assert m.schema == "PaperCallout/v1"
    assert m.agent_compat == ("claude-code", "cursor")
    assert m.cost_estimate == "~4k tokens"
    assert m.inputs == {"citekey": "required"}
    assert m.extra == {"custom_field": "kept"}


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "no frontmatter here\n")
    with pytest.raises(ManifestError, match="frontmatter YAML ausente"):
        parse_skill_file(skill)


def test_missing_name_raises(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "---\ndescription: x\n---\nbody\n")
    with pytest.raises(ManifestError, match="'name' obrigatório"):
        parse_skill_file(skill)


def test_invalid_determinism_raises(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "x" / "SKILL.md",
        "---\nname: x\ndescription: y\nprumo:\n  determinism: magical\n---\nbody\n",
    )
    with pytest.raises(ManifestError, match="determinism="):
        parse_skill_file(skill)


def test_registry_indexes_by_name(tmp_path: Path) -> None:
    _write(
        tmp_path / "alpha" / "SKILL.md",
        "---\nname: alpha\ndescription: A\n---\nbody\n",
    )
    _write(
        tmp_path / "beta" / "SKILL.md",
        "---\nname: beta\ndescription: B\n---\nbody\n",
    )
    reg, _ = load_skill_registry(tmp_path)
    assert reg.names() == ["alpha", "beta"]
    assert reg.get("alpha").description == "A"


def test_registry_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    _write(
        tmp_path / "real" / "SKILL.md",
        "---\nname: real\ndescription: r\n---\nbody\n",
    )
    (tmp_path / "empty").mkdir()
    reg, _ = load_skill_registry(tmp_path)
    assert reg.names() == ["real"]


def test_registry_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    reg, _ = load_skill_registry(tmp_path / "absent")
    assert reg.names() == []


def test_registry_rejects_duplicate_names(tmp_path: Path) -> None:
    _write(
        tmp_path / "a" / "SKILL.md",
        "---\nname: dup\ndescription: A\n---\nbody\n",
    )
    _write(
        tmp_path / "b" / "SKILL.md",
        "---\nname: dup\ndescription: B\n---\nbody\n",
    )
    with pytest.raises(ManifestError, match="duplicada"):
        load_skill_registry(tmp_path)


def test_registry_tolerant_mode_skips_malformed(tmp_path: Path) -> None:
    _write(
        tmp_path / "good" / "SKILL.md",
        "---\nname: good\ndescription: ok\n---\nbody\n",
    )
    # Frontmatter quebrado: tabs em vez de espaços + colon em valor unquoted
    _write(
        tmp_path / "bad" / "SKILL.md",
        "---\n: invalid yaml\n---\nbody\n",
    )
    reg, warnings = load_skill_registry(tmp_path, strict=False)
    assert reg.names() == ["good"]
    assert len(warnings) == 1


def test_registry_strict_mode_aborts_on_malformed(tmp_path: Path) -> None:
    _write(tmp_path / "bad" / "SKILL.md", "---\n: invalid\n---\nbody\n")
    with pytest.raises(ManifestError):
        load_skill_registry(tmp_path, strict=True)


def test_parses_guidelines_reviewed(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "pr" / "SKILL.md",
        '---\nname: pr\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-05-30"\n---\nbody\n',
    )
    m = parse_skill_file(skill)
    assert m.guidelines_reviewed == "2026-05-30"


def test_guidelines_reviewed_defaults_none(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "---\nname: x\ndescription: d\n---\nbody\n")
    assert parse_skill_file(skill).guidelines_reviewed is None


def test_guidelines_reviewed_not_in_extra(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "x" / "SKILL.md",
        '---\nname: x\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-01-01"\n---\nbody\n',
    )
    assert "guidelines_reviewed" not in parse_skill_file(skill).extra


def test_stale_guideline_warnings_flags_old(tmp_path: Path) -> None:
    from datetime import date

    from par.core.skills import stale_guideline_warnings

    _write(
        tmp_path / "old" / "SKILL.md",
        '---\nname: old\ndescription: d\nprumo:\n  guidelines_reviewed: "2025-12-01"\n---\nb\n',
    )
    _write(
        tmp_path / "fresh" / "SKILL.md",
        '---\nname: fresh\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-05-30"\n---\nb\n',
    )
    _write(tmp_path / "nodate" / "SKILL.md", "---\nname: nodate\ndescription: d\n---\nb\n")
    reg, _ = load_skill_registry(tmp_path)
    warns = stale_guideline_warnings(reg, today=date(2026, 6, 1), max_age_days=180)
    joined = " ".join(warns)
    assert "old" in joined
    assert "fresh" not in joined
    assert "nodate" not in joined


def test_stale_guideline_warnings_flags_malformed_date(tmp_path: Path) -> None:
    from datetime import date

    from par.core.skills import stale_guideline_warnings

    _write(
        tmp_path / "bad" / "SKILL.md",
        '---\nname: bad\ndescription: d\nprumo:\n  guidelines_reviewed: "not-a-date"\n---\nb\n',
    )
    reg, _ = load_skill_registry(tmp_path)
    warns = stale_guideline_warnings(reg, today=date(2026, 6, 1))
    assert any("bad" in w and "inválid" in w for w in warns)


def test_requires_lista_canonica(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: [cli, qmd]\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ("cli", "qmd")


def test_requires_string_unica(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: zotero\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ("zotero",)


def test_requires_ausente_eh_vazio(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ()


def test_requires_valor_invalido_manifest_error(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: [terminal]\n---\n\nBody.\n",
    )
    with pytest.raises(ManifestError, match="requires"):
        parse_skill_file(skill)


def test_requires_duplicata_deduplicada(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: [cli, cli, qmd]\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ("cli", "qmd")


def test_prose_defaults_to_false(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: A demo skill.\n---\n\nBody.\n",
    )
    m = parse_skill_file(skill)
    assert m.prose is False
    assert m.locale_lock is None


def test_parses_prose_and_locale_lock(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "cep" / "SKILL.md",
        (
            "---\n"
            "name: write-projeto-cep\n"
            "description: CEP.\n"
            "prumo:\n"
            "  prose: true\n"
            "  locale_lock: pt-BR\n"
            "---\n\nBody.\n"
        ),
    )
    m = parse_skill_file(skill)
    assert m.prose is True
    assert m.locale_lock == "pt-BR"
    # campos conhecidos não vazam pra `extra`
    assert "prose" not in m.extra and "locale_lock" not in m.extra


def test_prose_must_be_boolean(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "bad" / "SKILL.md",
        "---\nname: bad\ndescription: X.\nprumo:\n  prose: sim\n---\n\nBody.\n",
    )
    with pytest.raises(ManifestError) as ei:
        parse_skill_file(skill)
    assert "prumo.prose" in str(ei.value)


def test_invalid_locale_lock_raises(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "bad" / "SKILL.md",
        "---\nname: bad\ndescription: X.\nprumo:\n  prose: true\n  locale_lock: en\n---\n\nBody.\n",
    )
    with pytest.raises(ManifestError) as ei:
        parse_skill_file(skill)
    assert "locale_lock" in str(ei.value)
    assert "en-US" in str(ei.value)


def test_locale_lock_without_prose_raises(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "bad" / "SKILL.md",
        "---\nname: bad\ndescription: X.\nprumo:\n  locale_lock: pt-BR\n---\n\nBody.\n",
    )
    with pytest.raises(ManifestError) as ei:
        parse_skill_file(skill)
    assert "prose: true" in str(ei.value)


# ---------------------------------------------------------------------------
# Modos (spec 2026-09-12 superfície de skills, D1/D2/D7)
# ---------------------------------------------------------------------------


def _skill_with_modes(root: Path) -> Path:
    _write(root / "paper" / "SKILL.md", "---\nname: paper\ndescription: Acervo.\n---\n\n# paper\n")
    _write(
        root / "paper" / "modes" / "extract.md",
        "---\nname: extract\ndescription: Extrai PDF.\n"
        "allowed-tools: Read Bash(prumo paper *) Agent\n"
        'argument-hint: "[citekey]"\n'
        'prumo:\n  phrases: ["resuma o paper X"]\n'
        "  legacy: [paper-extract, paper-extract-all]\n"
        "  disclosure_task: structured extraction\n"
        "  write_kind: paper\n"
        "  requires: [cli]\n---\n\n# extract\n",
    )
    _write(
        root / "paper" / "modes" / "library.md",
        '---\nname: library\ndescription: Sync.\nprumo:\n  phrases: ["sincroniza"]\n'
        "  legacy: paper-manager\n---\n\n# library\n",
    )
    return root


def test_allowed_tools_tokeniza_parenteses_com_espaco(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    m = parse_skill_file(root / "paper" / "modes" / "extract.md")
    assert m.allowed_tools == ("Read", "Bash(prumo paper *)", "Agent")
    assert m.argument_hint == "[citekey]"
    assert m.phrases == ("resuma o paper X",)
    assert m.legacy == ("paper-extract", "paper-extract-all")
    assert m.disclosure_task == "structured extraction"
    assert m.write_kind == "paper"
    assert "phrases" not in m.extra and "legacy" not in m.extra


def test_legacy_string_unica_vira_tupla(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    assert parse_skill_file(root / "paper" / "modes" / "library.md").legacy == ("paper-manager",)


def test_load_modes_ordena_e_valida_nome_igual_ao_arquivo(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    assert [m.name for m in load_modes(root / "paper")] == ["extract", "library"]
    _write(
        root / "paper" / "modes" / "bad.md",
        "---\nname: other\ndescription: x\nprumo:\n  phrases: [a]\n---\n",
    )
    with pytest.raises(ManifestError, match=r"bad\.md"):
        load_modes(root / "paper")


def test_load_modes_sem_diretorio_eh_vazio(tmp_path: Path) -> None:
    _write(tmp_path / "s" / "SKILL.md", "---\nname: s\ndescription: d\n---\n")
    assert load_modes(tmp_path / "s") == ()


def test_modo_sem_frase_eh_erro(tmp_path: Path) -> None:
    _write(tmp_path / "s" / "SKILL.md", "---\nname: s\ndescription: d\n---\n")
    _write(tmp_path / "s" / "modes" / "m.md", "---\nname: m\ndescription: d\n---\n")
    with pytest.raises(ManifestError, match="phrases"):
        load_modes(tmp_path / "s")


def test_registry_anexa_modos_e_resolve_referencias(tmp_path: Path) -> None:
    reg, _ = load_skill_registry(_skill_with_modes(tmp_path))
    assert [m.name for m in reg.get("paper").modes] == ["extract", "library"]
    ref = SkillRef("paper", "extract")
    assert ref.slug == "paper/extract"
    assert ref.invocation == "par:paper extract"
    assert reg.legacy_map()["paper-extract-all"] == ref
    for value in (
        "paper/extract",
        "par:paper extract",
        "/par:paper extract",
        "paper-extract",
        "par:paper-extract",
    ):
        assert reg.resolve(value) == ref, value
    assert reg.resolve("paper") is None
    assert reg.resolve("nada/aqui") is None
    assert reg.find_mode(ref) is not None
    assert reg.find_mode(SkillRef("wiki", "query")) is None
    assert [r.slug for r, _ in reg.iter_modes()] == ["paper/extract", "paper/library"]


def test_legacy_duplicado_entre_modos_eh_erro(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    _write(root / "wiki" / "SKILL.md", "---\nname: wiki\ndescription: w\n---\n")
    _write(
        root / "wiki" / "modes" / "query.md",
        "---\nname: query\ndescription: q\nprumo:\n  phrases: [q]\n  legacy: paper-manager\n---\n",
    )
    with pytest.raises(ManifestError, match="paper-manager"):
        load_skill_registry(root)


def test_registry_tolerante_pula_skill_com_modo_malformado(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    _write(root / "wiki" / "SKILL.md", "---\nname: wiki\ndescription: w\n---\n")
    _write(root / "wiki" / "modes" / "query.md", "---\nname: query\ndescription: q\n---\n")
    reg, warns = load_skill_registry(root, strict=False)
    assert reg.names() == ["paper"]
    assert len(warns) == 1 and "phrases" in warns[0]


def test_stale_guideline_warnings_olha_os_modos(tmp_path: Path) -> None:
    _write(tmp_path / "review" / "SKILL.md", "---\nname: review\ndescription: r\n---\n")
    _write(
        tmp_path / "review" / "modes" / "critique.md",
        "---\nname: critique\ndescription: c\nprumo:\n  phrases: [x]\n"
        '  guidelines_reviewed: "2020-01-01"\n---\n',
    )
    reg, _ = load_skill_registry(tmp_path)
    out = stale_guideline_warnings(reg, today=date(2026, 9, 12))
    assert len(out) == 1 and "review critique" in out[0]


# ---------------------------------------------------------------------------
# Subcomando ausente = sem CLI (CLI global mais antigo que o plugin, 2026-09-12)
# ---------------------------------------------------------------------------

_REPO_SKILLS = Path(__file__).resolve().parents[3] / "skills"


def _bodies_calling(subcommand: str) -> dict[str, str]:
    """Corpo (sem frontmatter) de cada skill/modo real que manda rodar ``subcommand``."""
    reg, _ = load_skill_registry(_REPO_SKILLS, strict=True)
    bodies = {name: reg.get(name).body for name in reg.names()}
    bodies |= {ref.slug: mode.body for ref, mode in reg.iter_modes()}
    return {slug: body for slug, body in bodies.items() if subcommand in body}


@pytest.mark.parametrize(
    ("subcommand", "expected"),
    [
        ("prumo validate", {"paper/support", "review/critique"}),
        ("prumo status", {"start"}),
    ],
)
def test_subcomando_recente_tem_fallback_de_subcomando_ausente(
    subcommand: str, expected: set[str]
) -> None:
    """`prumo --version` passar não garante o subcomando: CLI 0.67.2 não tem `validate`."""
    callers = _bodies_calling(subcommand)
    assert set(callers) == expected
    missing = subcommand.split()[1]
    for slug, body in callers.items():
        assert f"No such command '{missing}'" in body, slug
        assert "uv tool upgrade prumo-assistant-for-researcher" in body, slug
        assert "consentimento" in body, slug
