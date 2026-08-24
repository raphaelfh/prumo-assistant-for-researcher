"""Pacote do projeto — código próprio, importável de qualquer lugar.

O projeto é instalado em editable no `.venv` (`uv sync`), então o import
resolve por instalação e não pelo `cwd`. Notebook, pytest, papermill, CI e
IDE veem exatamente a mesma coisa. Nada de `sys.path.insert`.

Onde cada coisa mora (ADR-0027):

- `__pkg__/<modulo>.py` — código usado por MAIS DE UM estudo ou notebook.
  A raiz do pacote é o compartilhado; é o caminho curto de propósito.
- `__pkg__/<estudo>/<modulo>.py` — código de um estudo só. O nome do
  subpacote vem do slug de `docs/studies/`, sem o prefixo numérico
  (`01_estudo` → `estudo`).

    from __pkg__.cohort import load_raw
    from __pkg__.estudo.prep import build_cohort
"""

from __future__ import annotations
