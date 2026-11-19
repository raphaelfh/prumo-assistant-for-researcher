"""Grupo `viz` do módulo `code` instalável em toda versão que o template aceita.

Num projeto com `requires-python >= 3.13`, o uv pode escolher Python 3.14. Lá o
`ydata-profiling` não instala (fixa `numba<0.63`, sem wheel 3.14) e `matplotlib < 3.10.5`
entra em recursão no `deepcopy` de `Path`. Verificado num projeto sintético: os quatro
tipos de notebook rodam em 3.13 e em 3.14 com as restrições abaixo.
"""

from __future__ import annotations

import tomllib

from packaging.requirements import Requirement

from par.core.paths import resolve_resource

_PYPROJECT = resolve_resource("templates") / "modules" / "code" / "pyproject.toml"


def _viz(python: str) -> dict[str, str]:
    """Requisitos do grupo `viz` que valem em ``python`` (nome → especificador)."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for raw in data["dependency-groups"]["viz"]:
        req = Requirement(raw)
        if req.marker is None or req.marker.evaluate({"python_version": python}):
            out[req.name] = str(req.specifier)
    return out


def test_python_314_nao_instala_ydata_profiling_e_exige_matplotlib_corrigido() -> None:
    viz = _viz("3.14")
    assert "ydata-profiling" not in viz
    assert viz["matplotlib"] == ">=3.10.5"


def test_python_313_mantem_ydata_profiling() -> None:
    viz = _viz("3.13")
    assert "ydata-profiling" in viz
    assert "matplotlib" in viz
