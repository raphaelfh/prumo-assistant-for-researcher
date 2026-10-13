"""Reescrita de invocações de skills antigas (spec 2026-09-12, D6).

Só o TOKEN de invocação muda — ``par:<antigo>`` ou ``prumo-assist:<antigo>``
(projeto anterior à ADR-0034) vira ``par:<skill> <modo>``. Valor sem o prefixo (``generator: wiki-query``)
é dado de proveniência e fica como está (Princípio IV). O acervo gerado em
``docs/references/papers/`` também fica: é saída de máquina, não instrução.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from par.core.skills import SkillRef

__all__ = [
    "ObsoleteRef",
    "RefChange",
    "backup_plugin_copies",
    "exclude_paths",
    "migrate_skill_names",
    "move_plugin_copies",
    "obsolete_ref_issues",
    "obsolete_refs",
    "plugin_copies",
    "rewrite_invocations",
    "scan_obsolete_refs",
    "scan_skill_refs",
]

_SUFFIXES = frozenset({".md", ".toml"})
_SKIP_DIRS = frozenset({".git", ".venv", ".prumo", "node_modules", "graphify-out", "_build"})
_SKIP_PREFIX = "docs/references/papers/"


@dataclass(frozen=True)
class RefChange:
    """Um arquivo do ``pj_*`` com ``count`` invocações antigas."""

    path: str
    count: int


def _pattern(legacy: Mapping[str, SkillRef]) -> re.Pattern[str] | None:
    if not legacy:
        return None
    # Mais longo primeiro: ``paper-extract-all`` não pode casar como ``paper-extract``.
    names = sorted(legacy, key=len, reverse=True)
    alternation = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w-])(?:prumo-assist|par):({alternation})(?![\w-])")


def rewrite_invocations(text: str, legacy: Mapping[str, SkillRef]) -> tuple[str, int]:
    """Troca cada ``par:<antigo>``/``prumo-assist:<antigo>`` pela invocação nova. Devolve (texto, trocas)."""
    pattern = _pattern(legacy)
    if pattern is None:
        return text, 0
    return pattern.subn(lambda m: legacy[m.group(1)].invocation, text)


def _candidates(pj_root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(pj_root.rglob("*")):
        if path.suffix not in _SUFFIXES or not path.is_file():
            continue
        rel = path.relative_to(pj_root)
        if _SKIP_DIRS & set(rel.parts) or rel.as_posix().startswith(_SKIP_PREFIX):
            continue
        out.append(path)
    return out


def _walk(pj_root: Path, legacy: Mapping[str, SkillRef], *, write: bool) -> list[RefChange]:
    changes: list[RefChange] = []
    if not legacy:
        return changes
    for path in _candidates(pj_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, count = rewrite_invocations(text, legacy)
        if not count:
            continue
        if write:
            path.write_text(new, encoding="utf-8")
        changes.append(RefChange(path.relative_to(pj_root).as_posix(), count))
    return changes


def scan_skill_refs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Arquivos com invocação antiga, sem escrever nada (``--dry-run`` e ``doctor``)."""
    return _walk(pj_root, legacy, write=False)


