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
export``. O perfil é gerado por máquina (caminho absoluto do filtro no
wheel instalado) — nunca commitado no template.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import yaml

from prumo_assist.core.csl import CslNotFoundError, resolve_csl
from prumo_assist.domains.write.export import _zotero_live_docx_filter

PROFILE_RELPATH = Path("docs") / "templates" / "prumo-docx.yaml"
REFERENCE_DOC_RELPATH = Path("docs") / "templates" / "reference.docx"

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

    Exige a raiz de um pj_* (``references/_references.bib`` presente) —
    sem isso o perfil seria criado em diretório arbitrário.
    """
    bib = pj_path / "references" / "_references.bib"
    if not bib.is_file():
        raise FileNotFoundError(
            f"{pj_path} não parece a raiz de um pj_* (esperado references/_references.bib). "
            "Rode na raiz do projeto ou aponte-a: `prumo write zettlr-profile --path <raiz>`."
        )
    profile: dict[str, object] = {
        "reader": _READER,
        "writer": "docx",
        "standalone": True,
        "filters": ["citeproc", str(_zotero_live_docx_filter())],
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
    return out


def profile_issues(pj_path: Path) -> list[str]:
    """Checagem para o doctor: perfil existente apontando arquivo morto.

    Perfil ausente NÃO é problema (projeto legado ou pré-perfil);
    quebrado (wheel movido/reinstalado) é.
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
            if isinstance(f, str) and f != "citeproc" and not Path(f).is_file():
                issues.append(
                    f"Perfil Zettlr aponta filtro inexistente: {f}. "
                    "Regenere: `prumo write zettlr-profile`."
                )
    ref = data.get("reference-doc")
    if isinstance(ref, str) and not Path(ref).is_file():
        issues.append(
            f"Perfil Zettlr aponta reference-doc inexistente: {ref}. "
            "Regenere: `prumo write zettlr-profile`."
        )
    return issues
