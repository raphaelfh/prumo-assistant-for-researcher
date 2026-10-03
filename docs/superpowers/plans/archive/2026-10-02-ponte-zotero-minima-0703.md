---
status: implemented
verified: 2026-10-02
release: "pendente — 0.70.3 PATCH (corte separado, RELEASING.md)"
spec: "[[2026-10-02-ponte-zotero-minima-design]]"
---

> **Fechamento (2026-10-02).** Tasks 1–8 e 10 implementadas em TDD no branch `fix/ponte-zotero-0703` (PR B): ADR-0037 aceita; `core/deps` com `zotero_base`, `bbt_rpc_url`, `in_claude_sandbox`, `pandoc_path` e a linha `pandoc` do doctor (piso 3.8.2, Zettlr.app como alternativa); `zotero_live_docx.lua` com `uris` sempre array, `zotero.lua` e `zotero_bibliography_docx.lua` apagados, pandoc 3.8.2 no CI; export docx sem gate, com `BbtLookup` melhor-esforço de 2 s, `docx_link_warning` (E1–E4), `{redo}` e E7; nota E6 só no `export` e avisos via `on_warning`; ingest com E5; `reconcile` com o prefixo `mcp__plugin_par_prumo__`; documentação da 0.70.3 e entrada do CHANGELOG em `[Não publicado]`. A Task 9 (receita do 54yyyu no onboarding) foi feita e revertida neste branch: a receita afirma que o PAR não lê anotações, o que só vale depois da aposentadoria dos `sync-*` (0.71.0); ela sai com o PR da 0.71.0 (plano `2026-10-02-ponte-zotero-minima-0710`). Desvio deliberado da Spec B §Componentes (`write/cli.py`, que manda emitir `"warnings": avisos` no payload): `warnings` só no payload `--json` (o modo texto já mostra cada aviso via `console.warn`; Princípio VIII). Verificação: suíte inteira com 1321 passed e nenhum SKIPPED (a baseline tinha 4 SKIPPED "pandoc ausente" em `test_export_crossref.py`; agora `pandoc_path()` acha o pandoc 3.10.1 do Zettlr.app); ruff, mypy, `gen_indexes --check`, `validate_manifests` e `sync_manifest_version --check` limpos; greps de regressão vazios, e a única leitura de `PRUMO_ZOTERO_BASE` fica em `core/deps.py::zotero_base`. Smoke dentro do sandbox (`SANDBOX_RUNTIME=1`) num `prumo init` novo: `write export --to docx` sai com exit 0, aviso E2 com `prumo write export … --to docx --force` e a nota E6; `_read_docx_citations` dá `unlinked == ['silva2020']`; `--json` traz `warnings`; `prumo doctor --json` mostra `pandoc 3.10.1 do Zettlr.app`. Correções da revisão (commit `fix(ponte-zotero): correções da revisão`): o piso 3.8.2 entrou também em `templates/pj_base/README.md`, arquivo fora da lista fechada do B7 (lacuna da spec; o README do template ainda dizia "Zettlr ≥ 3.0"); o lookup do BBT passou a guardar só `itemID` inteiro e `uri` string não vazia, e o filtro testa `type()` (um `null` saía `"uris":[null]` e escapava do aviso); corpo não-JSON vira `rpc_error`; `errors[k] > 0` do BBT (citekey duplicada) sai do E4 e ganha frase própria (texto fora da tabela §Erros da Spec B, a registrar na spec); `PRUMO_ZOTERO_BASE=""` cai no padrão; o E5 cita a página com `shlex.quote`. Pendente: G2 (CI do PR B: passo "Pandoc 3.8.2 (piso do export)" e nenhum SKIPPED "pandoc ausente" nas duas versões de Python), G1 (máquina do dono: Better BibTeX ≥ 9.0.65, os dois `curl` do `item.pandoc_filter` e o Word real, itens a–d), o rebase sobre `main` com os índices regerados (Task 10, Step 9) e o corte da 0.70.3 pelos 8 passos do `RELEASING.md`.

# Ponte Zotero mínima — 0.70.3 (docx sem gate, `uris` sempre array, pandoc, sandbox) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a parte 0.70.3 PATCH da Spec B, sem breaking. O docx sai com `uris` sempre presente e sempre array, então o Refresh do Zotero no Word deixa de quebrar. O lookup do vínculo volta a funcionar, porque o export para de mandar `library=""` ao Better BibTeX. O export docx deixa de exigir o Zotero aberto: o lookup vira melhor-esforço de 2 s, e um aviso por causa diz quantas citekeys saíram sem vínculo e dá o comando de refazer. O ingest ganha mensagem própria quando o coautor usou os botões do Zotero. O pandoc passa a ser resolvido pelo PATH ou pelo Zettlr.app, sob o piso único 3.8.2, e o doctor ganha a linha `pandoc`. A base URL do Zotero fica com uma fonte só em `core/deps.py`, o Lua morto sai, o modo `reconcile` passa a pré-aprovar as tools pelo prefixo do plugin, e a ADR-0037 entra aceita.

**Architecture:** Tudo o que é Zotero/pandoc e não é de domínio mora em `src/par/core/deps.py`: `zotero_base()`, `bbt_rpc_url()`, `in_claude_sandbox()`, `pandoc_path()` e `_pandoc_version()`. `domains/write/export.py` importa de `core` o lookup melhor-esforço (`BbtLookup`), o aviso pós-export (`docx_link_warning`) e o `{redo}` (`_redo_command`). O aviso sai do domínio por um callback `on_warning`, no mesmo padrão de `connect_collection(confirm=…)`; a fachada `write/cli.py` imprime com `console.warn` e põe `warnings` no `--json`. O filtro `zotero_live_docx.lua` emite `uris` com `json.decode('[]')` quando não há vínculo. `review.check_conservation` ganha uma guarda nova antes do agrupamento por `occ_id`. Nenhum domínio importa outro.

