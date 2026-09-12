"""Auditoria determinística do wiki, um escopo (``docs/studies/<slug>/``) por vez.

Detecta problemas estruturais que LLM não precisa ver:

- Citekeys marcados (``[@key]``) ausentes do .bib.
- Páginas órfãs (sem links de entrada) — identidade de página é o CAMINHO
  relativo ao escopo, não o ``stem``: duas páginas homônimas em escopos
  diferentes são páginas diferentes.
- Wikilink ``[[termo]]`` ambíguo dentro do escopo (mais de uma página com o
  mesmo ``stem``).
- Frontmatter ausente em páginas direto sob ``notes/``, ``writing/`` ou
  ``decisions/`` do escopo.
- ``_index.md`` ou ``_log.md`` ausentes.
- Entradas de ``_log.md`` fora do padrão de prefixo (``broken_log_prefix``).
- Bibliografia ausente SÓ quando há citação marcada em algum escopo
  (``bib_missing``) — projeto sem citação nenhuma não precisa de .bib.
- Links mortos em campos de frontmatter ``links_to``/``sources``/``related``
  (``dead_link``) — resolvidos dentro do escopo que cita, um alvo só existe
  se existir no MESMO escopo (homônimo de outro escopo não resolve).
- Conceitos citados ≥3× sem página correspondente dentro do escopo
  (``concept_candidate``, severity ``info``).

``check_single_primary`` (mais de uma nota com ``role: primary`` em
``docs/references/papers/``) é opt-in: só faz sentido quando o projeto
declara ter um paper principal, então não é chamado por ``lint()`` — rode
explicitamente quando aplicável.

Contradições e stale claims permanecem semânticas — trabalho da skill
``wiki lint`` (modo agêntico via host), não deste módulo determinístico.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from prumo_assist.core import pj_layout
from prumo_assist.core.bib import parse_bib
from prumo_assist.core.citations import body_lines, scan_marked_citekeys
from prumo_assist.core.obsidian import split_frontmatter

# Subdiretórios do ESCOPO onde frontmatter é esperado — não é mais taxonomia
# de docs/, é a estrutura fixa de todo `docs/studies/<slug>/` (ADR-0022/0024).
EXPECTED_DIRS = pj_layout.SCOPE_DIRS
PAGE_LINK_RE = re.compile(r"\[\[([^\]@\|]+)(?:\|[^\]]+)?\]\]")
# Links markdown padrão [texto](alvo) — projetos Pandoc-puros não usam
# wikilink de página; sem isto, toda página nova viraria "órfã".
MD_LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")
LOG_PREFIX_RE = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision|milestone|note) \| .+$"
)


@dataclass(frozen=True)
class WikiIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    page: str | None = None
    scope: str | None = None


def lint(pj_path: Path) -> dict[str, Any]:
    """Roda os checks do wiki, um escopo por vez. Retorna ``{"ok", "issues", "summary"}``."""
    pj_layout.assert_current_layout(pj_path)
    issues: list[WikiIssue] = []
    docs = pj_path / "docs"

    if not docs.is_dir():
        issues.append(WikiIssue("error", "docs_missing", f"{docs} não existe"))
        return _report(issues)

    if not (docs / "_index.md").is_file():
        issues.append(WikiIssue("warning", "no_index", "docs/_index.md ausente"))
    if not (docs / "_log.md").is_file():
        issues.append(WikiIssue("warning", "no_log", "docs/_log.md ausente"))

    bib = pj_layout.bib_path(pj_path)
    bib_keys: set[str] = set()
    if bib.is_file():
        bib_keys = {e.citekey for e in parse_bib(bib.read_text())}

    scopes = pj_layout.iter_scopes(pj_path)
    if not scopes:
        issues.append(
            WikiIssue(
                "warning",
                "no_scope",
                "nenhum escopo em docs/studies/. Crie um com `prumo add study <slug>`.",
            )
        )

    for scope in scopes:
        issues.extend(_lint_scope(pj_path, scope, bib_keys, bib.is_file()))

    issues.extend(_check_log_prefixes(docs))

    return _report(issues)


def _lint_scope(
    pj_path: Path, scope: Path, bib_keys: set[str], bib_exists: bool
) -> list[WikiIssue]:
    """Checks de um escopo. Identidade de página é o caminho relativo ao escopo."""
    issues: list[WikiIssue] = []
    slug = scope.name
    pages = sorted(scope.rglob("*.md"))
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    # Identidade por CAMINHO — `stem` funde homônimas de escopos diferentes.
    keys = {p: p.relative_to(scope).as_posix() for p in pages}
    incoming: dict[str, int] = dict.fromkeys(keys.values(), 0)
    # Índice stem -> caminhos, para resolver wikilink dentro do escopo.
    by_stem: dict[str, list[str]] = {}
    for p in pages:
        by_stem.setdefault(p.stem, []).append(keys[p])

    cited = False
    for page in pages:
        text = texts[page]
        rel = page.relative_to(pj_path).as_posix()

        parent = page.parent.name
        if parent in EXPECTED_DIRS and not text.startswith("---"):
            issues.append(
                WikiIssue("warning", "no_frontmatter", "sem frontmatter", page=rel, scope=slug)
            )

        for ck in scan_marked_citekeys(text):
            cited = True
            if bib_exists and ck not in bib_keys:
                issues.append(
                    WikiIssue(
                        "warning",
                        "broken_citekey",
                        f"@{ck} não existe no .bib",
                        page=rel,
                        scope=slug,
                    )
                )

        for stem in _page_link_targets(text):
            targets = by_stem.get(stem, [])
            if len(targets) > 1:
                issues.append(
                    WikiIssue(
                        "warning",
                        "ambiguous_link",
                        f"[[{stem}]] casa {len(targets)} páginas neste escopo",
                        page=rel,
                        scope=slug,
                    )
                )
            for t in targets:
                incoming[t] += 1

    if cited and not bib_exists:
        issues.append(
            WikiIssue(
                "warning",
                "bib_missing",
                "há citação `[@key]` e nenhuma bibliografia em docs/references/_references.bib. "
                "Aponte o .bib do seu gerenciador ou rode `prumo paper connect <coleção>`.",
                scope=slug,
            )
        )

    for key, count in sorted(incoming.items()):
        stem = Path(key).stem
        if count == 0 and not stem.startswith("_") and stem not in {"README", "protocol"}:
            issues.append(
                WikiIssue(
                    "warning",
                    "orphan_page",
                    "página sem links de entrada",
                    page=(scope / key).relative_to(pj_path).as_posix(),
                    scope=slug,
                )
            )

    page_stems = set(by_stem.keys())
    issues.extend(_check_dead_frontmatter_links(texts, pj_path, page_stems, slug))
    issues.extend(_check_concept_candidates(texts, page_stems, slug))

    return issues


def _link_stem(match: str | tuple[str, ...]) -> str:
    """Normaliza um match de ``PAGE_LINK_RE`` para o stem do alvo (sem âncora)."""
    target = match if isinstance(match, str) else match[0]
    return target.strip().split("#")[0]


def _is_external_link(target: str) -> bool:
    """Alvo de link markdown que NÃO aponta para página do wiki.

    Única fonte para os dois caminhos que precisam disso (corpo e
    frontmatter): enquanto divergiam, o do frontmatter pulava só ``"://"`` e
    um ``[contato](mailto:x@y.br)`` em ``sources`` virava ``dead_link``
    falso.
    """
    return "://" in target or target.startswith("mailto:")


def _page_link_targets(text: str) -> Iterator[str]:
    """Stems de página referenciados em ``text``, nas duas sintaxes.

    Fonte ÚNICA para os dois caminhos que precisam disso — contagem de links
    de entrada no corpo e validação de alvo em ``links_to``/``sources``/
    ``related``. Enquanto eram duas implementações, divergiram: o caminho do
    frontmatter pulava só ``"://"`` (um ``mailto:`` virava ``dead_link``
    falso) e cada uma carregava seu próprio regex de wikilink.

    Alvo NU não entra de propósito: ``sources`` recebe string livre (título
    de paper, URL, nome de dataset) e qualquer não-stem viraria ``dead_link``,
    inundando o relatório. Citekey também não — ``PAGE_LINK_RE`` exclui ``@``
    do charset; quem valida citekey é ``scan_marked_citekeys``.
    """
    for target in PAGE_LINK_RE.findall(text):
        yield _link_stem(target)
    for md_target in MD_LINK_RE.findall(text):
        alvo = _link_stem(md_target)
        if _is_external_link(alvo):
            continue
        yield Path(alvo).stem


def _report(issues: list[WikiIssue]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    info = sum(1 for i in issues if i.severity == "info")
    return {
        "ok": errors == 0,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "total": len(issues),
        },
        "issues": [asdict(i) for i in issues],
    }


_ROLE_PRIMARY_RE = re.compile(r"^role:\s*primary\s*$", re.MULTILINE)


def check_single_primary(pj_path: Path) -> list[WikiIssue]:
    """Opt-in: ``role: primary`` deve aparecer em no máximo 1 paper de ``docs/references/papers/``.

    Não é chamado por ``lint()``. Um revisor sistemático tem N papers
    incluídos e zero paper principal; o check só faz sentido quando o
    projeto declara ter um — rode explicitamente nesse caso.
    """
    papers = pj_layout.papers_dir(pj_path)
    if not papers.is_dir():
        return []
    primaries = [
        meta.parent.name
        for meta in sorted(papers.rglob("_meta.md"))
        if _ROLE_PRIMARY_RE.search(meta.read_text(encoding="utf-8"))
    ]
    if len(primaries) >= 2:
        return [
            WikiIssue(
                "warning",
                "multiple_primary",
                f"{len(primaries)} notas com role: primary ({', '.join(primaries)}); esperado ≤ 1",
            )
        ]
    return []


def _check_log_prefixes(docs: Path) -> list[WikiIssue]:
    """Cada ``## `` em ``_log.md`` deve casar ``[YYYY-MM-DD] <verbo> | <texto>``.

    Só prosa: o cabeçalho do próprio ``_log.md`` do template documenta o
    formato num code fence (``## [YYYY-MM-DD] <action> | <título curto>``), e
    lê-lo como entrada fazia todo projeto recém-criado nascer com um warning.
    """
    log = docs / "_log.md"
    if not log.is_file():
        return []
    issues: list[WikiIssue] = []
    for line in body_lines(log.read_text(encoding="utf-8")):
        if line.startswith("## ") and not LOG_PREFIX_RE.match(line):
            issues.append(
                WikiIssue(
                    "warning", "broken_log_prefix", f"entrada de log fora do padrão: {line!r}"
                )
            )
    return issues


_FM_LINK_FIELDS = ("links_to", "sources", "related")


def _check_dead_frontmatter_links(
    texts: dict[Path, str],
    pj_path: Path,
    page_stems: set[str],
    scope: str,
) -> list[WikiIssue]:
    """Wikilinks e links markdown em ``links_to``/``sources``/``related`` cujo alvo (de página) não existe.

    ``page_stems`` é o conjunto de stems do PRÓPRIO escopo — um alvo só
    resolve dentro do escopo que o cita, nunca por homônimo de outro escopo.
    """
    issues: list[WikiIssue] = []
    for page, text in texts.items():
        try:
            fm, _ = split_frontmatter(text)
        except yaml.YAMLError:
            continue
        if not fm:
            continue
        rel = page.relative_to(pj_path).as_posix()
        for field in _FM_LINK_FIELDS:
            value = fm.get(field)
            if not isinstance(value, list):
                continue
            for raw in value:
                for target in _page_link_targets(str(raw)):
                    if target not in page_stems:
                        issues.append(
                            WikiIssue(
                                "warning",
                                "dead_link",
                                f"{field}: {target} não existe no vault",
                                page=rel,
                                scope=scope,
                            )
                        )
    return issues


_CONCEPT_CANDIDATE_MIN = 3


def _check_concept_candidates(
    texts: dict[Path, str], page_stems: set[str], scope: str
) -> list[WikiIssue]:
    """Wikilink ``[[termo]]`` citado ≥3× sem página correspondente → candidato a concept.

    Contagem por escopo — ``page_stems`` é local ao escopo, mesma razão de
    ``_check_dead_frontmatter_links``.
    """
    counts: dict[str, int] = {}
    for text in texts.values():
        for target in PAGE_LINK_RE.findall(text):
            name = _link_stem(target)
            if name and name not in page_stems:
                counts[name] = counts.get(name, 0) + 1
    issues: list[WikiIssue] = []
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count >= _CONCEPT_CANDIDATE_MIN:
            issues.append(
                WikiIssue(
                    "info",
                    "concept_candidate",
                    f"'{name}' citado {count}× sem página (candidato a /prumo-assist:wiki ingest)",
                    scope=scope,
                )
            )
    return issues
