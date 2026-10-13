"""Integration tests: `prumo update` reflui o `pj_base` num projeto vivo."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from par.cli import app

runner = CliRunner()


def _init(target: Path) -> None:
    res = runner.invoke(app, ["init", str(target), "--json"])
    assert res.exit_code == 0, res.output


def test_update_restaura_arquivo_do_nucleo_apagado(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "project_guide.md").unlink()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "docs" / "project_guide.md").is_file()
    payload = json.loads(res.output)
    assert "docs/project_guide.md" in payload["copied"]


def test_update_aplica_o_nome_do_projeto_no_que_copia(tmp_path: Path) -> None:
    """Mesmo tratamento do `init`: o README recriado leva o nome real, não `pj_<NOME>`."""
    pj = tmp_path / "pj_xyz"
    _init(pj)
    (pj / "README.md").unlink()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    readme = (pj / "README.md").read_text(encoding="utf-8")
    assert "pj_xyz" in readme
    assert "pj_<NOME>" not in readme


def test_update_nao_injeta_escopo_do_template(tmp_path: Path) -> None:
    """A armadilha do desenho: o `pj_base` traz `docs/studies/principal/`, e
    recopiá-lo num projeto que renomeou o escopo criaria um segundo escopo
    órfão — fazendo todo comando por-escopo passar a exigir `--scope`."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "studies" / "principal").rename(pj / "docs" / "studies" / "01_estudo")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert not (pj / "docs" / "studies" / "principal").exists()
    assert [p.name for p in (pj / "docs" / "studies").iterdir()] == ["01_estudo"]


def test_update_dry_run_nao_escreve(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "project_guide.md").unlink()

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert not (pj / "docs" / "project_guide.md").exists()
    payload = json.loads(res.output)
    assert payload["dry_run"] is True
    assert "docs/project_guide.md" in payload["missing"]


