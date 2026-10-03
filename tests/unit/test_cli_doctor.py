"""Integration tests do prumo doctor com seção de dependências externas."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from par.cli import _resolve_template_dir, app
from par.core import scaffold
from par.core.deps import DepStatus

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    """Projeto no padrão ATUAL: layout por escopo + núcleo mínimo presente.

    O núcleo (`scaffold.REQUIRED_BASE_FILES`) entra copiado do `pj_base` real,
    não escrito à mão: as rules são comparadas por CONTEÚDO pelo
    `[fora_do_padrao]`, então um corpo inventado aqui reportaria drift em
    todo teste e esconderia o que o check deveria pegar.
    """
    pj = tmp_path / "pj_x"
    (pj / ".claude" / "rules").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (pj / ".claude" / "skills").mkdir()
    (pj / "docs" / "references").mkdir(parents=True)
    base = _resolve_template_dir()
    for rel in scaffold.REQUIRED_BASE_FILES:
        dst = pj / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((base / rel).read_bytes())
    return pj


def test_doctor_json_includes_external_deps(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=True, required_by=["wiki-query"], detail="ok", hint=""),
        DepStatus(
            name="zotero",
            present=False,
            required_by=["paper connect"],
            detail="down",
            hint="abra o Zotero",
        ),
    ]
    with patch("par.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    names = {d["name"] for d in payload["external_deps"]}
    assert names == {"qmd", "zotero"}


def test_doctor_missing_dep_does_not_fail_exit_code(tmp_path: Path) -> None:
    """Dep externa ausente é informativa: não derruba o exit code (só estrutura derruba)."""
    pj = _project(tmp_path)
    fake = [
        DepStatus(
            name="qmd", present=False, required_by=["wiki-query"], detail="missing", hint="instale"
        ),
    ]
    with patch("par.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    # estrutura do projeto está OK → exit 0 mesmo com qmd ausente
    assert result.exit_code == 0, result.output


def test_doctor_human_output_shows_missing_dep_hint(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(
            name="qmd",
            present=False,
            required_by=["wiki-query"],
            detail="qmd não está no PATH",
            hint="bun install -g @tobilu/qmd",
        ),
    ]
    with patch("par.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert "qmd" in result.output
    assert "bun install -g @tobilu/qmd" in result.output


def test_doctor_flags_broken_zettlr_profile(tmp_path: Path) -> None:
    import yaml

    pj = _project(tmp_path)
    profile = pj / "docs" / "templates" / "prumo-docx.yaml"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        yaml.safe_dump({"reader": "markdown", "writer": "docx", "filters": ["/nao/existe.lua"]}),
        encoding="utf-8",
    )
    with patch("par.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 1
    assert "prumo write zettlr-profile" in result.output


def test_doctor_silent_when_no_zettlr_profile(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    with patch("par.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 0, result.output


def test_doctor_avisa_bib_placeholder(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "docs" / "references" / "_references.bib").write_text(
        "% Bibliografia do projeto — formato Better BibTeX (BBT).\n%\n% Fluxo...\n",
        encoding="utf-8",
    )
    with patch("par.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert any("prumo paper connect" in w for w in payload["warnings"])


def test_doctor_sem_aviso_com_bib_real(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "docs" / "references" / "_references.bib").write_text(
        "@article{x2020,\n  title = {T},\n}\n", encoding="utf-8"
    )
    with patch("par.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    # Só o aviso de bib importa aqui; o `project_context.md` do template
    # nasce em branco e tem aviso próprio, coberto em teste separado.
    assert not any("_references.bib" in w for w in payload["warnings"])


def test_doctor_acusa_layout_legado(tmp_path: Path) -> None:
    """`references/` na raiz agora entra no `[fora_do_padrao]`: mesmo remédio
    dos outros sintomas de projeto atrasado, então mensagem única (VIII)."""
    pj = _project(tmp_path)
    (pj / "docs" / "references").rmdir()
    (pj / "references").mkdir()
    result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert "fora_do_padrao" in result.stdout
    assert "references/" in result.stdout


def test_doctor_acusa_studies_na_raiz(tmp_path: Path) -> None:
    """O caso que passou meses sem aviso: prosa em `studies/` na raiz."""
    pj = _project(tmp_path)
    (pj / "studies" / "01_polymorphism").mkdir(parents=True)
    result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("fora_do_padrao" in i and "studies/" in i for i in payload["issues"])


def test_doctor_acusa_project_guide_ausente(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "docs" / "project_guide.md").unlink()
    result = runner.invoke(app, ["doctor", str(pj), "--json"])
    payload = json.loads(result.stdout)
    assert any("docs/project_guide.md" in i for i in payload["issues"])


def test_doctor_acusa_references_ressuscitado_pelo_zotero(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "references").mkdir()
    result = runner.invoke(app, ["doctor", str(root), "--json"])
    assert "references_ressuscitado" in result.stdout


# ---------------------------------------------------------------------------
# Empacotamento (ADR-0027)
# ---------------------------------------------------------------------------


def test_doctor_acusa_projeto_com_codigo_e_sem_build_system(tmp_path: Path) -> None:
    """O caso que motivou a ADR-0027: `src/` com código, pyproject sem
    `[build-system]`, e notebooks recorrendo a `sys.path.insert`."""
    pj = _project(tmp_path)
    (pj / "pyproject.toml").write_text(
        '[project]\nname = "pj_x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (pj / "src" / "x").mkdir(parents=True)
    (pj / "src" / "x" / "prep.py").write_text("x = 1\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(pj), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("projeto_nao_instalavel" in i for i in payload["issues"])


def test_doctor_nao_opina_sobre_projeto_sem_o_modulo_code(tmp_path: Path) -> None:
    """`pj_*` de revisão sistemática não tem código — o doctor fica quieto."""
    pj = _project(tmp_path)

    result = runner.invoke(app, ["doctor", str(pj), "--json"])

    payload = json.loads(result.stdout)
    assert not any("projeto_nao_instalavel" in i for i in payload["issues"])
    assert not any("sys_path_hack" in i for i in payload["issues"])


def _obsoletas(pj: Path) -> list[str]:
    with patch("par.cli.check_external_deps", return_value=[]):
        res = runner.invoke(app, ["doctor", str(pj), "--json"])
    issues: list[str] = json.loads(res.stdout)["issues"]
    return [i for i in issues if i.startswith("[skill_obsoleta]")]


def _copia_paper(pj: Path, body: str) -> None:
    d = pj / ".claude" / "skills" / "paper"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_doctor_aponta_copias_e_invocacao_numa_issue_so(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    _copia_paper(pj, "/par:peer-review\n")
    (pj / ".claude" / "agents").mkdir(parents=True)
    (pj / ".claude" / "agents" / "reviewer.md").write_text("x", encoding="utf-8")
    (pj / ".claude" / "skills" / "minha-skill").mkdir(parents=True)
    (pj / "README.md").write_text("/par:peer-review\n", encoding="utf-8")

    obsoleta = _obsoletas(pj)

    assert len(obsoleta) == 1, obsoleta
    msg = obsoleta[0]
    for trecho in (
        ".claude/skills/paper",
        ".claude/agents/reviewer.md",
        "README.md",
        "prumo update",
        ".prumo/legacy-copies/",
    ):
        assert trecho in msg, msg
    assert "minha-skill" not in msg
    depois = msg.split("invocações antigas em", 1)[1]
    assert ".claude/skills/paper/SKILL.md" not in depois


def test_doctor_ignora_invocacao_dentro_das_copias(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    _copia_paper(pj, "/par:peer-review\n")

    obsoleta = _obsoletas(pj)

    assert len(obsoleta) == 1, obsoleta
    assert ".claude/skills/paper" in obsoleta[0]
    assert "invocações antigas em" not in obsoleta[0]


def test_doctor_so_invocacao_antiga_mantem_o_texto(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "README.md").write_text("/par:peer-review\n", encoding="utf-8")

    obsoleta = _obsoletas(pj)

    assert obsoleta == [
        "[skill_obsoleta] o PAR agora tem 5 skills com modos "
        "(paper, wiki, protocol, write, review): invocações antigas em README.md. "
        "Rode `prumo update` para reescrever as invocações."
    ]


def test_doctor_sem_sobras_nao_emite_skill_obsoleta(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "README.md").write_text("/par:review critique\n", encoding="utf-8")

    with patch("par.cli.check_external_deps", return_value=[]):
        res = runner.invoke(app, ["doctor", str(pj), "--json"])

    assert not [i for i in json.loads(res.stdout)["issues"] if "[skill_obsoleta]" in i]


def test_doctor_reprova_dado_versionavel(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    issue = "[dado_versionavel] fake"
    with (
        patch("par.cli.check_external_deps", return_value=[]),
        patch("par.cli.safe_outputs_issues", return_value=[issue]),
    ):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 1, result.output
    assert issue in json.loads(result.stdout)["issues"]