def migrate_skill_names(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Reescreve as invocações antigas do projeto. Idempotente."""
    return _walk(pj_root, legacy, write=True)


#: Arquivos que o agente lê como instrução. Histórico (``docs/_log.md``, ``decisions/``,
#: ``_archive/``) fica de fora por desenho: registra o passado, não ensina o presente.
_INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", "README.md", "docs/project_guide.md", "Makefile")
_INSTRUCTION_GLOB = ".claude/rules/*.md"

#: Scripts do CLI antigo que projetos de antes do pacote ``prumo`` guardavam em
#: ``.claude/scripts/``. Lista FECHADA: script de outro nome é do pesquisador.
_LEGACY_SCRIPTS: frozenset[str] = frozenset(
    {
        "README_zotero_annotations.md",
        "_bib.py",
        "_csl.py",
        "_obsidian_md.py",
        "cite_graph.py",
        "cite_lookup.py",
        "export_page.py",
        "extract_comments.py",
        "paper_sync.py",
        "sync_zotero_annotations.py",
        "sync_zotero_pdfs.py",
    }
)


@dataclass(frozen=True)
class _Obsolete:
    """O que o PAR não usa mais: ``pattern`` acha a linha, ``label`` diz o que vale hoje.

    Linha que casa ``unless`` diz o certo sobre o assunto ("não há MCP do qmd") e não conta.
    """

    label: str
    pattern: re.Pattern[str]
    unless: re.Pattern[str] | None = None

    def hit(self, line: str) -> bool:
        if self.pattern.search(line) is None:
            return False
        return self.unless is None or self.unless.search(line) is None


#: O que o PAR não usa mais, na ordem em que a issue fala.
#: Menção ao CLI ``qmd`` vale (ADR-0038, item 7); só o servidor MCP dele saiu. Por isso o
#: MCP do qmd só conta no nome de tool (``mcp__qmd__*``) ou colado ao qmd ("MCP `qmd`",
#: "MCP do qmd", "qmd (MCP)"), e a linha com negação ("não", "sem", "nunca", "saiu") diz o
#: certo, salvo se ainda trouxer o nome de tool. Sem "no"/"not": "no" é "em o" em pt-BR.
_OBSOLETE: tuple[_Obsolete, ...] = (
    _Obsolete(
        "`prumo-assist` (o plugin hoje é `par`)",
        re.compile(r"(?<![\w-])prumo-assist(?![A-Za-z])"),
    ),
    _Obsolete(
        "MCP do qmd (saiu: a busca no wiki é pelo CLI, `qmd query`)",
        re.compile(
            r"mcp__qmd__|\bMCP\s+(?:d[oe]\s+)?[`'\"]?qmd\b|\bqmd[`'\"]?\s+\(?(?:via\s+)?MCP\b"
        ),
        unless=re.compile(r"^(?!.*mcp__qmd__).*(?<!\w)(?:não|sem|nunca|saiu)(?!\w)", re.IGNORECASE),
    ),
    _Obsolete(
        "`prumo-zettlr-export` (saiu; o docx vem de `/par:write export`)",
        re.compile(r"prumo-zettlr-export"),
    ),
    _Obsolete(
        "`uv tool install` do PAR (o CLI vem com o plugin)",
        re.compile(r"uv tool install\b[^\n]*prumo-assistant-for-researcher"),
    ),
    _Obsolete(
        "script do CLI antigo em `.claude/scripts/` (o `prumo update` o tira do projeto; "
        "o comando hoje é `prumo paper …` ou `prumo write …`)",
        re.compile(
            r"\.claude/scripts/(?:"
            + "|".join(re.escape(s) for s in sorted(_LEGACY_SCRIPTS))
            + r")(?!\w)"
        ),
    ),
    _Obsolete("`.Codex/` (o caminho é `.claude/`)", re.compile(r"\.Codex/")),
)


@dataclass(frozen=True)
class ObsoleteRef:
    """Linha ``line`` de ``path`` cita o que o PAR não usa mais (``label`` diz o que vale)."""

    path: str
    line: int
    label: str


def obsolete_refs(text: str) -> list[tuple[int, str]]:
    """``(linha, rótulo)`` de cada referência obsoleta em ``text``; linha conta de 1."""
    return [
        (n, rule.label)
        for n, line in enumerate(text.splitlines(), start=1)
        for rule in _OBSOLETE
        if rule.hit(line)
    ]


def _instruction_files(pj_root: Path) -> list[Path]:
    """Arquivos de instrução do pj; link para um arquivo já listado não repete."""
    candidates = [pj_root / rel for rel in _INSTRUCTION_FILES]
    candidates += sorted(pj_root.glob(_INSTRUCTION_GLOB))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        if not path.is_file() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        out.append(path)
    return out


def scan_obsolete_refs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[ObsoleteRef]:
    """Referências obsoletas nos arquivos de instrução do pj, sem escrever nada.

    O texto é lido como fica depois do ``prumo update``: invocação antiga
    (``prumo-assist:<antigo>``) o update reescreve sozinho e é do ``[skill_obsoleta]``.
    """
    out: list[ObsoleteRef] = []
    for path in _instruction_files(pj_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(pj_root).as_posix()
        text, _ = rewrite_invocations(text, legacy)
        out.extend(ObsoleteRef(rel, n, label) for n, label in obsolete_refs(text))
    return out


def obsolete_ref_issues(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[str]:
    """Issue ÚNICA ``[referencia_obsoleta]`` (ou lista vazia): um remédio, editar as linhas.

    As linhas vêm agrupadas pelo que mudou, para cada correção ser dita uma vez.
    """
    refs = scan_obsolete_refs(pj_root, legacy)
    if not refs:
        return []
    groups: dict[str, list[str]] = {}
    for r in refs:
        groups.setdefault(r.label, []).append(f"{r.path}:{r.line}")
    partes = [
        f"{rule.label}: {', '.join(groups[rule.label])}"
        for rule in _OBSOLETE
        if rule.label in groups
    ]
    return [
        "[referencia_obsoleta] instruções do projeto citam o que o PAR não usa mais — "
        + "; ".join(partes)
        + ". Edite estas linhas (o `prumo update` não as corrige)."
    ]


#: O que o ``.claude/make/`` do ``pj_base`` antigo tinha quando ninguém o usou.
_EMPTY_MAKE = frozenset({".gitkeep", ".DS_Store"})

#: Marca do PAR no conteúdo de um espelho do Codex: só o que o PAR publica e o pesquisador
#: não escreve. O bloco ``prumo:`` do frontmatter das skills, o bloco gerado
#: ``prumo:runtime`` e o contrato JSON dos agents e modos (``SupportReport/v1``). Citar o
#: projeto (``pj_*``), o CLI (``prumo status``) ou a palavra "prumo" não basta: uma skill
#: do pesquisador num ``pj_*`` faz isso. Versões muito antigas sem marca nenhuma ficam onde
#: estão, o que é inofensivo: o Claude Code não lê ``.agents/`` nem ``.codex/``.
_PAR_MARK = re.compile(
    r"^prumo:[ \t]*$"
    r"|prumo:runtime"
    r"|\b(?:PaperCallout|PaperExtract|PeerReviewReport|PicotSpec|ScientificWritingPass"
    r"|SessionLog|SupportReport|WikiLintReport|WikiQueryResponse|WikiSource|WriteOutput)/v\d",
    re.MULTILINE,
)

#: Diretórios onde moram as cópias, o mais fundo antes do que o contém; cada um sai do pj
#: só se guardava uma cópia movida e ficou vazio.
_COPY_CONTAINERS = (
    ".claude/skills",
    ".claude/agents",
    ".claude/scripts",
    ".codex/agents",
    ".codex",
    ".agents/skills",
    ".agents",
)


def _owned_dir(pj_root: Path, d: Path) -> bool:
    """``d`` é diretório real do pj: nenhum segmento do pj até ele é link, e resolve dentro do pj."""
    cur = pj_root
    for part in d.relative_to(pj_root).parts:
        cur = cur / part
        if cur.is_symlink():
            return False
    return d.is_dir() and d.resolve().is_relative_to(pj_root.resolve())


def _has_par_mark(path: Path) -> bool:
    """``path`` é arquivo com a :data:`_PAR_MARK` (ausente ou ilegível: não tem)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _PAR_MARK.search(text) is not None


def _entries(pj_root: Path, rel_dir: str, keep: Callable[[Path], bool]) -> list[str]:
    """Filhos de ``rel_dir`` que ``keep`` aceita, em ordem alfabética (vazio se não é do pj)."""
    d = pj_root / rel_dir
    if not _owned_dir(pj_root, d):
        return []
    return [f"{rel_dir}/{p.name}" for p in sorted(d.iterdir(), key=lambda p: p.name) if keep(p)]


def plugin_copies(
    pj_root: Path, skill_names: Iterable[str], agent_files: Iterable[str]
) -> list[str]:
    """Cópias do que o plugin provê, deixadas no ``pj_*`` por versões antigas do PAR (A11).

    Devolve caminhos POSIX relativos ao pj, nesta ordem e cada grupo em ordem
    alfabética: ``.claude/skills/<n>`` (diretório, inclusive link para diretório, com
    ``n`` em ``skill_names``), ``.claude/agents/<f>`` (``f`` em ``agent_files``),
    ``.claude/scripts/<s>`` (``s`` em :data:`_LEGACY_SCRIPTS`), ``.claude/make`` (só se
    vazio), os espelhos do Codex ``.codex/agents/<agent>.toml`` e ``.agents/skills/<n>``.
    Nomes fora dessas listas nunca entram. Só lista: nada é movido nem apagado.

    Espelho do Codex só entra com a marca do PAR no conteúdo (:data:`_PAR_MARK`; na skill,
    no ``SKILL.md``). O Claude Code não lê ``.agents/`` nem ``.codex/``: um homônimo ali
    não sombreia o plugin, e com nome como ``peer-review`` costuma ser de outro pacote
    ou do pesquisador — sem a marca, fica onde está.

    Diretório que seja link (ou resolva fora do pj) em qualquer segmento não é do pj: o
    conteúdo pertence a outra árvore e nunca é listado — senão o ``prumo update``
    arrancaria diretórios de fora do projeto.
    """
    skills = frozenset(skill_names)
    agents = frozenset(agent_files)
    codex_agents = frozenset(f"{Path(a).stem}.toml" for a in agents)
    make = pj_root / ".claude" / "make"
    empty_make = _owned_dir(pj_root, make) and all(p.name in _EMPTY_MAKE for p in make.iterdir())
    return [
        *_entries(pj_root, ".claude/skills", lambda p: p.name in skills and p.is_dir()),
        *_entries(pj_root, ".claude/agents", lambda p: p.name in agents and p.is_file()),
        *_entries(pj_root, ".claude/scripts", lambda p: p.name in _LEGACY_SCRIPTS and p.is_file()),
        *([".claude/make"] if empty_make else []),
        *_entries(
            pj_root,
            ".codex/agents",
            lambda p: p.name in codex_agents and p.is_file() and _has_par_mark(p),
        ),
        *_entries(
            pj_root,
            ".agents/skills",
            lambda p: p.name in skills and p.is_dir() and _has_par_mark(p / "SKILL.md"),
        ),
    ]


def move_plugin_copies(pj_root: Path, rels: Sequence[str], dest: Path) -> list[str]:
    """Move as cópias listadas por :func:`plugin_copies` para ``dest/``.

    O que vinha de ``.claude/`` cai em ``dest/{skills,agents,scripts,make}``; os
    espelhos do Codex guardam o caminho inteiro (``dest/.codex/...``, ``dest/.agents/...``).
    Nada é apagado: cada cópia vai inteira para o backup (``.prumo/legacy-copies/...``),
    e nomes fora de ``rels`` nunca são tocados. Depois do move, sai o diretório de
    :data:`_COPY_CONTAINERS` que guardava uma cópia movida e ficou vazio; o vazio que não
    guardava nenhuma (criado pelo pesquisador) fica. Com ``rels`` vazio, ``dest`` não é criado.
    """
    for rel in rels:
        target = dest / rel.removeprefix(".claude/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pj_root / rel), str(target))
    # Mais fundo primeiro (ordem de _COPY_CONTAINERS): ``.codex/agents`` antes de ``.codex``.
    for container in _COPY_CONTAINERS:
        if not any(rel.startswith(container + "/") for rel in rels):
            continue
        d = pj_root / container
        if _owned_dir(pj_root, d) and not any(d.iterdir()):
            d.rmdir()
    return list(rels)


def exclude_paths(changes: Sequence[RefChange], rels: Sequence[str]) -> list[RefChange]:
    """Tira as ``RefChange`` dentro de ``rels`` (cópias do PAR): a cópia é movida, não reescrita."""
    return [
        c for c in changes if not any(c.path == rel or c.path.startswith(rel + "/") for rel in rels)
    ]


def backup_plugin_copies(pj_root: Path, rels: Sequence[str], stamp: str) -> str | None:
    """Move as cópias para ``.prumo/legacy-copies/<stamp>/`` e devolve esse caminho relativo.

    Sem cópias, nada é criado e devolve ``None``.
    """
    if not rels:
        return None
    dest = pj_root / ".prumo" / "legacy-copies" / stamp
    move_plugin_copies(pj_root, rels, dest)
    return dest.relative_to(pj_root).as_posix()
