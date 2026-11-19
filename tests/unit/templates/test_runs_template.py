"""Helper de rodada que o módulo `ml` copia para o projeto (`src/<pkg>/runs.py`, ADR-0047).

O arquivo é importado direto do template, de uma cópia em `tmp_path`: é código do
projeto, não do `prumo`. Dado sintético; `git` mockado no seam `_git`.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from par.core.paths import resolve_resource

_TEMPLATE = resolve_resource("templates") / "modules" / "ml" / "src" / "__pkg__" / "runs.py"


@pytest.fixture
def runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    copy = tmp_path / "runs_copy.py"
    copy.write_text(_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("runs_copy", copy)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `@dataclass` resolve anotações pelo módulo em `sys.modules`.
    monkeypatch.setitem(sys.modules, "runs_copy", module)
    spec.loader.exec_module(module)
    answers = {"rev-parse": "abc123def4567890", "status": " M notebooks/x.py"}
    monkeypatch.setattr(module, "_git", lambda args, cwd: answers[args[0]])
    return module


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "pj_exemplo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'pj-exemplo'\n", encoding="utf-8")
    return root


class _Fig:
    def savefig(self, fname: Path, **kwargs: Any) -> None:
        Path(fname).write_bytes(b"png sintetico")


def test_rodada_completa_grava_os_quatro_artefatos(runs: Any, project: Path) -> None:
    run = runs.start_run("baseline", seed=42, scope="estudo", root=project)
    assert run.dir == project / "experiments" / f"{date.today().isoformat()}_baseline"
    run.log_params({"C": 0.1})
    run.log_metrics([{"metrica": "auc", "valor": 0.8}])
    run.log_metrics({"metrica": "brier", "valor": 0.1, "nota": "sintético"})
    run.save_fig(_Fig(), "calibracao")
    assert run.finish("Rodada sintética de teste.") == run.dir

    info = json.loads((run.dir / "run.json").read_text(encoding="utf-8"))
    assert info["seed"] == 42
    assert info["scope"] == "estudo"
    assert info["params"] == {"C": 0.1}
    assert info["git"] == {"commit": "abc123def4567890", "dirty": True}
    assert info["summary"] == "Rodada sintética de teste."
    assert "python" in info and isinstance(info["libraries"], dict)

    with (run.dir / "metrics.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["metrica"] for r in rows] == ["auc", "brier"]
    assert rows[1]["nota"] == "sintético"

    assert (run.dir / "figs" / "calibracao.png").is_file()
    readme = (run.dir / "README.md").read_text(encoding="utf-8")
    assert "Rodada sintética de teste." in readme
    assert "abc123def456" in readme and "não commitadas" in readme
    assert "| C | 0.1 |" in readme
    assert "[calibracao.png](figs/calibracao.png)" in readme


def test_nome_repetido_no_dia_ganha_sufixo(runs: Any, project: Path) -> None:
    a = runs.start_run("baseline", seed=1, root=project)
    b = runs.start_run("baseline", seed=1, root=project)
    c = runs.start_run("baseline", seed=1, root=project)
    assert b.dir.name == f"{a.dir.name}_2"
    assert c.dir.name == f"{a.dir.name}_3"


def test_sem_git_os_campos_ficam_nulos(
    runs: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs, "_git", lambda args, cwd: None)
    run = runs.start_run("x", seed=0, root=project)
    run.finish("ok")
    info = json.loads((run.dir / "run.json").read_text(encoding="utf-8"))
    assert info["git"] == {"commit": None, "dirty": None}
    assert "sem git" in (run.dir / "README.md").read_text(encoding="utf-8")


def test_raiz_default_e_a_pasta_com_pyproject(
    runs: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nb = project / "notebooks" / "estudo"
    nb.mkdir(parents=True)
    monkeypatch.chdir(nb)
    run = runs.start_run("x", seed=0)
    assert run.dir.parent == project / "experiments"


def test_sem_pyproject_falha_com_a_correcao(runs: Any, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="root="):
        runs.find_project_root(tmp_path / "solto")
