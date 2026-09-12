"""`prumo validate` — o CLI checa os contratos que os subagents devolvem (spec D3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from par import PrumoError
from par.cli import app
from par.contracts import CONTRACTS, validate_contract
from par.core.paths import resolve_resource

runner = CliRunner()

_VERDICT = {"sentence": "A reduz B.", "citekey": "k", "justification": "j"}


def test_nome_no_registry_bate_com_schema_version() -> None:
    assert set(CONTRACTS) == {"PaperCallout/v1", "SupportReport/v1", "PeerReviewReport/v1"}
    for name, model in CONTRACTS.items():
        assert model.model_fields["schema_version"].default == name


def test_validate_contract_devolve_payload_normalizado() -> None:
    out = validate_contract(
        "SupportReport/v1", {"page": "x.md", "verdicts": [{**_VERDICT, "verdict": "no-source"}]}
    )
    assert out["schema_version"] == "SupportReport/v1"
    assert out["verdicts"][0]["quote"] is None


def test_validate_contract_invalido_levanta_com_o_campo() -> None:
    bad = {"page": "x.md", "verdicts": [{**_VERDICT, "verdict": "fully"}]}
    with pytest.raises(PrumoError, match=r"verdicts\.0"):
        validate_contract("SupportReport/v1", bad)


def test_cli_valido_emite_ok() -> None:
    payload = {"page": "x.md", "verdicts": []}
    res = runner.invoke(app, ["validate", "SupportReport/v1", "--json"], input=json.dumps(payload))
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["valid"] is True
    assert out["schema"] == "SupportReport/v1"


def test_cli_invalido_aponta_o_campo_e_a_correcao() -> None:
    bad = {"page": "x.md", "verdicts": [{**_VERDICT, "verdict": "fully"}]}
    res = runner.invoke(app, ["validate", "SupportReport/v1"], input=json.dumps(bad))
    assert res.exit_code == 1
    assert "verdicts.0" in res.output
    assert "Corrija" in res.output


def test_cli_schema_desconhecido_lista_os_conhecidos() -> None:
    res = runner.invoke(app, ["validate", "Nada/v1"], input="{}")
    assert res.exit_code == 1
    assert "PeerReviewReport/v1" in res.output


# ---------------------------------------------------------------------------
# PeerReviewReport/v1 — quote conferido contra o draft (spec quote-anchors)
# ---------------------------------------------------------------------------

_DRAFT = "## Results\n\nO modelo combinado supera\n  os baselines de comparação em AUROC.\n"


def _report(draft_path: str, *quotes: str) -> dict[str, object]:
    return {
        "draft_path": draft_path,
        "draft_genre": "other",
        "thesis_in_one_sentence": "t",
        "recommendation": "major",
        "executive_summary": "e",
        "critical_weaknesses": [
            {"section": "Results", "point": "p", "fix": "f", "quote": q} for q in quotes
        ],
        "mental_model_applied": "none",
    }


@pytest.fixture
def draft(tmp_path: Path) -> Path:
    path = tmp_path / "draft.md"
    path.write_text(_DRAFT, encoding="utf-8")
    return path


def test_quote_literal_com_espacos_diferentes_valida(draft: Path) -> None:
    payload = {**_report(str(draft), "combinado supera os baselines"), "sources_read": ["p.md"]}
    out = validate_contract("PeerReviewReport/v1", payload)
    assert out["critical_weaknesses"][0]["quote"] == "combinado supera os baselines"
    assert out["sources_read"] == ["p.md"]


def test_quote_parafraseado_falha_nomeando_secao_e_trecho(draft: Path) -> None:
    with pytest.raises(PrumoError, match=r"seção 'Results'.*\"combinado vence os baselines\""):
        validate_contract(
            "PeerReviewReport/v1", _report(str(draft), "combinado vence os baselines")
        )


def test_quote_acima_de_25_palavras_falha(draft: Path) -> None:
    longo = " ".join(["palavra"] * 26)
    with pytest.raises(PrumoError, match="25 palavras"):
        validate_contract("PeerReviewReport/v1", _report(str(draft), longo))


def test_sem_quote_nem_sources_read_valida_sem_ler_o_draft(tmp_path: Path) -> None:
    out = validate_contract("PeerReviewReport/v1", _report(str(tmp_path / "nao-existe.md")))
    assert out["sources_read"] == []


def test_draft_ilegivel_reporta_uma_vez(tmp_path: Path) -> None:
    missing = str(tmp_path / "nao-existe.md")
    with pytest.raises(PrumoError) as exc:
        validate_contract("PeerReviewReport/v1", _report(missing, "a", "b"))
    assert str(exc.value).count("draft_path") == 1


def test_sample_report_do_plugin_valida_com_o_draft_presente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_path = resolve_resource("skills") / "review" / "examples" / "sample_report.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    quotes = [
        item["quote"]
        for field in ("critical_weaknesses", "minor_weaknesses", "claims_without_evidence")
        for item in sample[field]
        if item.get("quote")
    ]
    assert quotes and sample["sources_read"]
    monkeypatch.chdir(tmp_path)
    target = tmp_path / sample["draft_path"]
    target.parent.mkdir(parents=True)
    target.write_text("\n\n".join(quotes), encoding="utf-8")
    assert validate_contract("PeerReviewReport/v1", sample)["recommendation"] == "major"
