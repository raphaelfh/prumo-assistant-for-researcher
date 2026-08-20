---
title: Plano de implementação — Zettlr como front humano
date: 2026-07-22
status: implemented
verified: 2026-07-22
release: "0.62.1"
spec: ../specs/2026-07-22-zettlr-front-design.md
tags: [zettlr, write, citations, pj-base, release-policy, plan]
---

# Zettlr Front Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zettlr vira o front humano dos projetos `pj_*` novos: scaffold Pandoc-puro sem Obsidian, perfil de export docx gerado, gramática única de citekey e docx canônico com guardas — release PATCH 0.62.1 sob a nova política pré-1.0 (ADR-0015).

**Architecture:** O prumo nunca escreve config do Zettlr; ele fala a língua nativa do Zettlr por convenção (frontmatter `bibliography:`, defaults file gerado com `citeproc` ANTES do filtro Lua, custom command via console-script). Um novo `core/citations.py` é o único reconhecedor de citekeys do pacote (export, compose, wiki lint, paper graph). Projetos legados ficam intocados (`normalize_markdown` permanece).

**Tech Stack:** Python 3.11 (Typer/Pydantic/PyYAML), Pandoc ≥ 3.0 (filtro `zotero_live_docx.lua`), Zettlr ≥ 3.0, pytest + mypy --strict + ruff.

## Global Constraints

