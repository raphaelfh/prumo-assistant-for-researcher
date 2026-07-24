# Ponte docx↔CriticMarkup — Fase 3: prumo-MCP + reconciliador — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Servidor MCP local (stdio) do prumo expondo o ciclo de revisão para agentes (Claude Code/Desktop), e o reconciliador como skill que transforma eventos ambíguos em **propostas** — marcas CriticMarkup pendentes no worklist `review.md` com âncora `{>>prumo-autor: agente<<}` — que o humano aceita/rejeita pelo `apply` existente. Modo degradado sem agente: checklist manual via CLI.

**Architecture:** "Código garante, agente propõe, humano decide" vira mecânica literal: a proposta do agente NÃO é um caminho novo de escrita — é uma marca normal do worklist da T9, decidida pelo mesmo `apply_review` com as mesmas guardas (conservação pós-apply inclusive). O servidor MCP é fachada fina sobre o domínio (`mcp_server.py` no topo do pacote — importa domains livremente; `core/` intocado); a única ferramenta de ESCRITA (`propose_prose_edit`) insere a marca por âncora-de-excerto ÚNICA e recusa qualquer proposta que toque citação (I1/I3b: agente nunca cunha nem move citação). Transporte stdio não é testado em unidade — as funções-ferramenta são testadas diretamente; o registro de tools é assertado por nome.

**Tech Stack:** `mcp==1.28.1` (SDK oficial, FastMCP; dependência nova — ADR-0017), Python 3.11, Typer (comando raiz `prumo mcp serve`), skill `review-reconcile` (SKILL.md frontmatter `prumo:`).

**Spec:** docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md (Fase 3 da tabela; §Ingest e transplante "Reconciliador"; modo degradado; I1/I3b). Guarda-chuva: Fase 3 do zero-friction (superfície Desktop consome MCP local de plugin — spec 2026-07-22 D0).

## Global Constraints

- Release boundary: PATCH (ADR-0015 — tudo releasável é PATCH pré-1.0); sem release neste plano; CHANGELOG em "Não publicado".
- `mypy --strict`; `from __future__ import annotations`; pt-BR com comando embutido; identificadores em inglês.
- Layering: `mcp_server.py` vive em `src/prumo_assist/` (topo — importa domains); `core/` NUNCA importa domains; fachadas finas (o servidor delega ao domínio; zero lógica de revisão no servidor além de montar argumentos).
- **I1/I3b duros na ferramenta de proposta:** payload (`a`/`b`) contendo padrão de citekey (`CITEKEY_RE` de `core/citations`) ou sintaxe de citação (`[@`, `[[@`) → recusa pt-BR; âncora localizada que INTERSECTA ou TANGENCIA (adjacência imediata) um span `[[@...]]` no worklist → recusa ("citação é átomo — decisão humana").
- Âncora de autor das propostas: `{>>prumo-autor: agente<<}` (o pairing/strip da T9 já a trata como qualquer autor; `--by-author agente` filtra propostas).
- Bateria COMPLETA antes de cada commit: `uv run pytest` (615 baseline), `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`, `uv run python .github/scripts/gen_indexes.py --check` (nas tasks que tocam skills/docs).
- Dependência `mcp` é a PRIMEIRA dependência de servidor do pacote: pin exato `mcp==1.28.1` em pyproject `[project.dependencies]`; se `uv lock`/sync reclamar de resolução com o Python floor do repo, reportar BLOCKED (não afrouxar o pin sem registro).

---

### Task 1: Dependência + servidor MCP read-only (`prumo mcp serve`)

**Files:** Modify `pyproject.toml` (dependencies + `[project.scripts]` fica como está — o comando é do Typer raiz); Create `src/prumo_assist/mcp_server.py`; Modify `src/prumo_assist/cli.py` (comando raiz `mcp serve`, fachada fina); Create `tests/unit/test_mcp_server.py`

