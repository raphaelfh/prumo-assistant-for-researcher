"""Guard do modo `/par:write export`: a pesquisadora é guiada até o docx certo
sem saber o código (ADR-0037). Conteúdo de skill é prosa; estes testes impedem
que uma edição futura derrube a decisão revisão × final ou dessincronize a
skill da CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from par.cli import app
from par.core.skills import parse_skill_file

_SKILLS = Path(__file__).resolve().parents[2] / "skills"
_MODE = _SKILLS / "write" / "modes" / "export.md"


def _body() -> str:
    """Corpo do modo, sem o frontmatter (o ``allowed-tools`` também cita o comando)."""
    texto = _MODE.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    return " ".join(texto.split())


def test_modo_existe_e_exige_cli() -> None:
    manifest = parse_skill_file(_MODE)
    assert manifest.name == "export"
    assert "cli" in manifest.requires
    assert any("Bash(prumo write export" in tool for tool in manifest.allowed_tools)


def test_pergunta_revisao_ou_final_antes_de_exportar() -> None:
    body = _body()
    assert "revisão" in body and "final" in body
    assert body.index("Pergunte") < body.index("prumo write export")


def test_comandos_dos_dois_caminhos() -> None:
    body = _body()
    assert "prumo write export <página> --to docx" in body
    assert "--to docx --final" in body


def test_contrato_da_revisao_e_do_final() -> None:
    body = _body()
    assert "botões do Zotero" in body
    assert "prumo write review ingest" in body
    assert "nunca vai para a revisão" in body


def test_nunca_simula_e_repassa_o_aviso() -> None:
    body = _body()
    assert "Nunca gere o docx por outro caminho" in body
    assert "repasse o aviso" in body


def test_porta_lista_o_modo() -> None:
    door = (_SKILLS / "write" / "SKILL.md").read_text(encoding="utf-8")
    assert "| `export` |" in door


def test_cli_tem_a_flag_que_a_skill_cita() -> None:
    result = CliRunner().invoke(app, ["write", "export", "--help"])
    assert "--final" in result.output
