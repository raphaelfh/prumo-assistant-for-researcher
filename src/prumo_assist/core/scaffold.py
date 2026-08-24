"""Scaffold compartilhado: overlay de templates + descoberta de módulos.

Extraído do ``cli.py`` para que ``init`` e ``add`` reusem a mesma lógica
(regra da ARCHITECTURE: ``cli.py`` é fachada fina, sem lógica de negócio).
"""

from __future__ import annotations

import re
import shutil
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prumo_assist import PrumoError
from prumo_assist.core import pj_layout
from prumo_assist.core.paths import resolve_resource

#: Formas do placeholder de nome usadas em ``templates/pj_base/``
#: (``pj-NOME`` no pyproject.toml, ``pj_<NOME>`` nos títulos markdown).
_NAME_PLACEHOLDERS: tuple[str, ...] = ("pj_<NOME>", "pj-NOME")

#: Nome do manifesto de módulo em ``templates/modules/<nome>/``. É metadata
#: pro ``prumo add`` (description/when_to_use/anchor), NÃO payload do projeto:
#: ``overlay`` o ignora, senão todo ``prumo add`` deixava um ``_module.toml``
#: órfão na raiz do ``pj_*``.
MODULE_MANIFEST = "_module.toml"

#: Segmento de caminho usado por módulos cujo payload é por-escopo (ex.:
#: ``clinical``). ``overlay`` substitui esse segmento pelo slug real antes de
#: copiar; ``is_applied`` faz o mesmo antes de checar o anchor. Ver ADR-0024
#: (escopo é resolvido por posição em ``docs/studies/<slug>/``, sem sentinela).
SCOPE_MARKER = "__scope__"

#: Segmento (e placeholder de conteúdo) usado por módulos cujo payload é o
#: pacote Python do projeto (ex.: ``code``). ``overlay`` substitui em CAMINHO;
#: :func:`apply_pkg_name` substitui em CONTEÚDO — o ``pyproject.toml`` precisa
#: do nome real em ``[tool.hatch.build.targets.wheel] packages``. Ver ADR-0027.
PKG_MARKER = "__pkg__"

#: Prefixo de diretório de projeto. Marca o `pj_*` para humano e agente, e é
#: ruído em `import` — some do nome do pacote (ADR-0027, D2).
_PJ_PREFIX = "pj_"

#: Prefixo numérico de slug de escopo (`01_estudo`, `02-triage`). Ordena
#: a leitura em `docs/studies/` e não pode abrir um identificador Python.
_NUMERIC_PREFIX_RE = re.compile(r"^\d+[_-]")


def _substitute_scope(rel: Path, scope: str) -> Path:
    """Troca o segmento ``__scope__`` de ``rel`` pelo slug real do escopo."""
    return Path(*(scope if part == SCOPE_MARKER else part for part in rel.parts))


def _substitute_pkg(rel: Path, pkg: str) -> Path:
    """Troca o segmento ``__pkg__`` de ``rel`` pelo nome real do pacote."""
    return Path(*(pkg if part == PKG_MARKER else part for part in rel.parts))


def pkg_name(project_name: str) -> str:
    """Nome do pacote de import a partir do nome do projeto (ADR-0027, D2).

    ``pj_piloto_genetica`` → ``piloto_genetica``. O ``[project]
    name`` do ``pyproject.toml`` continua sendo o nome do projeto; só o pacote
    de import perde o prefixo.
    """
    candidate = (
        project_name[len(_PJ_PREFIX) :] if project_name.startswith(_PJ_PREFIX) else project_name
    )
    if not candidate.isidentifier():
        raise PrumoError(
            f"O projeto {project_name!r} não é um nome de pacote Python válido "
            f"(viraria {candidate!r}). Renomeie o diretório para `pj_<letra>...`, "
            "usando apenas [a-z0-9_] e sem começar por dígito."
        )
    return candidate


def scope_pkg_name(slug: str) -> str:
    """Nome do subpacote a partir do slug de escopo (ADR-0027, D3).

    ``01_estudo`` → ``estudo``; ``mortalidade-uti`` →
    ``mortalidade_uti``. O slug de `docs/studies/` NÃO muda — a numeração
    ordena a leitura e é ruído no import.
    """
    candidate = _NUMERIC_PREFIX_RE.sub("", slug).replace("-", "_")
    if not candidate.isidentifier():
        raise PrumoError(
            f"O escopo {slug!r} não vira um nome de pacote Python válido "
            f"(viraria {candidate!r}). Renomeie o escopo em `docs/studies/` para "
            "que sobre ao menos uma letra depois do prefixo numérico."
        )
    return candidate


