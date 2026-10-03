"""Integration tests pros subcomandos ``prumo paper *``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from par.cli import app
from par.domains.paper import connect

runner = CliRunner()


def _norm(text: str) -> str:
    """Normaliza espaços: o Rich quebra mensagens longas em 80 colunas fora de TTY."""
    return " ".join(text.split())


def _bootstrap_project(tmp_path: Path, bib_text: str) -> Path:
    pj = tmp_path / "pj_demo"
    refs = pj / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text)
    return pj


def test_paper_sync_creates_meta_md(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        "@article{smith2024,\n  title = {Multimodal Fusion},\n  year = 2024\n}\n",
    )
    result = runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["created"] == 1
    assert (pj / "docs" / "references" / "papers" / "smith2024" / "_meta.md").is_file()


def test_paper_find_returns_results(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        '@article{smith2024,\n  title = {Multi-Modal Fusion},\n  author = "Smith, J.",\n  year = 2024\n}\n',
    )
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "find", "multimodal", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["query"] == "multimodal"
    results = payload["results"]
    assert isinstance(results, list)
    assert any(r["citekey"] == "smith2024" for r in results)


def test_paper_lint_clean_project(tmp_path: Path) -> None:
    pj = _bootstrap_project(tmp_path, "@article{a,title={X}}\n")
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "lint", str(pj), "--json"])
    assert result.exit_code == 0
    payload = _last_json(result.stdout)
    assert payload["ok"]


def test_paper_set_primary(tmp_path: Path) -> None:
    pj = _bootstrap_project(tmp_path, "@article{a,title={X}}\n@article{b,title={Y}}\n")
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "set-primary", "a", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["primary"] == "a"


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last


def test_paper_extract_prep_emits_language(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    result = runner.invoke(app, ["paper", "extract-prep", "smith2020", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["language"] == "pt-BR"
    assert Path(str(out["meta_path"])).exists()


def test_paper_extract_applies_content_from_stdin(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    # template com 1 seção pra apply_extraction popular (### = nível que o parser reconhece):
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps({"Resumo": "Estudo de coorte sobre RWE."})
    result = runner.invoke(
        app,
        [
            "paper",
            "extract",
            "smith2020",
            "--model",
            "claude-x",
            "--date",
            "2026-06-14",
            str(pj),
            "--json",
        ],
        input=body,
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["changed"] is True
    extract_md = pj / "docs" / "references" / "papers" / "smith2020" / "_extract.md"
    assert extract_md.exists()
    assert "Estudo de coorte" in extract_md.read_text(encoding="utf-8")


def test_paper_extract_idempotent_second_apply_reports_unchanged(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps({"Resumo": "Estudo de coorte sobre RWE."})
    args = [
        "paper",
        "extract",
        "smith2020",
        "--model",
        "claude-x",
        "--date",
        "2026-06-14",
        str(pj),
        "--json",
    ]
    first = runner.invoke(app, args, input=body)
    assert first.exit_code == 0, first.output
    assert _last_json(first.stdout)["changed"] is True
    second = runner.invoke(app, args, input=body)
    assert second.exit_code == 0, second.output
    assert _last_json(second.stdout)["changed"] is False


_RETIRED_COMMANDS = ["sync-annotations", "sync-notes", "sync-all"]


@pytest.mark.parametrize("cmd", _RETIRED_COMMANDS)
def test_paper_help_nao_lista_comando_aposentado(cmd: str) -> None:
    result = runner.invoke(app, ["paper", "--help"])
    assert result.exit_code == 0, result.output
    assert cmd not in result.output
    assert "connect" in result.output


@pytest.mark.parametrize("cmd", _RETIRED_COMMANDS)
def test_paper_comando_aposentado_responde_no_such_command(cmd: str, tmp_path: Path) -> None:
    result = runner.invoke(app, ["paper", cmd, str(tmp_path)])
    assert result.exit_code == 2
    assert "No such command" in result.output


def _fake_report(pj: Path, **overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "pj": str(pj),
        "page": None,
        "scope": ["a1"],
        "checked": 1,
        "findings": [],
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "deep": False,
    }
    report.update(overrides)
    return report


def test_verify_refs_ok_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(tmp_path)

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("par.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "verificada" in result.output


def test_verify_refs_erro_exit_um(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(
        tmp_path,
        findings=[
            {
                "citekey": "a1",
                "level": "error",
                "kind": "retracted",
                "message": "RETRATADO: reavalie a citação.",
                "source": "crossref",
            },
        ],
        summary={"errors": 1, "warnings": 0, "infos": 0},
    )

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("par.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "a1" in result.output and "retracted" in result.output


def test_verify_refs_repassa_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(
        pj_path: Path,
        *,
        page: Path | None = None,
        refresh: bool = False,
        cache_path: Path | None = None,
    ) -> dict[str, Any]:
        captured.update(pj=pj_path, page=page, refresh=refresh)
        return _fake_report(pj_path, scope=[], checked=0)

    monkeypatch.setattr("par.domains.paper.verify.verify_refs", fake)
    pagina = tmp_path / "p.md"
    pagina.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        ["paper", "verify-refs", str(tmp_path), "--page", str(pagina), "--refresh"],
    )
    assert result.exit_code == 0, result.output
    assert captured["refresh"] is True
    assert captured["page"] == pagina.resolve()


def test_verify_refs_sem_opcao_deep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("verify_refs não deveria rodar com --deep")

    monkeypatch.setattr("par.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path), "--deep"])
    assert result.exit_code == 2


def test_verify_refs_bib_ausente_mensagem_limpa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise FileNotFoundError("_references.bib não existe — Better BibTeX export?")

    monkeypatch.setattr("par.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "Better BibTeX" in result.output


def test_paper_connect_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from par.domains.paper.connect import CollectionRef, ConnectResult

    result_obj = ConnectResult(
        collection=CollectionRef(
            library="My Library",
            path="GynOb",
            bbt_path="/My Library/GynOb",
            segments=("My Library", "GynOb"),
        ),
        bib_path=tmp_path / "docs" / "references" / "_references.bib",
        exported=True,
    )

    def fake(*args: Any, **kwargs: Any) -> ConnectResult:
        return result_obj

    monkeypatch.setattr("par.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "GynOb", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "GynOb" in result.output and "conectada" in result.output


def test_paper_connect_export_pendente_avisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from par.domains.paper.connect import CollectionRef, ConnectResult

    result_obj = ConnectResult(
        collection=CollectionRef(
            library="My Library", path="G", bbt_path="/My Library/G", segments=("My Library", "G")
        ),
        bib_path=tmp_path / "b.bib",
        exported=False,
    )

    def fake(*args: Any, **kwargs: Any) -> ConnectResult:
        return result_obj

    monkeypatch.setattr("par.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "G", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert _norm(connect.EXPORT_PENDING_HINT) in _norm(result.output)
    assert "9.0.65" in connect.EXPORT_PENDING_HINT
    assert "prumo paper sync" in connect.EXPORT_PENDING_HINT


@pytest.mark.parametrize(
    "exception_instance,expected_exit,expected_substring",
    [
        (
            connect.CollectionNotFoundError("coleção 'X' não existe no Zotero — NADA foi criado."),
            1,
            "NADA foi criado",
        ),
        (
            connect.AmbiguousCollectionError("ambígua — use --library"),
            1,
            "ambígua — use --library",
        ),
        (
            connect.AlreadyConnectedError("já tem entradas reais — Automatic export"),
            1,
            "Automatic export",
        ),
        (
            connect.UnsupportedCollectionNameError("contém '/' — NADA foi criado"),
            1,
            "NADA foi criado",
        ),
        (
            connect.ZoteroOfflineError("abra o Zotero"),
            2,
            "abra o Zotero",
        ),
    ],
)
def test_paper_connect_error_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_instance: Exception,
    expected_exit: int,
    expected_substring: str,
) -> None:
    """Trava de regressão: cada erro de ``connect_collection`` mapeia pro exit code
    e mensagem certos, sem traceback vazando pro usuário (review final F4, c2)."""

    def fake(*args: Any, **kwargs: Any) -> Any:
        raise exception_instance

    monkeypatch.setattr("par.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "X", "--path", str(tmp_path)])
    assert result.exit_code == expected_exit, result.output
    assert expected_substring in result.output
    assert "Traceback" not in result.output


def test_paper_sync_pdfs_distinguishes_not_downloaded_from_no_attachment(
    tmp_path: Path,
) -> None:
    """A linha humana separa os dois motivos e ensina o remédio do segundo."""
    ausente = tmp_path / "storage" / "BBB" / "nao-baixado.pdf"
    pj = _bootstrap_project(
        tmp_path,
        "@article{semanexo,\n  title = {x}\n}\n"
        "@article{naobaixado,\n  title = {y},\n  file = {" + str(ausente) + "}\n}\n",
    )

    result = runner.invoke(app, ["paper", "sync-pdfs", str(pj)])

    assert result.exit_code == 0, result.output
    # o Console quebra linha na largura do terminal — normaliza antes de casar
    rendered = " ".join(result.output.split())
    assert "1 sem anexo PDF no Zotero" in rendered
    assert "1 com PDF não baixado" in rendered
    assert "Download files" in rendered


# --- `prumo paper connect --create` (ADR-0028) -----------------------------


def _capture_connect(monkeypatch: pytest.MonkeyPatch, *, created: bool) -> dict[str, Any]:
    """Substitui o motor por um espião e devolve o dict de kwargs capturados."""
    from par.domains.paper.connect import CollectionRef, ConnectResult

    seen: dict[str, Any] = {}

    def fake(pj_path: Any, name: str, **kwargs: Any) -> ConnectResult:
        seen["name"] = name
        seen.update(kwargs)
        confirm = kwargs.get("confirm")
        if confirm is not None:
            from par.domains.paper.connect import ConnectPlan, SegmentPlan

            plan = ConnectPlan(
                collection=CollectionRef(
                    library="My Library",
                    path="Nova",
                    bbt_path="/My Library/Nova",
                    segments=("My Library", "Nova"),
                ),
                segments=(SegmentPlan("My Library", True), SegmentPlan("Nova", False)),
                will_create=True,
            )
            seen["confirm_result"] = confirm(plan)
            if not seen["confirm_result"]:
                # Espelha o contrato do motor: confirm negado NÃO muta e levanta.
                from par.domains.paper.connect import CreationDeclinedError

                raise CreationDeclinedError("criação cancelada — NADA foi criado.")
        return ConnectResult(
            collection=CollectionRef(
                library="My Library",
                path="Nova",
                bbt_path="/My Library/Nova",
                segments=("My Library", "Nova"),
            ),
            bib_path=Path("/tmp/_references.bib"),
            exported=True,
            created=created,
        )

    monkeypatch.setattr("par.domains.paper.connect.connect_collection", fake)
    return seen


def test_paper_connect_sem_create_nao_pede_criacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture_connect(monkeypatch, created=False)
    result = runner.invoke(app, ["paper", "connect", "Nova", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert seen["create"] is False
    assert seen["confirm"] is None


def test_paper_connect_create_com_yes_segue_direto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture_connect(monkeypatch, created=True)
    result = runner.invoke(
        app, ["paper", "connect", "Nova", "--create", "--yes", "--path", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert seen["create"] is True
    assert seen["confirm_result"] is True
    # Eco do caminho a materializar, com os segmentos marcados.
    assert "/My Library/Nova" in result.output
    assert "SERÁ CRIADA" in result.output
    # Requisito: a ausência de undo tem de aparecer no sucesso.
    assert "Zotero" in result.output and "desfaz" in result.output.lower()


def test_paper_connect_create_sem_yes_nao_interativo_recusa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CliRunner não é TTY: sem --yes o comando recusa em vez de travar ou criar."""
    _capture_connect(monkeypatch, created=True)
    result = runner.invoke(app, ["paper", "connect", "Nova", "--create", "--path", str(tmp_path)])
    assert result.exit_code == 130, result.output
    assert "--yes" in result.output


def test_paper_connect_create_json_expoe_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_connect(monkeypatch, created=True)
    result = runner.invoke(
        app,
        ["paper", "connect", "Nova", "--create", "--yes", "--path", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0, result.output
    assert _last_json(result.stdout)["created"] is True


def test_paper_extract_aceita_payload_estruturado_com_locators(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps(
        {
            "sections": {"Resumo": "Coorte retrospectiva."},
            "locators": {"Resumo": [{"page": 2, "quote": "retrospective cohort"}]},
        }
    )
    args = ["paper", "extract", "smith2020", "--model", "m", "--date", "2026-09-12", str(pj)]
    result = runner.invoke(app, [*args, "--json"], input=body)
    assert result.exit_code == 0, result.output
    extract_md = pj / "docs" / "references" / "papers" / "smith2020" / "_extract.md"
    assert 'p. 2 — "retrospective cohort"' in extract_md.read_text(encoding="utf-8")


def test_paper_extract_secao_errada_falha_com_instrucao(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    args = ["paper", "extract", "smith2020", "--model", "m", "--date", "2026-09-12", str(pj)]
    result = runner.invoke(app, args, input=json.dumps({"Sumario": "x"}))
    assert result.exit_code == 1
    assert "Resumo" in result.output
