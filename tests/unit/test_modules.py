"""Integração: módulos opcionais do núcleo (code, data, notebooks, clinical, ml)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    """Raiz do projeto no layout ATUAL: só o marcador `.claude/pj_config.toml`."""
    root = tmp_path / "pj_x"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    return root


def _scope(root: Path, slug: str) -> Path:
    """Escopo `docs/studies/<slug>/{notes,writing,decisions}`."""
    scope = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (scope / sub).mkdir(parents=True)
    return scope


def test_modulos_do_nucleo_existem_e_sao_descobriveis() -> None:
    from prumo_assist.core.scaffold import discover_modules

    nomes = {m.name for m in discover_modules()}
    assert {"code", "data", "notebooks", "clinical", "ml"} <= nomes


def test_add_clinical_nao_cria_protocolo_fora_do_escopo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "principal")
    result = runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "docs" / "studies" / "principal" / "writing" / "protocol.md").is_file()
    assert not (root / "docs" / "protocol.md").exists()


def test_add_clinical_cai_no_escopo_de_nome_arbitrario(tmp_path: Path) -> None:
    """Fix round 1: o anchor do `clinical` era hardcoded em `principal` — se o
    usuário renomeasse o escopo (wizard da Task 10 deriva o slug do NOME do
    projeto, não de "principal"), `add clinical` recriava um escopo fantasma.
    Com um único escopo, não importa o nome: o payload cai nele."""
    root = _project(tmp_path)
    _scope(root, "mortalidade-uti")
    result = runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "docs" / "studies" / "mortalidade-uti" / "writing" / "protocol.md").is_file()
    assert not (root / "docs" / "studies" / "principal").exists()


def test_add_clinical_com_dois_escopos_exige_flag_scope(tmp_path: Path) -> None:
    """Com mais de um escopo, o comando não adivinha — exige `--scope <slug>`
    e a mensagem de erro (pt-BR) traz os slugs disponíveis."""
    root = _project(tmp_path)
    _scope(root, "mortalidade-uti")
    _scope(root, "sepse-pediatrica")

    sem_flag = runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert sem_flag.exit_code != 0
    assert "mortalidade-uti" in sem_flag.output
    assert "sepse-pediatrica" in sem_flag.output
    assert "--scope" in sem_flag.output
    assert not (root / "docs" / "studies" / "mortalidade-uti" / "writing" / "protocol.md").exists()
    assert not (root / "docs" / "studies" / "sepse-pediatrica" / "writing" / "protocol.md").exists()

    com_flag = runner.invoke(
        app, ["add", "clinical", "--target", str(root), "--scope", "sepse-pediatrica"]
    )
    assert com_flag.exit_code == 0, com_flag.output
    assert (root / "docs" / "studies" / "sepse-pediatrica" / "writing" / "protocol.md").is_file()
    assert not (root / "docs" / "studies" / "mortalidade-uti" / "writing" / "protocol.md").exists()


def test_add_clinical_scope_desconhecido_erra_com_slugs_disponiveis(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "mortalidade-uti")
    result = runner.invoke(app, ["add", "clinical", "--target", str(root), "--scope", "nao-existe"])
    assert result.exit_code != 0
    assert "nao-existe" in result.output
    assert "mortalidade-uti" in result.output


def test_add_clinical_sem_escopo_pede_para_criar_um(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert result.exit_code != 0
    assert "prumo add study" in result.output


def test_add_list_marca_clinical_aplicado_apos_resolucao_de_escopo(tmp_path: Path) -> None:
    """`is_applied` precisa continuar reconhecendo o anchor do módulo depois
    da resolução de escopo, mesmo quando o escopo não se chama "principal"."""
    import json

    root = _project(tmp_path)
    _scope(root, "mortalidade-uti")
    assert runner.invoke(app, ["add", "clinical", "--target", str(root)]).exit_code == 0
    result = runner.invoke(app, ["add", "--list", "--target", str(root), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    by_name = {m["name"]: m for m in payload["modules"]}
    assert by_name["clinical"]["applied"] is True


def test_add_code_cria_camada_de_codigo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "code", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "src").is_dir()
    assert (root / "tests").is_dir()
    assert (root / "pyproject.toml").is_file()


def test_add_code_substitutes_project_name(tmp_path: Path) -> None:
    """O pyproject.toml do módulo `code` ainda carrega o placeholder `pj-NOME`
    (bug histórico do núcleo, ver test_cli_init.py) — `prumo add` precisa
    aplicar a mesma substituição de nome que `prumo init` aplica."""
    root = tmp_path / "pj_demo"
    assert runner.invoke(app, ["init", str(root), "--json"]).exit_code == 0
    result = runner.invoke(app, ["add", "code", "--target", str(root)])
    assert result.exit_code == 0, result.output
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "pj_demo"' in text
    assert "pj-NOME" not in text


def test_add_data_cria_camadas_de_dado(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "data", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "content" / "01_raw").is_dir()
    assert (root / "content" / "02_processed").is_dir()


def test_add_notebooks_cria_pasta_de_notebooks(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "notebooks", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "notebooks").is_dir()


def test_add_nao_deixa_manifesto_do_modulo_no_projeto(tmp_path: Path) -> None:
    """`overlay` fazia `rglob("*")` sobre `templates/modules/<nome>/` sem excluir
    o `_module.toml` — metadata do módulo (description/when_to_use/anchor), não
    payload. Todo `prumo add` deixava um `_module.toml` órfão na raiz do `pj_*`,
    descrevendo o módulo aplicado PRIMEIRO (os seguintes o viam existir e
    pulavam), o que dava a impressão de um marcador de módulo que não é."""
    root = _project(tmp_path)
    for modulo in ("data", "code", "notebooks"):
        result = runner.invoke(app, ["add", modulo, "--target", str(root)])
        assert result.exit_code == 0, result.output
        assert not (root / "_module.toml").exists(), f"`add {modulo}` vazou o manifesto"
    # o payload real continua chegando
    assert (root / "content" / "01_raw").is_dir()
    assert (root / "src").is_dir()
    assert (root / "notebooks").is_dir()