**Tech Stack:** Python 3.11/3.12, Typer, Pydantic v2, stdlib `urllib`/`subprocess`/`shlex`, pandoc + Lua (filtros vendorados), pytest, mypy `--strict`, ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md` (Spec B): §Decisões B1–B8 e B13; §Componentes "0.70.3 PATCH"; §Erros E1–E9; §Testes "0.70.3"; §ADRs e emendas; §Release e migração (0.70.3); §Spikes e gates pré-merge (G1, G2); §Quando reavaliar. A receita do onboarding (B12, §Componentes 0.71.0 "Receita do onboarding") é só documentação e sai já, sem bump (Task 9). Tudo o que a Spec B marca como 0.71.0 fica FORA deste plano: aposentadoria de `sync-*`, sonda `_bbt_probe`, transporte do `connect`, mensagens E10–E18, linha `zotero` nova do doctor.

## Global Constraints

- **Ambiente (sandbox desta máquina).** Prefixe todo `uv` com `UV_CACHE_DIR="$TMPDIR/uvcache"`. O `.venv` do worktree não tem as dependências de dev: antes da Task 1, rode uma vez `UV_CACHE_DIR="$TMPDIR/uvcache" uv sync --frozen --extra dev` (o mesmo do CI). Depois disso `uv run pytest` funciona.
- **Baseline.** Antes da Task 1, rode `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest -q` e anote as falhas e os skips que já existem em `main`. "Suíte verde" neste plano quer dizer: nenhuma falha nova em relação a essa baseline, e cada task termina com os testes que ela criou passando.
- **`SANDBOX_RUNTIME=1` está definido neste ambiente** (o Bash do Claude Code roda no sandbox). Por isso a Task 2 põe no `tests/unit/conftest.py` uma fixture `autouse` que o remove; os testes do E2 o definem com `monkeypatch.setenv`. Sem isso, o teste do E1 viraria E2 aqui e passaria no CI.
- **Layering (`.claude/rules/code.md`).** `core/` nunca importa `domains/`. `domains/write` e `domains/paper` importam de `core.deps`. Nenhum domínio importa outro.
- **Fachadas finas.** `write/cli.py` só faz parsing, chamada do domínio e saída, sempre dentro de `cli_run(...)`. Nada de `print()`: saída só por `core.output.Console`.
- **Tipagem.** `from __future__ import annotations` em todo módulo; `mypy --strict` (cobre `src/par` e `tests`); value objects em `@dataclass(frozen=True)`.
- **Mensagens.** pt-BR, com o comando de correção dentro. Os textos E1–E9 abaixo são reproduzidos **literalmente** da tabela de §Erros da Spec B; não reescreva. Em `str.format`/f-string, chaves literais do texto viram `{{`/`}}` (E4: `zotero: {{library: …}}`; E9: `{{#tbl:…}}`).
- **Dependência externa só nos seams.** pandoc real só nos testes marcados com `skipif(_PANDOC is None)`; Zotero/BBT sempre com `urlopen` mockado; `subprocess.run` mockado nos testes de `_pandoc_version`.
- **Ramo Zettlr/ausente do pandoc nos testes.** Da Task 3 em diante o CI tem `/usr/bin/pandoc` no PATH, e `pandoc_path()` devolve esse binário antes de olhar o Zettlr. Todo teste que afirma o ramo do Zettlr.app ou o ramo "pandoc ausente" faz `monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)` junto com a troca de `_ZETTLR_PANDOC`. Sem isso o teste passa nesta máquina (sem pandoc no PATH) e quebra só no CI, travando o G2.
- **Texto das specs.** As duas specs aprovadas existem só nos commits `c2ff3d3`/`fe9f5b8` do branch `claude/prumo-uvx-pinned-version-546b59`; `main` ainda não as tem. Todo texto copiado "literalmente" da Spec B (ADR, blocos de código, mensagens, receita, CHANGELOG) sai do branch das specs ou de `git show fe9f5b8:docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md`, nunca de um checkout de `main`.
- **Blocos gerados.** `skills/review/SKILL.md`, `docs/_index.md` e `docs/adr/_index.md` só mudam pelo `uv run python .github/scripts/gen_indexes.py`. Nunca à mão. O gerador lista os planos ativos em `docs/_index.md`, então todo commit que adiciona, move ou arquiva plano roda o gerador.
- **O gerador lê o disco, não o git.** Ele varre `docs/*.md`, `docs/superpowers/{specs,plans,plans/archive}/*.md`, `docs/adr/adr-*.md` e `skills/`. Antes de **qualquer** `gen_indexes.py` (com ou sem `--check`), `git status --porcelain --untracked-files=all docs skills` não pode listar nenhum `??`. Se listar plano ou spec deste esforço, ele entra no mesmo commit do índice regerado (Task 1). Se listar arquivo de outra frente, tire-o do worktree antes (mova para o scratchpad) e devolva depois. Senão o `docs/_index.md` local cita um arquivo que o commit não leva: o `--check` local passa e o do CI falha.
- **Versão.** Nenhuma task deste plano bumpa versão nem toca `src/par/_version.py`, `plugin.json`, `marketplace.json` ou `CITATION.cff`. O corte da 0.70.3 é feito à parte pela orquestração, nos 8 passos do `RELEASING.md`. O `CHANGELOG.md` só muda na Task 10, em `## [Não publicado]`.
- **Commits.** Um commit por task, mensagem no padrão `tipo(escopo): resumo` em pt-BR. Toda mensagem de commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, e o corpo de todo PR termina com `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Ordem, dependências e PRs

| Task | Depende de | PR |
|---|---|---|
| 1. ADR-0037 e índices | — | PR B |
| 2. `core/deps`: base única, sandbox, pandoc e linha `pandoc` | — | PR B |
| 3. Lua: `uris` sempre array; Lua morto sai; pandoc real no teste e no CI | 2 | PR B |
| 4. Export docx sem gate: lookup melhor-esforço, aviso por causa, `{redo}`, E7 | 2, 3 | PR B |
| 5. CLI: nota de primeiro uso (E6) e `warnings` | 4 | PR B |
| 6. Ingest: mensagem própria quando o Zotero reescreveu os campos (E5) | — | PR B |
| 7. `reconcile`: prefixo `mcp__plugin_par_prumo__` | — | PR B |
| 8. Documentação da 0.70.3 | 1 | PR B |
| 9. Onboarding: receita do 54yyyu no lugar do cookjohn | — | PR A |
| 10. Verificação, CHANGELOG, índices, gates e arquivamento | 1–8 | PR B |

- **PR A** (`docs/onboarding-zotero-54yyyu`): só a Task 9. Documentação, sem bump; pode entrar em `main` a qualquer momento (Spec B §Release e migração, "Já, sem bump"). **Base:** `origin/main`, num worktree separado e limpo (`git fetch origin && git worktree add "$TMPDIR/par-pr-a" -b docs/onboarding-zotero-54yyyu origin/main`), para não arrastar as specs nem os planos não rastreados deste worktree. A receita sai de `git show fe9f5b8:docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md` (o PR A não precisa da spec em `main`: o texto copiado não aponta para ela).
- **PR B** (`fix/ponte-zotero-0703`): Tasks 1–8 e 10, num PR único (Spec B: "0.70.3 PATCH, num PR, sem depender de spike da Spec A"). O merge exige o CI verde com o G2 cumprido e o G1 registrado no PR (Task 10). **Base:** `claude/prumo-uvx-pinned-version-546b59` (HEAD `fe9f5b8`, os dois commits das specs). Neste worktree: `git switch -c fix/ponte-zotero-0703`. Assim as Specs A e B entram em `main` com o PR B, e o `Origem: [[2026-10-02-ponte-zotero-minima-design]]` da ADR-0037 aponta para um arquivo que existe. Se a orquestração já tiver levado as specs a `main` por outro PR (`git merge-base --is-ancestor fe9f5b8 origin/main` sai com 0), crie o branch a partir de `origin/main`.
- **Release:** depois do merge do PR B, a orquestração corta a 0.70.3 pelos 8 passos do `RELEASING.md`. Este plano não corta release. O corte da 0.70.3 acontece logo após o merge do PR B e antes de qualquer PR da 0.71.0 (Spec A, PRs 1–5, e o plano `2026-10-02-ponte-zotero-minima-0710`) entrar em `main`: o passo 2 do `RELEASING.md` leva para a release tudo o que estiver em `## [Não publicado]`. O PR A (docs, sem CHANGELOG) pode entrar a qualquer momento.

## File Structure

| Arquivo | Task | Responsabilidade |
|---|---|---|
| `docs/adr/adr-0037-ponte-zotero-minima.md` (criar) | 1 | ADR aceita com a 0.70.3 |
| `docs/adr/_index.md`, `docs/_index.md` (gerados) | 1, 10 | índices regerados |
| `docs/superpowers/plans/2026-10-02-*.md` (os três planos, hoje não rastreados) | 1 | entram no git junto com o `docs/_index.md` que os lista |
| `src/par/core/deps.py` (modificar) | 2 | `zotero_base`, `bbt_rpc_url`, `in_claude_sandbox`, `pandoc_path`, `_pandoc_version`, linha `pandoc` |
| `src/par/domains/paper/zotero.py` (modificar) | 2 | `_zotero_base`/`_bbt_rpc` delegam a `core.deps` |
| `tests/unit/conftest.py` (modificar) | 2 | fixtures `autouse` sem pandoc real e fora do sandbox |
| `tests/unit/core/test_deps.py` (modificar) | 2 | base, sandbox, `pandoc_path`, `_pandoc_version`, linha `pandoc` |
| `src/par/_filters/zotero_live_docx.lua` (modificar) | 3 | `uris` sempre array; cabeçalho com piso 3.8.2; comentário do `prumoOcc` |
| `src/par/_filters/zotero.lua`, `src/par/_filters/zotero_bibliography_docx.lua` (apagar) | 3 | Lua morto |
| `src/par/_filters/__init__.py` (modificar) | 3 | docstring lista os dois filtros vivos |
| `.github/workflows/ci.yml` (modificar) | 3 | instala o pandoc 3.8.2 antes do Pytest |
| `tests/unit/write/test_export_zotero_link.py` (criar) | 3, 4 | Lua com pandoc real; lookup, aviso, `{redo}`, `_check_pandoc` |
| `tests/unit/write/test_export_crossref.py` (modificar) | 3 | pipeline real usa `pandoc_path()` |
| `tests/unit/write/test_export_pandoc_cmd.py` (modificar) | 3 | saem os testes dos helpers do Lua morto |
| `src/par/domains/write/export.py` (modificar) | 3, 4 | sem gate; `BbtLookup`; `docx_link_warning`; `_redo_command`; `on_warning`; E7 |
| `tests/unit/write/test_export_docx_validation.py` (modificar) | 3, 4 | docstring; seam de lookup devolve `BbtLookup` |
| `tests/unit/write/test_errors.py` (modificar) | 4 | sai `ZoteroNotRunningError` |
| `src/par/domains/write/cli.py` (modificar) | 5 | E6 só no `export`; `on_warning`; `warnings` no `--json` |
| `tests/unit/write/test_cli.py` (modificar) | 4, 5 | param `export-zotero-down` sai; E6; avisos (o `test_zettlr_entry_forwards_warnings` novo é apagado pelo PR 2 da Spec A, Task 10, junto com `zettlr_export_entry`) |
| `src/par/domains/write/review.py` (modificar) | 6 | guarda E5 em `check_conservation` |
| `tests/unit/write/test_review_reader.py` (modificar) | 6 | três testes do E5 |
| `skills/review/modes/reconcile.md` (modificar) | 7 | prefixo do plugin |
| `skills/review/SKILL.md` (gerado) | 7 | `allowed-tools` regerado |
| `tests/unit/core/test_skills.py` (modificar) | 7 | invariante: nenhum `mcp__prumo__` em `skills/**` |
| `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `templates/pj_base/docs/project_guide.md`, `docs/superpowers/specs/2026-07-22-zettlr-front-design.md` (modificar) | 8 | documentação da 0.70.3 |
| `docs/onboarding-pesquisador.md` (modificar) | 9 | § "Perguntar ao seu Zotero" |
| `CHANGELOG.md` (modificar) | 10 | entrada em `[Não publicado]` |

---

### Task 1: ADR-0037 e índices

**Files:**
- Create: `docs/adr/adr-0037-ponte-zotero-minima.md`
- Add (já no disco, não rastreados): `docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0703.md`, `docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0710.md`, `docs/superpowers/plans/2026-10-02-plugin-distribuicao-unica.md`
- Modify (gerado): `docs/adr/_index.md`, `docs/_index.md`

- [ ] **Step 0: Branch.** Crie o branch do PR B como em "Ordem, dependências e PRs" (`git switch -c fix/ponte-zotero-0703` neste worktree, a partir de `fe9f5b8`). Confira `git merge-base --is-ancestor fe9f5b8 HEAD` → sai com 0 e `ls docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md docs/superpowers/specs/2026-10-02-plugin-distribuicao-unica-design.md` → os dois existem.
- [ ] **Step 1: Criar a ADR.** Copie **literalmente** o bloco ```` ```markdown ```` de Spec B §"ADRs e emendas" (começa em `# ADR-0037 — Ponte Zotero mínima: anotações e notas saem do PAR; Better BibTeX só no connect e no lookup do docx` e termina no parágrafo de §Consequências). Mantenha `- Status: aceito` e `- Data: 2026-10-02`. Não toque nas ADR-0007, 0008, 0020 nem 0026: ADR aceita é imutável, e a emenda fica registrada só na Origem da ADR nova (mesmo precedente da ADR-0026 sobre a 0017).
- [ ] **Step 2: Planos não rastreados entram junto.** Rode `git status --porcelain --untracked-files=all docs skills`. Hoje ele lista três planos não rastreados: `docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0703.md` (este), `docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0710.md` e `docs/superpowers/plans/2026-10-02-plugin-distribuicao-unica.md` (Spec A). Dê `git add` em **todos** os `docs/superpowers/plans/*.md` não rastreados, para irem no mesmo commit do `docs/_index.md` regerado. Se aparecer `??` fora de `docs/superpowers/plans/`, siga a regra de "O gerador lê o disco, não o git" (Global Constraints). Depois disso o comando só pode listar arquivos já adicionados (`A `).
- [ ] **Step 3: Regerar os índices.** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py`. Confira que `docs/adr/_index.md` ganhou a linha `[[adr/adr-0037-ponte-zotero-minima]] — Ponte Zotero mínima: … · aceito` e que `docs/_index.md` lista os três planos ativos do Step 2.
- [ ] **Step 4: Conferir.** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check` → sem diferença; `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/test_gen_indexes.py -q` → PASS; `git status --porcelain --untracked-files=all docs skills` → nenhum `??`.
- [ ] **Step 5: Commit** `docs(adr): ADR-0037 ponte Zotero mínima` (ADR, `docs/adr/_index.md`, `docs/_index.md` e os três planos).

### Task 2: `core/deps` — base única do Zotero, sandbox, resolução do pandoc e linha `pandoc` do doctor

Spec B §B6, §B7, §B1 ("Dono do ramo do sandbox"), §Componentes 0.70.3 (`core/deps.py`, `paper/zotero.py`), §Erros E8–E9, §Testes 0.70.3 (`test_deps.py`, `conftest.py`).

**Files:**
- Modify: `src/par/core/deps.py`
- Modify: `src/par/domains/paper/zotero.py`
- Modify: `tests/unit/conftest.py`
- Test: `tests/unit/core/test_deps.py`

**Interfaces:**
- Consumes: `_binary_on_path(name) -> str | None` (seam existente).
- Produces (em `par.core.deps`):
  - `_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"` (fica), `_ZETTLR_PANDOC = Path("/Applications/Zettlr.app/Contents/Resources/pandoc")`, `_PANDOC_FLOOR = (3, 8, 2)`
  - `zotero_base() -> str` (lê `PRUMO_ZOTERO_BASE`)
  - `bbt_rpc_url() -> str` (`f"{zotero_base()}/better-bibtex/json-rpc"`)
  - `in_claude_sandbox() -> bool` (`os.environ.get("SANDBOX_RUNTIME") == "1"`)
  - `pandoc_path() -> str | None` (PATH; senão `_ZETTLR_PANDOC` se for arquivo executável)
  - `_pandoc_version(path: str, timeout: float = 5.0) -> str | None` (seam)
  - `check_external_deps()` acrescenta, **no fim da lista**, o `DepStatus` `pandoc` com `required_by=["write export", "write compose"]`. A linha `zotero` não muda nesta release.
  - `par.domains.paper.zotero._zotero_base()` devolve `zotero_base()`; `_bbt_rpc()` devolve `bbt_rpc_url()`.

- [ ] **Step 1: Fixtures `autouse` em `tests/unit/conftest.py`.** Acrescente (com `from pathlib import Path` já importado):

```python
@pytest.fixture(autouse=True)
def _no_real_pandoc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Nenhum teste executa pandoc real pelo doctor (regra de seams, `.claude/rules/code.md`).

    O Zettlr.app do dono e o pandoc 3.8.2 do CI ficam fora: `_ZETTLR_PANDOC`
    aponta para um caminho que não existe, e `_pandoc_version` não roda nada.
    Os testes da linha `pandoc` e de `pandoc_path()` sobrescrevem os dois.
    """
    monkeypatch.setattr("par.core.deps._ZETTLR_PANDOC", tmp_path / "sem-zettlr" / "pandoc")
    monkeypatch.setattr("par.core.deps._pandoc_version", lambda path, timeout=5.0: None)


@pytest.fixture(autouse=True)
def _outside_claude_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """A suíte roda igual dentro e fora do sandbox do Claude Code (que define
    ``SANDBOX_RUNTIME=1``). Os testes das variantes de sandbox definem a variável."""
    monkeypatch.delenv("SANDBOX_RUNTIME", raising=False)
```

  Até o Step 4 criar `_pandoc_version` e `_ZETTLR_PANDOC`, essas fixtures fazem todo teste de `tests/unit` errar no setup com `AttributeError`. É o vermelho esperado; os Steps 1–5 vão num commit só.
- [ ] **Step 2: Testes que falham** em `tests/unit/core/test_deps.py`. No topo do módulo, guarde a função real antes das fixtures: `from par.core import deps` e `_REAL_PANDOC_VERSION = deps._pandoc_version` (o import roda na coleta, antes da fixture `autouse`). Casos:
  - `test_zotero_base_default_is_loopback` (`monkeypatch.delenv("PRUMO_ZOTERO_BASE", raising=False)` → `"http://127.0.0.1:23119"`);
  - `test_zotero_base_env_override`;
  - `test_bbt_rpc_url_follows_base` (`PRUMO_ZOTERO_BASE=http://example.test:1234` → `http://example.test:1234/better-bibtex/json-rpc`);
  - `test_in_claude_sandbox_true_with_runtime_1`; `test_in_claude_sandbox_false_without_var`; `test_in_claude_sandbox_false_with_other_value` (`"0"` e `"true"`);
  - `test_pandoc_path_prefers_path` (`_binary_on_path` → `"/opt/bin/pandoc"` e um `_ZETTLR_PANDOC` executável em `tmp_path` → `"/opt/bin/pandoc"`);
  - `test_pandoc_path_falls_back_to_zettlr` (`_binary_on_path` → `None`; `_ZETTLR_PANDOC` = arquivo em `tmp_path` com `chmod(0o755)` → `str(esse caminho)`);
  - `test_pandoc_path_none_without_any` (PATH vazio e o `_ZETTLR_PANDOC` inexistente do conftest → `None`); `test_pandoc_path_ignores_non_executable_zettlr` (`monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)` e `_ZETTLR_PANDOC` = arquivo em `tmp_path` com `chmod(0o644)` → `None`). Nos três testes de `pandoc_path` sem PATH, o `_binary_on_path` vai a `None` explicitamente (Global Constraints, "Ramo Zettlr/ausente");
  - linha `pandoc` (`patch("par.core.deps._binary_on_path", return_value="/opt/bin/pandoc")`, `patch("par.core.deps._zotero_api_root", return_value=None)` e `monkeypatch.setattr("par.core.deps._pandoc_version", lambda path, timeout=5.0: "<v>")`):
    - `test_pandoc_line_present_with_3_10_1` (`present is True`, `version == "3.10.1"`, `detail == "pandoc 3.10.1 em /opt/bin/pandoc"`, `required_by == ["write export", "write compose"]`);
    - `test_pandoc_line_rejects_3_1_2` (`present is False`; hint contém `"3.8.2"`, `"brew upgrade pandoc"` e `"prumo doctor"`);
    - `test_pandoc_line_accepts_floor_3_8_2` (`present is True`);
    - `test_pandoc_line_fail_safe_without_version` (`_pandoc_version` → `None`: `present is True`, `version is None`, `"versão não detectada" in detail`);
    - `test_pandoc_line_absent_hint` (`_binary_on_path` → `None`: `present is False`, `detail == "pandoc não encontrado (nem no PATH nem no Zettlr.app)"`, hint contém `"brew install pandoc"`, `"github.com/jgm/pandoc/releases"` e `"3.8.2"`);
    - `test_pandoc_line_names_zettlr` (PATH vazio, `_ZETTLR_PANDOC` executável, versão `"3.10.1"` → `detail == "pandoc 3.10.1 do Zettlr.app"`);
  - `_pandoc_version` real (`_REAL_PANDOC_VERSION`, com `monkeypatch.setattr("par.core.deps.subprocess.run", …)`): `test_pandoc_version_parses_first_line` (stdout `"pandoc 3.10.1\nFeatures: +server\n"` → `"3.10.1"`); `test_pandoc_version_none_on_missing_binary` (`FileNotFoundError` → `None`); `test_pandoc_version_none_on_timeout` (`subprocess.TimeoutExpired` → `None`); `test_pandoc_version_none_on_garbage` (stdout `"oops"` → `None`).
- [ ] **Step 3:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/core/test_deps.py -q` → FAIL (`AttributeError` no setup das fixtures e `ImportError` de `zotero_base`, `pandoc_path`…).
- [ ] **Step 4: Implementar** em `src/par/core/deps.py`, seguindo o esboço de Spec B §Componentes 0.70.3 ("`src/par/core/deps.py` (esboço…)"):
  - imports novos: `subprocess`, `from pathlib import Path`;
  - `zotero_base()`, `bbt_rpc_url()`, `in_claude_sandbox()`, `pandoc_path()` como no esboço (docstrings do esboço);
  - `_pandoc_version`: `subprocess.run([path, "--version"], capture_output=True, text=True, timeout=timeout, check=False)`; `except (OSError, subprocess.SubprocessError): return None`; casa a 1ª linha com `re.match(r"pandoc(?:\.exe)?\s+(\d+(?:\.\d+)*)", first_line)` e devolve o grupo 1, ou `None`;
  - `_zotero_api_root` passa a montar a URL com `zotero_base()`; `_zotero_host_port` passa a `urlparse(zotero_base())`. Nenhuma outra leitura de `PRUMO_ZOTERO_BASE` sobra no arquivo;
  - helper privado `_pandoc_status() -> DepStatus`, chamado no fim de `check_external_deps` (`statuses.append(_pandoc_status())`). Textos literais (E8 e E9):

```python
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
```

    Regras de `_pandoc_status`: sem `pandoc_path()` → `present=False`, detail e hint de E8. Com caminho, `where = "do Zettlr.app"` se `path == str(_ZETTLR_PANDOC)`, senão `f"em {path}"`. Versão `None` → `present=True`, `detail=f"pandoc {where} (versão não detectada)"`, `hint=""` (o fail-safe da linha `zotero`). Versão conhecida → `detail=f"pandoc {v} {where}"`; compara `tuple(int(p) for p in re.findall(r"\d+", v))` com `_PANDOC_FLOOR`; abaixo do piso → `present=False`, `hint=_PANDOC_OLD_HINT.format(v=v)`; senão `present=True`, `hint=""`. `version=v` nos dois casos.
  - docstring do módulo: acrescente o item "**Pandoc** — `write export`/`write compose`; o do PATH ou o que vem dentro do Zettlr.app, com o piso 3.8.2 (ADR-0037)".
  - `src/par/domains/paper/zotero.py`: `from par.core.deps import bbt_rpc_url, zotero_base, zotero_local_api_up`; sai `_DEFAULT_ZOTERO_BASE`; `_zotero_base()` faz `return zotero_base()` e `_bbt_rpc()` faz `return bbt_rpc_url()` (os nomes ficam porque `connect._rpc` chama `zotero._bbt_rpc()` e `tests/unit/paper/test_zotero_client.py`, nos testes de base URL perto da l.536-548, chama os dois diretamente; nenhum teste faz monkeypatch neles). Na docstring de `_zotero_base` sai "unifica com os filtros Lua"; fica "Base URL do Zotero local; delega a `core.deps.zotero_base` (override por env, ADR-0007)". A única leitura da variável fica em `core/deps.py::zotero_base` (o grep da Task 10, Step 3, confere). Se `os` ficar sem uso no módulo, saia o import.
- [ ] **Step 5:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/core/test_deps.py tests/unit/paper tests/unit/test_cli_doctor.py tests/unit/test_cli_init.py -q` → PASS; depois a suíte inteira, `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest -q` → sem falha nova em relação à baseline; `UV_CACHE_DIR="$TMPDIR/uvcache" uv run mypy` e `UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff check . && UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff format --check .` limpos.
- [ ] **Step 6: Commit** `feat(core): base única do Zotero, sandbox e pandoc do Zettlr no doctor (ADR-0037)`.

### Task 3: Filtro Lua — `uris` sempre array; Lua morto sai; pandoc real no teste e no CI

Spec B §B2, §B5, §Componentes 0.70.3 (`zotero_live_docx.lua`, `zotero.lua`, `zotero_bibliography_docx.lua`, `_filters/__init__.py`, `.github/workflows/ci.yml`), §Testes 0.70.3 ("Lua com pandoc real", `test_export_crossref.py`, `test_export_pandoc_cmd.py`), gate G2.

**Files:**
- Modify: `src/par/_filters/zotero_live_docx.lua`
- Delete: `src/par/_filters/zotero.lua`, `src/par/_filters/zotero_bibliography_docx.lua`
- Modify: `src/par/_filters/__init__.py`
- Modify: `src/par/domains/write/export.py` (só saem `_zotero_lua_filter` e `_zotero_bibliography_docx_filter`)
- Modify: `.github/workflows/ci.yml`
- Create: `tests/unit/write/test_export_zotero_link.py`
- Modify: `tests/unit/write/test_export_crossref.py`, `tests/unit/write/test_export_pandoc_cmd.py`, `tests/unit/write/test_export_docx_validation.py` (docstring)

**Interfaces:**
- Consumes: `par.core.deps.pandoc_path`, `export._build_pandoc_cmd`, `export._run_pandoc_checked`, `export._assert_no_citeproc_missing`, `export._INSTR_TEXT_RE`, `export._ZOTERO_ITEM_CSL_MARKER`, `export._parse_csl_payload`.
- Produces: cada `citationItem` do campo `ZOTERO_ITEM` leva `uris`: `[<URI canônica>]` com vínculo, `[]` sem. Saem `_zotero_lua_filter()` e `_zotero_bibliography_docx_filter()`.

- [ ] **Step 1: Teste que falha** — crie `tests/unit/write/test_export_zotero_link.py` (docstring do módulo: "Vínculo das citações do docx com a biblioteca do Zotero (ADR-0037)."). No nível do módulo: `_PANDOC = pandoc_path()` (de `par.core.deps`; resolvido na coleta, antes das fixtures) e `requires_pandoc = pytest.mark.skipif(_PANDOC is None, reason="pandoc ausente (nem no PATH nem no Zettlr.app)")`. Helper `_field_payloads(docx: Path) -> list[dict[str, Any]]`: lê `word/document.xml`, percorre `export_mod._INSTR_TEXT_RE`, filtra pelo marcador `export_mod._ZOTERO_ITEM_CSL_MARKER` e decodifica com `export_mod._parse_csl_payload(html.unescape(raw), i, error_cls=export_mod.CiteMapMismatchError)`. Teste:
  - `test_lua_uris_is_always_a_json_array` (`@requires_pandoc`): `.bib` com `linked2020` e `unlinked2021`; CSL vindo de `subprocess.run([_PANDOC, "--print-default-data-file", "default.csl"], …)`; `zotero_lookup.json` = `{"linked2020": {"itemID": 42, "uri": "http://zotero.org/users/local/abcd/items/ABCD1234", "fingerprint": "sha256:x"}}`; `in.md` = `"Cita [@linked2020] e [@unlinked2021].\n\n::: {#refs}\n:::\n"`; a CSL é gravada em `tmp_path / "style.csl"`, o `.bib` em `tmp_path / "refs.bib"` e o lookup em `tmp_path / "zotero_lookup.json"`. O comando, com todos os argumentos nomeados (espelha o `_cmd` de `test_export_crossref.py`):

```python
cmd = export_mod._build_pandoc_cmd(
    pandoc_bin=_PANDOC,
    input_md=tmp_path / "in.md",
    output=tmp_path / "out.docx",
    bib=tmp_path / "refs.bib",
    csl=tmp_path / "style.csl",
    style="apa",
    metadata_file=None,
    template=None,
    reference_doc=None,
    to_format="docx",
    zotero_lookup_file=tmp_path / "zotero_lookup.json",
    resource_path=tmp_path,
)
```

  Depois `export_mod._run_pandoc_checked(cmd)`; então `uris = {item["id"]: item.get("uris", "<ausente>") for p in _field_payloads(tmp_path / "out.docx") for item in p["citationItems"]}` e `assert uris == {"linked2020": ["http://zotero.org/users/local/abcd/items/ABCD1234"], "unlinked2021": []}`. Use o mesmo `_PANDOC` no comando e no `--print-default-data-file` (nunca o `"pandoc"` literal), para que a condição de skip e o binário executado sejam o mesmo. Para o mypy (`warn_unreachable`), faça `assert _PANDOC is not None` no começo do teste.
- [ ] **Step 2: `test_export_crossref.py` usa o pandoc resolvido.** `_PANDOC = pandoc_path()` no nível do módulo; `requires_pandoc = pytest.mark.skipif(_PANDOC is None, reason="pandoc ausente (nem no PATH nem no Zettlr.app)")`; `_cmd` passa `pandoc_bin=_PANDOC or "pandoc"` (os testes do builder rodam sem pandoc e só inspecionam a lista); `_run_docx` roda `[_PANDOC, "--print-default-data-file", "default.csl"]` (com `assert _PANDOC is not None`). Docstring do módulo: "Os de pipeline completo usam o pandoc real (`pandoc_path()`: PATH ou Zettlr.app) e são pulados sem ele; o CI instala o 3.8.2, o piso." Saia o `import shutil` se ficar sem uso.
- [ ] **Step 3:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write/test_export_zotero_link.py tests/unit/write/test_export_crossref.py -q -rs` → o teste do Lua FALHA (`"unlinked2021": "<ausente>"`). Nesta máquina o pandoc vem do Zettlr.app; se uma máquina não tiver pandoc nenhum, o teste aparece como SKIPPED com o motivo acima, e o CI (Step 6) cobre.
- [ ] **Step 4: Implementar o B2** em `src/par/_filters/zotero_live_docx.lua`:
  - a linha `if lookup.uri then item.uris = { lookup.uri } end` (l.99) vira o bloco de Spec B §Componentes 0.70.3 ("`src/par/_filters/zotero_live_docx.lua`, no lugar da l.99"), copiado literalmente: o comentário de 6 linhas mais `item.uris = lookup.uri and { lookup.uri } or json.decode('[]')`. `json` já é o `local json = pandoc.json` do topo. **Não** use `pandoc.List`;
  - cabeçalho, em "Pré-requisitos": a linha ``- Pandoc 3.0+ (para `pandoc.json`).`` vira ``- Pandoc ≥ 3.8.2: piso único do export (o `crossref.lua` precisa da extensão `table_attributes`).``;
  - comentário do `prumoOcc` (o bloco `-- I2b (spec da ponte): prumoOcc é um contador PRÓPRIO…`; ache-o pelo texto `normalizado; melhor-esforço (se o Refresh descartar chaves custom`, sem confiar em número de linha): o trecho "melhor-esforço (se o Refresh descartar chaves custom, a conservação degrada pro multiconjunto de citekeys, sem quebrar)." vira "o Zotero descarta `prumoOcc` no Refresh e no Add/Edit Citation; o ingest recusa esse docx com mensagem própria (ADR-0037).".
- [ ] **Step 5: Implementar o B5.**
  - `git rm src/par/_filters/zotero.lua src/par/_filters/zotero_bibliography_docx.lua`;
  - em `export.py`, saem `_zotero_lua_filter` e `_zotero_bibliography_docx_filter` (o `_zotero_live_docx_filter` e o `_crossref_filter` ficam; `importlib.resources` continua usado);
  - em `test_export_pandoc_cmd.py`, saem os imports dos dois helpers (l.29 e l.31) e os testes `test_zotero_lua_filter_resolves_to_real_file`, `test_zotero_bibliography_docx_filter_resolves_to_real_file` e `test_docx_does_not_chain_legacy_bbt_filters`; a docstring do módulo deixa de falar em "filtros Lua do Zotero" no plural ("docx → `crossref.lua` + citeproc + `zotero_live_docx.lua`");
  - `src/par/_filters/__init__.py`, docstring nova (sai a instrução "Atualizar: curl …"):

```python
"""Filtros Lua do Pandoc vendorados com o pacote.

- ``crossref.lua`` — numeração de figuras e tabelas e resolução de
  ``@fig:x``/``@tbl:x`` (ADR-0035).
- ``zotero_live_docx.lua`` — campos vivos do Zotero no docx: citações e
  bibliografia já formatadas pelo citeproc, embrulhadas em campos do Word
  (ADR-0037).
"""
```

  - `test_export_docx_validation.py`, docstring do módulo: a frase "o CI (``ubuntu-latest``) não tem pandoc instalado, então nenhum teste deste arquivo pode depender do binário real" vira "nenhum teste deste arquivo depende do binário real (o pipeline real fica em ``test_export_crossref.py`` e ``test_export_zotero_link.py``)".
  - `hatch` empacota `src/par` inteiro: o `pyproject.toml` não muda.
- [ ] **Step 6: CI (G2).** Em `.github/workflows/ci.yml`, passo novo logo antes de `- name: Pytest`:

```yaml
      - name: Pandoc 3.8.2 (piso do export)
        run: curl -fsSLo "$RUNNER_TEMP/pandoc.deb" https://github.com/jgm/pandoc/releases/download/3.8.2/pandoc-3.8.2-1-amd64.deb && sudo dpkg -i "$RUNNER_TEMP/pandoc.deb" && pandoc --version | head -1
```

  O asset `pandoc-3.8.2-1-amd64.deb` existe (conferido em 2026-10-02). `.github/` não bumpa versão.
- [ ] **Step 7:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write -q -rs` → PASS, e nesta máquina nenhum SKIPPED com "pandoc ausente"; suíte inteira sem falha nova; `mypy`, `ruff check` e `ruff format --check` limpos.
- [ ] **Step 8: Commit** `fix(write): uris sempre array no docx; filtros Lua mortos saem; pandoc 3.8.2 no CI (ADR-0037)`.

### Task 4: Export docx sem gate — lookup melhor-esforço, aviso por causa, `{redo}` e E7

Spec B §B1, §B3, §Componentes 0.70.3 (`src/par/domains/write/export.py` e o esboço "`src/par/domains/write/export.py` (esboço)"), §Erros E1–E4 e E7, §Testes 0.70.3 (`test_export_zotero_link.py`, `test_errors.py`, `test_export_docx_validation.py`, `test_cli.py`).

**Files:**
- Modify: `src/par/domains/write/export.py`
- Test: `tests/unit/write/test_export_zotero_link.py` (estende o da Task 3)
- Modify: `tests/unit/write/test_export_docx_validation.py`, `tests/unit/write/test_errors.py`, `tests/unit/write/test_cli.py`

**Interfaces:**
- Consumes: `par.core.deps.bbt_rpc_url`, `zotero_base`, `in_claude_sandbox`, `pandoc_path`.
- Produces (em `par.domains.write.export`):
  - `@dataclass(frozen=True) class BbtLookup: items: dict[str, dict[str, object]]; failure: Literal["", "unreachable", "rpc_error"] = ""; detail: str = ""; library: str | None = None`
  - `fetch_bbt_zotero_metadata(citekeys: list[str], library: str | None, *, timeout: float = 2.0) -> BbtLookup` — nunca levanta
  - `docx_link_warning(docx_path: Path, lookup: BbtLookup, redo_command: str) -> str | None`
  - `_redo_command(subcommand: Literal["export", "compose"], target: Path, *, style: str | None = None, bib: Path | None = None, out_dir: Path | None = None, reference_doc: Path | None = None) -> str`
  - `_write_zotero_lookup(td_path, meta, text, bib) -> tuple[Path | None, BbtLookup]`
  - `_read_docx_citations(...)`: cada ocorrência ganha `"unlinked": list[str]` (citekeys do campo cujo item tem `uris` ausente ou vazio: `not item.get("uris")`)
  - `export(..., on_warning: Callable[[str], None] | None = None) -> Path` e `compose(..., on_warning: Callable[[str], None] | None = None) -> Path` (padrão: `logger.warning`; retorno inalterado, porque `par.domains.write.api` re-exporta os dois)
  - `_check_pandoc() -> str` usa `pandoc_path()` e levanta `ToolNotFoundError` com o E7
  - **Saem:** `BBT_JSONRPC_URL`, `ZoteroNotRunningError`, `_check_bbt_running` e as duas chamadas (em `export()` e `compose()`). `ZoteroNotRunningError` não é API pública (`write/api.py` re-exporta só `compose`, `export`, `list_styles`).

- [ ] **Step 1: Testes que falham** em `tests/unit/write/test_export_zotero_link.py`. Importe os helpers de `tests.unit.write.test_export_docx_validation` (só nomes com `_`, para o pytest não recoletar testes): `_fake_project`, `_patch_export_seams`, `_fake_run_writing_output_flag`, `_docx_bytes_for_export_wiring`, `_write_minimal_docx_with_payloads`. Payload de referência: `'{"citationID":"00000001","prumoOcc":"00000001","citationItems":[{"id":"smith2020","uris":[],"prumoFingerprint":"doi:10.1/x"}],"properties":{"formattedCitation":"(Smith, 2020)"}}'`. Para o `urlopen`, faça `monkeypatch.setattr("par.domains.write.export.urllib.request.urlopen", spy)` com um `def spy(req: urllib.request.Request, timeout: float) -> io.BytesIO` que guarda `req` e `timeout` e devolve `io.BytesIO(json.dumps(body).encode())`, ou levanta. Para ler os params, `json.loads(cast(bytes, req.data))["params"]` (o `cast` é para o `mypy --strict`: `Request.data` não é tipado como `bytes`). Casos:
  - `fetch_bbt_zotero_metadata`:
    - `test_fetch_unreachable_on_url_error` (`urllib.error.URLError(ConnectionRefusedError())`), `test_fetch_unreachable_on_timeout` (`TimeoutError()`), `test_fetch_unreachable_on_http_404` (`urllib.error.HTTPError(url, 404, "Not Found", hdrs=email.message.Message(), fp=None)`) → `failure == "unreachable"` e `items == {}`;
    - `test_fetch_rpc_error_on_jsonrpc_error_body` (corpo `{"jsonrpc":"2.0","error":{"code":-32603,"message":"could not find library"}}` → `failure == "rpc_error"`, `"could not find library" in detail`) e `test_fetch_rpc_error_on_http_500` (`"500" in detail`);
    - `test_fetch_rpc_error_on_malformed_result` (corpo `{"result": []}` → `failure == "rpc_error"`, `detail == "resposta JSON-RPC inesperada"`, `items == {}`, sem exceção);
    - `test_fetch_success_returns_items` (corpo com `result.items.smith2020.custom = {"itemID": 7, "uri": "http://zotero.org/users/local/k/items/AB"}` e `result.items.ghost2020 = null` → `items == {"smith2020": {"itemID": 7, "uri": "http://zotero.org/users/local/k/items/AB"}}`, `failure == ""`);
    - `test_fetch_params_omit_library_when_absent` (`json.loads(cast(bytes, req.data))["params"] == [["k"], True]`) e `test_fetch_params_include_library` (`library="Lab"` → `[["k"], True, "Lab"]`, e `BbtLookup.library == "Lab"`);
    - `test_fetch_timeout_is_two_seconds` (`timeout == 2.0`);
    - `test_fetch_url_follows_prumo_zotero_base` (`PRUMO_ZOTERO_BASE=http://example.test:1234` → `req.full_url == "http://example.test:1234/better-bibtex/json-rpc"`);
    - `test_fetch_without_citekeys_does_not_call` (lista vazia → `BbtLookup({})`, `spy` nunca chamado).
  - `_read_docx_citations`: `test_read_docx_citations_marks_unlinked`. Dois payloads: o 1º com os itens `a2020` (`"uris":["u"]`) e `b2021` (`"uris":[]`); o 2º com o item `c2022` sem a chave `uris`. `unlinked` é por ocorrência: `occs = _read_docx_citations(docx)` e `assert [o["unlinked"] for o in occs] == [["b2021"], ["c2022"]]`.
  - `docx_link_warning`, sobre docx de `_write_minimal_docx_with_payloads`, com `redo = "prumo write export docs/p.md --to docx --force"`:
    - `test_warning_none_when_all_linked` (todos com `uris` preenchido → `None`);
    - `test_warning_unreachable_e1` (`BbtLookup({}, failure="unreachable")` → começa com "Não consegui falar com o Better BibTeX" e contém o `redo`);
    - `test_warning_sandbox_e2` (`monkeypatch.setenv("SANDBOX_RUNTIME", "1")` → contém "sandbox do Claude Code", `sandbox.excludedCommands`, `zotero_base()` e o `redo`);
    - `test_warning_rpc_error_e3` (`failure="rpc_error", detail="could not find library"` → contém `could not find library`, `9.0.65`, `zotero.library` e o `redo`);
    - `test_warning_not_found_e4_lists_keys_and_library` (`BbtLookup({"a2020": {...}}, library="Lab")` com `b2021` sem vínculo → contém `b2021`, `(Lab)` e o `redo`; com `library=None` → `(My Library, a padrão)`);
    - `test_warning_e4_truncates_after_five_keys` (7 chaves sem vínculo → as 5 primeiras na ordem do documento, seguidas de `, …`);
    - `test_warning_counts_distinct_citekeys` (a mesma chave sem vínculo em duas ocorrências → texto contém `1 citekey(s)`).
  - `_redo_command`: `test_redo_export_defaults` (→ `"prumo write export /tmp/p.md --to docx --force"`), `test_redo_quotes_paths_with_spaces` (`Path("/tmp/meu draft.md")` → contém `'/tmp/meu draft.md'`), `test_redo_compose_with_all_options` (→ `prumo write compose --index … --to docx --force --style vancouver --bib … --out-dir … --reference-doc …`, nessa ordem).
  - Fiação, com `_fake_project` + `_patch_export_seams` + `_fake_run_writing_output_flag([_docx_bytes_for_export_wiring(tmp_path, [payload])], calls)`, página `"Cita [@smith2020] aqui.\n"` e `monkeypatch.setattr(export_mod, "fetch_bbt_zotero_metadata", lambda keys, lib, **kw: BbtLookup({}, failure="unreachable"))`:
    - `test_export_unreachable_does_not_raise_and_warns_once` (`avisos: list[str] = []`, `export(..., on_warning=avisos.append)` → docx gravado, `len(avisos) == 1`, `"prumo write export" in avisos[0]`, `"--style" not in avisos[0]`);
    - `test_export_redo_carries_style_and_reference_doc` (`style="vancouver"`, `reference_doc=tmp_path / "revista.docx"` (arquivo criado) → `"--style vancouver" in avisos[0]` e `"--reference-doc" in avisos[0]`);
    - `test_compose_unreachable_does_not_raise_and_warns_once` (index `"---\npages: [docs/page.md]\n---\n"` → `len(avisos) == 1`, `"prumo write compose --index" in avisos[0]`);
    - `test_export_default_on_warning_logs` (sem `on_warning`, com `caplog` → um registro WARNING com "Não consegui falar").
  - `_check_pandoc`: `test_check_pandoc_e7_without_pandoc` (`monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)` e o `_ZETTLR_PANDOC` inexistente do conftest → `ToolNotFoundError` cuja mensagem contém `"3.8.2"` e `"prumo doctor"`); `test_check_pandoc_uses_zettlr_binary` (`monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)` e `_ZETTLR_PANDOC` apontando para um executável em `tmp_path`, com `chmod(0o755)` → devolve `str(esse caminho)`; sem o `_binary_on_path` a `None`, o CI devolveria `/usr/bin/pandoc`).
- [ ] **Step 2: Ajustar os testes antigos.**
  - `test_export_docx_validation.py`, `_patch_export_seams`: sai `monkeypatch.setattr(export_mod, "_check_bbt_running", …)`; o de `fetch_bbt_zotero_metadata` vira `lambda keys, lib, **kw: BbtLookup({})` (importe `BbtLookup`); `_check_pandoc` continua mockado.
  - `test_errors.py`: sai `export.ZoteroNotRunningError` de `_WRITE_LEAVES`.
  - `test_cli.py`: sai o caso parametrizado `("export", export.ZoteroNotRunningError)` e o id `"export-zotero-down"` de `test_write_error_paths_show_clean_error`. Docstring de `_stub_pandoc_seams`: sai "`--to html` evita a checagem de BBT (só exigida para docx) e"; fica "`--to html` evita a validação estrutural do zip docx, mantendo o teste focado na guarda."
- [ ] **Step 3:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write/test_export_zotero_link.py -q` → FAIL (`ImportError: BbtLookup`).
- [ ] **Step 4: Implementar** em `src/par/domains/write/export.py`:
  - imports: `shlex`, `http.client`, `from collections.abc import Callable`, `from dataclasses import dataclass`, `Literal` em `typing`, `from par.core.deps import bbt_rpc_url, in_claude_sandbox, pandoc_path, zotero_base`. `shutil` fica (o `_check_typst` usa `shutil.which`).
  - **Saem** `BBT_JSONRPC_URL`, `ZoteroNotRunningError`, `_check_bbt_running` e as chamadas `if to == "docx": _check_bbt_running()` em `export()` e `compose()`.
  - `_check_pandoc`:

```python
def _check_pandoc() -> str:
    pandoc = pandoc_path()
    if not pandoc:
        raise ToolNotFoundError(
            "pandoc não encontrado (nem no PATH nem dentro do Zettlr.app). Instale o pandoc "
            "3.8.2 ou mais novo (macOS: `brew install pandoc`; Linux: pacote oficial em "
            "https://github.com/jgm/pandoc/releases) e confira com: prumo doctor"
        )
    return pandoc
```

    O export **não** checa versão (B7: o doctor avisa).
  - `BbtLookup` como no esboço da Spec B. `fetch_bbt_zotero_metadata` conforme o esboço: lista vazia → `BbtLookup({}, library=library or None)` sem rede; `params = [citekeys, True]` e `params.append(library)` só se `library`; POST JSON em `bbt_rpc_url()` (calculada na chamada) com o `timeout` recebido; o payload continua `{"jsonrpc": "2.0", "method": "item.pandoc_filter", "params": params}`. Ordem dos `except`: `urllib.error.HTTPError` primeiro (404 → `"unreachable"`; outro código → `"rpc_error"`, `detail=f"HTTP {exc.code}"`); depois `(OSError, ValueError, http.client.HTTPException)` → `"unreachable"`, `detail=repr(exc)`. Corpo que não é `dict` → `"rpc_error"`, `detail="resposta JSON-RPC inesperada"`. Corpo com `"error"` → `"rpc_error"`, `detail = error.get("message")` se for dict com mensagem, senão `str(error)`. Sucesso: a extração de `itemID`/`uri` de hoje, mas com `isinstance(..., dict)` em cada nível, porque a função nunca levanta: `result = body.get("result")` e `items = result.get("items", {})` (só se `result` for dict); se `result` ou `items` não forem `dict` → `BbtLookup({}, failure="rpc_error", detail="resposta JSON-RPC inesperada", library=…)`. Por item, `data` que não é `dict` (o `null` de hoje incluído) ou `custom = data.get("custom")` que não é `dict` → a citekey fica fora de `items` (sai sem vínculo, como hoje); `itemID` e `uri` ambos `None` → fora também. `library` do resultado = `str(library) if library else None`. Docstring: sai a menção ao `zotero.lua`; diz "melhor-esforço, nunca levanta (ADR-0037)".
  - `_write_zotero_lookup` devolve `(lookup_file | None, lookup)`. Grava o arquivo só quando `lookup.items` não está vazio, montando um dict novo `{key: {**entry, "fingerprint": _fingerprint_for(entries_raw.get(key), entry)}}`, sem mutar `lookup.items`.
  - `_read_docx_citations`: acrescente `"unlinked": [item["id"] for item in citation_items if not item.get("uris")]` em cada ocorrência; docstring cita a chave nova.
  - `_redo_command`: monta `prumo write export {q(page)}` ou `prumo write compose --index {q(index)}`, depois `--to docx --force`, e acrescenta nessa ordem `--style {q(style)}`, `--bib {q(bib)}`, `--out-dir {q(out_dir)}` e `--reference-doc {q(reference_doc)}` para cada um que não for `None` (`q = shlex.quote`, caminhos com `str(...)`). `out` não entra: não tem flag na CLI.
  - `docx_link_warning`: junta as `unlinked` de `_read_docx_citations(docx_path)` em ordem de primeira aparição, sem repetir; vazio → `None`. `n = len(chaves)`. `failure == "unreachable"` → E2 se `in_claude_sandbox()`, senão E1. `"rpc_error"` → E3. `""` → E4, com `library = lookup.library or "My Library, a padrão"` e `keys = ", ".join(chaves[:5]) + (", …" if n > 5 else "")`. Textos literais:

```python
_LINK_UNREACHABLE_MSG = (
    "Não consegui falar com o Better BibTeX (Zotero fechado, sem o Better BibTeX, ainda "
    "iniciando ou sem resposta em 2 s): {n} citekey(s) saíram sem vínculo com a sua "
    "biblioteca. O docx abre, e o Refresh do Word funciona com os dados embutidos. Para "
    "vincular, abra o Zotero e rode: {redo}"
)
_LINK_SANDBOX_MSG = (
    "O sandbox do Claude Code não deixou o export falar com o Zotero em {base}: {n} "
    "citekey(s) saíram sem vínculo com a sua biblioteca (o docx abre e o Refresh funciona). "
    "Para vincular, peça para repetir fora do sandbox (o Claude pede permissão): {redo}. "
    'Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em '
    "`sandbox.excludedCommands` no `~/.claude/settings.json`."
)
_LINK_RPC_ERROR_MSG = (
    "O Better BibTeX recusou a consulta ({detail}): {n} citekey(s) saíram sem vínculo com "
    "a sua biblioteca. Causas comuns: `zotero.library` no frontmatter com um nome que não "
    "existe no Zotero, ou Better BibTeX anterior a 9.0.65 com a janela principal do Zotero "
    "fechada. Corrija (Tools → Plugins atualiza o Better BibTeX; abra a janela do Zotero) "
    "e rode: {redo}"
)
_LINK_NOT_FOUND_MSG = (
    "{n} citekey(s) não foram achadas pelo Better BibTeX na biblioteca consultada "
    "({library}): {keys}. Saem sem vínculo. Se estão numa biblioteca de grupo, ponha "
    '`zotero: {{library: "<nome do grupo>"}}` no frontmatter e rode: {redo}'
)
```

    `{base}` = `zotero_base()`. A lista vem do OOXML e não do texto, porque `scan_citekeys` admite falso positivo (B1).
  - `export()`: guarde `bib_arg = bib` antes de `bib = bib or pj_layout.bib_path(...)`. Ao lado de `zotero_lookup_file: Path | None = None`, declare `lookup = BbtLookup({})`, para o nome existir em todo formato. No ramo docx, rebind com `zotero_lookup_file, lookup = _write_zotero_lookup(...)`; depois de `_finalize_docx(cmd, out)` e de `_emit_review_sidecars(...)`, monte `redo = _redo_command("export", page, style=None if style == "apa" else style, bib=bib_arg, out_dir=out_dir, reference_doc=reference_doc)` e, se `aviso := docx_link_warning(out, lookup, redo)`, chame `(on_warning or logger.warning)(aviso)`.
  - `compose()`: guarde `style_arg = style` e `bib_arg = bib` antes das reatribuições; a mesma declaração `lookup = BbtLookup({})` ao lado de `zotero_lookup_file: Path | None = None` e o rebind no ramo docx; mesmo fluxo depois de `_finalize_docx`, com `_redo_command("compose", index, style=style_arg, bib=bib_arg, out_dir=out_dir, reference_doc=reference_doc)`.
  - Docstrings: a do módulo troca "Exige Zotero + Better BibTeX rodando em ``127.0.0.1:23119`` para fornecer as URIs dos itens (sem URIs, Refresh ainda funciona via CSL JSON embedado mas "Add/Edit Citation" não relinka)." por "Usa o Better BibTeX, se estiver aberto, para vincular as citações à biblioteca: o lookup é melhor-esforço (2 s); sem vínculo, cada citação sai com ``uris`` vazio e ``itemData`` embutido, e :func:`docx_link_warning` avisa com o comando de refazer (ADR-0037)."; a de `ZoteroCitekeyNotFoundError` troca "``zotero.lua`` não encontrou" por "O citeproc não encontrou"; `export()`/`compose()` documentam `on_warning`.
- [ ] **Step 5:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write -q` → PASS; suíte inteira sem falha nova; `mypy`, `ruff check` e `ruff format --check` limpos. `grep -rn "ZoteroNotRunningError\|_check_bbt_running\|BBT_JSONRPC_URL" src tests` → nada.
- [ ] **Step 6: Commit** `fix(write): export docx sem exigir o Zotero; vínculo melhor-esforço com aviso e comando de refazer (ADR-0037)`.

### Task 5: CLI — nota de primeiro uso (E6) e avisos do vínculo

Spec B §B1 (callback), §B4 (nota só no `export`), §Componentes 0.70.3 (`src/par/domains/write/cli.py`), §Erros E6, §Testes 0.70.3 (`test_cli.py`).

**Files:**
- Modify: `src/par/domains/write/cli.py`
- Test: `tests/unit/write/test_cli.py`

**Interfaces:**
- Consumes: `export.export(..., on_warning=...)`, `export.compose(..., on_warning=...)` (Task 4).
- Produces: `FIRST_USE_DOCX_NOTE` (E6), impressa só por `export_command` com `--to docx`; no `--json` de `write export` e `write compose`, a chave aditiva `"warnings": list[str]`.

- [ ] **Step 1: Testes que falham** em `tests/unit/write/test_cli.py`. A saída do Rich quebra linha em 80 colunas no `CliRunner`; compare sobre `" ".join(result.output.split())`. Casos:
  - `test_write_export_docx_prints_first_use_note` (modificado): contém "Primeiro uso no Word" e "não precisa de Refresh"; **não** contém "use Zotero → Refresh";
  - `test_write_compose_docx_omits_first_use_note` (substitui `test_write_compose_docx_prints_first_use_note`, l.368-378): `"Primeiro uso no Word" not in result.output`;
  - `test_write_export_warning_goes_to_console` e `test_write_compose_warning_goes_to_console`: o `export.export`/`export.compose` falso (`monkeypatch.setattr("par.domains.write.cli.export.export", fake)`) chama `kw["on_warning"]("aviso teste")` e devolve o caminho; a saída contém `⚠ aviso teste`;
  - `test_write_export_json_carries_warnings` e `test_write_compose_json_carries_warnings`: com `--json`, `json.loads(result.stdout)["warnings"] == ["aviso teste"]` (no modo JSON o `console.warn` vai para o stderr);
  - `test_write_export_json_warnings_empty_without_warning`: `--json` sem aviso → `"warnings": []`;
  - `test_zettlr_entry_forwards_warnings`: `page = tmp_path / "draft.md"` (com `page.write_text("x")`; não precisa de projeto, porque `export.export` é falso); `monkeypatch.setattr("sys.argv", ["prumo-zettlr-export", str(page)])` (sem isso `zettlr_export_entry` levanta "uso: …" e sai com `SystemExit(1)`); `def fake(**kwargs: Any) -> Path` chama `kwargs["on_warning"]("aviso z")` e devolve `tmp_path / "out.docx"`; `monkeypatch.setattr("par.domains.write.cli.export.export", fake)`; `zettlr_export_entry()` → `"aviso z" in capsys.readouterr().out`. Mesmo molde dos `test_zettlr_entry_*` que já existem no arquivo. Este teste é apagado pelo PR 2 da Spec A (Task 10 do plano `2026-10-02-plugin-distribuicao-unica`), junto com `zettlr_export_entry`.
  - Tipagem dos falsos: `**kwargs: Any` (o `Any` já é importado no arquivo). Com `**kwargs: object`, a chamada `kwargs["on_warning"](…)` não passa no `mypy --strict`.
- [ ] **Step 2:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write/test_cli.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - `FIRST_USE_DOCX_NOTE` nova, literal (E6):

```python
FIRST_USE_DOCX_NOTE = (
    "Primeiro uso no Word: o docx já sai com citações e bibliografia formatadas e com as "
    "preferências do Zotero embutidas, então não precisa de Refresh. Se ele for para "
    "revisão com `prumo write review ingest`, peça ao coautor para não usar os botões do "
    "Zotero (Refresh, Add/Edit Citation) nesse arquivo: o Zotero reescreve os campos de "
    "citação e o ingest recusa o arquivo."
)
```

  - `export_command` e `compose_command`: `avisos: list[str] = []`; passam `on_warning=avisos.append`; depois do `console.success(...)`, `for aviso in avisos: console.warn(aviso)`; só `export_command` imprime `FIRST_USE_DOCX_NOTE` (quando `to == "docx"`); `compose_command` deixa de imprimi-la. Payload: `payload: dict[str, object] = {...}` como hoje e, **só em modo JSON** (`if json_mode: payload["warnings"] = avisos`), para o modo texto não repetir o aviso que o `console.warn` já mostrou (Princípio VIII); depois `console.emit(payload)`.
  - `zettlr_export_entry`: `export.export(page=page, to="docx", force=True, on_warning=console.warn)` (o comando sai na 0.71.0, pela Spec A).
- [ ] **Step 4:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write -q` → PASS; suíte sem falha nova; `mypy` e `ruff` limpos.
- [ ] **Step 5: Commit** `fix(write): nota de primeiro uso sem Refresh e avisos de vínculo no export/compose`.

### Task 6: Ingest — mensagem própria quando o Zotero reescreveu os campos (E5)

Spec B §B4, §Componentes 0.70.3 (`src/par/domains/write/review.py` e o bloco "no início de `check_conservation`"), §Erros E5, §Testes 0.70.3 (`test_review_reader.py`).

**Files:**
- Modify: `src/par/domains/write/review.py`
- Test: `tests/unit/write/test_review_reader.py`

**Interfaces:**
- Consumes: `DocxCitation.occ_id`, `CiteMapFile.page`.
- Produces: `check_conservation` levanta `CitationConservationError(_ZOTERO_REWROTE_MSG.format(n=…, page=citemap.page))` antes de qualquer outra checagem de conservação quando **alguma** citação observada tem `occ_id` vazio.

- [ ] **Step 1: Testes que falham** em `tests/unit/write/test_review_reader.py` (seção de conservação). Helper local `_zotero_rewritten_payload(citekeys: list[str], formatted: str, *, linked_id: int | None = None) -> str`: o JSON que o Zotero grava depois do Refresh (Spec B §Contexto, "O Refresh também apaga as marcas do PAR"). Sem `prumoOcc`, sem `prumoFingerprint` e sem `zoteroItemID`; `citationID` aleatório (ex.: `"q7Xk2LpA"`); cada item vira `{"id": f"SESS/RND{i}", "itemData": {"id": citekey, "type": "article-journal", "title": "T"}}`, ou seja, o `id` deixa de ser a citekey e só o `itemData.id` a guarda. Com `linked_id`, o 1º item sai com `"id": linked_id` (inteiro, o itemID numérico do item vinculado); `properties.formattedCitation = formatted`. Casos, sempre pelo leitor real `read_docx_citations_with_state` sobre `_write_docx_with_fields`:
  - `test_check_conservation_all_rewritten_by_zotero` (dois campos reescritos, um deles com `linked_id=42`; citemap com dois occ) → E5 com `2 campo(s)`, e `"occ_id duplicado" not in str(exc.value)`. O `id` inteiro prova que a guarda do E5 dispara antes de qualquer checagem usar `citekeys`;
  - `test_check_conservation_one_rewritten_among_many` (um campo normal com `prumoOcc` `00000001` e um reescrito; citemap com dois occ) → E5 com `1 campo(s)`;
  - `test_check_conservation_rewritten_message_names_buttons_and_command` → a mensagem contém "Refresh", "Add/Edit Citation" e `prumo write export docs/page.md --to docx --force` (`_citemap` usa `page="docs/page.md"`).
- [ ] **Step 2:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write/test_review_reader.py -q` → FAIL (o primeiro cai em "occ_id duplicado").
- [ ] **Step 3: Implementar.** Constante de módulo, literal (E5):

```python
_ZOTERO_REWROTE_MSG = (
    "{n} campo(s) de citação deste docx foram reescritos pelo plugin do Zotero no Word "
    "(Refresh ou Add/Edit Citation) e perderam as marcas do PAR: o ingest não consegue "
    "parear as citações. Peça ao coautor a versão de antes de usar esses botões e rode o "
    "ingest nela. Ou guarde a cópia do coautor fora de build/exports/, re-exporte com "
    "`prumo write export {page} --to docx --force` (acrescente as mesmas opções do export "
    "original, como `--style` ou `--reference-doc`) e peça uma revisão nova sem os botões "
    "do Zotero."
)
```

  No início de `check_conservation`, antes do `by_occ`, o bloco de Spec B §Componentes 0.70.3 ("`src/par/domains/write/review.py`, no início de `check_conservation`"). Docstring: novo item **0.** "Campo reescrito pelo Zotero (`occ_id` vazio em qualquer citação): o PAR sempre grava `prumoOcc`, então só o Refresh ou o Add/Edit Citation do Zotero o apagam; vem antes do agrupamento, porque com vários vazios o ramo de duplicata dispararia com 'paste-clone' (ADR-0037)." As checagens que `ingest()` faz antes de `check_conservation` não mudam de lugar.
- [ ] **Step 4:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/write/test_review_reader.py tests/unit/write/test_review_ingest.py -q` → PASS (os de `test_review_ingest.py` que dependem de `uvx` seguem a baseline); `mypy` e `ruff` limpos.
- [ ] **Step 5: Commit** `fix(write): ingest diz quando o Zotero reescreveu os campos do docx (ADR-0037)`.

### Task 7: `reconcile` pré-aprova as tools pelo prefixo do plugin

Spec B §B8, §Componentes 0.70.3 (`skills/review/modes/reconcile.md`), §Testes 0.70.3 (`test_skills.py`).

**Files:**
- Modify: `skills/review/modes/reconcile.md`
- Modify (gerado): `skills/review/SKILL.md`
- Test: `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces: invariante "nenhum `mcp__prumo__` em `skills/**`" (a Spec A estende o mesmo teste a `mcp__qmd__`).

- [ ] **Step 1: Teste que falha** em `tests/unit/core/test_skills.py`, junto de `_REPO_SKILLS`:

```python
def test_skills_use_plugin_mcp_prefix() -> None:
    """O servidor do plugin aparece como `mcp__plugin_par_prumo__*` (ADR-0037, B8)."""
    offenders = [
        str(p.relative_to(_REPO_SKILLS))
        for p in sorted(_REPO_SKILLS.rglob("*.md"))
        if "mcp__prumo__" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
```

- [ ] **Step 2:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/core/test_skills.py -q` → FAIL (`review/modes/reconcile.md`, `review/SKILL.md`).
- [ ] **Step 3: Implementar.** Em `skills/review/modes/reconcile.md`, l.5 (`allowed-tools`) e l.218 ("Ferramentas `mcp__prumo__*` não aparecem disponíveis"): `mcp__prumo__` vira `mcp__plugin_par_prumo__`, sem lista dupla. A pré-aprovação de `propose_prose_edit` (ADR-0017) fica. Regere a porta, com `git status --porcelain --untracked-files=all docs skills` sem `??` (Global Constraints): `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py` (atualiza o `allowed-tools` de `skills/review/SKILL.md`; nunca edite à mão).
- [ ] **Step 4:** `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/core/test_skills.py tests/unit/test_gen_indexes.py -q` → PASS; `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check` limpo.
- [ ] **Step 5: Commit** `fix(skills): reconcile pré-aprova as tools pelo prefixo do plugin`.

### Task 8: Documentação da 0.70.3

Spec B §Componentes 0.70.3 (linhas `README.md`, `templates/pj_base/docs/project_guide.md`, `docs/superpowers/specs/2026-07-22-zettlr-front-design.md`, `ROADMAP.md`, `ARCHITECTURE.md`), §Quando reavaliar.

**Files:**
- Modify: `README.md`, `templates/pj_base/docs/project_guide.md`, `docs/superpowers/specs/2026-07-22-zettlr-front-design.md`, `ROADMAP.md`, `ARCHITECTURE.md`

Não edite `docs/actions-by-context.md`: o pré-requisito "Zotero + Better BibTeX rodando" e o "clicar `Refresh`" que ele traz ficam desatualizados com a 0.70.3, mas o arquivo inteiro é apagado no PR 1 da Spec A (0.71.0, Task 7 do plano `2026-10-02-plugin-distribuicao-unica`), e a Spec B não o lista.

- [ ] **Step 1: `README.md`, §"Pré-requisitos externos".**
  - "O plugin orquestra duas ferramentas" vira "O plugin orquestra três ferramentas";
  - na linha do Zotero, a célula "Necessária para" passa a: `` `paper sync-annotations`, `paper sync-notes`, `write export --to docx` (vínculo das citações, opcional) `` (sai "(citações vivas)"; o docx deixa de exigir o Zotero);
  - linha nova na tabela, depois da do Zotero, literal:

```markdown
| **Pandoc ≥ 3.8.2** | `write export`, `write compose` | macOS: `brew install pandoc` (ou o Zettlr, cujo pandoc o PAR usa quando não há um no PATH); Linux: pacote oficial em https://github.com/jgm/pandoc/releases (o do apt costuma ser antigo); confira com `prumo doctor`. |
```
- [ ] **Step 2: `templates/pj_base/docs/project_guide.md`, l.20.** "(≥ 3.0 — o Pandoc embutido precisa ser 3.x)" vira "(recente: o 4.8 traz o pandoc 3.10.1; o export do PAR precisa de pandoc 3.8.2 ou mais novo, confira com `prumo doctor`)". Vale para projetos novos; o `update` não reflui este arquivo.
- [ ] **Step 3: spec do Zettlr.** Logo abaixo da tabela de §"Tratamento de erros e degradações" (depois da linha "Pandoc embutido do Zettlr < 3.0", antes de "## Testes"), uma linha em branco e a nota literal: `> As linhas 'Zotero/BBT fechado — caminho canônico' (l.107) e 'Pandoc embutido do Zettlr < 3.0' (l.112) foram substituídas pela ADR-0037: o export degrada com aviso, e o piso do pandoc é 3.8.2.`
- [ ] **Step 4: `ARCHITECTURE.md`, l.85.** "filtros Lua vendorados do Pandoc (zotero_live_docx.lua)" vira "filtros Lua vendorados do Pandoc (crossref.lua, zotero_live_docx.lua)", mantendo o alinhamento da árvore.
- [ ] **Step 5: `ROADMAP.md`, fim da lista de "## Decisões deliberadas postergadas".** Os três bullets de Spec B §"Quando reavaliar" ("Bullets novos de 'Decisões deliberadas postergadas' do `ROADMAP.md` (0.70.3)"), copiados literalmente: **Ingest tolerante aos botões do Zotero**, **Versão do Better BibTeX no doctor** e **`prumo paper connect --replace`**.
- [ ] **Step 6:** Com `git status --porcelain --untracked-files=all docs skills` sem `??`, `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check` limpo (nenhum bloco gerado mudou; se mudar, rode sem `--check` e inclua); `UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest tests/unit/test_pj_base_integration.py tests/unit/test_cli_init.py -q` → PASS.
- [ ] **Step 7: Commit** `docs: pré-requisito pandoc 3.8.2, Zotero opcional no docx e decisões postergadas (ADR-0037)`.

### Task 9 (PR A): Onboarding — receita do 54yyyu no lugar do cookjohn

Spec B §B12 e §Componentes 0.71.0 ("Receita do onboarding"; "É só documentação e pode sair já, sem bump"); §Release e migração ("Já, sem bump").

**Files:**
- Modify: `docs/onboarding-pesquisador.md`

- [ ] **Step 0: Worktree limpo a partir de `origin/main`.** Não use este worktree (ele tem as specs commitadas no branch e planos não rastreados que vazariam para o `--check`). Rode `git fetch origin` e `git worktree add "$TMPDIR/par-pr-a" -b docs/onboarding-zotero-54yyyu origin/main`; todos os passos abaixo rodam dentro de `$TMPDIR/par-pr-a` (o `uv run` cria o `.venv` dele na primeira chamada). Confira `git -C "$TMPDIR/par-pr-a" status --porcelain --untracked-files=all docs skills` → vazio.
- [ ] **Step 1:** Em `$TMPDIR/par-pr-a/docs/onboarding-pesquisador.md`, substitua a seção `### Busca semântica no seu acervo do Zotero, sem terminal` (o H3 e o parágrafo que cita `cookjohn/zotero-mcp`, l.174-180) pelo bloco ```` ```markdown ```` de Spec B §Componentes 0.71.0, "**Receita do onboarding**", copiado literalmente (começa em `### Perguntar ao seu Zotero (opcional, ferramenta de terceiros)` e termina no último bullet de **Privacidade**). A spec não existe em `origin/main`: leia o bloco com `git show fe9f5b8:docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md` (os objetos do git são compartilhados entre worktrees). O resto do arquivo não muda: a §4 e a reescrita da trilha são da 0.71.0.
- [ ] **Step 2:** `grep -n "cookjohn" docs/onboarding-pesquisador.md` → nada; `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check` limpo (o `title:` do frontmatter não muda; num worktree limpo de `origin/main` o `--check` já passa antes da mudança, conferido em 2026-10-02).
- [ ] **Step 3: Commit** `docs(onboarding): receita opcional do 54yyyu/zotero-mcp no lugar do cookjohn`. Sem bump e sem entrada no CHANGELOG (só documentação, `.claude/rules/release.md`). Abra o PR A; ele não depende do PR B.
- [ ] **Step 4: Antes do merge.** Se `main` andou desde o Step 0: `git fetch origin && git rebase origin/main`, rode `gen_indexes.py` (sem `--check`), commite qualquer diferença, confirme o `--check` limpo e `git push --force-with-lease`. Depois do merge, `git worktree remove "$TMPDIR/par-pr-a"`.

### Task 10: Verificação, CHANGELOG, índices, gates e arquivamento

Spec B §Release e migração (0.70.3), §Spikes e gates pré-merge (G1, G2).

**Files:**
- Modify: `CHANGELOG.md`
- Move: este plano para `docs/superpowers/plans/archive/`
- Modify (gerado): `docs/_index.md`

- [ ] **Step 1: CHANGELOG.** Em `## [Não publicado]`, cole **literalmente** o bloco ```` ```markdown ```` de Spec B §"Release e migração", "**0.70.3 PATCH** … Entrada do CHANGELOG": seções `### Corrigido`, `### Alterado`, `### Removido` e a linha final "Para atualizar: …". Não crie a seção `## [0.70.3]`: isso é do corte.
- [ ] **Step 2: Comandos, todos limpos.**

```sh
UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest -q -rs
UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff check . && UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff format --check .
UV_CACHE_DIR="$TMPDIR/uvcache" uv run mypy
UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check
UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/validate_manifests.py
UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/sync_manifest_version.py --check
```

  O `pytest` não pode ter falha nova em relação à baseline, e nesta máquina nenhum SKIPPED com "pandoc ausente".
- [ ] **Step 3: Greps de regressão.** `grep -rn "ZoteroNotRunningError\|_check_bbt_running\|BBT_JSONRPC_URL\|zotero_bibliography_docx\|_zotero_lua_filter" src tests skills` → nada; `grep -rn "mcp__prumo__" skills` → nada; `grep -rn 'environ.get("PRUMO_ZOTERO_BASE"' src` → exatamente uma linha, em `src/par/core/deps.py` (dentro de `zotero_base`). Docstrings que só citam o nome da variável não contam: o grep procura a leitura.
- [ ] **Step 4: Smoke (dentro do sandbox, Zotero inalcançável).** Pré-condição: o `--style` padrão (`apa`) é resolvido em `~/Zotero/styles/apa.csl` (`core/csl.resolve_csl`). Se esse arquivo não existir, o export falha com `CslNotFoundError`, alheio a esta mudança: instale o estilo (Zotero → Settings → Cite → Styles) ou passe `--style <nome>` de um `.csl` que exista em `~/Zotero/styles/` nos três `prumo write export` abaixo. Num diretório do scratchpad:
  - `UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo init <scratch>/pj_smoke`;
  - grave `@article{silva2020, author={Silva, Ana}, title={T}, journal={J}, year={2020}}` em `<pj>/docs/references/_references.bib` e uma página `<pj>/docs/p.md` com `Texto [@silva2020].\n\n::: {#refs}\n:::\n`;
  - `UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo write export <pj>/docs/p.md --to docx` → exit 0, docx em `build/exports/`, um aviso ⚠ com o E2 (com `SANDBOX_RUNTIME=1`; fora do sandbox, E1 ou vínculo de verdade), o comando `prumo write export … --to docx --force` e a nota E6;
  - `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python -c "from pathlib import Path; from par.domains.write.export import _read_docx_citations as r; print(r(Path('<docx>')))"` → `unlinked` igual a `['silva2020']`;
  - `UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo write export <pj>/docs/p.md --to docx --force --json` → JSON com `"warnings"` contendo o aviso;
  - `UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo doctor <pj> --json` → `external_deps` com `pandoc` presente (nesta máquina: `"pandoc 3.10.1 do Zettlr.app"`, `version` `"3.10.1"`).
- [ ] **Step 5: Arquivar este plano.** `git mv docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0703.md docs/superpowers/plans/archive/`. Frontmatter de fechamento, no formato de `archive/2026-09-12-superficie-f3-status.md`: `status: implemented`, `verified: <data>`, `release: "pendente — 0.70.3 PATCH (corte separado, RELEASING.md)"`, `spec: "[[2026-10-02-ponte-zotero-minima-design]]"`, e o parágrafo `> **Fechamento (<data>).**` com o que foi entregue, o resultado da verificação e o que ficou pendente (G1, corte). O parágrafo registra também o desvio deliberado da Spec B §Componentes (`write/cli.py`, que manda emitir `"warnings": avisos` no payload): "`warnings` só no payload `--json` (o modo texto já mostra cada aviso via `console.warn`; Princípio VIII)". Depois, com `git status --porcelain --untracked-files=all docs skills` sem `??`, `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py` e `--check`.
- [ ] **Step 6: Commit** `docs: CHANGELOG da ponte Zotero mínima (0.70.3) e plano arquivado`.
- [ ] **Step 7: Gate G2 (CI do PR B).** No run do PR, o passo "Pandoc 3.8.2 (piso do export)" imprime `pandoc 3.8.2`, e o resumo `-ra` do Pytest não lista SKIPPED com "pandoc ausente" (`gh run view <id> --log | grep -n "pandoc ausente"` → nada) nas duas versões de Python. Se algum teste de pipeline real falhar só no 3.8.2 (P14), corrija antes do merge; nunca o pule.
- [ ] **Step 8: Gate G1 (máquina do dono, antes do merge do PR B).** É manual e depende do dono: o Word real e o upgrade do BBT não são automatizáveis daqui. A orquestração pede ao dono os itens de Spec B §"Spikes e gates pré-merge", G1:
  - 0. atualizar o Better BibTeX para ≥ 9.0.65, reiniciar o Zotero e rodar `prumo doctor`;
  - 1. os dois `curl` do `item.pandoc_filter`, com `""` e sem o terceiro parâmetro. O agente pode rodá-los fora do sandbox, com permissão, se o Zotero estiver aberto;
  - 2. Word real com o branch: (a) Zotero fechado + Refresh sem erro, com o aviso E1; (b) Zotero aberto com a janela principal fechada + Refresh religa; (c) depois de um Refresh, `prumo write review ingest` falha com E5; (d) perfil do Zettlr + Refresh sem erro.

  Registre o resultado no PR. Se (a), (c) ou (d) falhar, o merge espera a correção. Se só (b) falhar com a janela fechada, repita com ela aberta para separar as causas (P2, P4).
- [ ] **Step 9:** Antes do merge, sincronize com `main`, porque PRs paralelos (PR A e outros) regeneram o mesmo bloco de `docs/_index.md`: `git fetch origin && git rebase origin/main` (num conflito em `docs/_index.md`, `docs/adr/_index.md` ou `skills/review/SKILL.md`, aceite qualquer lado e regenere; nunca resolva bloco gerado à mão); confira `git status --porcelain --untracked-files=all docs skills` sem `??`; rode `UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py`, commite qualquer diferença (`docs: índices regerados após rebase`), confirme o `--check` limpo e a suíte do Step 2, e `git push --force-with-lease`. Com G1 e G2 registrados e o CI verde nesse último push, o PR B entra em `main`. O corte da 0.70.3 (bump, `CHANGELOG` datado, `CITATION.cff`, tag e release) fica com a orquestração, nos 8 passos do `RELEASING.md`.
