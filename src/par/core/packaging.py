"""Checks de empacotamento do ``pj_*`` para o ``prumo doctor`` (ADR-0027).

Quatro perguntas determinísticas, sem LLM (Princípio II), todas com o comando
de correção embutido na mensagem:

- ``projeto_nao_instalavel`` — há código próprio, mas o ``pyproject.toml`` não
  declara ``[build-system]``; o uv trata o projeto como *virtual project* e o
  código nunca entra no ``.venv``.
- ``pacote_sem_nome`` — o código está solto em ``src/`` (ou num ``src/src/``),
  então o "pacote" é um namespace implícito e o import mente sobre o nome.
- ``sys_path_hack`` — sobrou ``sys.path.insert``/``append`` em notebook ou
  módulo, o sintoma do layout antigo.
- ``projeto_nao_sincronizado`` — o projeto é instalável, existe ``.venv/``, e
  o pacote não está lá dentro: falta rodar ``uv sync``.

O que NÃO entra aqui, deliberadamente: "import de módulo não declarado". Ele
exigiria resolver o grafo de imports contra os ``[dependency-groups]``, que são
opt-in (``uv sync --group tabular``), tornando o falso-positivo o caso comum.
Isso é trabalho de ``deptry`` ou do ``ruff``, não do doctor (ADR-0027, D6).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

#: Padrão do sintoma. Cobre `sys.path.insert(...)` e `sys.path.append(...)`
#: com espaço arbitrário, que é como o anti-padrão aparece na prática.
_SYS_PATH_RE = re.compile(r"sys\s*\.\s*path\s*\.\s*(insert|append)\s*\(")

#: Onde procurar código. `docs/` fica de fora de propósito: prosa que MENCIONA
#: `sys.path` (inclusive esta regra, distribuída como rule do módulo `code`)
#: não é ocorrência do defeito.
_CODE_DIRS = ("src", "notebooks")

#: Teto de arquivos varridos. Notebook com saída embutida é grande, e o doctor
#: precisa continuar barato o suficiente para rodar a cada sessão.
_MAX_FILES = 500


def _read_pyproject(root: Path) -> dict[str, object] | None:
    """Parseia ``pyproject.toml``; ``None`` se ausente ou ilegível.

    TOML quebrado não é problema DESTE check — quem reclama de sintaxe é o uv,
    com mensagem melhor. Aqui, ilegível significa "não sei afirmar nada".
    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return None


def _iter_code_files(root: Path) -> list[Path]:
    """Arquivos de código do projeto (`.py` e `.ipynb`) sob :data:`_CODE_DIRS`."""
    found: list[Path] = []
    for rel in _CODE_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in {".py", ".ipynb"} and path.is_file():
                found.append(path)
                if len(found) >= _MAX_FILES:
                    return found
    return found


def _has_own_code(root: Path) -> bool:
    """``True`` se existe ao menos um ``.py`` sob ``src/``."""
    src = root / "src"
    return src.is_dir() and any(src.rglob("*.py"))


def _package_dirs(root: Path) -> list[Path]:
    """Diretórios filhos diretos de ``src/`` que parecem pacote."""
    src = root / "src"
    if not src.is_dir():
        return []
    return [p for p in sorted(src.iterdir()) if p.is_dir() and not p.name.startswith(".")]


def _dist_installed(root: Path, project_name: str) -> bool | None:
    """O projeto está instalado no ``.venv``? ``None`` se não há ``.venv``.

    Compara nomes normalizados (PEP 427: hífen vira underscore no nome do
    diretório ``.dist-info``), então ``name = "pj-demo"`` casa com
    ``pj_demo-0.1.0.dist-info``.
    """
    site_packages = sorted((root / ".venv").glob("lib/*/site-packages"))
    if not site_packages:
        # Windows põe em `.venv/Lib/site-packages`.
        site_packages = sorted((root / ".venv").glob("Lib/site-packages"))
    if not site_packages:
        return None
    alvo = project_name.replace("-", "_").lower()
    for sp in site_packages:
        for dist in sp.glob("*.dist-info"):
            if dist.name.split("-")[0].replace("-", "_").lower() == alvo:
                return True
    return False


def packaging_issues(root: Path) -> list[str]:
    """Lista de problemas de empacotamento de ``root`` (vazia = tudo certo)."""
    issues: list[str] = []
    data = _read_pyproject(root)

    if data is not None and _has_own_code(root):
        project = data.get("project")
        name = project.get("name", "") if isinstance(project, dict) else ""
        project_name = name if isinstance(name, str) else ""

        if "build-system" not in data:
            issues.append(
                "[projeto_nao_instalavel] há código próprio em `src/` mas o `pyproject.toml` "
                "não declara `[build-system]` — o uv trata o projeto como *virtual project* e "
                "o pacote nunca entra no `.venv`, o que força `sys.path.insert` nos notebooks. "
                "Peça ao agente: `adeque este projeto ao layout instalável` (ADR-0027). "
                "Depois: `uv sync`."
            )
        elif project_name:
            instalado = _dist_installed(root, project_name)
            if instalado is False:
                issues.append(
                    f"[projeto_nao_sincronizado] `{project_name}` declara `[build-system]` mas "
                    "não está instalado no `.venv/` — o import de código próprio vai falhar. "
                    "Rode: `uv sync`."
                )

        soltos = sorted(p.name for p in (root / "src").glob("*.py"))
        if soltos:
            issues.append(
                f"[pacote_sem_nome] há módulo solto na raiz de `src/` ({', '.join(soltos)}) — "
                "sem um diretório de pacote nomeado o import depende de `src/` estar no "
                "`sys.path`. Mova para `src/<pacote>/`, onde `<pacote>` é o nome do projeto "
                "sem o prefixo `pj_` (ADR-0027)."
            )
        if any(p.name == "src" for p in _package_dirs(root)):
            issues.append(
                "[pacote_sem_nome] existe `src/src/` — o pacote se chama literalmente `src` e "
                "o import vira `from src.… import …`, que quebra no dia em que o projeto for "
                "instalado. Renomeie para o nome do projeto sem o prefixo `pj_` (ADR-0027)."
            )

    hits: list[str] = []
    for path in _iter_code_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if _SYS_PATH_RE.search(text):
            hits.append(path.relative_to(root).as_posix())
    if hits:
        amostra = ", ".join(hits[:3]) + (f" (+{len(hits) - 3})" if len(hits) > 3 else "")
        issues.append(
            f"[sys_path_hack] `sys.path.insert`/`append` em {amostra} — o IDE não segue "
            "`sys.path`, então o import fica unresolved e o `# noqa: E402` vira permanente. "
            "Com o projeto instalável (`uv sync`) o import resolve sozinho: apague o "
            "preâmbulo e importe pelo nome do pacote (ADR-0027)."
        )

    return issues
