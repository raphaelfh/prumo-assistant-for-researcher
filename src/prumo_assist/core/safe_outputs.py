"""Fronteira de confidencialidade do ``pj_*`` para o ``prumo doctor``.

Uma pergunta só, barata e certa (Princípio II): dado bruto e trace local de
LLM estão fora do git? A rule ``.claude/rules/safe_outputs.md`` cobre o resto
(mínimo necessário, célula mínima), que exige semântica e não é checável sem
falso-positivo — ver ``docs/superpowers/specs/2026-09-12-safe-outputs-design.md``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: Pastas que nunca entram no histórico: ``content/`` guarda dado bruto e
#: processado (módulo ``data``); ``.prumo/`` guarda trace local de LLM.
PRIVATE_DIRS: tuple[str, ...] = ("content", ".prumo")

#: Placeholder de pasta vazia; rastreá-lo não expõe dado.
_PLACEHOLDER = ".gitkeep"


def _git(root: Path, *args: str) -> str | None:
    """Roda ``git`` em ``root``; stdout, ou ``None`` se falhou ou não há git.

    Seam dos testes: nenhum teste chama o binário de verdade.
    """
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    except (FileNotFoundError, OSError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def safe_outputs_issues(root: Path) -> list[str]:
    """Issue ``[dado_versionavel]`` (ou lista vazia). Fora de git, silêncio."""
    if _git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return []

    # Sonda com nome inexistente: arquivo rastreado nunca é "ignorado" para o
    # check-ignore, então testar um arquivo real mascararia o .gitignore.
    nao_ignorados = [
        d for d in PRIVATE_DIRS if _git(root, "check-ignore", "-q", f"{d}/__probe__") is None
    ]
    listagem = _git(root, "ls-files", "--", *PRIVATE_DIRS) or ""
    rastreados = [p for p in listagem.splitlines() if p and Path(p).name != _PLACEHOLDER]
    if not nao_ignorados and not rastreados:
        return []

    partes: list[str] = []
    if nao_ignorados:
        linhas = ", ".join(f"`{d}/`" for d in nao_ignorados)
        partes.append(f"{linhas} fora do `.gitignore` — adicione a(s) linha(s) {linhas}")
    if rastreados:
        amostra = ", ".join(rastreados[:5]) + (" …" if len(rastreados) > 5 else "")
        # Só as pastas com arquivo rastreado: pathspec sem casamento derruba o git rm.
        alvos = " ".join(d for d in PRIVATE_DIRS if any(p.startswith(f"{d}/") for p in rastreados))
        partes.append(
            f"{len(rastreados)} arquivo(s) rastreado(s) ({amostra}) — rode "
            f"`git rm -r --cached {alvos}` e faça commit; se já houve push, "
            "o dado continua no histórico remoto e precisa de reescrita"
        )
    return [
        "[dado_versionavel] dado do projeto pode vazar pelo git: "
        + "; ".join(partes)
        + ". Ver `.claude/rules/safe_outputs.md` (traga-a com `prumo update`)."
    ]
