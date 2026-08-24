"""Unit tests para core/packaging.py — os checks de empacotamento do doctor.

Todos determinísticos e sem LLM (Princípio II). Ver ADR-0027, D6.
"""

from __future__ import annotations

import json
from pathlib import Path

from prumo_assist.core import packaging

_PYPROJECT_VIRTUAL = '[project]\nname = "pj_demo"\nversion = "0.1.0"\n'
_PYPROJECT_INSTALAVEL = (
    '[project]\nname = "pj_demo"\nversion = "0.1.0"\n\n'
    '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
)


def _codigo(root: Path, rel: str = "src/demo/prep.py") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n", encoding="utf-8")


def _site_packages(root: Path, dist: str | None) -> None:
    """Simula um `.venv` com (ou sem) o projeto instalado."""
    sp = root / ".venv" / "lib" / "python3.13" / "site-packages"
    sp.mkdir(parents=True)
    if dist is not None:
        (sp / dist).mkdir()


def _codigos(issues: list[str]) -> set[str]:
    return {i.split("]")[0].lstrip("[") for i in issues}


# ---------------------------------------------------------------------------
# projeto_nao_instalavel
# ---------------------------------------------------------------------------


def test_projeto_com_codigo_e_sem_build_system_e_acusado(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_VIRTUAL, encoding="utf-8")
    _codigo(tmp_path)

    issues = packaging.packaging_issues(tmp_path)

    assert "projeto_nao_instalavel" in _codigos(issues)
    assert any("uv sync" in i for i in issues)


def test_projeto_sem_codigo_proprio_nao_e_acusado(tmp_path: Path) -> None:
    """Virtual project que só declara dependências é legítimo — nada a dizer."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_VIRTUAL, encoding="utf-8")

    assert packaging.packaging_issues(tmp_path) == []


def test_projeto_sem_pyproject_nao_e_acusado(tmp_path: Path) -> None:
    """`pj_*` sem o módulo `code` não tem opinião de empacotamento."""
    assert packaging.packaging_issues(tmp_path) == []


def test_projeto_instalavel_e_sincronizado_passa_limpo(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path)
    _site_packages(tmp_path, "pj_demo-0.1.0.dist-info")

    assert packaging.packaging_issues(tmp_path) == []


# ---------------------------------------------------------------------------
# pacote_sem_nome
# ---------------------------------------------------------------------------


def test_modulo_solto_na_raiz_de_src_e_acusado(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path, "src/prep.py")
    _site_packages(tmp_path, "pj_demo-0.1.0.dist-info")

    issues = packaging.packaging_issues(tmp_path)

    assert "pacote_sem_nome" in _codigos(issues)


def test_src_src_e_acusado(tmp_path: Path) -> None:
    """`from src.x import y` — o pacote se chama literalmente `src`."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path, "src/src/prep.py")
    _site_packages(tmp_path, "pj_demo-0.1.0.dist-info")

    issues = packaging.packaging_issues(tmp_path)

    assert "pacote_sem_nome" in _codigos(issues)


# ---------------------------------------------------------------------------
# sys_path_hack
# ---------------------------------------------------------------------------


def test_sys_path_insert_em_notebook_e_acusado(tmp_path: Path) -> None:
    nb = tmp_path / "notebooks" / "estudo" / "03_desc.ipynb"
    nb.parent.mkdir(parents=True)
    nb.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["import sys\n", "sys.path.insert(0, PROJECT_ROOT)\n"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    issues = packaging.packaging_issues(tmp_path)

    assert "sys_path_hack" in _codigos(issues)
    assert any("03_desc.ipynb" in i for i in issues)


def test_sys_path_append_em_modulo_e_acusado(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path)
    (tmp_path / "src" / "demo" / "prep.py").write_text(
        "import sys\nsys.path.append('..')\n", encoding="utf-8"
    )
    _site_packages(tmp_path, "pj_demo-0.1.0.dist-info")

    assert "sys_path_hack" in _codigos(packaging.packaging_issues(tmp_path))


def test_mencao_a_sys_path_em_prosa_nao_dispara(tmp_path: Path) -> None:
    """O check olha código, não documentação — `docs/` está fora do alcance."""
    doc = tmp_path / "docs" / "studies" / "s" / "notes" / "a.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("Não use `sys.path.insert(0, ...)` neste projeto.\n", encoding="utf-8")

    assert packaging.packaging_issues(tmp_path) == []


# ---------------------------------------------------------------------------
# projeto_nao_sincronizado
# ---------------------------------------------------------------------------


def test_venv_sem_o_projeto_instalado_e_acusado(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path)
    _site_packages(tmp_path, "pandas-2.2.0.dist-info")

    issues = packaging.packaging_issues(tmp_path)

    assert "projeto_nao_sincronizado" in _codigos(issues)
    assert any("uv sync" in i for i in issues)


def test_sem_venv_nao_ha_o_que_afirmar(tmp_path: Path) -> None:
    """Sem `.venv/` o pesquisador pode estar em conda/system — não inventamos."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_INSTALAVEL, encoding="utf-8")
    _codigo(tmp_path)

    assert "projeto_nao_sincronizado" not in _codigos(packaging.packaging_issues(tmp_path))


def test_dist_info_normaliza_hifen_e_underscore(tmp_path: Path) -> None:
    """`name = "pj-demo"` instala como `pj_demo-0.1.0.dist-info` (PEP 427)."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pj-demo"\nversion = "0.1.0"\n\n'
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
        encoding="utf-8",
    )
    _codigo(tmp_path)
    _site_packages(tmp_path, "pj_demo-0.1.0.dist-info")

    assert packaging.packaging_issues(tmp_path) == []


def test_pyproject_ilegivel_nao_derruba_o_doctor(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\nname = ", encoding="utf-8")
    _codigo(tmp_path)

    assert packaging.packaging_issues(tmp_path) == []
