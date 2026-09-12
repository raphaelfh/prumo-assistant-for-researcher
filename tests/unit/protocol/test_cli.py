"""Integration tests para ``prumo protocol *``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.domains.protocol.picot_io import write_picot
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

runner = CliRunner()


def _mk_project(tmp_path: Path, slug: str = "principal") -> tuple[Path, Path]:
    """Cria a raiz do projeto (marcador ``.claude/pj_config.toml``) e um escopo
    vazio (``notes/``, ``writing/``, ``decisions/``). Devolve ``(pj_root, scope)``.
    """
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    scope = pj / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (scope / sub).mkdir(parents=True)
    return pj, scope


def _bootstrap(tmp_path: Path, slug: str = "principal") -> tuple[Path, Path]:
    """``_mk_project`` + ``protocol.md`` (escopo) e ``project_guide.md`` (projeto)."""
    pj, scope = _mk_project(tmp_path, slug)
    (scope / "writing" / "protocol.md").write_text("# Protocolo\n")
    (pj / "docs" / "project_guide.md").write_text("---\ntitle: x\n---\n\n# Projeto\n")
    return pj, scope


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
    pj, scope = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(scope), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["protocol_status"] == "inserted"
    assert payload["project_status"] == "inserted"


def test_protocol_diff_no_baseline(tmp_path: Path) -> None:
    pj, scope = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "diff", str(scope), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["changes"] == []
    assert payload["has_structural"] is False
    assert payload["drift"] == []


def test_protocol_diff_reports_manuscript_drift_for_explicit_draft(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
    writing = scope / "writing"
    (writing / "protocol.md").write_text("Coleta entre março e agosto de 2023.\n")
    (writing / "paper.md").write_text("Between March and July 2023.\n")
    (writing / "other.md").write_text("Between May and June 2023.\n")
    result = runner.invoke(app, ["protocol", "diff", str(writing / "paper.md"), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["missing"] is True
    drift = payload["drift"]
    assert isinstance(drift, list)
    assert [(d["kind"], d["draft_locs"]) for d in drift] == [
        ("window", ["docs/studies/principal/writing/paper.md:1"])
    ]


def test_protocol_propagate_from_pj_root_uses_the_single_scope(tmp_path: Path) -> None:
    """Regressão dupla. (a) Apontar `propagate` pra raiz do pj_* devolvia
    `protocol_status: "missing"` em silêncio — `writing_dir(<raiz>)` virava
    `<raiz>/writing/protocol.md`, que nunca existe. (b) Depois passou a sair
    com exit 1, quebrando a invocação bare das skills (nenhuma passa `--path`).
    Com um escopo só, `find_scope_root` resolve sozinho."""
    pj, scope = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["protocol_status"] == "inserted"
    assert "<!-- picot:begin " in (scope / "writing" / "protocol.md").read_text(encoding="utf-8")


def test_protocol_propagate_sem_escopo_nenhum_falha_com_add_study(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code != 0
    assert "escopo" in result.output.lower()
    assert "prumo add study" in result.output


def test_protocol_propagate_com_varios_escopos_exige_escolha(tmp_path: Path) -> None:
    """Ambiguidade real continua exigindo decisão explícita, com os slugs na
    mensagem — nada de escolher um escopo em silêncio."""
    pj, _scope = _bootstrap(tmp_path, "artigo-a")
    for sub in ("notes", "writing", "decisions"):
        (pj / "docs" / "studies" / "artigo-b" / sub).mkdir(parents=True)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code != 0
    assert "artigo-a" in result.output
    assert "artigo-b" in result.output


def test_protocol_propagate_missing_picot(tmp_path: Path) -> None:
    _pj, scope = _bootstrap(tmp_path)  # sem picot.toml
    result = runner.invoke(app, ["protocol", "propagate", str(scope), "--json"])
    assert result.exit_code != 0
    assert "picot.toml" in result.output or "picot.toml" in result.stderr


def test_protocol_detect_mode_init(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
    result = runner.invoke(app, ["protocol", "detect-mode", str(scope)])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "init"


def test_protocol_init_writes_and_emits(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
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
        ["protocol", "init", "--date", "2026-06-14", "--path", str(scope), "--json"],
        input=json.dumps(payload),
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["adr_path"])).exists()


def test_protocol_init_invalid_payload_fails(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
    result = runner.invoke(
        app, ["protocol", "init", "--date", "2026-06-14", "--path", str(scope)], input="{}"
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


def test_protocol_adr_writes(tmp_path: Path) -> None:
    pj, scope = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(
        app,
        [
            "protocol",
            "adr",
            "--motivation",
            "novo dataset",
            "--slug",
            "novo-dataset",
            "--date",
            "2026-06-14",
            "--path",
            str(scope),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["adr_path"])).exists()


def test_protocol_adr_missing_picot_fails(tmp_path: Path) -> None:
    _pj, scope = _bootstrap(tmp_path)  # sem picot.toml
    result = runner.invoke(
        app,
        [
            "protocol",
            "adr",
            "--motivation",
            "x",
            "--slug",
            "y",
            "--date",
            "2026-06-14",
            "--path",
            str(scope),
        ],
    )
    assert result.exit_code == 1
