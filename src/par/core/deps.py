"""Detecção de dependências externas do ecossistema prumo.

prumo orquestra ferramentas que vivem fora do pacote Python:

- **qmd** — CLI de busca (BM25 + vector + rerank) que os modos ``wiki query``,
  ``wiki ingest`` e ``wiki study`` usam. Binário no PATH.
- **Zotero + Better BibTeX** — citation keys, auto-export do ``.bib``
  (``paper connect``) e vínculo das citações do docx.
- **Pandoc** — ``write export``/``write compose``; o do PATH ou o que vem dentro
  do Zettlr.app, com o piso 3.8.2 (ADR-0037).

Este módulo é puramente declarativo: retorna ``DepStatus`` por dependência.
Quem decide o que fazer (warning, erro, JSON) é o ``doctor``. Centralizar aqui
evita espalhar ``shutil.which`` e checagem de porta pelo CLI.
"""

from __future__ import annotations

import http.client
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"
_ZETTLR_PANDOC = Path("/Applications/Zettlr.app/Contents/Resources/pandoc")
_PANDOC_FLOOR = (3, 8, 2)


@dataclass
class DepStatus:
    """Estado de uma dependência externa."""

    name: str
    present: bool
    required_by: list[str]
    detail: str
    hint: str
    version: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "required_by": self.required_by,
            "detail": self.detail,
            "hint": self.hint,
            "version": self.version,
        }


def _binary_on_path(name: str) -> str | None:
    """Caminho do binário no PATH, ou ``None``. Seam testável."""
    return shutil.which(name)


def zotero_base() -> str:
    """Base HTTP do Zotero local (connector + Better BibTeX). Override: ``PRUMO_ZOTERO_BASE`` (ADR-0007)."""
    return os.environ.get("PRUMO_ZOTERO_BASE") or _DEFAULT_ZOTERO_BASE  # "" = padrão


def bbt_rpc_url() -> str:
    """Endpoint JSON-RPC do Better BibTeX — único no pacote (ADR-0037)."""
    return f"{zotero_base()}/better-bibtex/json-rpc"


def in_claude_sandbox() -> bool:
    """``True`` dentro do sandbox do Bash do Claude Code, que não alcança o Zotero do host."""
    return os.environ.get("SANDBOX_RUNTIME") == "1"


def pandoc_path() -> str | None:
    """pandoc do PATH; senão o que vem dentro do Zettlr.app (macOS). Seam: ``_binary_on_path``/``_ZETTLR_PANDOC``."""
    found = _binary_on_path("pandoc")
    if found:
        return found
    if _ZETTLR_PANDOC.is_file() and os.access(_ZETTLR_PANDOC, os.X_OK):
        return str(_ZETTLR_PANDOC)
    return None


def _pandoc_version(path: str, timeout: float = 5.0) -> str | None:
    """``"3.10.1"`` a partir da 1ª linha de ``pandoc --version``; ``None`` se falhar. Seam testável."""
    try:
        proc = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (proc.stdout or "").splitlines()
    first_line = lines[0] if lines else ""
    m = re.match(r"pandoc(?:\.exe)?\s+(\d+(?:\.\d+)*)", first_line)
    return m.group(1) if m else None


_SUPPORTED_ZOTERO_MAJOR = 9


@dataclass(frozen=True)
class _BbtProbe:
    status: int | None  # None = nada escutando
    zotero_version: str | None  # header X-Zotero-Version, presente até no 404


def _bbt_probe(timeout: float = 2.0) -> _BbtProbe:
    """GET {zotero_base()}/better-bibtex/cayw?probe=true. 200 = BBT carregado
    ('ready' ou 'starting'); 404 = Zotero sem BBT ou BBT ainda iniciando. Não
    depende da API local. Seam testável."""
    url = f"{zotero_base()}/better-bibtex/cayw?probe=true"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return _BbtProbe(int(resp.status), resp.headers.get("X-Zotero-Version"))
    except urllib.error.HTTPError as exc:
        headers = exc.headers
        return _BbtProbe(int(exc.code), headers.get("X-Zotero-Version") if headers else None)
    except (OSError, http.client.HTTPException):
        return _BbtProbe(None, None)


def _zotero_major(version: str | None) -> int | None:
    """Major numérico de ``version`` (ex. ``"9.0.3"`` → 9), ou ``None``."""
    if not version:
        return None
    m = re.match(r"(\d+)", version)
    return int(m.group(1)) if m else None


_PANDOC_ABSENT_DETAIL = "pandoc não encontrado (nem no PATH nem no Zettlr.app)"
_PANDOC_ABSENT_HINT = (
    "Instale o pandoc 3.8.2 ou mais novo. macOS: `brew install pandoc` (ou instale o "
    "Zettlr, que já traz um). Linux: pacote oficial em https://github.com/jgm/pandoc/releases "
    "(o do apt costuma ser antigo). Depois rode: prumo doctor"
)
_PANDOC_OLD_HINT = (
    "O pandoc {v} é anterior a 3.8.2: tabelas numeradas (`{{#tbl:…}}`) falham no export. "
    "Atualize (macOS: `brew upgrade pandoc`; Linux: pacote oficial em "
    "https://github.com/jgm/pandoc/releases) e rode: prumo doctor"
)


