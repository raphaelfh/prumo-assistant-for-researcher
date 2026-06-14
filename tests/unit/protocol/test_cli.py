"""Integration tests para ``prumo protocol *``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.domains.protocol.picot_io import write_picot
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

runner = CliRunner()


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n")
    (pj / "docs" / "project_guide.md").write_text("---\ntitle: x\n---\n\n# Projeto\n")
    (pj / "docs" / "decisions").mkdir()
    return pj


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A",
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def test_protocol_propagate_inserts_blocks(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["protocol_status"] == "inserted"
    assert payload["project_status"] == "inserted"


def test_protocol_diff_no_baseline(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "diff", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["changes"] == []
    assert payload["has_structural"] is False


def test_protocol_propagate_missing_picot(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)  # sem picot.toml
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code != 0
    assert "picot.toml" in result.output or "picot.toml" in result.stderr


def test_protocol_detect_mode_init(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["protocol", "detect-mode", str(pj)])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "init"


def test_protocol_init_writes_and_emits(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    payload = {
        "type": "clinical",
        "created_at": "2026-06-14",
        "last_updated": "2026-06-14",
        "version": 1,
        "population": "DS_A",
        "intervention": "IntervencaoX",
        "comparison": "best baseline",
        "outcome": "AUROC ≥ 0.85",
        "time": "retrospectivo",
        "hypothesis": {"statement": "x", "rationale": "y", "metrics": ["AUROC"]},
    }
    result = runner.invoke(
        app,
        ["protocol", "init", "--date", "2026-06-14", "--path", str(pj), "--json"],
        input=json.dumps(payload),
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["adr_path"])).exists()


def test_protocol_init_invalid_payload_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(
        app, ["protocol", "init", "--date", "2026-06-14", "--path", str(pj)], input="{}"
    )
    assert result.exit_code == 1
    assert "hypothesis" in result.output


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last