**Interfaces (produz — Tasks 2/4 consomem):**
```python
# mcp_server.py
server = FastMCP("prumo-review")            # instância módulo-level

@server.tool()
def review_status(page: str) -> dict: ...    # counts: marcas pendentes (parse do review.md), eventos por kind, comentários, drops pendentes
@server.tool()
def review_events(page: str) -> list[dict]: ...   # events.yaml completo (model_dump)
@server.tool()
def review_worklist(page: str) -> str: ...   # conteúdo do review.md

def run_stdio() -> None: ...                 # server.run() — chamado pelo CLI
```
Resolução de caminhos: cada tool resolve `project_root` via `export.detect_project_root(Path(page))` e slug via `export._slugify` (mesmo padrão do ingest); sidecars ausentes → a tool retorna erro ESTRUTURADO (raise ValueError pt-BR — FastMCP serializa como tool error; NÃO deixar traceback cru: envolver corpo de cada tool em try/except que re-levanta ValueError com mensagem pt-BR + comando, padrão `_read_sidecars`).

Steps (TDD): testes chamam as FUNÇÕES diretamente (fixtures reutilizam helpers de `test_review_ingest.py` — importe os builders ou construa mínimos locais): (1) `review_status` de um ciclo pós-ingest sintético → counts certos; (2) `review_events` lista kinds; (3) `review_worklist` == conteúdo; (4) sem sidecars → ValueError pt-BR; (5) `server` registra exatamente {"review_status","review_events","review_worklist"} (via API do FastMCP de listagem de tools — descubra o accessor no SDK 1.28.1 e asserte por nome). CLI: `prumo mcp serve` chama `run_stdio` (teste: monkeypatch `run_stdio`, invoke, assert chamado — padrão fachada).

Commit: `feat(mcp): servidor prumo-review stdio com tools read-only do ciclo de revisão`

---

### Task 2: Ferramenta de proposta (`propose_prose_edit`) com guardas I1/I3b

**Files:** Modify `src/prumo_assist/mcp_server.py`; Modify `src/prumo_assist/domains/write/review.py` (função de domínio `propose_prose_edit(...)` — a lógica mora no domínio; a tool MCP é fachada); Modify `tests/unit/write/test_review_apply.py` (append — domínio) e `tests/unit/test_mcp_server.py` (append — fachada)

**Interfaces:**
```python
# review.py (domínio)
@dataclass(frozen=True)
class ProposalResult:
    review_md: Path
    inserted_mark_index: int      # índice da marca nova na ordem de parse do worklist

def propose_prose_edit(
    page: Path, *, anchor_excerpt: str, position: Literal["before", "after", "replace"],
    kind: Literal["ins", "del", "sub"], a: str = "", b: str = "",
    author: str = "agente", project_root: Path | None = None,
) -> ProposalResult: ...
```
(`comment` removido dos kinds aceitos — não-pareável pelo apply; achado do review da T2.)
Regras (todas hard-fail ValueError pt-BR): anchor_excerpt deve ocorrer EXATAMENTE 1 vez no review.md (0 → "âncora não encontrada"; >1 → "âncora ambígua — amplie o excerto"); guardas I1/I3b das Global Constraints (payload com citekey/sintaxe de citação; âncora intersectando/tangenciando `[[@...]]` — use regex de wikilink-citação do source-flavor: `\[\[@[^\]]+\]\]`, spans no review.md; adjacência imediata = distância 0); `position="replace"` exige `kind` del/sub e `a == anchor_excerpt` (o alvo é o excerto); a marca é inserida com `criticmarkup.emit(kind, a, b) + "{>>prumo-autor: " + author + "<<}"` (before: antes do excerto; after: depois; replace: no lugar); worklist reescrito; `inserted_mark_index` calculado por re-parse.

Testes (domínio): ins after com âncora única → worklist contém marca+âncora e `apply --by-author agente --accept` aplica (E2E curto reusando fluxo da T9); âncora 0/>1 → erros; payload com `[@smith2020]` → recusa I3b; âncora colada em `[[@key]]` → recusa I1; replace com a != excerto → erro. Fachada MCP: tool delega e traduz Path/tipos.

Commit: `feat(write): propose_prose_edit — proposta do agente vira marca pendente no worklist (I1/I3b)`

---

### Task 3: Modo degradado — `prumo write review events --checklist`

**Files:** Modify `src/prumo_assist/domains/write/cli.py` (comando `events` no `review_app`); Modify `tests/unit/write/test_cli.py` (append)