def _pandoc_status() -> DepStatus:
    """Linha ``pandoc`` do doctor: presença e piso 3.8.2 (ADR-0037).

    Versão não detectada conta como presente — o mesmo fail-safe da linha
    ``zotero``. O export não checa versão; quem avisa é o doctor.
    """
    required_by = ["write export", "write compose"]
    path = pandoc_path()
    if not path:
        return DepStatus(
            name="pandoc",
            present=False,
            required_by=required_by,
            detail=_PANDOC_ABSENT_DETAIL,
            hint=_PANDOC_ABSENT_HINT,
        )
    where = "do Zettlr.app" if path == str(_ZETTLR_PANDOC) else f"em {path}"
    version = _pandoc_version(path)
    if version is None:
        return DepStatus(
            name="pandoc",
            present=True,
            required_by=required_by,
            detail=f"pandoc {where} (versão não detectada)",
            hint="",
        )
    below_floor = tuple(int(p) for p in re.findall(r"\d+", version)) < _PANDOC_FLOOR
    return DepStatus(
        name="pandoc",
        present=not below_floor,
        required_by=required_by,
        detail=f"pandoc {version} {where}",
        hint=_PANDOC_OLD_HINT.format(v=version) if below_floor else "",
        version=version,
    )


_ZOTERO_REQUIRED_BY = ["paper connect", "write export --to docx (vínculo com a biblioteca)"]
_ZOTERO_CLOSED_HINT = (
    "Abra o Zotero 9 ou mais novo, com o Better BibTeX, e rode: prumo doctor. "
    "Só o `prumo paper connect` e o vínculo das citações do docx precisam dele; "
    "o resto do PAR funciona sem ele."
)
#: Receita para o ``prumo`` sair do sandbox do Bash do Claude Code de vez — fonte
#: única (Princípio I) para o doctor, o ``paper connect`` e o ``write export``.
SANDBOX_EXCLUDE_HINT = (
    'Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em '
    "`sandbox.excludedCommands` no `~/.claude/settings.json`."
)
_ZOTERO_SANDBOX_HINT = (
    "Peça para repetir fora do sandbox (o Claude pede permissão): prumo doctor. "
    + SANDBOX_EXCLUDE_HINT
)
_ZOTERO_OLD_HINT = (
    "Atualize para o Zotero 9+: baixe em https://www.zotero.org/download, instale e "
    "reabra o app. Depois atualize o Better BibTeX em Tools → Plugins se ele avisar "
    "(o BBT acompanha o major do Zotero)."
)
#: Dica de Better BibTeX ausente ou iniciando (E12, HTTP 404) — o ``paper connect``
#: reusa o mesmo texto quando o JSON-RPC do BBT responde 404.
ZOTERO_NO_BBT_HINT = (
    "Sem Better BibTeX (ou ainda iniciando — aguarde e rode prumo doctor). Para "
    "instalar: baixe o .xpi em https://github.com/retorquere/zotero-better-bibtex/releases "
    "e, no Zotero, Tools → Plugins → ⚙ → Install Plugin From File. Depois rode: prumo doctor"
)


def _zotero_status() -> DepStatus:
    """Linha ``zotero`` do doctor: uma sonda só ao Better BibTeX (ADR-0037, B10).

    Não depende da API local do Zotero (o toggle "Allow other applications").
    Estados, o primeiro que casa decide: E10/E11 (nada escutando), E14 (major
    abaixo de 9, inclusive no 404), E12 (404), E13 (outro HTTP), ✓ (200).
    """
    base = zotero_base()
    probe = _bbt_probe()
    v = probe.zotero_version
    major = _zotero_major(v)

    present = False
    hint = ""
    if probe.status is None:
        if in_claude_sandbox():
            detail = f"o sandbox do Claude Code não deixa este comando falar com o Zotero em {base}"
            hint = _ZOTERO_SANDBOX_HINT
        else:
            detail = f"nada escutando em {base}"
            hint = _ZOTERO_CLOSED_HINT
    elif major is not None and major < _SUPPORTED_ZOTERO_MAJOR:
        detail = (
            f"Zotero {v} rodando em {base} — abaixo do par suportado "
            f"(Zotero {_SUPPORTED_ZOTERO_MAJOR}+ com Better BibTeX)"
        )
        hint = _ZOTERO_OLD_HINT
    elif probe.status == 404:
        opened = f"Zotero {v} aberto" if v else "Zotero aberto"
        detail = f"{opened} em {base}, mas o Better BibTeX não respondeu (HTTP 404)"
        hint = ZOTERO_NO_BBT_HINT
    elif probe.status != 200:
        detail = f"o Zotero respondeu HTTP {probe.status} em /better-bibtex/cayw"
        hint = "Reinicie o Zotero e rode: prumo doctor"
    else:
        present = True
        detail = (
            f"Better BibTeX respondendo em {base} — Zotero {v}"
            if v
            else f"Better BibTeX respondendo em {base} (versão não detectada)"
        )
    return DepStatus(
        name="zotero",
        present=present,
        required_by=list(_ZOTERO_REQUIRED_BY),
        detail=detail,
        hint=hint,
        version=v,
    )


def check_external_deps() -> list[DepStatus]:
    """Audita dependências externas. Nunca levanta — sempre retorna a lista."""
    statuses: list[DepStatus] = []

    qmd_path = _binary_on_path("qmd")
    statuses.append(
        DepStatus(
            name="qmd",
            present=qmd_path is not None,
            required_by=["wiki query", "wiki ingest", "wiki study"],
            detail=f"qmd em {qmd_path}" if qmd_path else "qmd não está no PATH",
            hint=(
                "Instale o qmd: `npm install -g @tobilu/qmd` "
                "(ou `bun install -g @tobilu/qmd`) e indexe o projeto: `prumo wiki index`."
            ),
        )
    )

    statuses.append(_zotero_status())
    statuses.append(_pandoc_status())

    return statuses
