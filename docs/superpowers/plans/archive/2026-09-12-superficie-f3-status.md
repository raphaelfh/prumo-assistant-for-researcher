---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-superficie-de-skills-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–4 implementadas em TDD: `src/prumo_assist/status.py`, comando `prumo status`, `start` sugerindo `next.say`. Smoke num `prumo init` novo devolve `paper library` com a frase do frontmatter. Pendente: corte do release. Verificação: suíte inteira verde exceto os 11 testes de `tests/unit/write/test_review_ingest.py` que dependem de `uvx` no PATH (falham igual no `main`); ruff, mypy, `gen_indexes --check`, `validate_manifests` e `sync_manifest_version --check` limpos.

# Superfície de skills — F3: `prumo status` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prumo status [path] [--scope <slug>] [--json]` diz, só lendo o disco, em que ponto o estudo está e qual a próxima frase dizer ao agente; o `start` renderiza.

**Architecture:** Módulo `src/prumo_assist/status.py` no topo do pacote (precedente do `mcp_server.py`, ADR-0017) compõe leituras de `core/` e dos domínios `paper`, `protocol` e `write` em dataclasses congeladas. `next` segue ordem fixa e pega a frase do frontmatter do modo (Princípio I). CLI fina em `cli.py`.

**Tech Stack:** Python 3.12, Typer, PyYAML, Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-superficie-de-skills-design.md` (D5 + Emenda de implementação).

## Global Constraints

- Só leitura: nenhum arquivo escrito, nenhum estado novo gravado (lógica da ADR-0029).
- Zotero/autoexport NÃO é sinal de `status` (só observável por RPC; é do `doctor`).
- `core/` não importa `domains/`; `status.py` fica no topo do pacote.
- `cli.py` só parsing + chamada + `Console.result`; subcomando envolto em `cli_run`.
- `mypy --strict`, dataclasses `frozen=True`, mensagens pt-BR com comando de correção.
- JSON carrega `schema_version: "ProjectStatus/v1"`.
- Ordem de `next`: bibliografia vazia → papers com PDF sem extract → PICOT não fechada → escopo sem draft → eventos ambíguos de revisão.
- Eventos que pedem `review reconcile`: `unanchored-mark`, `ambiguous-anchor`, `non-identity-span` (constantes de `domains/write/review.py`). Marcas em `review.md` são informativas (aguardam `prumo write review apply`, humano).
- Release: PATCH (ADR-0015); este plano não corta release.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/prumo_assist/status.py` (criar) | sinais, `next`, `status_to_dict`, `render_status` |
| `src/prumo_assist/cli.py` (modificar) | comando `status`; helper `_skill_registry()` reusado por `_legacy_skill_map` |
| `skills/start/SKILL.md` (modificar) | roteamento usa `prumo status --json` |
| `tests/unit/test_status.py` (criar) | 14 cenários, lógica e CLI |
| `ARCHITECTURE.md`, `ROADMAP.md`, `CHANGELOG.md` (modificar) | comando novo |

---

### Task 1: Sinais e próximo passo (`status.py`)

**Files:**
- Create: `src/prumo_assist/status.py`
- Test: `tests/unit/test_status.py`

**Interfaces:**
- Consumes: `pj_layout.find_pj_root/iter_scopes/bib_path/pdfs_dir/writing_dir/STUDIES_RELPATH`, `core.bib.parse_bib`, `core.note_paths.iter_note_meta_files/citekey_from_meta_path/extract_path`, `core.criticmarkup.parse`, `core.skills.SkillRef/SkillRegistry`, `domains.paper.callout.hash_template`, `domains.paper.connect.bib_is_placeholder`, `domains.paper.sync.read_nota_yaml`, `domains.protocol.picot_io.read_picot`, `domains.write.review.EVENT_KIND_*`, `domains.write.schemas.v1.ReviewEventsFile`.
- Produces:
  - dataclasses `LibraryStatus(entries, placeholder, synced_at)`, `ExtractStatus(papers, pending, without_pdf, stale)`, `PicotStatus(closed, error)`, `ReviewSummary(review, reconcile_events, pending_marks)`, `ScopeStatus(slug, drafts, reviews)`, `NextStep(skill, mode, say, why, scope)` com `invocation`, `ProjectStatus(project, library, extracts, picot, scopes, next)`.
  - `project_status(start: Path, *, scope: str | None = None, registry: SkillRegistry | None = None) -> ProjectStatus`
  - `status_to_dict(status: ProjectStatus) -> dict[str, Any]`
  - `render_status(status: ProjectStatus) -> str`

