"""Rodadas de modelo em ``experiments/<run_id>/``, todas no mesmo formato.

Uso, no fim do notebook de ajuste::

    from __pkg__.runs import start_run

    run = start_run("baseline", seed=42, scope="estudo")
    run.log_params({"C": 0.1})
    run.log_metrics([{"metrica": "auc", "valor": 0.81}])
    run.save_fig(fig, "calibracao")
    run.finish("O que mudou nesta rodada e o que ela mostrou.")

A pasta da rodada recebe ``run.json`` (parâmetros, semente, escopo, commit do git e
versões), ``metrics.csv``, ``figs/`` e um ``README.md`` gerado do resumo. Bundle de
modelo (``.joblib``, ``.pkl``, ``.pt``) pode ir na pasta, mas fica fora do git.

Grave só métrica agregada, nunca linha por paciente: a regra de célula mínima do
projeto (``AGENTS.md``) vale para o ``metrics.csv`` e para as figuras.

Este arquivo é código do projeto, copiado pelo ``prumo add ml``: edite à vontade.
"""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

#: Bibliotecas cuja versão entra no ``run.json`` quando instaladas.
TRACKED_LIBRARIES = (
    "numpy",
    "pandas",
    "polars",
    "scikit-learn",
    "statsmodels",
    "scipy",
    "xgboost",
    "lightgbm",
    "torch",
    "lightning",
)


class _Figure(Protocol):
    def savefig(self, fname: Path, **kwargs: Any) -> None: ...


def _git(args: list[str], cwd: Path) -> str | None:
    """Saída de ``git <args>`` em ``cwd``, ou ``None`` sem git ou fora de um repositório."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def find_project_root(start: Path | None = None) -> Path:
    """Primeira pasta acima de ``start`` (ou do diretório atual) com ``pyproject.toml``."""
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(
        f"Nenhum pyproject.toml acima de {cur}. Passe a raiz do projeto: start_run(..., root=...)."
    )


def _library_versions() -> dict[str, str]:
    versions = {}
    for name in TRACKED_LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return versions


def _new_run_dir(experiments: Path, name: str) -> Path:
    base = f"{date.today().isoformat()}_{name}"
    candidate = experiments / base
    n = 2
    while candidate.exists():
        candidate = experiments / f"{base}_{n}"
        n += 1
    candidate.mkdir(parents=True)
    return candidate


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


@dataclass
class Run:
    """Uma rodada aberta. Crie com :func:`start_run`."""

    dir: Path
    info: dict[str, Any]
    metrics: list[dict[str, Any]] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)

    def _save_info(self) -> None:
        text = json.dumps(self.info, ensure_ascii=False, indent=2, default=str)
        (self.dir / "run.json").write_text(text + "\n", encoding="utf-8")

    def log_params(self, params: dict[str, Any]) -> None:
        """Acrescenta parâmetros ao ``run.json`` (chave repetida é sobrescrita)."""
        self.info["params"].update(params)
        self._save_info()

    def log_metrics(self, rows: list[dict[str, Any]] | dict[str, Any]) -> None:
        """Acrescenta linhas ao ``metrics.csv``. Um ``dict`` só vira uma linha."""
        self.metrics.extend([rows] if isinstance(rows, dict) else rows)
        columns: list[str] = []
        for row in self.metrics:
            columns += [k for k in row if k not in columns]
        with (self.dir / "metrics.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self.metrics)

    def save_fig(self, fig: _Figure, name: str, *, dpi: int = 300) -> Path:
        """Grava ``fig`` em ``figs/<name>.png``."""
        figs = self.dir / "figs"
        figs.mkdir(exist_ok=True)
        path = figs / f"{name}.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        self.figures.append(path.name)
        return path

    def finish(self, summary: str) -> Path:
        """Fecha a rodada: grava o resumo no ``run.json`` e escreve o ``README.md``."""
        self.info["summary"] = summary
        self.info["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_info()
        (self.dir / "README.md").write_text(self._readme(), encoding="utf-8")
        return self.dir

    def _readme(self) -> str:
        git = self.info["git"]
        commit = "sem git" if git["commit"] is None else git["commit"][:12]
        if git["dirty"]:
            commit += " (com mudanças não commitadas: o código desta rodada não está no commit)"
        lines = [
            f"# {self.info['run_id']}",
            "",
            self.info["summary"],
            "",
            f"- Escopo: {self.info['scope'] or '—'}",
            f"- Semente: {self.info['seed']}",
            f"- Commit: {commit}",
            f"- Início: {self.info['started_at']}",
            f"- Fim: {self.info['finished_at']}",
            "",
            "## Parâmetros",
            "",
            "| Parâmetro | Valor |",
            "|---|---|",
            *(f"| {_md(k)} | {_md(v)} |" for k, v in self.info["params"].items()),
        ]
        if self.metrics:
            columns: list[str] = []
            for row in self.metrics:
                columns += [k for k in row if k not in columns]
            lines += [
                "",
                "## Métricas",
                "",
                "| " + " | ".join(columns) + " |",
                "|" + "---|" * len(columns),
                *(
                    "| " + " | ".join(_md(r.get(c, "")) for c in columns) + " |"
                    for r in self.metrics
                ),
            ]
        if self.figures:
            lines += ["", "## Figuras", "", *(f"- [{f}](figs/{f})" for f in self.figures)]
        return "\n".join(lines) + "\n"


def start_run(name: str, *, seed: int, scope: str | None = None, root: Path | None = None) -> Run:
    """Abre ``experiments/<AAAA-MM-DD>_<name>/`` na raiz do projeto e grava o ``run.json``.

    Nome repetido no mesmo dia ganha sufixo ``_2``, ``_3``. ``root`` default: a pasta com
    ``pyproject.toml`` acima do diretório atual.
    """
    project = root or find_project_root()
    run_dir = _new_run_dir(project / "experiments", name)
    status = _git(["status", "--porcelain"], project)
    info: dict[str, Any] = {
        "schema": 1,
        "run_id": run_dir.name,
        "name": name,
        "scope": scope,
        "seed": seed,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "params": {},
        "git": {
            "commit": _git(["rev-parse", "HEAD"], project),
            "dirty": None if status is None else bool(status),
        },
        "python": platform.python_version(),
        "libraries": _library_versions(),
    }
    run = Run(dir=run_dir, info=info)
    run._save_info()
    return run