Comando `events --page <page.md> [--checklist] [--json]`: sem flags → lista eventos (kind, detail resumido); `--checklist` → formato de checklist manual pt-BR numerado com a AÇÃO por kind (citation-drop → "confirme com --confirm-citation-drops occ"; unanchored/ambiguous/non-identity → "edite review.md inserindo a mudança manualmente no ponto certo, ou rode a skill /prumo-assist:review-reconcile"; citation-touched → "decisão humana: rejeite no Word ou edite a fonte"); `--json` emite a lista estruturada. Fachada fina (`_REVIEW_CATCHES`). Testes: 3 (lista, checklist com ações por kind, sem sidecars → erro limpo).

Commit: `feat(write): review events --checklist — modo degradado sem agente`

---

### Task 4: Skill `review-reconcile`

**Files:** Create `skills/review-reconcile/SKILL.md`; regenerar índices (`gen_indexes` — README/start/catálogos)

Frontmatter (padrão do registry — copie a estrutura de uma skill existente, ex. `skills/wiki-query/SKILL.md`): `name: review-reconcile`; `description:` "Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana)."; `prumo:` determinism: hybrid; agent_compat: [claude-code].

Corpo (prompt): fluxo — (1) rode `prumo write review events --page <page> --json` (ou tools MCP `review_events`/`review_worklist` se disponíveis); (2) para CADA evento unanchored-mark/ambiguous-anchor/non-identity-span: leia o excerpt/autor/detail, localize no worklist o ponto certo LENDO o contexto, e chame `propose_prose_edit` (via MCP; fallback: instrua o usuário — a função ainda não tem comando CLI dedicado, e criar um está FORA deste escopo) com âncora única e o menor payload fiel à intenção do coautor; (3) eventos citation-* : NUNCA propor — listar para o humano com a ação (checklist do comando `events --checklist`); (4) fechar com resumo: N propostas (todas com autor `agente`, filtráveis por `--by-author agente`), M itens humanos, e o comando de apply sugerido. Iron rule no corpo: "Se a âncora for ambígua ou o evento tocar citação, PARE e escale — nunca chute."

Verificação: `uv run pytest` (registry/lint de skills se coberto por testes existentes — conferir `tests/unit/core/test_skills.py` carrega o diretório real? Se sim, o novo SKILL.md precisa parsear limpo), `gen_indexes` roda e `--check` fica em dia (README + start atualizados pelos blocos gerados).

Commit: `feat(skills): review-reconcile — reconciliador de eventos ambíguos (propõe, nunca decide)`

---

### Task 5: Distribuição + ADR-0017 + CHANGELOG + bateria final

**Files:** Modify `.mcp.json` (server `prumo-review`); Create `docs/adr/adr-0017-prumo-mcp-reconciliador.md`; Modify `CHANGELOG.md`; índices

1. `.mcp.json` ganha `"prumo-review": {"command": "prumo", "args": ["mcp", "serve"]}` — ARMADILHA DOCUMENTADA: o arquivo é config deste projeto E distribuída aos consumidores do plugin; consumidor sem o CLI instalado verá o server falhar ao subir (mesmo modo degradado do qmd — aceitável e documentado no ADR).
2. ADR-0017 (MADR minimal, formato do 0014/0016; prosa corrida): título "prumo-MCP local e reconciliador que propõe marcas"; contexto (Fase 3 do spec da ponte; superfície Desktop/Cowork consome MCP local de plugin — spec zero-friction D0); decisão (dependência `mcp==1.28.1`; servidor stdio fachada-fina com 3 tools read-only + 1 de proposta; proposta = marca pendente no worklist com autoria `agente`, decidida pelo apply humano — nenhuma escrita nova; guardas I1/I3b na ferramenta; modo degradado por checklist CLI); consequências (agente útil sem ser confiável-por-obrigação; custo: dependência de servidor no pacote e superfície MCP a versionar).
3. CHANGELOG "Não publicado" ### Adicionado: 1 bullet denso (servidor + tool de proposta + skill + modo degradado, refs spec/ADR-0017).
4. Bateria completa + `gen_indexes --check`.

Commit: `docs(adr): ADR-0017 prumo-MCP + reconciliador; distribuição via .mcp.json; changelog da Fase 3`

---

### Task 6 (controller): review final da fase + arquivar

Review final (modelo mais capaz) sobre o range da fase com triage dos minors herdados da F2 aplicáveis; fixes; arquivar o plano (frontmatter implemented/verified + archive/ + gen_indexes); push.