- [ ] **Step 1: Testes que falham** — `tests/unit/test_status.py` com os cenários: projeto recém-criado pede `paper library` com a frase do frontmatter; bib com paper sem extract pede `paper extract` e separa `without_pdf`; extract com hash de template antigo conta `stale`; sem PICOT pede `protocol picot`; PICOT inválida reporta `error`; PICOT fechada sem draft pede `write manuscript` com `scope`; draft com evento ambíguo pede `review reconcile` e conta marcas; eventos `applied`/`citation-drop` não pedem nada (`next is None`); multi-escopo lista todos e `--scope` filtra; escopo inexistente falha no CLI citando `prumo add study`; JSON com `schema_version` e `next.invocation`; subdiretório do projeto acha a raiz; texto mostra a frase.
- [ ] **Step 2:** `uv run pytest tests/unit/test_status.py -q` → FAIL (`ModuleNotFoundError: prumo_assist.status`).
- [ ] **Step 3: Implementar** `status.py` (funções `_library`, `_extracts`, `_picot`, `_drafts`, `_reviews`, `_scopes`, `_step`, `_next`, `project_status`, `status_to_dict`, `render_status`). `_extracts`: sem `_extract.md` e com PDF → `pending`; sem PDF → `without_pdf`; com extract e `extracted_template_hash` ≠ `hash_template(.claude/paper_extraction.md)` → `stale`. `_picot`: `FileNotFoundError` → aberta; `ValueError` (inclui `ValidationError` e `TOMLDecodeError`) → aberta com `error` = 1ª linha. `_drafts`: `writing/*.md` exceto `protocol.md` e nomes com `.`/`_`. `_reviews`: `reviews/studies__<slug>__*/` com `events.yaml` (contagem de `RECONCILE_KINDS`; sidecar ilegível conta 0) e `review.md` (`criticmarkup.parse`). `_scopes`: sem `--scope`, todos; com slug inexistente, `PjRootNotFoundError` citando `prumo add study <slug>`. `_step`: `say` = 1ª frase do modo no registry; sem registry, a própria invocação.
- [ ] **Step 4:** `uv run pytest tests/unit/test_status.py -q` → PASS; `uv run mypy src/prumo_assist/status.py` limpo.
- [ ] **Step 5: Commit** `feat: prumo status — onde o estudo está e a próxima frase`.

### Task 2: Comando `prumo status`

**Files:** Modify `src/prumo_assist/cli.py`.

- [ ] **Step 1:** Os testes de CLI da Task 1 falham enquanto o comando não existe.
- [ ] **Step 2: Implementar**

```python
def _skill_registry() -> SkillRegistry | None:
    """Registry do bundle de skills, ou ``None`` sem bundle."""
    skills_dir = _resolve_skills_dir()
    if skills_dir is None:
        return None
    registry, _ = load_skill_registry(skills_dir, strict=False)
    return registry


@app.command("status")
def status_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_* (default: cwd).")] = Path("."),
    scope: Annotated[
        str | None, typer.Option("--scope", help="Slug do escopo em docs/studies/ (default: todos).")
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json", help="Saída JSON.")] = False,
) -> None:
    """Onde o estudo está e qual a próxima frase dizer ao agente. Só lê o disco."""
    with cli_run(json_mode=json_mode) as console:
        result = project_status(path.resolve(), scope=scope, registry=_skill_registry())
        console.result(render_status(result), status_to_dict(result))
```

`_legacy_skill_map` passa a usar `_skill_registry()`.
- [ ] **Step 3:** `uv run pytest tests/unit/test_status.py tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py -q` → PASS.
- [ ] **Step 4: Commit** (junto com a Task 1 se feitas em sequência).

### Task 3: `start`, docs e CHANGELOG

- [ ] `skills/start/SKILL.md`: no cenário "Tudo OK", rodar `prumo status --json`; com `next`, oferecer em uma linha `next.say` com `next.invocation` e `next.why`; sem `next`, perguntar o que a pessoa quer.
- [ ] `ARCHITECTURE.md`: raiz do CLI inclui `status`; `status.py` no topo do pacote ao lado de `mcp_server.py`.
- [ ] `ROADMAP.md`: F3 implementada na linha "Superfície de skills".
- [ ] `CHANGELOG.md` `[Não publicado]` → Adicionado: `prumo status`.
- [ ] `uv run python .github/scripts/gen_indexes.py`; commit `docs: start usa prumo status; ARCHITECTURE/ROADMAP/CHANGELOG`.

### Task 4: Verificação

- [ ] `uv run pytest -q`; `uv run ruff check . && uv run ruff format --check .`; `uv run mypy`; `gen_indexes --check`.
- [ ] Smoke: `prumo init <scratch>/pj_status` → `prumo status <pj> --json` com `next.skill == "paper"`.
- [ ] Arquivar este plano com frontmatter de fechamento.
