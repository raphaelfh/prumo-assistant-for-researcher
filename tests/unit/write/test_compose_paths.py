"""Tests para resolve_template + compose_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.domains.write.compose import (
    compose_path,
    guide_paths,
    resolve_template,
    template_candidates,
)


def test_resolve_template_default_from_skill_bundle(tmp_path: Path) -> None:
    """O template do plugin mora em skills/<skill>/templates/<modo>.md."""
    expected = {
        "paper": "write/templates/manuscript.md",
        "scientific": "write/templates/section.md",
        "statistics": "protocol/templates/sap.md",
        "projeto-cep": "protocol/templates/cep.md",
    }
    for kind, suffix in expected.items():
        out = resolve_template(pj_path=tmp_path, kind=kind)  # type: ignore[arg-type]
        assert out.as_posix().endswith(suffix), (kind, out)


def test_resolve_template_project_override(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    over = pj / ".claude" / "writing_templates"
    over.mkdir(parents=True)
    (over / "paper.md").write_text("# Project Paper\n")
    out = resolve_template(pj_path=pj, kind="paper")
    assert out == over / "paper.md"


def test_resolve_template_explicit_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom.md"
    custom.write_text("# Custom\n")
    out = resolve_template(
        pj_path=tmp_path,
        kind="paper",
        explicit=custom,
    )
    assert out == custom


def test_resolve_template_explicit_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_template(
            pj_path=tmp_path,
            kind="paper",
            explicit=tmp_path / "nope.md",
        )


def test_resolve_template_invalid_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="kind"):
        resolve_template(pj_path=tmp_path, kind="bogus")  # type: ignore[arg-type]


def test_compose_path_drafts_default(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    out = compose_path(
        scope=pj,
        kind="paper",
        date="2026-05-03",
        slug="combinado",
    )
    assert out == pj / "writing" / "paper-2026-05-03-combinado.md"


def test_compose_path_into_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project_guide.md"
    target.write_text("# Projeto\n")
    out = compose_path(
        scope=pj,
        kind="paper",
        date="2026-05-03",
        slug="x",
        into=target,
    )
    assert out == target


def test_compose_path_out_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    target = tmp_path / "any" / "place.md"
    out = compose_path(
        scope=pj,
        kind="paper",
        date="2026-05-03",
        slug="x",
        out=target,
    )
    assert out == target


def test_compose_path_into_and_out_conflict(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        compose_path(
            scope=tmp_path,
            kind="paper",
            date="2026-05-03",
            slug="x",
            into=tmp_path / "a.md",
            out=tmp_path / "b.md",
        )


def test_template_candidates_espelha_a_chain_de_resolve(tmp_path: Path) -> None:
    """`list-templates` reporta os mesmos caminhos que `resolve_template` escolhe.

    Guarda contra a divergência real que já aconteceu: o CLI apontava para
    `templates/writing/<kind>.md` (vazio desde a migração) enquanto a resolução
    usava `skills/write-<kind>/template.md`.
    """
    candidates = template_candidates(pj_path=tmp_path, kind="paper")
    assert list(candidates) == ["project_override", "user_dir", "plugin_default"]
    assert candidates["user_dir"] is None  # sem pasta do usuário, o degrau não existe
    # sem override no projeto, o vencedor da chain é o default do plugin
    assert resolve_template(pj_path=tmp_path, kind="paper") == candidates["plugin_default"]
    assert candidates["plugin_default"] is not None
    assert candidates["plugin_default"].exists()

    override = tmp_path / ".claude" / "writing_templates" / "paper.md"
    override.parent.mkdir(parents=True)
    override.write_text("# override\n", encoding="utf-8")
    assert resolve_template(pj_path=tmp_path, kind="paper") == override
    assert template_candidates(pj_path=tmp_path, kind="paper")["project_override"] == override


def _user_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pasta do usuário sintética (ADR-0044): ``$XDG_CONFIG_HOME/prumo``."""
    root = tmp_path / "xdg" / "prumo"
    root.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return root


def _user_template(root: Path, kind: str = "paper") -> Path:
    template = root / "templates" / f"{kind}.md"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("# Template sintético de teste\n", encoding="utf-8")
    return template


def test_template_do_usuario_vence_o_do_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = _user_template(_user_dir(tmp_path, monkeypatch))
    pj = tmp_path / "pj_exemplo"
    (pj / ".claude").mkdir(parents=True)

    assert resolve_template(pj_path=pj, kind="paper") == template
    assert template_candidates(pj_path=pj, kind="paper")["user_dir"] == template


def test_template_do_projeto_vence_o_do_usuario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user_template(_user_dir(tmp_path, monkeypatch))
    override = tmp_path / "pj_exemplo" / ".claude" / "writing_templates" / "paper.md"
    override.parent.mkdir(parents=True)
    override.write_text("# Template sintético do projeto\n", encoding="utf-8")

    assert resolve_template(pj_path=tmp_path / "pj_exemplo", kind="paper") == override


def test_pasta_do_usuario_sem_o_kind_cai_no_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user_template(_user_dir(tmp_path, monkeypatch), kind="statistics")

    out = resolve_template(pj_path=tmp_path, kind="paper")
    assert out.as_posix().endswith("write/templates/manuscript.md")


def test_guias_so_do_kind_em_ordem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _user_dir(tmp_path, monkeypatch)
    for rel in (
        "guides/paper/b.md",
        "guides/paper/a.md",
        "guides/statistics/x.md",
        "guides/solta.md",
        "ml/formato.md",
    ):
        guide = root / rel
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("Guia sintética de teste\n", encoding="utf-8")

    got = [g.relative_to(root).as_posix() for g in guide_paths("paper")]
    # o resto da base é consulta livre, não leitura obrigatória
    assert got == ["guides/paper/a.md", "guides/paper/b.md"]


def test_sem_pasta_do_usuario_sem_guias() -> None:
    assert guide_paths("paper") == ()


def test_erro_sem_template_mostra_o_caminho_real_da_pasta_do_usuario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mensagem aponta ``$XDG_CONFIG_HOME/prumo``, não um ``~/.config`` fixo."""
    from par.domains.write import compose

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        compose,
        "template_candidates",
        lambda **_: {"project_override": None, "user_dir": None, "plugin_default": None},
    )

    with pytest.raises(FileNotFoundError) as exc:
        resolve_template(pj_path=tmp_path, kind="paper")

    assert str(tmp_path / "xdg" / "prumo" / "templates" / "paper.md") in str(exc.value)
