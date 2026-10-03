"""Geração do perfil de export do Zettlr (Pandoc defaults file).

O Zettlr exporta via perfis — defaults files com ``reader`` e ``writer``
obrigatórios (exigência do assets manager dele). Este módulo gera o
``docs/templates/prumo-docx.yaml`` do projeto replicando o que dá para
reproduzir do ``prumo write export --to docx`` sem Python: a cadeia
``citeproc`` ANTES do ``zotero_live_docx.lua``. O citeproc entra como
item da lista ``filters`` porque só a ordem DENTRO de ``filters:`` é
garantida pelo manual do Pandoc ("Filters are run in the order
specified"). ``citeproc: true`` não oferece controle de ordem — na
prática é prependado à cadeia (verificado com filtro-sonda em pandoc
3.9.0.2: o Lua recebe ``(Autor 2001)``, ou seja o citeproc já rodou),
mas isso é detalhe de implementação não documentado. NUNCA declarar os
dois juntos: o citeproc roda duas vezes e a bibliografia sai
duplicada.

Fica de fora por design (spec 2026-07-22): lookup BBT (URIs de relink)
e guardas pós-export — exclusivos do caminho canônico ``prumo write
export``. O perfil é gerado por máquina (cópia do filtro no projeto,
caminho estável entre versões) — nunca commitado: o
``zettlr-profile`` garante a linha do perfil no ``.gitignore`` do pj.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import yaml

from par.core import pj_layout
from par.core.csl import CslNotFoundError, resolve_csl
from par.domains.write.export import _zotero_live_docx_filter

PROFILE_RELPATH = Path("docs") / "templates" / "prumo-docx.yaml"
REFERENCE_DOC_RELPATH = Path("docs") / "templates" / "reference.docx"
FILTER_RELPATH = Path("docs") / "templates" / "zotero_live_docx.lua"

_GITIGNORE_LINE = PROFILE_RELPATH.as_posix()
_GITIGNORE_COMMENT = (
    "# perfil do Zettlr: caminhos absolutos desta máquina; "
    "regenere com `prumo write zettlr-profile`"
)

_READER = "markdown+yaml_metadata_block+pipe_tables+grid_tables+fenced_code_blocks"


def generate_profile(pj_path: Path, *, style: str = "apa") -> Path:
    """(Re)gera o defaults file do Zettlr no projeto. Idempotente.

    O CSL é best-effort: sem o estilo em ``~/Zotero/styles/``, o perfil
    sai sem ``csl`` (citeproc usa Chicago) — o docx de trabalho continua
    com campos vivos. ``bibliography`` não entra aqui: viaja no
    frontmatter de cada draft. ATENÇÃO à precedência real —
    ``bibliography`` num defaults file equivale a ``--bibliography`` e
    SOBRESCREVE o metadata do documento (verificado com dois .bib
    conflitantes). O frontmatter do draft só prevalece enquanto o campo
    "Citation database" das preferências do Zettlr estiver VAZIO: o
    exporter do Zettlr injeta a biblioteca global em qualquer defaults
    file importado.

    Exige a raiz de um pj_* (``docs/references/_references.bib`` presente)
    — sem isso o perfil seria criado em diretório arbitrário.
    """
    bib = pj_layout.bib_path(pj_path)
    if not bib.is_file():
        raise FileNotFoundError(
            f"{pj_path} não parece a raiz de um pj_* (esperado docs/references/_references.bib). "
            "Rode na raiz do projeto ou aponte-a: `prumo write zettlr-profile --path <raiz>`."
        )
    filter_copy = pj_path / FILTER_RELPATH
    filter_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_zotero_live_docx_filter(), filter_copy)
    profile: dict[str, object] = {
        "reader": _READER,
        "writer": "docx",
        "standalone": True,
        "filters": ["citeproc", str(filter_copy.resolve())],
        "metadata": {"zotero_csl_style": style},
    }
    with contextlib.suppress(CslNotFoundError):
        profile["csl"] = str(resolve_csl(style))
    reference_doc = pj_path / REFERENCE_DOC_RELPATH
    if reference_doc.is_file():
        profile["reference-doc"] = str(reference_doc.resolve())
    out = pj_path / PROFILE_RELPATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _ensure_gitignored(pj_path)
    return out


def _ensure_gitignored(pj_path: Path) -> None:
    """Garante a linha do perfil no ``<pj>/.gitignore`` (cria o arquivo se faltar).

    O perfil traz caminhos absolutos desta máquina; commitado, quebra o
    export do coautor. O ``prumo update`` não mexe num ``.gitignore`` que já
    existe, então nos pj existentes é este comando que acrescenta a linha.
    """
    gitignore = pj_path / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if any(line.strip() == _GITIGNORE_LINE for line in text.splitlines()):
        return
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"{_GITIGNORE_COMMENT}\n{_GITIGNORE_LINE}\n"
    gitignore.write_text(text, encoding="utf-8")


def profile_issues(pj_path: Path) -> list[str]:
    """Checagem para o doctor: perfil existente com filtro ou reference-doc quebrado.

    Perfil ausente NÃO é problema (projeto legado ou pré-perfil). Para o
    filtro, acusa três casos: arquivo inexistente, filtro fora do projeto
    (perfil antigo apontando para dentro de uma instalação do PAR) e cópia
    no projeto com bytes diferentes do filtro desta versão.
    """
    profile_path = pj_path / PROFILE_RELPATH
    if not profile_path.is_file():
        return []
    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return [
            f"Perfil Zettlr inválido (YAML): {profile_path}. "
            "Regenere: `prumo write zettlr-profile`."
        ]
    if not isinstance(data, dict):
        return [
            f"Perfil Zettlr inválido (YAML): {profile_path}. "
            "Regenere: `prumo write zettlr-profile`."
        ]
    issues: list[str] = []
    filters = data.get("filters") or []
    if isinstance(filters, list):
        for f in filters:
            if isinstance(f, str) and f != "citeproc":
                issue = _filter_issue(pj_path, f)
                if issue:
                    issues.append(issue)
    ref = data.get("reference-doc")
    if isinstance(ref, str) and not Path(ref).is_file():
        issues.append(
            f"Perfil Zettlr aponta reference-doc inexistente: {ref}. "
            "Regenere: `prumo write zettlr-profile`."
        )
    return issues


def _filter_issue(pj_path: Path, f: str) -> str | None:
    """Um problema do filtro ``f`` do perfil, ou ``None`` se ele está em dia."""
    path = Path(f)
    if not path.is_file():
        return (
            f"Perfil Zettlr aponta filtro inexistente: {f}. Regenere: `prumo write zettlr-profile`."
        )
    if path.resolve() != (pj_path / FILTER_RELPATH).resolve():
        return (
            f"Perfil Zettlr aponta filtro fora do projeto: {f}. "
            "Regenere: `prumo write zettlr-profile`"
        )
    if path.read_bytes() != _zotero_live_docx_filter().read_bytes():
        return (
            f"A cópia do filtro em {FILTER_RELPATH.as_posix()} está diferente da desta "
            "versão do PAR. Regenere: `prumo write zettlr-profile`"
        )
    return None