def test_update_em_projeto_no_padrao_nao_faz_nada(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["copied"] == []
    assert payload["updated"] == []


def test_update_fora_de_projeto_falha_com_instrucao(tmp_path: Path) -> None:
    res = runner.invoke(app, ["update", str(tmp_path), "--json"])
    assert res.exit_code == 1
    assert "prumo init" in res.output or "pj_config.toml" in res.output


def test_update_reescreve_invocacoes_antigas(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("use /par:paper-manager sync\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(encoding="utf-8") == "use /par:paper library sync\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_dry_run_lista_invocacoes_sem_escrever(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("/par:wiki-query\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(encoding="utf-8") == "/par:wiki-query\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_nao_reescreve_proveniencia(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    nota = pj / "docs" / "studies" / "principal" / "notes" / "f.md"
    nota.parent.mkdir(parents=True, exist_ok=True)
    nota.write_text("---\ntype: finding\ngenerator: wiki-query\n---\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert "generator: wiki-query" in nota.read_text(encoding="utf-8")


def test_update_traz_rule_safe_outputs_a_projeto_antigo(tmp_path: Path) -> None:
    """Projeto de antes da rule a recebe pelo caminho normal do `update`."""
    pj = tmp_path / "pj_antigo"
    _init(pj)
    rule = pj / ".claude" / "rules" / "safe_outputs.md"
    rule.unlink()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert rule.is_file()
    assert ".claude/rules/safe_outputs.md" in json.loads(res.output)["copied"]


# --- A11: cópias antigas do PAR no pj vão para .prumo/legacy-copies/ ---------


def _com_copias(pj: Path, *, skill_body: str = "x\n") -> None:
    for name in ("paper", "minha-skill"):
        d = pj / ".claude" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(skill_body if name == "paper" else "minha\n", encoding="utf-8")
    agents = pj / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "reviewer.md").write_text("reviewer\n", encoding="utf-8")
    (agents / "meu-agent.md").write_text("meu\n", encoding="utf-8")


def _backups(pj: Path) -> list[Path]:
    root = pj / ".prumo" / "legacy-copies"
    return sorted(root.iterdir()) if root.is_dir() else []


def test_update_move_copias_do_par_para_backup(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj, skill_body="corpo da cópia\n")
    original = (pj / ".claude" / "skills" / "paper" / "SKILL.md").read_bytes()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    backups = _backups(pj)
    assert len(backups) == 1
    bk = backups[0]
    assert re.fullmatch(r"\d{8}-\d{6}", bk.name)
    assert (bk / "skills" / "paper" / "SKILL.md").read_bytes() == original
    assert (bk / "agents" / "reviewer.md").is_file()
    assert not (pj / ".claude" / "skills" / "paper").exists()
    assert not (pj / ".claude" / "agents" / "reviewer.md").exists()
    assert (pj / ".claude" / "skills" / "minha-skill" / "SKILL.md").is_file()
    assert (pj / ".claude" / "agents" / "meu-agent.md").is_file()
    payload = json.loads(res.output)
    assert payload["plugin_copies"] == [".claude/skills/paper", ".claude/agents/reviewer.md"]
    assert payload["legacy_backup"] == ".prumo/legacy-copies/" + bk.name


def test_update_backup_guarda_a_copia_antes_da_reescrita(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj, skill_body="use /par:paper-manager sync\n")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    (bk,) = _backups(pj)
    text = (bk / "skills" / "paper" / "SKILL.md").read_text(encoding="utf-8")
    assert "/par:paper-manager" in text


def test_update_dry_run_so_lista_copias(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj)

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["plugin_copies"] == [".claude/skills/paper", ".claude/agents/reviewer.md"]
    assert payload["legacy_backup"] is None
    assert (pj / ".claude" / "skills" / "paper" / "SKILL.md").is_file()
    assert (pj / ".claude" / "agents" / "reviewer.md").is_file()
    assert not (pj / ".prumo" / "legacy-copies").exists()


def test_update_dry_run_nao_conta_invocacao_dentro_das_copias(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj, skill_body="use /par:paper-manager sync\n")

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["skill_refs"] == []


def test_update_sem_tty_move_copias_e_preserva_rule_customizada(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj)
    rule = pj / ".claude" / "rules" / "safe_outputs.md"
    rule.write_text("minha rule customizada\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj)])

    assert res.exit_code == 0, res.output
    assert not (pj / ".claude" / "skills" / "paper").exists()
    assert len(_backups(pj)) == 1
    assert rule.read_text(encoding="utf-8") == "minha rule customizada\n"


def test_update_yes_nao_muda_o_tratamento_das_copias(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj)

    res = runner.invoke(app, ["update", str(pj), "--yes", "--json"])

    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["plugin_copies"] == [".claude/skills/paper", ".claude/agents/reviewer.md"]
    assert not (pj / ".claude" / "skills" / "paper").exists()
    assert (pj / ".claude" / "skills" / "minha-skill" / "SKILL.md").is_file()
    assert (pj / ".claude" / "agents" / "meu-agent.md").is_file()


def test_update_resumo_cita_o_backup(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj)

    res = runner.invoke(app, ["update", str(pj)])

    assert res.exit_code == 0, res.output
    out = " ".join(res.output.split())
    assert "cópia(s) antiga(s) do PAR saíram do projeto para .prumo/legacy-copies/" in out
    assert "nada foi apagado" in out


def test_update_move_scripts_antigos_e_espelhos_do_codex(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    scripts = pj / ".claude" / "scripts"
    scripts.mkdir()
    (scripts / "cite_lookup.py").write_text("antigo\n", encoding="utf-8")
    (scripts / "meu_script.py").write_text("meu\n", encoding="utf-8")
    (pj / ".claude" / "make").mkdir()
    (pj / ".claude" / "make" / ".gitkeep").write_text("", encoding="utf-8")
    (pj / ".codex" / "agents").mkdir(parents=True)
    (pj / ".codex" / "agents" / "verifier.toml").write_text(
        'developer_instructions = "Devolve SupportReport/v1."\n', encoding="utf-8"
    )
    (pj / ".agents" / "skills" / "wiki").mkdir(parents=True)
    (pj / ".agents" / "skills" / "wiki" / "SKILL.md").write_text(
        "---\nname: wiki\nprumo:\n  version: 2.0.0\n---\n", encoding="utf-8"
    )
    (pj / "AGENTS.md").write_text("# meu AGENTS\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["plugin_copies"] == [
        ".claude/scripts/cite_lookup.py",
        ".claude/make",
        ".codex/agents/verifier.toml",
        ".agents/skills/wiki",
    ]
    (bk,) = _backups(pj)
    assert (bk / "scripts" / "cite_lookup.py").read_text(encoding="utf-8") == "antigo\n"
    assert (bk / "make" / ".gitkeep").is_file()
    assert (bk / ".codex" / "agents" / "verifier.toml").is_file()
    assert (bk / ".agents" / "skills" / "wiki" / "SKILL.md").is_file()
    assert (scripts / "meu_script.py").read_text(encoding="utf-8") == "meu\n"
    assert not (pj / ".claude" / "make").exists()
    assert not (pj / ".codex").exists()
    assert not (pj / ".agents").exists()
    assert (pj / "AGENTS.md").read_text(encoding="utf-8") == "# meu AGENTS\n"


def test_update_poupa_skill_de_terceiros_e_agent_do_pesquisador_com_nome_do_par(
    tmp_path: Path,
) -> None:
    """Um pacote de terceiros instala `.agents/skills/peer-review/`, nome que o PAR já usou.
    Sem a marca do PAR no conteúdo, não é cópia: o update não o tira do projeto."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    terceiros = pj / ".agents" / "skills" / "peer-review" / "SKILL.md"
    terceiros.parent.mkdir(parents=True)
    terceiros.write_text("---\ndescription: third-party\n---\n", encoding="utf-8")
    minha = pj / ".agents" / "skills" / "write" / "SKILL.md"
    minha.parent.mkdir(parents=True)
    minha.write_text("Escreva o draft do pj_leg1; rode `prumo status`.\n", encoding="utf-8")
    meu = pj / ".codex" / "agents" / "reviewer.toml"
    meu.parent.mkdir(parents=True)
    meu.write_text(
        'name = "reviewer"\ndeveloper_instructions = "o prumo do pj_demo"\n', encoding="utf-8"
    )

    res = runner.invoke(app, ["update", str(pj), "--yes", "--json"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["plugin_copies"] == []
    assert terceiros.read_text(encoding="utf-8") == "---\ndescription: third-party\n---\n"
    assert minha.is_file()
    assert meu.is_file()
    assert _backups(pj) == []


def test_update_resumo_so_fala_de_skill_quando_moveu_skill(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / ".claude" / "scripts").mkdir()
    (pj / ".claude" / "scripts" / "export_page.py").write_text("x\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj)])

    assert res.exit_code == 0, res.output
    out = " ".join(res.output.split())
    assert "1 cópia(s) antiga(s) do PAR saíram do projeto" in out
    assert "customizado" not in out


def test_update_resumo_aconselha_recriar_skill_customizada(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    _com_copias(pj)

    res = runner.invoke(app, ["update", str(pj)])

    assert res.exit_code == 0, res.output
    out = " ".join(res.output.split())
    assert "Se você tinha customizado uma skill, recrie-a com outro nome" in out


def test_doctor_aponta_receita_que_chamava_script_movido_antes_e_depois_do_update(
    tmp_path: Path,
) -> None:
    """O update move `.claude/scripts/paper_sync.py`; o Makefile que o chamava não pode
    quebrar calado: a linha aparece no `[referencia_obsoleta]` antes e depois."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / ".claude" / "scripts").mkdir()
    (pj / ".claude" / "scripts" / "paper_sync.py").write_text("x\n", encoding="utf-8")
    (pj / "Makefile").write_text(
        "sync-paper:\n\t@python3 .claude/scripts/paper_sync.py .\n", encoding="utf-8"
    )

    def referencias() -> list[str]:
        with patch("par.cli.check_external_deps", return_value=[]):
            res = runner.invoke(app, ["doctor", str(pj), "--json"])
        issues: list[str] = json.loads(res.stdout)["issues"]
        return [i for i in issues if i.startswith("[referencia_obsoleta]")]

    (antes,) = referencias()
    assert "Makefile:2" in antes
    assert runner.invoke(app, ["update", str(pj), "--json"]).exit_code == 0
    assert not (pj / ".claude" / "scripts" / "paper_sync.py").exists()
    (depois,) = referencias()
    assert "Makefile:2" in depois


# --- D4/A13: `.claude/settings.json` do template --------------------------------


def test_update_acrescenta_settings_ausente(tmp_path: Path) -> None:
    """pj sem `.claude/settings.json` o recebe como arquivo ausente."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    settings = pj / ".claude" / "settings.json"
    settings.unlink()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert settings.is_file()
    payload = json.loads(res.output)
    assert ".claude/settings.json" in payload["copied"]


def test_update_nao_toca_settings_existente(tmp_path: Path) -> None:
    """Um `.claude/settings.json` próprio do pj nunca é tocado, nem com `--yes`."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    settings = pj / ".claude" / "settings.json"
    proprio = b'{"permissions": {"allow": ["Bash(ls:*)"]}}\n'
    settings.write_bytes(proprio)

    res = runner.invoke(app, ["update", str(pj), "--yes", "--json"])

    assert res.exit_code == 0, res.output
    assert settings.read_bytes() == proprio