- Prosa, docstrings e mensagens de usuário em pt-BR; identificadores em inglês. Mensagem de erro embute o comando de correção literal.
- Todo módulo abre com `from __future__ import annotations`; `uv run mypy` roda `--strict` sobre `src/prumo_assist` E `tests/` (anote tudo, inclusive `-> None` em testes).
- Nada de `print()` direto — `core/output.Console`; subcomandos Typer envoltos em `core/cli_op.cli_run(...)` (exceção existente: `doctor_command`).
- Layering: `core/` NUNCA importa de `domains/`; `domains/` importam `core/`; `cli.py` (raiz e de domínio) é fachada fina.
- Testes espelham o layout (`tests/unit/<dominio>/test_<modulo>.py`, com `__init__.py`); deps externas nunca executadas — pandoc é testado via montagem pura de comando + parsers; Zotero/qmd via `patch` nos seams. Não há conftest.py; helpers são locais ao arquivo.
- Índices têm blocos gerados (README, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`): após tocar description de SKILL.md, ADR ou spec/plan, rode `uv run python .github/scripts/gen_indexes.py` — nunca edite o bloco à mão.
- `templates/` e `skills/` são force-included no wheel (`pyproject.toml`) e resolvidos por `core/paths.py` — este plano NÃO move esses roots.
- Release deste trabalho: **PATCH 0.62.1** sob a política do ADR-0015 (Task 13/16). Versão só em `src/prumo_assist/_version.py` + `python .github/scripts/sync_manifest_version.py`.
- Branch de trabalho: `spec/zettlr-front` (worktree `.claude/worktrees/zettlr-front-spec`). Commits frequentes, um por task.
- Comandos de verificação: `uv run pytest` · `uv run ruff check . && uv run ruff format --check .` · `uv run mypy`.

## Desvios registrados do spec (com motivo)

1. **`csl:` NÃO vai no frontmatter dos drafts** (spec dizia `bibliography:` + `csl:`): o valor de `csl` é um caminho absoluto por máquina (`~/Zotero/styles/<estilo>.csl`) e não pode viver em template versionado. Ele viaja no **perfil gerado** (`prumo-docx.yaml`, que já é por máquina), resolvido best-effort na geração. O frontmatter carrega só `bibliography:` (relativo, estável).
2. **Console-script sempre shipped** (spec deixava condicionado a verificação empírica do campo de comando do Zettlr): `prumo-zettlr-export` entra incondicionalmente — é barato, robusto a qualquer semântica do campo, e vira o nome único documentado no guia.
3. **Gramática única alcança também `paper graph` e a prosa das skills** (spec listava compose + wiki lint): sem isso o `cites:` das notas e as instruções de escrita continuariam produzindo/esperando só `[[@key]]`, violando o I7 que o spec fecha.

---

### Task 1: `core/citations.py` — gramática única de citekey

**Files:**
- Create: `src/prumo_assist/core/citations.py`
- Create: `tests/unit/core/test_citations.py`
- Modify: `src/prumo_assist/domains/write/export.py:103-129` (remove `_CITEKEY_RE` + `scan_citekeys`; importa do core)

**Interfaces:**
- Consumes: nada (módulo folha de `core/`).
- Produces: `CITEKEY_RE: re.Pattern[str]`; `iter_citekeys(markdown_text: str) -> Iterator[str]` (ordem de 1ª ocorrência, dedup); `scan_citekeys(markdown_text: str) -> list[str]` (ordenado, captura ampla); `scan_marked_citekeys(markdown_text: str) -> list[str]` (ordenado, só formas marcadas). Tasks 2–4 e 12 consomem exatamente esses nomes. `export.scan_citekeys` continua importável (re-export).

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/unit/core/test_citations.py`:

```python
"""Tests da gramática única de citekey (core/citations)."""

from __future__ import annotations

from prumo_assist.core.citations import iter_citekeys, scan_citekeys, scan_marked_citekeys


def test_scan_catches_all_pandoc_autocomplete_forms() -> None:
    text = (
        "Bracketed [@Author2015, p. 123] e narrativa @Author2016 "
        "e narrativa com locator @Author2017 [p. 9]."
    )
    assert scan_citekeys(text) == ["Author2015", "Author2016", "Author2017"]


def test_scan_catches_legacy_wikilink_and_alias() -> None:
    text = "Veja [[@smith2024cohort]] e [[@jones2023trial|Jones et al.]]."
    assert scan_citekeys(text) == ["jones2023trial", "smith2024cohort"]


def test_scan_does_not_truncate_composite_keys() -> None:
    # Regressão: o regex antigo do compose ([a-zA-Z0-9._+-]+) truncava
    # chaves com pontuação interna que o Pandoc aceita.
    text = "[@vanDijk2019:pt2] e [@key.sub/part]"
    assert scan_citekeys(text) == ["key.sub/part", "vanDijk2019:pt2"]


def test_scan_skips_emails_and_code_blocks() -> None:
    text = "contato foo@bar.com\n```\n[@dentro_de_code]\n```\n[@real2024]"
    assert scan_citekeys(text) == ["real2024"]


def test_iter_preserves_first_occurrence_order() -> None:
    text = "[@zeta2020] então [@alpha2019] e de novo [@zeta2020]"
    assert list(iter_citekeys(text)) == ["zeta2020", "alpha2019"]


def test_marked_accepts_bracketed_and_wikilink_only() -> None:
    text = (
        "Marcada [@smith2024] e legado [[@jones2023]] e grupo [@a2020; @b2021, p. 3]. "
        "Handle solto @twitter_user fica de fora."
    )
    assert scan_marked_citekeys(text) == ["a2020", "b2021", "jones2023", "smith2024"]


def test_marked_skips_code_blocks() -> None:
    text = "```\n[@fake]\n```\n[@real]"
    assert scan_marked_citekeys(text) == ["real"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_citations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prumo_assist.core.citations'`

- [ ] **Step 3: Implementar `src/prumo_assist/core/citations.py`**

```python
"""Gramática única de citekey (Pandoc + legado Obsidian).

Uma citação Pandoc é ``@key`` (narrativa) ou ``[@key]``/``[@a; @b]``
(bracketed). O legado Obsidian usa ``[[@key]]``/``[[@key|alias]]``
(normalizado para ``[@key]`` no export). Este módulo é o ÚNICO lugar
do pacote que reconhece citekeys em texto (spec 2026-07-22; invariante
I7 do spec 2026-07-05): export, compose, wiki lint e paper graph
consomem estas funções — nunca regexes próprios.

Dois níveis de captura:

- ``iter_citekeys``/``scan_citekeys`` — amplo: qualquer ``@key`` fora
  de code block. Para pre-fetch e relatórios (falso positivo é barato).
- ``scan_marked_citekeys`` — conservador: só formas marcadas
  (``[[@key]]``, ou dentro de colchetes ``[...]``). Para lint/validação,
  onde um handle ``@fulano`` em prosa não pode virar warning espúrio.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

# Pandoc citation keys: alphanumeric/underscore start, then internal
# `:.#$%&-+?<>~/` punctuation that must be followed by more word chars
# (so we don't grab trailing sentence punctuation like the `.` in
# `[@key].`). Negative lookbehind on `@\w` skips emails (foo@bar).
CITEKEY_RE = re.compile(r"(?<![@\w])@([A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*)")

# Um span entre colchetes sem colchetes internos. Cobre ``[@key]``,
# ``[@a; @b, p. 3]`` e também o miolo de ``[[@key]]`` (o span interno).
_BRACKET_SPAN_RE = re.compile(r"\[[^\[\]]*\]")


def _body_lines(markdown_text: str) -> Iterator[str]:
    """Linhas fora de fenced code blocks."""
    in_code_block = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        yield line


def iter_citekeys(markdown_text: str) -> Iterator[str]:
    """Citekeys em ordem de 1ª ocorrência, sem repetição (captura ampla)."""
    seen: set[str] = set()
    for line in _body_lines(markdown_text):
        for match in CITEKEY_RE.finditer(line):
            key = match.group(1)
            if key not in seen:
                seen.add(key)
                yield key


def scan_citekeys(markdown_text: str) -> list[str]:
    """Extrai citekeys ``[@key]`` / ``@key`` do markdown, ordenadas.

    Não tenta substituir o parser do Pandoc — só precisa achar TODAS as
    chaves para pre-fetch/relatório. False positives (ex. nomes de
    variáveis fora de code block) só geram queries extras sem-resultado.
    """
    return sorted(iter_citekeys(markdown_text))


def scan_marked_citekeys(markdown_text: str) -> list[str]:
    """Citekeys em formas MARCADAS, ordenadas: ``[[@key]]`` legado ou
    dentro de colchetes ``[@key]``/``[@a; @b, p. 3]``.

    Narrativa solta (``@key`` fora de colchete) fica de fora de
    propósito — ver docstring do módulo.
    """
    keys: set[str] = set()
    for line in _body_lines(markdown_text):
        for span in _BRACKET_SPAN_RE.finditer(line):
            for match in CITEKEY_RE.finditer(span.group(0)):
                keys.add(match.group(1))
    return sorted(keys)
```

- [ ] **Step 4: Apontar o export para o core**

Em `src/prumo_assist/domains/write/export.py`: deletar o bloco inteiro do comentário `# Pandoc citation keys:` até o fim da função `scan_citekeys` (linhas 103–129, regex `_CITEKEY_RE` incluído) e adicionar ao bloco de imports do topo (junto de `from prumo_assist.core.csl import ...`):

```python
from prumo_assist.core.citations import scan_citekeys
```

`scan_citekeys` continua sendo usado por `export()`/`compose()` e re-exportado para os testes existentes (`tests/unit/write/test_export_pandoc_cmd.py` importa de `export` — segue funcionando).

- [ ] **Step 5: Rodar tudo verde e commitar**

Run: `uv run pytest tests/unit/core/test_citations.py tests/unit/write/ -v`
Expected: PASS (novos + suíte write intacta)

```bash
git add src/prumo_assist/core/citations.py tests/unit/core/test_citations.py src/prumo_assist/domains/write/export.py
git commit -m "feat(core): citations.py — gramática única de citekey (I7); export re-exporta"
```

---

### Task 2: `compose` usa o scanner canônico

**Files:**
- Modify: `src/prumo_assist/domains/write/compose.py:265-268` (deleta `_extract_citekeys_used`) e `:253` (call site em `write_output`)
- Rewrite: `tests/unit/write/test_compose_refs.py`

**Interfaces:**
- Consumes: `core.citations.scan_citekeys` (Task 1).
- Produces: `WriteOutput.citations_used` agora cobre as duas gramáticas (mesmo schema `WriteOutput/v1` — campo não muda de nome/tipo). `extract_missing_refs` inalterado.

- [ ] **Step 1: Reescrever os testes (falham no estado atual)**

Substituir o conteúdo de `tests/unit/write/test_compose_refs.py` por:

```python
"""Tests para refs faltantes e citekeys usados no compose (gramática única)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import extract_missing_refs, write_output


def test_extract_missing_refs_captures_descriptions() -> None:
    text = "Claim [REF FALTANTE: coorte multicêntrica]. Outra [REF FALTANTE: guideline 2025]."
    assert extract_missing_refs(text) == ["coorte multicêntrica", "guideline 2025"]


def test_extract_missing_refs_empty() -> None:
    assert extract_missing_refs("texto sem pendências") == []


def test_write_output_reports_citations_in_both_flavors(tmp_path: Path) -> None:
    content = "Intro [@smith2024cohort] e legado [[@jones2023trial]] e narrativa @lee2025core.\n"
    result = write_output(
        content=content,
        pj_path=tmp_path,
        kind="paper",
        mode="drafts",
        date="2026-07-22",
        slug="s1",
    )
    assert result.citations_used == ["jones2023trial", "lee2025core", "smith2024cohort"]


def test_write_output_does_not_truncate_composite_keys(tmp_path: Path) -> None:
    result = write_output(
        content="[@vanDijk2019:pt2]\n",
        pj_path=tmp_path,
        kind="paper",
        mode="drafts",
        date="2026-07-22",
        slug="s2",
    )
    assert result.citations_used == ["vanDijk2019:pt2"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_compose_refs.py -v`
Expected: FAIL — `citations_used == []` nos dois testes de `write_output` (regex antigo só via `[[@...]]` e truncava chave composta).

- [ ] **Step 3: Implementar**

Em `src/prumo_assist/domains/write/compose.py`:

1. Adicionar import no topo: `from prumo_assist.core.citations import scan_citekeys`
2. Deletar a função `_extract_citekeys_used` inteira (4 linhas no fim do arquivo).
3. Em `write_output`, trocar `citations_used=_extract_citekeys_used(content),` por `citations_used=scan_citekeys(content),`.

- [ ] **Step 4: Verde + commit**

Run: `uv run pytest tests/unit/write/ -v`
Expected: PASS

```bash
git add src/prumo_assist/domains/write/compose.py tests/unit/write/test_compose_refs.py
git commit -m "refactor(write): compose usa scanner canônico — morre o regex divergente (I7)"
```

---

### Task 3: `wiki lint` flavor-agnóstico

**Files:**
- Modify: `src/prumo_assist/domains/wiki/lint.py`
- Modify: `tests/unit/wiki/test_lint.py` (acrescenta testes)

**Interfaces:**
- Consumes: `core.citations.scan_marked_citekeys` (Task 1).
- Produces: `lint(pj_path)` com mesma assinatura/payload; código `broken_citekey` agora dispara para `[@key]` E `[[@key]]` (mensagem vira `f"@{ck} não existe no .bib"`); links markdown `[texto](arquivo.md)` contam como link de entrada (novos projetos não usam wikilink de página).

- [ ] **Step 1: Testes novos (falham)**

Acrescentar ao fim de `tests/unit/wiki/test_lint.py`:

```python
def test_lint_flags_broken_citekey_in_pandoc_form(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path, "@article{real,title={X}}\n")
    (pj / "docs" / "findings" / "f2.md").write_text(
        "---\ntype: finding\n---\n\nVer [@real] e [@ghost2020] e grupo [@real; @ghost2021].\n"
    )
    report = lint(pj)
    msgs = [i["message"] for i in report["issues"] if i["code"] == "broken_citekey"]
    assert any("ghost2020" in m for m in msgs)
    assert any("ghost2021" in m for m in msgs)
    assert not any("real" in m for m in msgs)


def test_lint_ignores_bare_handles_in_prose(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path, "@article{real,title={X}}\n")
    (pj / "docs" / "findings" / "f3.md").write_text(
        "---\ntype: finding\n---\n\nO autor @fulano comentou. Cite [@real].\n"
    )
    report = lint(pj)
    assert not any(
        i["code"] == "broken_citekey" and "fulano" in i["message"] for i in report["issues"]
    )


def test_lint_counts_markdown_links_as_incoming(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "concepts" / "alpha.md").write_text("---\ntype: concept\n---\n\nbody\n")
    (pj / "docs" / "concepts" / "beta.md").write_text(
        "---\ntype: concept\n---\n\nVer [alpha](alpha.md). E [[beta]] auto-ref.\n"
    )
    report = lint(pj)
    orphans = [i["page"] for i in report["issues"] if i["code"] == "orphan_page"]
    assert "alpha" not in orphans
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: FAIL nos 3 novos (pandoc-form não flagrado; alpha aparece como órfã).

- [ ] **Step 3: Implementar em `lint.py`**

1. Import: `from prumo_assist.core.citations import scan_marked_citekeys`
2. Deletar a constante `WIKILINK_RE` (linha 54 — não fica mais nenhum uso).
3. Adicionar constante logo abaixo de `PAGE_LINK_RE`:

```python
# Links markdown padrão [texto](alvo) — projetos Pandoc-puros não usam
# wikilink de página; sem isto, toda página nova viraria "órfã".
MD_LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")
```

4. No loop de páginas, trocar o bloco "Citekeys quebrados" por:

```python
        # Citekeys quebrados — formas marcadas nas duas gramáticas
        # ([@key] Pandoc e [[@key]] legado); narrativa solta fica fora
        # de propósito (handle @fulano em prosa não é citação).
        for ck in scan_marked_citekeys(text):
            if bib_keys and ck not in bib_keys:
                issues.append(
                    WikiIssue(
                        "warning",
                        "broken_citekey",
                        f"@{ck} não existe no .bib",
                        page=rel,
                    )
                )
```

5. Logo após o loop `for target in PAGE_LINK_RE.findall(text):` adicionar:

```python
        for md_target in MD_LINK_RE.findall(text):
            target = md_target.split("#")[0].strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            stem = Path(target).stem
            if stem in incoming:
                incoming[stem] += 1
```

6. Atualizar o bullet da docstring do módulo: `- Citekeys ``[[@key]]`` referenciados mas ausentes do .bib.` → `- Citekeys marcados (``[@key]`` Pandoc ou ``[[@key]]`` legado) ausentes do .bib.`

- [ ] **Step 4: Verde + commit**

Run: `uv run pytest tests/unit/wiki/ -v`
Expected: PASS (inclusive os testes antigos — `test_lint_flags_broken_citekey` só checa o código do issue, não a mensagem).

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki): lint flavor-agnóstico — valida [@key] e [[@key]]; links md contam como entrada"
```

---

### Task 4: `paper graph` flavor-agnóstico

**Files:**
- Modify: `src/prumo_assist/domains/paper/graph.py`
- Modify: `tests/unit/paper/test_graph.py`
- Modify: `src/prumo_assist/domains/paper/cli.py:48` e `src/prumo_assist/domains/paper/__init__.py:6` (docstrings)

**Interfaces:**
- Consumes: `core.citations.iter_citekeys` (Task 1).
- Produces: `extract_citekeys(body: str, known: set[str], self_citekey: str | None = None) -> list[str]` (renomeia `extract_wikilinks`; mesma semântica: ordem de 1ª ocorrência, dedup, filtra `known`/self). `update_graph(pj_path)` inalterado por fora.

- [ ] **Step 1: Testes novos (falham)**

Acrescentar a `tests/unit/paper/test_graph.py`:

```python
def test_extract_citekeys_accepts_pandoc_forms() -> None:
    body = "Baseia-se em [@a2020] e cita @b2021 [p. 3] além de [[@c2022]]."
    known = {"a2020", "b2021", "c2022", "unused"}
    assert extract_citekeys(body, known) == ["a2020", "b2021", "c2022"]


def test_extract_citekeys_filters_unknown_and_self() -> None:
    body = "[@self2020] e [@known2021] e [@ghost2022]"
    assert extract_citekeys(body, {"self2020", "known2021"}, "self2020") == ["known2021"]
```

E no mesmo arquivo, renomear mecanicamente todo uso/import de `extract_wikilinks` para `extract_citekeys` (o comportamento legado `[[@key]]` é preservado — os testes existentes devem continuar passando após o rename).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/paper/test_graph.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_citekeys'`

- [ ] **Step 3: Implementar em `graph.py`**

Substituir docstring do módulo, imports e a função por:

```python
"""Grafo passivo de citação: citações no corpo → ``cites:`` no YAML.

Reconhece as duas gramáticas via ``core/citations`` (``[@key]``/``@key``
Pandoc e ``[[@key]]`` legado). O filtro por ``known`` descarta qualquer
falso positivo da captura ampla. Migrado de ``cite_graph.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.core.citations import iter_citekeys
from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files
from prumo_assist.domains.paper.sync import FRONTMATTER_RE, read_nota_yaml, write_nota


def extract_citekeys(body: str, known: set[str], self_citekey: str | None = None) -> list[str]:
    """Retorna citekeys referenciados no body.

    - Preserva ordem da 1ª ocorrência; dedup.
    - Filtra os não-existentes em ``known`` e (se fornecido) o próprio
      ``self_citekey``.
    """
    return [key for key in iter_citekeys(body) if key != self_citekey and key in known]
```

(`import re` e `WIKILINK_RE` saem.) Em `update_graph`, trocar `new_cites = extract_wikilinks(body, known, self_key)` por `new_cites = extract_citekeys(body, known, self_key)`.

Docstrings-fachada: em `domains/paper/cli.py:48` → `"""Grafo passivo de citação: lê ``[@key]``/``[[@key]]`` no body, popula ``cites:`` no YAML."""`; em `domains/paper/__init__.py:6` → `- ``graph``        — grafo passivo de citação a partir de ``[@key]``/``[[@key]]```. Rodar `grep -rn "extract_wikilinks" src tests` e confirmar zero ocorrências restantes.

- [ ] **Step 4: Verde + commit**

Run: `uv run pytest tests/unit/paper/ -v`
Expected: PASS

```bash
git add src/prumo_assist/domains/paper/ tests/unit/paper/test_graph.py
git commit -m "feat(paper): graph flavor-agnóstico via core/citations (rename extract_citekeys)"
```

---

### Task 5: `domains/write/zettlr.py` + `prumo write zettlr-profile`

**Files:**
- Create: `src/prumo_assist/domains/write/zettlr.py`
- Create: `tests/unit/write/test_zettlr_profile.py`
- Modify: `src/prumo_assist/domains/write/cli.py` (novo subcomando)
- Modify: `src/prumo_assist/domains/write/api.py` (re-exports)

**Interfaces:**
- Consumes: `core.csl.resolve_csl` (levanta `CslNotFoundError`), `export._zotero_live_docx_filter()`.
- Produces: `PROFILE_RELPATH = Path("docs/templates/prumo-docx.yaml")`; `REFERENCE_DOC_RELPATH = Path("docs/templates/reference.docx")`; `generate_profile(pj_path: Path, *, style: str = "apa") -> Path` (idempotente); `profile_issues(pj_path: Path) -> list[str]`. Tasks 7 (doctor), 8 (init) e o CLI consomem esses nomes.

- [ ] **Step 1: Testes (falham)**

Criar `tests/unit/write/test_zettlr_profile.py`:

```python
"""Tests do gerador de perfil de export do Zettlr (defaults file)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from prumo_assist.domains.write.zettlr import PROFILE_RELPATH, generate_profile, profile_issues


def _gen(tmp_path: Path) -> Any:
    with patch(
        "prumo_assist.domains.write.zettlr.resolve_csl",
        return_value=Path("/fake/styles/apa.csl"),
    ):
        out = generate_profile(tmp_path)
    assert out == tmp_path / PROFILE_RELPATH
    return yaml.safe_load(out.read_text(encoding="utf-8"))


def test_profile_has_reader_writer_required_by_zettlr(tmp_path: Path) -> None:
    data = _gen(tmp_path)
    assert data["reader"].startswith("markdown")
    assert data["writer"] == "docx"


def test_profile_runs_citeproc_before_lua_filter(tmp_path: Path) -> None:
    # Num defaults file, `citeproc: true` rodaria DEPOIS dos lua filters
    # e quebraria o zotero_live_docx.lua — a ordem TEM que vir da lista.
    data = _gen(tmp_path)
    filters = data["filters"]
    assert filters[0] == "citeproc"
    assert filters[1].endswith("zotero_live_docx.lua")
    assert Path(filters[1]).is_file()


def test_profile_carries_style_metadata_and_csl(tmp_path: Path) -> None:
    data = _gen(tmp_path)
    assert data["metadata"]["zotero_csl_style"] == "apa"
    assert data["csl"] == "/fake/styles/apa.csl"


def test_profile_omits_csl_when_style_unavailable(tmp_path: Path) -> None:
    from prumo_assist.core.csl import CslNotFoundError

    with patch(
        "prumo_assist.domains.write.zettlr.resolve_csl",
        side_effect=CslNotFoundError("sem estilo"),
    ):
        out = generate_profile(tmp_path)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "csl" not in data


def test_profile_includes_reference_doc_when_present(tmp_path: Path) -> None:
    ref = tmp_path / "docs" / "templates" / "reference.docx"
    ref.parent.mkdir(parents=True)
    ref.write_bytes(b"PK\x03\x04fake")
    data = _gen(tmp_path)
    assert data["reference-doc"] == str(ref.resolve())


def test_profile_is_idempotent(tmp_path: Path) -> None:
    assert _gen(tmp_path) == _gen(tmp_path)


def test_profile_issues_empty_when_absent(tmp_path: Path) -> None:
    assert profile_issues(tmp_path) == []


def test_profile_issues_flags_broken_filter_with_fix_command(tmp_path: Path) -> None:
    p = tmp_path / PROFILE_RELPATH
    p.parent.mkdir(parents=True)
    p.write_text(
        yaml.safe_dump(
            {
                "reader": "markdown",
                "writer": "docx",
                "filters": ["citeproc", "/caminho/que/nao/existe.lua"],
            }
        ),
        encoding="utf-8",
    )
    issues = profile_issues(tmp_path)
    assert issues
    assert "prumo write zettlr-profile" in issues[0]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_zettlr_profile.py -v`
Expected: FAIL — módulo `zettlr` inexistente.

- [ ] **Step 3: Implementar `src/prumo_assist/domains/write/zettlr.py`**

```python
"""Geração do perfil de export do Zettlr (Pandoc defaults file).

O Zettlr exporta via perfis — defaults files com ``reader`` e ``writer``
obrigatórios (exigência do assets manager dele). Este módulo gera o
``docs/templates/prumo-docx.yaml`` do projeto replicando o que dá para
reproduzir do ``prumo write export --to docx`` sem Python: a cadeia
``citeproc`` ANTES do ``zotero_live_docx.lua``. ATENÇÃO: num defaults
file, ``citeproc: true`` rodaria o citeproc DEPOIS dos lua filters e
quebraria o filtro — por isso o citeproc entra como item da lista
``filters``, na frente.

Fica de fora por design (spec 2026-07-22): lookup BBT (URIs de relink)
e guardas pós-export — exclusivos do caminho canônico ``prumo write
export``. O perfil é gerado por máquina (caminho absoluto do filtro no
wheel instalado) — nunca commitado no template.
"""

from __future__ import annotations

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
    frontmatter de cada draft, que tem precedência sobre o defaults file.
    """
    profile: dict[str, object] = {
        "reader": _READER,
        "writer": "docx",
        "standalone": True,
        "filters": ["citeproc", str(_zotero_live_docx_filter())],
        "metadata": {"zotero_csl_style": style},
    }
    try:
        profile["csl"] = str(resolve_csl(style))
    except CslNotFoundError:
        pass
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
    issues: list[str] = []
    filters = data.get("filters") or []
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
```

- [ ] **Step 4: Subcomando + api**

Em `src/prumo_assist/domains/write/cli.py`, adicionar (padrão do `disclosure_command` — import local):

```python
@write_app.command("zettlr-profile")
def zettlr_profile_command(
    path: Annotated[Path, typer.Option("--path", help="Raiz do pj_*.")] = Path("."),
    style: Annotated[str, typer.Option("--style", help="Estilo CSL (default: apa).")] = "apa",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """(Re)gera o perfil de export docx do Zettlr (defaults file) do projeto."""
    with cli_run(json_mode=json_mode, catches=(OSError,)) as console:
        from prumo_assist.domains.write.zettlr import generate_profile

        out = generate_profile(path.resolve(), style=style)
        console.success(
            f"Perfil Zettlr gerado: {out}. Importe uma vez no Zettlr "
            "(Assets Manager → defaults files); re-rode este comando se o prumo for reinstalado."
        )
        console.emit({"profile": str(out)})
```

Em `src/prumo_assist/domains/write/api.py` (re-export puro), adicionar:

```python
from prumo_assist.domains.write.zettlr import generate_profile as generate_zettlr_profile
from prumo_assist.domains.write.zettlr import profile_issues as zettlr_profile_issues
```

e incluir `"generate_zettlr_profile"` e `"zettlr_profile_issues"` no `__all__` (ordem alfabética).

- [ ] **Step 5: Verde + commit**

Run: `uv run pytest tests/unit/write/ -v && uv run mypy && uv run ruff check .`
Expected: PASS / sem erros

```bash
git add src/prumo_assist/domains/write/zettlr.py src/prumo_assist/domains/write/cli.py src/prumo_assist/domains/write/api.py tests/unit/write/test_zettlr_profile.py
git commit -m "feat(write): prumo write zettlr-profile — defaults file do Zettlr com citeproc→lua"
```

---

### Task 6: console-script `prumo-zettlr-export` (custom command do Zettlr)

**Files:**
- Modify: `src/prumo_assist/domains/write/cli.py` (função `zettlr_export_entry`)
- Modify: `pyproject.toml` (`[project.scripts]`)
- Modify: `tests/unit/write/test_cli.py` (teste novo)

**Interfaces:**
- Consumes: `export.export(page=..., to="docx")` (assinatura existente).
- Produces: entrypoint `prumo-zettlr-export <arquivo.md>` — o campo de custom command do Zettlr aceita um binário e anexa o caminho absoluto do arquivo; este wrapper fecha o contrato sem depender de o campo aceitar argumentos.

- [ ] **Step 1: Teste (falha)**

Acrescentar a `tests/unit/write/test_cli.py`:

```python
def test_zettlr_entry_calls_canonical_docx_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "draft.md"
    page.write_text("x")
    called: dict[str, object] = {}

    def fake_export(*, page: Path, to: str = "docx", **kwargs: object) -> Path:
        called["page"] = page
        called["to"] = to
        return tmp_path / "out.docx"

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", fake_export)
    monkeypatch.setattr("sys.argv", ["prumo-zettlr-export", str(page)])
    from prumo_assist.domains.write.cli import zettlr_export_entry

    zettlr_export_entry()
    assert called == {"page": page.resolve(), "to": "docx"}
```

(Se `test_cli.py` ainda não importa `pytest`/`Path`, adicionar os imports no topo.)

Run: `uv run pytest tests/unit/write/test_cli.py -v` → FAIL (`zettlr_export_entry` inexistente).

- [ ] **Step 2: Implementar**

Em `src/prumo_assist/domains/write/cli.py` (fim do arquivo):

```python
def zettlr_export_entry() -> None:
    """Console-script pro custom command do Zettlr: `prumo-zettlr-export <arquivo.md>`.

    O Zettlr invoca o comando com o caminho absoluto do arquivo
    selecionado como único argumento e mostra a saída ao usuário.
    Caminho canônico: mesmas guardas do ``prumo write export --to docx``.
    """
    import sys

    with cli_run(
        json_mode=False, catches=(FileNotFoundError, ValueError, RuntimeError)
    ) as console:
        if len(sys.argv) != 2:
            raise PrumoError("uso: prumo-zettlr-export <arquivo.md>")
        page = Path(sys.argv[1]).resolve()
        result = export.export(page=page, to="docx")
        console.success(f"exportado: {result}")
```

Em `pyproject.toml`:

```toml
[project.scripts]
prumo = "prumo_assist.cli:app"
prumo-zettlr-export = "prumo_assist.domains.write.cli:zettlr_export_entry"
```

- [ ] **Step 3: Verde + commit**

Run: `uv run pytest tests/unit/write/test_cli.py -v && uv run mypy`
Expected: PASS

```bash
git add src/prumo_assist/domains/write/cli.py pyproject.toml tests/unit/write/test_cli.py
git commit -m "feat(write): console-script prumo-zettlr-export p/ custom command do Zettlr"
```

---

### Task 7: `doctor` checa o perfil Zettlr

**Files:**
- Modify: `src/prumo_assist/cli.py` (doctor_command, linhas ~526–594)
- Modify: `tests/unit/test_cli_doctor.py`

**Interfaces:**
- Consumes: `domains.write.zettlr.profile_issues` (Task 5).
- Produces: `prumo doctor` inclui issues do perfil Zettlr no bloco estrutural (exit 1 + mensagem com `prumo write zettlr-profile`). Perfil ausente = silêncio.

- [ ] **Step 1: Teste (falha)**

Acrescentar a `tests/unit/test_cli_doctor.py` (o helper `_project` já existe no arquivo):

```python
def test_doctor_flags_broken_zettlr_profile(tmp_path: Path) -> None:
    import yaml

    pj = _project(tmp_path)
    profile = pj / "docs" / "templates" / "prumo-docx.yaml"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        yaml.safe_dump({"reader": "markdown", "writer": "docx", "filters": ["/nao/existe.lua"]}),
        encoding="utf-8",
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 1
    assert "prumo write zettlr-profile" in result.output


def test_doctor_silent_when_no_zettlr_profile(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 0, result.output
```

Run: `uv run pytest tests/unit/test_cli_doctor.py -v` → FAIL no primeiro (exit 0, sem mensagem).

- [ ] **Step 2: Implementar**

Em `src/prumo_assist/cli.py`: adicionar import no topo (bloco de imports do prumo):

```python
from prumo_assist.domains.write.zettlr import profile_issues as zettlr_profile_issues
```

Em `doctor_command`, logo após o loop `for adapter_cls in INTEGRATIONS.values(): ...`:

```python
    # Perfil de export do Zettlr (se existir) aponta pra arquivos vivos?
    issues.extend(zettlr_profile_issues(target))
```

- [ ] **Step 3: Verde + commit**

Run: `uv run pytest tests/unit/test_cli_doctor.py -v`
Expected: PASS

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_doctor.py
git commit -m "feat(doctor): acusa perfil Zettlr quebrado com fix embutido"
```

---

### Task 8: `prumo init` gera o perfil

**Files:**
- Modify: `src/prumo_assist/cli.py` (init_command, linhas ~532–616)
- Modify: `tests/unit/test_cli_init.py`

**Interfaces:**
- Consumes: `domains.write.zettlr.generate_profile` (Task 5).
- Produces: payload JSON do init ganha a chave `"zettlr_profile": str | None`. Falha na geração NÃO bloqueia o scaffold (warn com fix).

- [ ] **Step 1: Teste (falha)**

Acrescentar a `tests/unit/test_cli_init.py`:

```python
def test_init_generates_zettlr_profile(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output
    profile = target / "docs" / "templates" / "prumo-docx.yaml"
    assert profile.is_file()
    payload = json.loads(result.stdout)
    assert payload["zettlr_profile"] == str(profile)
```

(Em CI sem `~/Zotero/styles/`, `generate_profile` omite `csl` sozinho — sem mock.)

Run: `uv run pytest tests/unit/test_cli_init.py::test_init_generates_zettlr_profile -v` → FAIL.

- [ ] **Step 2: Implementar**

Em `init_command`, após o bloco de módulos (`modules_applied`) e ANTES da montagem do `payload`:

```python
        # Perfil de export do Zettlr — caminhos absolutos por máquina,
        # então é gerado aqui (nunca vem do template). Não pode derrubar
        # o scaffold: falha vira warning com o fix embutido.
        zettlr_profile: str | None = None
        try:
            from prumo_assist.domains.write.zettlr import generate_profile

            zettlr_profile = str(generate_profile(target))
        except (OSError, PrumoError) as e:
            console.warn(
                f"Perfil Zettlr não gerado ({e}). Rode depois: `prumo write zettlr-profile`."
            )
```

E no dict `payload`, adicionar a linha `"zettlr_profile": zettlr_profile,` (após `"modules_applied"`).

- [ ] **Step 3: Verde + commit**

Run: `uv run pytest tests/unit/test_cli_init.py tests/unit/test_pj_base_integration.py -v`
Expected: PASS

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_init.py
git commit -m "feat(init): scaffold gera perfil Zettlr do projeto (tolerante a falha)"
```

---

### Task 9: `templates/pj_base` v2 — Obsidian sai, Pandoc puro entra

**Files:**
- Delete: `templates/pj_base/.obsidian/` (5 arquivos), `templates/pj_base/references/views/papers.base`, `templates/pj_base/docs/canvas/project.canvas`
- Create: `templates/pj_base/docs/templates/reference.docx` (gerado com pandoc, binário commitado)
- Modify: `templates/pj_base/.gitignore`, `templates/pj_base/references/templates/literature_note.md`, `templates/pj_base/references/_index.md`, `templates/pj_base/.claude/rules/documentation.md`, `templates/pj_base/CLAUDE.md`, `templates/pj_base/README.md`, `templates/pj_base/docs/project_guide.md`
- Modify: `tests/unit/test_pj_base_integration.py`, `tests/unit/test_cli_init.py`

**Interfaces:**
- Consumes: nada de código — só o template copiado por `shutil.copytree`/`overlay`.
- Produces: árvore v2 que a Task 5 (`REFERENCE_DOC_RELPATH`) e o teste `test_init_scaffold_is_pandoc_pure` esperam.

- [ ] **Step 1: Testes primeiro (falham)**

Em `tests/unit/test_pj_base_integration.py`, na lista de núcleo do teste `test_core_is_minimal_and_modules_rebuild`: remover a entrada `"docs/canvas/project.canvas"` e adicionar `"docs/templates/reference.docx"`.

Em `tests/unit/test_cli_init.py`, acrescentar:

```python
def test_init_scaffold_is_pandoc_pure(tmp_path: Path) -> None:
    """pj_base v2: sem vault Obsidian e sem sintaxe Obsidian nos .md."""
    target = tmp_path / "pj_demo"
    assert runner.invoke(app, ["init", str(target), "--json"]).exit_code == 0
    assert not (target / ".obsidian").exists()
    assert not (target / "references" / "views").exists()
    assert not (target / "docs" / "canvas").exists()
    offenders: list[str] = []
    for md in target.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        if "[[@" in text or "![[" in text or "> [!" in text:
            offenders.append(str(md.relative_to(target)))
    assert offenders == []
```

Run: `uv run pytest tests/unit/test_cli_init.py::test_init_scaffold_is_pandoc_pure -v` → FAIL (lista `.obsidian`, `literature_note.md`, `documentation.md`, `_index.md`).

- [ ] **Step 2: Remoções + reference.docx**

```bash
git rm -r templates/pj_base/.obsidian templates/pj_base/references/views templates/pj_base/docs/canvas
mkdir -p templates/pj_base/docs/templates
pandoc --print-default-data-file reference.docx > templates/pj_base/docs/templates/reference.docx
file templates/pj_base/docs/templates/reference.docx   # esperado: "Microsoft Word 2007+" ou "Zip archive"
```

- [ ] **Step 3: `.gitignore` do template**

Deletar o bloco inteiro (8 linhas):

```gitignore
# Obsidian — ignorar estado pessoal, manter config compartilhada
.obsidian/workspace*.json
.obsidian/cache/
.obsidian/updates.json
.obsidian/plugins/*/data.json
!.obsidian/plugins/obsidian-linter/data.json
.obsidian/plugins/*/.cache/
.obsidian/hotkeys.json
```

- [ ] **Step 4: `literature_note.md` (corpo novo; frontmatter YAML fica IDÊNTICO)**

Substituir o corpo (tudo após o `---` de fechamento do frontmatter) por:

```markdown
**TL;DR** — _(uma frase: o que o paper fez e resultado principal)_

## Problema

_(pergunta clínica/técnica, gap na literatura)_

## Método

_(dataset, n, modalidades, arquitetura, backbone, treino, hiperparâmetros, baselines)_

## Resultados

_(métricas principais com IC; referenciar figuras/tabelas como `Fig. 3 (p.7)`, `Table 2 (p.5)`)_

> "trecho exato" (p. XX)

## Limitações

_(o que o paper assume, o que não testou, reproducibilidade)_

## Relevância para este projeto

_(por que entrou no acervo; o que reaproveitar — split, métrica, backbone, baseline)_

## Referências citadas

_(citações Pandoc para outras notas do acervo)_

- [@citekey_outro]

## Notas

_(observações, dúvidas abertas, ideias)_
```

- [ ] **Step 5: `references/_index.md`**

Trocar a linha `_(agrupar quando começar a haver papers; use wikilinks `[[@citekey]]`)_` por `_(agrupar quando começar a haver papers; use citações Pandoc `[@citekey]`)_`.

- [ ] **Step 6: `.claude/rules/documentation.md` — conteúdo INTEGRAL novo**

```markdown
---
paths:
  - "**/pj_*/docs/**"
  - "**/pj_*/references/**"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/documentation.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Documentação de projeto e acervo bibliográfico

Contrato do que vive em cada `pj_*` para documentação de estudo e gestão de artigos. A fonte é Markdown Pandoc puro versionado em git; o front humano é o **Zettlr** (workspace na raiz do projeto — setup one-time em `docs/project_guide.md`, seção Editor).

## Estrutura

| Pasta | Conteúdo |
|-------|----------|
| `docs/` | Documentação do estudo — `README.md`, `protocol.md`, `decisions/`, `templates/` (reference.docx + perfil Zettlr gerado) |
| `references/` | Acervo bibliográfico — MOC, BibTeX, PDFs, notas, templates |

```
pj_*/references/
├── _index.md             # MOC: paper primário, por tema, por status
├── _references.bib       # Zotero + Better BibTeX (auto-export)
├── pdfs/                 # PDFs gitignorados (copyright)
├── templates/literature_note.md
└── notes/<citekey>/_meta.md    # 1 pasta por paper (layout α)
```

## Citation key — fonte única de identidade

Padrão **Better BibTeX**: `<sobrenomeMinúsculo><ano><primeiraPalavraTítuloMinúscula>` em ASCII puro, sem espaços/acentos. Desempate com sufixo `a/b/c`.

Ex.: `smith2024cohort`, `jones2023trial`, `jones2023triala` (desempate).

A mesma string é usada em **todos** os artefatos:

- nome do PDF: `pdfs/<citekey>.pdf`
- nome da nota: `notes/<citekey>/_meta.md`
- entrada BibTeX: `@article{<citekey>, ...}`
- citação no corpo: `[@<citekey>]` — sintaxe Pandoc; o Zettlr renderiza no editor e autocompleta ao digitar `@`

## YAML é a única fonte de verdade

Toda metadata de paper vive no **YAML frontmatter** da nota. Proibido metadata inline no corpo das notas versionadas — polui o RAG file-based.

Campos obrigatórios (subset CSL-JSON + curadoria):

| Campo | Tipo | Valores |
|-------|------|---------|
| `id` | string | = citekey |
| `type` | string | `article-journal`, `paper-conference`, `manuscript`, `chapter`, `review` |
| `title` | string | título do paper |
| `author` | lista | `[{family: "...", given: "..."}]` |
| `issued` | objeto | `{date-parts: [[YYYY]]}` |
| `DOI` | string | vazio se preprint sem DOI |
| `container-title` | string | journal / conferência / preprint server |
| `URL` | string | link canônico |
| `pdf` | string | caminho relativo `../../pdfs/<citekey>.pdf` |
| `tags` | lista | keywords livres |
| `role` | string | `primary` (exatamente 1 por projeto), `supporting`, `background`, `replaced` |
| `status` | string | `unread`, `reading`, `read`, `skimmed` |
| `rating` | int ou null | 1–5 |
| `added` | date | ISO `YYYY-MM-DD` |
| `tldr` | string | 1 linha |
| `cites` | lista | citekeys de papers citados que estão neste acervo |

## Seções fixas da nota (corpo markdown)

Ordem canônica, cabeçalhos `##` exatos:

```
## Problema
## Método
## Resultados
## Limitações
## Relevância para este projeto
## Referências citadas
## Notas
```

Destaques usam Markdown puro: parágrafo com **TL;DR** em negrito, blockquote `> "trecho exato" (p. XX)` para citações literais. Callouts do Obsidian são legado — não usar em material novo.

## Como o agente busca no acervo

| Intenção | Comando |
|----------|---------|
| Paper principal do projeto | `rg "^role: primary" references/notes/` |
| Fuzzy por autor/título | `/prumo-assist:paper-manager find "<query>"` ou `make cite Q="<query>"` |
| Papers sobre um tema | `rg -l "combinado" references/notes/` |
| O que um paper cita (grafo passivo) | `Read references/notes/<citekey>/_meta.md` (campo `cites:`, populado por `update-cites` ao fim de `sync`) |
| Quem cita um paper | `rg "@<citekey>" references/notes/` ou `/prumo-assist:paper-manager graph <citekey>` |
| Não lidos | `rg "^status: unread" references/notes/` |
| Bibliografia formatada | `Read references/_references.bib` |

## Skill dedicada

Operações de alto nível (adicionar paper via DOI, promover para `primary`, listar, sincronizar `.bib`) estão em `/prumo-assist:paper-manager`. Preferir a skill a editar YAML à mão quando for ingestão.

Para extrair conteúdo estruturado do PDF (TL;DR, PICOT, Método, Resultados, Limitações), use `/prumo-assist:paper-extract <citekey>` (single) ou `/prumo-assist:paper-extract-all` (batch). Pressuposto: `/prumo-assist:paper-manager sync` + `make sync-pdfs` já executados.

## PDFs e copyright

`references/pdfs/*.pdf` é **gitignored**. Versionam-se apenas as notas `.md` e o `.bib`. Cada colaborador cuida do próprio diretório local de PDFs.
```

- [ ] **Step 7: `CLAUDE.md`, `README.md` e `project_guide.md` do template**

`CLAUDE.md`: na árvore "Estrutura do projeto (núcleo)", trocar a linha `├── docs/{_index.md, _log.md, project_guide.md, decisions/, canvas/}` por `├── docs/{_index.md, _log.md, project_guide.md, decisions/, templates/}`. Na seção "Como operar", adicionar bullet após o de Bibliografia:

```markdown
- **Editor:** o front humano é o Zettlr (workspace na raiz do projeto). Setup one-time e limitações: `docs/project_guide.md`, seção "Editor (Zettlr)".
```

`README.md`: na Estrutura, trocar `├── docs/         Wiki + project_guide.md + decisions/ + canvas/` por `├── docs/         Wiki + project_guide.md + decisions/ + templates/`. No Setup, adicionar linha após o bloco de código:

```markdown
Editor recomendado: [Zettlr](https://www.zettlr.com) ≥ 3.0 — preview vivo de citações; setup em `docs/project_guide.md`.
```

`docs/project_guide.md`: acrescentar ao final:

```markdown
## Editor (Zettlr) — setup one-time

O front humano deste projeto é o [Zettlr](https://www.zettlr.com) (≥ 3.0 — o Pandoc embutido precisa ser 3.x). Uma vez só:

1. **Workspace:** File → Open Workspace → raiz deste projeto.
2. **Preview de citação:** Settings → Display → ligar "Render citations".
3. **Autocomplete:** digite `@` — as chaves vêm do `bibliography:` no frontmatter dos drafts (`references/_references.bib`, mantido pelo Better BibTeX com "Keep updated").
4. **Perfil docx de trabalho:** Settings → Assets Manager → defaults files → importar `docs/templates/prumo-docx.yaml`. Produz docx estilizado com campos Zotero vivos — sem URIs de relink e sem guardas: bom para leitura/compartilhamento, NUNCA para entrega.
5. **Docx canônico (entrega/coautores):** Settings → Import/Export → Custom export commands → nome "prumo docx (canônico)", comando `prumo-zettlr-export`. Ou no terminal: `prumo write export docs/drafts/<arquivo>.md`.
6. **Convivência com agentes:** ativar o reload automático de mudanças externas ("Always load remote changes to the current file").
7. Prumo reinstalado e o export do perfil quebrou? `prumo write zettlr-profile` regenera (o `prumo doctor` avisa).

Limitações documentadas: o preview in-editor é sempre Chicago in-text (o CSL real aparece nos exports); com Zotero fechado o preview segue funcionando (lê o `.bib` estático), mas o `.bib` pode estar stale.
```

- [ ] **Step 8: Verde + commit**

Run: `uv run pytest tests/unit/test_cli_init.py tests/unit/test_pj_base_integration.py tests/unit/test_cli_add.py -v`
Expected: PASS

```bash
git add -A templates/pj_base tests/unit/test_pj_base_integration.py tests/unit/test_cli_init.py
git commit -m "feat(pj_base)!: v2 Zettlr-ready — sai vault Obsidian, entra Pandoc puro + reference.docx"
```

---

### Task 10: templates `write-*` Zettlr-ready (frontmatter + `{#refs}`)

**Files:**
- Modify: `skills/write-paper/template.md`, `skills/write-projeto-cep/template.md`, `skills/write-statistics/template.md`, `skills/write-scientific/template.md`
- Create: `tests/unit/write/test_templates_zettlr.py`

**Interfaces:**
- Consumes: `core.paths.resolve_resource("skills")`.
- Produces: drafts nascem com `bibliography:` (preview/autocomplete no Zettlr sem config global) e manuscritos com o placeholder `::: {#refs}` que a guarda `_assert_bibliography_present` exige no docx.

- [ ] **Step 1: Teste (falha)**

Criar `tests/unit/write/test_templates_zettlr.py`:

```python
"""Templates write-* prontos pro Zettlr (frontmatter bibliography + refs div)."""

from __future__ import annotations

from prumo_assist.core.paths import resolve_resource

KINDS = ("paper", "projeto-cep", "statistics", "scientific")


def test_all_write_templates_declare_bibliography() -> None:
    skills = resolve_resource("skills")
    for kind in KINDS:
        text = (skills / f"write-{kind}" / "template.md").read_text(encoding="utf-8")
        assert "bibliography: ../../references/_references.bib" in text, kind


def test_manuscript_templates_have_refs_placeholder() -> None:
    skills = resolve_resource("skills")
    for kind in ("paper", "projeto-cep"):
        text = (skills / f"write-{kind}" / "template.md").read_text(encoding="utf-8")
        assert "::: {#refs}" in text, kind
```

Run: `uv run pytest tests/unit/write/test_templates_zettlr.py -v` → FAIL.

- [ ] **Step 2: Implementar**

Nos 4 templates, adicionar como ÚLTIMA linha do frontmatter YAML (antes do `---` de fechamento): `bibliography: ../../references/_references.bib` (drafts vivem em `docs/drafts/` — `compose_path` — logo o relativo sobe dois níveis).

Em `skills/write-paper/template.md`, substituir o final:

```markdown
# References

<!-- NÃO gerar; lista é responsabilidade do export Pandoc + CSL. -->
```

por:

```markdown
# References

<!-- NÃO gerar a lista à mão — o export (Pandoc + CSL) materializa aqui. -->

::: {#refs}
:::
```

Em `skills/write-projeto-cep/template.md`, acrescentar ao final do arquivo:

```markdown

# Referências

::: {#refs}
:::
```

- [ ] **Step 3: Verde + commit**

Run: `uv run pytest tests/unit/write/test_templates_zettlr.py -v`
Expected: PASS

```bash
git add skills/write-paper/template.md skills/write-projeto-cep/template.md skills/write-statistics/template.md skills/write-scientific/template.md tests/unit/write/test_templates_zettlr.py
git commit -m "feat(write-family): templates com bibliography no frontmatter + placeholder {#refs}"
```

---

### Task 11: convenção de citação Pandoc nas skills + regen de índices

**Files:**
- Modify: `skills/scientific-writing/SKILL.md`, `skills/write-paper/SKILL.md`, `skills/paper-manager/SKILL.md`, `skills/wiki-query/SKILL.md`, `skills/wiki-lint/SKILL.md`, `skills/active-learning/SKILL.md`
- Regenerate: `README.md`, `skills/start/SKILL.md` (blocos gerados — via script)

**Interfaces:**
- Consumes: nada de código.
- Produces: skills instruem `[@key]` na ESCRITA; leitura/lint mencionam as duas formas. `skills/start` NÃO se edita à mão (bloco gerado da description do wiki-query).

- [ ] **Step 1: Substituições exatas (old → new, por arquivo)**

`skills/scientific-writing/SKILL.md`:
- L36: `- Citações no draft seguem o padrão Obsidian wikilink `[[@citekey|display text opcional]]`.` → `- Citações no draft seguem a sintaxe Pandoc: `[@citekey]` (bracketed; múltiplas no mesmo colchete separadas por `;` — `[@a; @b]`). Legado `[[@citekey|alias]]` é aceito na leitura/export, mas não escreva novo.`
- L43: `**Regra.** Toda citação `[[@citekey]]` (com ou sem alias `|`) deve aparecer **antes do ponto final** ...` → `**Regra.** Toda citação `[@citekey]` deve aparecer **antes do ponto final** ...` (resto da frase igual)
- L46: `> Modelos combinados [[@smith2025review]] atingem ...` → `> Modelos combinados [@smith2025review] atingem ...`
- L49: `> Modelos combinados atingem alto desempenho quando todas as modalidades estão presentes [[@smith2025review]].` → `> Modelos combinados atingem alto desempenho quando todas as modalidades estão presentes [@smith2025review].`
- L52: `> Liang et al [[@liang2024foundations]] propõem três princípios.` → `> Liang et al. [@liang2024foundations] propõem três princípios.`
- L59: `> ...premissa raramente sustentada [[@a]], [[@b]], [[@c]].` → `> ...premissa raramente sustentada [@a], [@b], [@c].`
- L62: `> ...premissa raramente sustentada [[@a]] [[@b]] [[@c]].` → `> ...premissa raramente sustentada [@a; @b; @c].`

`skills/write-paper/SKILL.md`:
- L35: `1. **Citação strict.** Só `[[@citekey]]` que existe em ...` → `1. **Citação strict.** Só `[@citekey]` que existe em ...` (resto igual, trocando também `sem wikilink` por `sem citekey`)
- L78: `Cada `[[@<key>]]` deve estar em `inputs.citekeys` ...` → `Cada `[@<key>]` deve estar em `inputs.citekeys` ...`

`skills/paper-manager/SKILL.md`:
- L135: `... com o novo wikilink `[[@<citekey>]]` + título ...` → `... com a citação `[@<citekey>]` + título ...`
- L183: `... e insira `[[@<citekey>]]` na linha <N>?` → `... e insira `[@<citekey>]` na linha <N>?`

`skills/wiki-query/SKILL.md`:
- L3 (description do frontmatter): trocar `([[wikilinks]] e [[@citekeys]])` por `([[wikilinks]] e [@citekeys])`
- L62: `- <bullet 1> — ver [[página-a]], [[@citekey]]` → `- <bullet 1> — ver [[página-a]], [@citekey]`
- L75: `(wikilink `[[…]]` ou `[[@citekey]]`)` → `(wikilink `[[…]]` ou citação `[@citekey]`)`

`skills/wiki-lint/SKILL.md`:
- L64: `Toda `[[@foo]]` deve ter entrada `@<tipo>{foo,…}` em ...` → `Toda citação `[@foo]` (ou legado `[[@foo]]`) deve ter entrada `@<tipo>{foo,…}` em ...`
- L177: `- `[[@foo]]` referenciada em [[página-x]] — ausente do .bib` → `- `[@foo]` referenciada em [[página-x]] — ausente do .bib`

`skills/active-learning/SKILL.md`:
- L56: `> - [[@hanley1982roc]]` → `> - [@hanley1982roc]`
- L79: `"citations":["[[@k]]"]` → `"citations":["[@k]"]`
- L88: `Cite `[[@key]]` que confirma.` → `Cite `[@key]` que confirma.`
- L100: `mostre a fonte correta `[[@key]]` ou `[[page]]`.` → `mostre a fonte correta `[@key]` ou `[[page]]`.`

- [ ] **Step 2: Regenerar índices**

Run: `uv run python .github/scripts/gen_indexes.py`
Expected: `atualizado README.md` e `atualizado skills/start/SKILL.md` (a description do wiki-query mudou). Depois: `uv run python .github/scripts/gen_indexes.py --check` → "tudo em dia".

- [ ] **Step 3: Verificar e commitar**

Run: `grep -rn '\[\[@' skills/*/SKILL.md` — restam APENAS menções deliberadas de legado (`wiki-lint` L64 e a linha de scientific-writing L36 que menciona a forma legada). `uv run pytest` verde.

```bash
git add skills/ README.md
git commit -m "docs(skills): convenção de citação vira Pandoc [@key]; legado aceito na leitura"
```

---

### Task 12: guarda de citekey faltante no docx canônico

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (nova assert + captura de stderr em `export()` e `compose()`)
- Modify: `tests/unit/write/test_export_pandoc_cmd.py`

**Interfaces:**
- Consumes: `ZoteroCitekeyNotFoundError` (existente).
- Produces: `_assert_no_citeproc_missing(stderr: str) -> None`; `export()`/`compose()` docx falham alto quando o citeproc reporta citekey ausente do `.bib` (spec 2026-07-22, tabela de erros: "export canônico falha alto").

- [ ] **Step 1: Testes (falham)**

Acrescentar a `tests/unit/write/test_export_pandoc_cmd.py` (import de `_assert_no_citeproc_missing` junto aos demais):

```python
def test_citeproc_missing_clean_stderr_passes() -> None:
    _assert_no_citeproc_missing("[INFO] Running filter citeproc\n")


def test_citeproc_missing_raises_with_keys_and_fix() -> None:
    stderr = (
        "[WARNING] Citeproc: citation smith2024 not found\n"
        "[WARNING] Citeproc: citation ghost2020 not found\n"
    )
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_citeproc_missing(stderr)
    msg = str(exc.value)
    assert "smith2024" in msg and "ghost2020" in msg
    assert "sync-paper" in msg
```

Run: `uv run pytest tests/unit/write/test_export_pandoc_cmd.py -v` → FAIL (import).

- [ ] **Step 2: Implementar**

Em `export.py`, após `_assert_no_missing_citekeys` (que permanece — pipeline legado):

```python
_CITEPROC_MISSING_RE = re.compile(r"\[WARNING\] Citeproc: citation (\S+) not found")


def _assert_no_citeproc_missing(stderr: str) -> None:
    """Promove o warning do citeproc (citekey ausente do ``.bib``) a erro.

    O pandoc sai com exit 0 deixando a citação como ``(key?, ...)`` no
    docx — inaceitável num artefato de entrega (spec 2026-07-22).
    """
    missing = sorted(set(_CITEPROC_MISSING_RE.findall(stderr)))
    if missing:
        raise ZoteroCitekeyNotFoundError(
            f"{len(missing)} citekey(s) não existem no .bib: "
            + ", ".join(missing)
            + ". Confira a grafia ou rode `make sync-paper` para atualizar o .bib."
        )
```

Em `export()` E em `compose()`, substituir `subprocess.run(cmd, check=True, text=True)` por:

```python
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"pandoc falhou (exit {proc.returncode}):\n{proc.stderr.strip()[-2000:]}"
            )
        if to == "docx":
            _assert_no_citeproc_missing(proc.stderr)
```

(Em `export()` a linha `logger.info(...)` fica; a chamada `_assert_bibliography_present(out)` que já existe permanece depois.)

- [ ] **Step 3: Verde + commit**

Run: `uv run pytest tests/unit/write/ -v && uv run mypy`
Expected: PASS

```bash
git add src/prumo_assist/domains/write/export.py tests/unit/write/test_export_pandoc_cmd.py
git commit -m "feat(write): docx canônico falha alto em citekey ausente (warning citeproc → erro)"
```

---

### Task 13: ADR-0015 — política de release pré-1.0 + emendas

**Files:**
- Create: `docs/adr/adr-0015-pre-1-0-patch-para-releasavel.md`
- Modify: `RELEASING.md`, `.claude/rules/release.md`
- Regenerate: `docs/adr/_index.md` (script)

**Interfaces:** nenhum código. ADR-0011 fica imutável (superseded parcialmente por referência).

- [ ] **Step 1: Criar o ADR (formato MADR minimal do repo)**

`docs/adr/adr-0015-pre-1-0-patch-para-releasavel.md`:

```markdown
# ADR-0015 — Pré-1.0: PATCH para todo release; MINOR reservado a breaking/marco

- Status: aceito
- Data: 2026-07-22
- Origem: [[2026-07-22-zettlr-front-design]]

## Contexto
Sob o ADR-0011, qualquer skill/subcomando novo bumpa MINOR. Em fase de iteração frequente isso infla o número (0.6 → 0.61 → 0.62…) e treina o consumidor a ignorar releases — o oposto do que a regra-mãe quer.

## Decisão
Enquanto a versão for `0.x`: PATCH cobre tudo que é releasável, inclusive skill/subcomando novo; MINOR fica reservado a breaking ("⚠ Breaking") ou fechamento de fase/marco do ROADMAP. A regra-mãe do ADR-0011 permanece (versão = interface pública; `.github/`, README, CHANGELOG, `.gitignore` e `docs/` não bumpam). Semântica: MINOR = "leia o changelog antes de atualizar"; PATCH = "atualize sem medo".

## Consequências
Supersede o mapeamento pré-1.0 do ADR-0011 (o restante daquele ADR segue válido). RELEASING.md e `.claude/rules/release.md` emendados. Primeiro release sob a política: 0.62.1 (spec Zettlr-front). No 1.0.0, SemVer pleno reassume e este ADR expira.
```

- [ ] **Step 2: Emendar `RELEASING.md`**

Inserir nova seção logo APÓS "## Regra-mãe":

```markdown
## Pré-1.0 — mapeamento vigente (ADR-0015)

Enquanto a versão for `0.x`, este mapeamento SUBSTITUI as seções MINOR/PATCH abaixo:

- **PATCH** (`0.62.0 → 0.62.1`): tudo que é releasável — inclusive skill nova, subcomando novo, template alterado. "Atualize sem medo."
- **MINOR** (`0.62.x → 0.63.0`): breaking (**⚠ Breaking** no CHANGELOG) ou fechamento de fase/marco do ROADMAP. "Leia o changelog antes de atualizar."
- **MAJOR**: reservado ao `1.0.0`, quando o SemVer pleno reassume e as seções abaixo voltam a ser o mapeamento literal.

As seções seguintes permanecem como referência do espírito de cada categoria.
```

- [ ] **Step 3: Emendar `.claude/rules/release.md`**

Trocar a linha `- PATCH: correções e refinamentos sem mudança de trigger/output. MINOR: algo invocável novo; breaking pré-1.0 vai em MINOR com "⚠ Breaking". NÃO-releasável: ...` por:

```markdown
- Pré-1.0 (ADR-0015): PATCH = tudo releasável (inclusive invocável novo); MINOR = breaking ("⚠ Breaking") ou marco do ROADMAP; MAJOR reservado ao 1.0.0. NÃO-releasável: `.github/`, `README.md`, `CHANGELOG.md`, `.gitignore`, `docs/` — reorganização de docs/infra nunca bumpa versão.
```

- [ ] **Step 4: Regenerar índice + commit**

Run: `uv run python .github/scripts/gen_indexes.py` → `atualizado docs/adr/_index.md`

```bash
git add docs/adr/ RELEASING.md .claude/rules/release.md
git commit -m "docs(adr): ADR-0015 — pré-1.0, PATCH para todo release; MINOR = breaking/marco"
```

---

### Task 14: docs do repo + CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `README.md` (repo), `CLAUDE.md` (repo)

**Interfaces:** nenhum código. ATENÇÃO: o checkout principal do dono tem edições NÃO commitadas em ARCHITECTURE/README/RELEASING — este trabalho vive na branch `spec/zettlr-front`; sinalizar no PR que pode conflitar.

- [ ] **Step 1: CHANGELOG — seção "Não publicado"**

Substituir `## [Não publicado]` (vazia) por:

```markdown
## [Não publicado]

### Adicionado
- `prumo write zettlr-profile` — gera o defaults file de export docx do Zettlr (`docs/templates/prumo-docx.yaml`) com a cadeia `citeproc → zotero_live_docx.lua` (spec 2026-07-22; primeiro release sob ADR-0015).
- Console-script `prumo-zettlr-export` — entrypoint para o custom command do Zettlr disparar o export docx canônico (guardas intactas).
- `core/citations.py` — gramática única de citekey (Pandoc + legado), consumida por export, compose, wiki lint e paper graph (invariante I7 do spec 2026-07-05).
- Export docx canônico falha alto em citekey ausente do `.bib` (warning do citeproc promovido a erro).
- `prumo doctor` acusa perfil Zettlr quebrado (filtro/reference-doc inexistentes) com o fix embutido.

### Mudado
- `templates/pj_base` v2 (Zettlr-ready): sai o vault Obsidian (`.obsidian/`, `references/views/`, `docs/canvas/`); templates nascem Pandoc-puros (`[@key]`, sem callouts); entra `docs/templates/reference.docx` e frontmatter `bibliography:` nos drafts. Projetos existentes não são tocados (Princípio: legado intocado — `normalize_markdown` permanece).
- Skills de escrita/consulta instruem citação Pandoc `[@key]`; leitura/lint aceitam as duas gramáticas.
- `wiki lint` e `paper graph` flavor-agnósticos; links markdown contam como link de entrada no cálculo de órfãs.

### Documentação
- ADR-0015 — política de release pré-1.0 (PATCH para tudo releasável; MINOR reservado a breaking/marco).
- Guia one-time de setup do Zettlr em `docs/project_guide.md` do pj_base; ROADMAP marca `prumo write preview` como superado pelo Zettlr para projetos novos.
```

- [ ] **Step 2: ROADMAP, ARCHITECTURE, README, CLAUDE.md**

`ROADMAP.md`, seção "Em curso", adicionar bullet:

```markdown
- Zettlr como front humano (spec 2026-07-22): implementado na v0.62.1. `prumo write preview` fica **superado pelo Zettlr** para projetos novos — não construir sem novo trigger.
```

`ARCHITECTURE.md`: no mapa de módulos, adicionar `core/citations.py` (gramática única de citekey) na lista de `core/` e `zettlr.py` (perfil de export do Zettlr) na lista de `domains/write/`; trocar menções de "Obsidian" como front por "Zettlr (novos) / Obsidian (legado)" onde descreverem o produto pj_*.

`README.md` (repo) e `CLAUDE.md` (repo): trocar a descrição `wiki (Obsidian)` por `wiki (Markdown; front Zettlr — legado Obsidian)` na frase de pitch de cada um.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md ROADMAP.md ARCHITECTURE.md README.md CLAUDE.md
git commit -m "docs: CHANGELOG não-publicado + ROADMAP/ARCHITECTURE/README refletem Zettlr front"
```

---

### Task 15: verificação final + checklist manual

**Files:** nenhum novo.

- [ ] **Step 1: Suíte completa**

Run: `uv run pytest`
Expected: PASS, 0 failed (≈ suíte atual + ~25 testes novos)

- [ ] **Step 2: Lint + types + índices**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo limpo / "tudo em dia"

- [ ] **Step 3: Smoke real do CLI (sem Zettlr)**

```bash
cd /tmp && uv run --project <repo>/.claude/worktrees/zettlr-front-spec prumo init pj_smoke --yes --json
cat pj_smoke/docs/templates/prumo-docx.yaml   # reader/writer/filters presentes; citeproc antes do .lua
uv run --project <repo>/.claude/worktrees/zettlr-front-spec prumo doctor pj_smoke
rm -rf pj_smoke
```

Expected: init exit 0 com `zettlr_profile` no JSON; doctor exit 0.

- [ ] **Step 4: Registrar o checklist manual (pós-merge, com Zettlr real — não é CI)**

Adicionar ao PR a lista de verificação humana:

1. `prumo init pj_zettlr_teste` → abrir a pasta como workspace no Zettlr 3.x.
2. Criar draft com `bibliography:` do template + 2 citações `[@key]` reais → autocomplete funciona ao digitar `@`; citação renderiza no preview.
3. Importar `docs/templates/prumo-docx.yaml` no Assets Manager → export docx pelo menu → abre no Word com citações vivas (campo cinza ao clicar).
4. Registrar custom command `prumo-zettlr-export` → export → guardas rodam (testar com citekey inexistente: deve falhar alto).
5. Editar um `.md` por agente (CLI) com o arquivo aberto no Zettlr → reload automático (com a opção ligada).

- [ ] **Step 5: Commit final de ajustes (se houver) e push**

```bash
git push -u origin spec/zettlr-front
```

---

### Task 16: release 0.62.1 (após aprovação do PR de feature)

**Files:**
- Modify: `src/prumo_assist/_version.py`, `CHANGELOG.md`, `CITATION.cff`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (via script)

- [ ] **Step 1: Abrir PR da feature e aguardar merge**

```bash
gh pr create --base main --head spec/zettlr-front --title "feat: Zettlr como front humano (spec 2026-07-22)" --fill
```

Aguardar CI + revisão do dono + merge. Os passos seguintes acontecem em branch nova a partir de `main` atualizado.

- [ ] **Step 2: Bump + sync (PATCH sob ADR-0015)**

1. `src/prumo_assist/_version.py`: `__version__ = "0.62.1"`
2. `CHANGELOG.md`: mover o conteúdo de `## [Não publicado]` para `## [0.62.1] - <data do release>`; recriar `## [Não publicado]` vazia; no rodapé, atualizar `[Não publicado]: ...compare/v0.62.1...HEAD` e adicionar `[0.62.1]: https://github.com/raphaelfh/prumo-assist/compare/v0.62.0...v0.62.1`.
3. `CITATION.cff`: `version: 0.62.1`.

```bash
python .github/scripts/sync_manifest_version.py
python .github/scripts/validate_manifests.py
python .github/scripts/sync_manifest_version.py --check
```

Expected: manifests alinhados em v0.62.1, validação OK.

- [ ] **Step 3: Branch de release + PR + tag**

```bash
git checkout -b release/v0.62.1
git add CHANGELOG.md CITATION.cff src/prumo_assist/_version.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "release: 0.62.1 - Zettlr front (pj_base v2, zettlr-profile, gramática única, ADR-0015)"
git push -u origin release/v0.62.1
gh pr create --title "release: v0.62.1" --fill
# após o merge:
git tag -a v0.62.1 -m "v0.62.1" && git push origin v0.62.1
gh release create v0.62.1 --notes "$(awk '/^## \[0.62.1\]/,/^## \[/' CHANGELOG.md | head -n -1)" --title "v0.62.1"
```