def overlay(
    template: Path, target: Path, *, scope: str | None = None, pkg: str | None = None
) -> tuple[list[str], list[str]]:
    """Copia ``template/*`` para ``target/`` sem sobrescrever arquivos existentes.

    Retorna ``(copied, skipped)`` com paths relativos ao target. Cria
    diretórios faltantes; ignora arquivos cujo destino já existe.

    Quando o payload do template usa o marcador :data:`SCOPE_MARKER` no
    caminho (módulos por-escopo, ex. ``clinical``), ``scope`` é obrigatório
    — o chamador resolve o slug real (via CLI ou pelo escopo recém-criado no
    ``init``) antes de chamar ``overlay``. Idem :data:`PKG_MARKER` e ``pkg``
    para o módulo ``code``, cujo payload é o pacote Python do projeto.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for src in template.rglob("*"):
        rel = src.relative_to(template)
        if rel == Path(MODULE_MANIFEST):
            continue
        if scope is not None:
            rel = _substitute_scope(rel, scope)
        elif SCOPE_MARKER in rel.parts:
            raise PrumoError(
                f"{src} usa o marcador de escopo `{SCOPE_MARKER}` mas nenhum escopo foi "
                "resolvido antes do overlay (defeito interno do chamador)."
            )
        if pkg is not None:
            rel = _substitute_pkg(rel, pkg)
        elif PKG_MARKER in rel.parts:
            raise PrumoError(
                f"{src} usa o marcador de pacote `{PKG_MARKER}` mas nenhum nome de pacote "
                "foi resolvido antes do overlay (defeito interno do chamador)."
            )
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if dst.exists():
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))
    return copied, skipped


def _apply_placeholders(
    target: Path, rel_paths: Iterable[str], placeholders: Iterable[str], value: str
) -> list[str]:
    """Troca ``placeholders`` por ``value`` no conteúdo de ``rel_paths``.

    Opera apenas sobre ``rel_paths`` (arquivos recém-copiados do scaffold) —
    arquivos preservados do usuário em ``--merge`` nunca são reescritos.
    Arquivos binários são ignorados. Retorna os paths relativos alterados.
    """
    changed: list[str] = []
    for rel in rel_paths:
        path = target / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = text
        for placeholder in placeholders:
            new_text = new_text.replace(placeholder, value)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return changed


def apply_project_name(target: Path, name: str, rel_paths: Iterable[str]) -> list[str]:
    """Substitui os placeholders de nome do template pelo nome real do projeto."""
    return _apply_placeholders(target, rel_paths, _NAME_PLACEHOLDERS, name)


def apply_pkg_name(target: Path, pkg: str, rel_paths: Iterable[str]) -> list[str]:
    """Substitui :data:`PKG_MARKER` no CONTEÚDO pelo nome real do pacote.

    O caminho já foi resolvido por ``overlay``; o que sobra é o corpo dos
    arquivos — ``[tool.hatch.build.targets.wheel] packages`` e os exemplos de
    ``import`` na rule do módulo ``code``.
    """
    return _apply_placeholders(target, rel_paths, (PKG_MARKER,), pkg)


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    description: str
    when_to_use: str
    anchor: str | None
    path: Path


def _modules_root() -> Path:
    return resolve_resource("templates") / "modules"


def discover_modules() -> list[ModuleInfo]:
    """Lista módulos em ``templates/modules/`` lendo cada ``_module.toml``."""
    root = _modules_root()
    if not root.is_dir():
        return []
    out: list[ModuleInfo] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        meta: dict[str, Any] = {}
        meta_path = d / MODULE_MANIFEST
        if meta_path.is_file():
            with meta_path.open("rb") as f:
                meta = tomllib.load(f)
        out.append(
            ModuleInfo(
                name=d.name,
                description=meta.get("description", ""),
                when_to_use=meta.get("when_to_use", ""),
                anchor=meta.get("anchor"),
                path=d,
            )
        )
    return out


def get_module(name: str) -> ModuleInfo | None:
    for m in discover_modules():
        if m.name == name:
            return m
    return None


def module_requires_scope(module: ModuleInfo) -> bool:
    """``True`` se o payload do módulo usa :data:`SCOPE_MARKER` no caminho.

    Módulos assim (ex. ``clinical``) precisam de um escopo resolvido
    (``docs/studies/<slug>/``) antes de ``overlay`` — ver ``add_command``.
    """
    return any(SCOPE_MARKER in p.relative_to(module.path).parts for p in module.path.rglob("*"))


def module_requires_pkg(module: ModuleInfo) -> bool:
    """``True`` se o payload do módulo usa :data:`PKG_MARKER` no caminho.

    Módulos assim (ex. ``code``) precisam do nome do pacote resolvido a partir
    do nome do projeto antes de ``overlay`` — ver ``add_command``.
    """
    return any(PKG_MARKER in p.relative_to(module.path).parts for p in module.path.rglob("*"))


def is_applied(target: Path, module: ModuleInfo) -> bool:
    """``True`` se o ``anchor`` declarado do módulo existe em ``target``.

    Quando o anchor usa :data:`SCOPE_MARKER`, verifica em QUALQUER escopo
    existente sob ``target/docs/studies/`` — não importa o slug escolhido
    pelo usuário (Task 10 deriva o slug do nome do projeto, não de
    ``"principal"``).
    """
    if not module.anchor:
        return False
    anchor = Path(module.anchor)
    if SCOPE_MARKER not in anchor.parts:
        return (target / anchor).exists()
    return any(
        (target / _substitute_scope(anchor, s.name)).exists() for s in pj_layout.iter_scopes(target)
    )
