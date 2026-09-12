"""`prumo validate` — o CLI checa os contratos que os subagents devolvem (spec D3)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from prumo_assist import PrumoError
from prumo_assist.cli import app
from prumo_assist.contracts import CONTRACTS, validate_contract

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
