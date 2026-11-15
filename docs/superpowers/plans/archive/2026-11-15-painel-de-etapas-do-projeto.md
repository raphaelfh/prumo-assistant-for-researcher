---
status: implemented
verified: 2026-11-15
release: "PATCH (ADR-0015) — pendente do corte"
spec: "[[2026-11-14-painel-de-etapas-do-projeto-design]]"
---

> **Fechamento (2026-11-15).** Tasks 2–6 entregues em commits consecutivos no branch `feat/painel-etapas-projeto`, empilhado sobre `feat/pesquisa-em-saude` (ainda fora de `main`; o módulo `protocol` e o `question.toml` vêm dele). `core/scaffold` ganha `module_writing_files` e `is_pristine`, e os esqueletos de módulo saem de `drafts`; `status.py` deriva sete etapas e o `next` passa a ser o da etapa atual, com a pergunta antes da bibliografia; `core/skills.bundled_skill_registry` serve o CLI e a tool MCP `project_status`; `hooks/mods/project.tsx` (`/projeto`) substitui `review.tsx` (`/revisao`); ADR-0043, ARCHITECTURE e CHANGELOG. Desvio da spec: a etapa Protocolo acompanha só o SAP e o projeto CEP, porque o bloco da pergunta já altera o `protocol.md` (spec corrigida no mesmo commit). Verificação: suíte pytest verde, ruff, `ruff format --check`, mypy, `gen_indexes --check`, `validate_manifests` e `sync_manifest_version --check` limpos; `claude plugin validate .` (os mesmos 2 avisos de antes) e `claude plugin test .` (6 de 6). Num `pj_exemplo` sintético com `--with protocol`, `prumo status --json` e a tool `project_status` devolvem as mesmas etapas e o mesmo `next`. Pendentes: ver o painel no Desktop com `claude --plugin-dir .` e comparar a etapa Revisão num projeto piloto com revisão ingerida.

# Painel "Projeto" — etapas do estudo num mod fino sobre o `prumo status` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o `prumo status` passa a calcular as etapas do estudo (`stages`); o servidor MCP expõe esse cálculo em `project_status`; o mod troca o painel "Revisão do manuscrito" pelo painel "Projeto" (`/projeto`), que só desenha o JSON. De passagem, os esqueletos do módulo `protocol` deixam de contar como draft e a pergunta do estudo passa a ser a primeira etapa.

**Architecture:** toda a lógica fica em `src/par/status.py` (topo do pacote, compõe domínios; `core/` continua sem importar `domains/`). Um helper novo em `core/scaffold.py` diz se um arquivo do scaffold ainda é esqueleto. `mcp_server.py` ganha uma tool só leitura. O mod (`hooks/mods/project.tsx`) faz uma chamada MCP por atualização e não interpreta nada.

**Tech Stack:** Python 3.11/3.12, Typer, FastMCP (`mcp_server.py`), pytest, ruff, mypy `--strict`; TypeScript/TSX do kit de mods (`claude plugin test .`, `claude plugin validate .`).

**Spec:** `docs/superpowers/specs/2026-11-14-painel-de-etapas-do-projeto-design.md` (§Decisão 1–5, §Testes, §Aceitação).

## Global Constraints

- **Layering:** `core/` nunca importa `domains/`. `status.py` e `mcp_server.py` vivem no topo do pacote e podem importar domínios.
- **Schema forward-only (Princípio IV):** `ProjectStatus/v1` só ganha a chave `stages`. Nenhuma chave existente some ou muda de forma (`library`, `extracts`, `question`, `picot`, `scopes`, `next`).
- **Uma regra para "agora":** `next` é sempre o `next` da etapa `current`. Nenhum outro caminho calcula o próximo passo.
- **Tipagem:** `from __future__ import annotations` em todo módulo; `@dataclass(frozen=True)`; `mypy --strict` vale para `tests/` também (anote `-> None`, `tmp_path: Path`).
- **Mensagens:** pt-BR, com o comando de correção dentro. Identificadores em inglês.
- **Fixtures sintéticas:** projetos `pj_demo`/`pj_exemplo` criados em `tmp_path` por `prumo init`. Nada de projeto real (`.claude/rules/privacy.md`).
- **Blocos gerados** (`docs/_index.md`, `docs/adr/_index.md`, `skills/start/SKILL.md`, README) só via `uv run python .github/scripts/gen_indexes.py`.
- **Sem bump de versão.** Não toque em `src/par/_version.py`, `plugin.json`, `marketplace.json`. O corte é PATCH (ADR-0015), feito depois pelos 8 passos do `RELEASING.md`.
- **`uv.lock` e `shims/prumo` não mudam** (mudar re-baixa o ambiente de cada pesquisadora).
- **Commits:** estilo do repo (`feat(status): …`, `feat(mods)!: …`), pt-BR, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Cada task fecha com a suíte verde ("verde" = nenhuma falha nova em relação à linha de base da Task 1).
- **Branch e PR:** um PR para as Tasks 2–7, branch `feat/painel-etapas-projeto` a partir de `main`.

## File Structure

| Arquivo | Ação | Responsabilidade | Task |
|---|---|---|---|
| `src/par/core/scaffold.py` | Modificar | `module_writing_files()` e `is_pristine()` | 2 |
| `tests/unit/core/test_scaffold.py` | Modificar | testes dos dois helpers | 2 |
| `src/par/status.py` | Modificar | `_NOT_DRAFTS` derivado (T2); `Stage`, `_stages()`, `_next` derivado, ordem nova, `stages` no JSON, `render_status` (T3) | 2, 3 |
| `tests/unit/test_status.py` | Modificar | esqueleto não é draft (T2); etapas, ordem, JSON (T3) | 2, 3 |
| `src/par/mcp_server.py` | Modificar | tool `project_status`; docstring | 4 |
| `tests/unit/test_mcp_server.py` | Modificar | 11 tools; `project_status` dentro e fora de `pj_*` | 4 |
| `hooks/mods/project.tsx` | Criar | painel "Projeto", `/projeto`, `$.ui.status` | 5 |
| `hooks/mods/review.tsx` | Apagar | — | 5 |
| `hooks/mods/register.ts` | Modificar | `registerProject` no lugar de `registerReview` | 5 |
| `types/index.d.ts` | Modificar | `ProjectSnapshot` no lugar de `Review*` | 5 |
| `tests/mods/mods.test.tsx` | Modificar | testes do painel novo; os da pergunta ficam | 5 |
| `docs/adr/adr-0043-painel-de-etapas.md` | Criar | substitui o item 3 da ADR-0039 | 6 |
| `ARCHITECTURE.md`, `CHANGELOG.md`, `skills/start/SKILL.md` (fonte, se o texto citar a ordem) | Modificar | docs | 6 |
| `docs/_index.md`, `docs/adr/_index.md` | Regerar | — | 6, 7 |
| este plano | Arquivar | `plans/archive/` com frontmatter de fechamento | 7 |

## Dependências entre tasks

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7. A Task 5 depende da 4 (o mod chama a tool) e a 4 da 3 (a tool devolve `stages`).

---

### Task 1: Pré-condições (sem commit)

- [ ] **Step 1:** `git switch main && git pull && git switch -c feat/painel-etapas-projeto`.
- [ ] **Step 2:** `claude --version` ≥ 2.1.286 (mods; ADR-0039). Se menor, pare e reporte.
- [ ] **Step 3:** linha de base: `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`, `claude plugin validate .`, `claude plugin test .`. Anote falhas e skips existentes.
- [ ] **Step 4:** confira as suposições da spec:
  - `templates/modules/protocol/docs/studies/__scope__/writing/` tem `protocol.md`, `projeto-cep.md` e `statistical_analysis_plan_skeleton.md`;
  - `prumo init <tmp>/pj_demo --with protocol --json` copia os três para `docs/studies/<slug>/writing/` e `project_status(...).scopes[0].drafts` hoje inclui `projeto-cep.md` (o defeito);
  - `read_question(pj)` devolve o spec com `type` e `framework` (anote os nomes exatos para o `summary` da Task 3).

### Task 2: Esqueletos de módulo não contam como draft

Arquivos: `src/par/core/scaffold.py`, `src/par/status.py`, `tests/unit/core/test_scaffold.py`, `tests/unit/test_status.py`.

- [ ] **Step 1 (teste vermelho):** em `test_status.py`:

```python
def test_esqueletos_do_protocol_nao_contam_como_draft(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    res = runner.invoke(app, ["init", str(pj), "--with", "protocol", "--json"])
    assert res.exit_code == 0, res.output
    st = project_status(pj)
    assert all(scope.drafts == () for scope in st.scopes)
```

- [ ] **Step 2 (teste vermelho):** em `test_scaffold.py`:
  - `module_writing_files()` contém `"protocol.md"`, `"projeto-cep.md"` e `"statistical_analysis_plan_skeleton.md"`;
  - num pj criado com `--with protocol`, `is_pristine(pj, rel)` é `True` para `docs/studies/<slug>/writing/projeto-cep.md` recém-copiado e `False` depois de acrescentar uma linha;
  - `is_pristine` de um arquivo que não vem de template nenhum é `False`.
- [ ] **Step 3 (implementação):** em `core/scaffold.py`, junto de `discover_modules()`:

```python
def module_writing_files() -> frozenset[str]:
    """Nomes de arquivo que os módulos copiam para ``writing/`` de cada escopo.

    Esqueleto de módulo não é draft de manuscrito: ``prumo status`` os exclui.
    """
    names: set[str] = set()
    for module in discover_modules():
        writing = module.path / "docs" / "studies" / SCOPE_MARKER / "writing"
        if writing.is_dir():
            names.update(p.name for p in writing.iterdir() if p.is_file())
    return frozenset(names)


def is_pristine(pj_root: Path, rel: Path) -> bool:
    """``rel`` (relativo ao pj) ainda é o esqueleto do scaffold, sem edição.

    Compara com o template de algum módulo depois dos mesmos placeholders de nome
    que o ``init`` aplica (``pj_root.name``). Pasta renomeada depois do ``init``
    conta como editado: o erro é para o lado de "feito", nunca de esconder etapa.
    """
```

  Confira o atributo de caminho de `ModuleInfo` (`path` ou equivalente). Para achar o template: troque o segmento do escopo de `rel` por `SCOPE_MARKER` e procure em cada módulo. O texto esperado aplica `_NAME_PLACEHOLDERS` → `pj_root.name` (mesma substituição de `_apply_placeholders`, sem gravar). Arquivo ilegível ou template ausente → `False`.
- [ ] **Step 4:** em `status.py`, `_NOT_DRAFTS = frozenset({"protocol.md"})` vira `module_writing_files()` (calculado uma vez por chamada de `project_status`, passado a `_drafts`). Um esqueleto **editado** continua fora de `drafts`: é peça do protocolo, não manuscrito.
- [ ] **Step 5:** suíte verde; commit `fix(status): esqueletos de módulo em writing/ não contam como draft`.

### Task 3: Etapas em `status.py`; pergunta antes da bibliografia

Arquivos: `src/par/status.py`, `tests/unit/test_status.py`.

- [ ] **Step 1 (testes vermelhos)** em `test_status.py`. Um helper `_states(st) -> dict[str, str]` (`{stage.id: stage.state}`, com `id` sufixado por `:<scope>` nas etapas de escopo). Casos:
  1. recém-criado: `question` é `current`; `library`, `reading`, `writing:<slug>` são `todo`; não há `protocol`, `review` nem `delivery`. `st.next` é `("protocol", "question")`;
  2. pergunta fechada, `.bib` placeholder: `question` `done`, `library` `current`;
  3. pronto para escrever com um extract desatualizado: `reading` `attention` (com `next` = `paper extract`), `writing:<slug>` `current`;
  4. `--with protocol` recém-criado e pronto para escrever: `protocol` existe e é `current` (os três arquivos são esqueleto); `summary` cita os três;
  5. o mesmo, com os três editados: `protocol` `done`;
  6. draft e evento ambíguo: `review:<slug>` `current`, `next` = `review reconcile`;
  7. draft sem `build/exports/<slug>.docx`: `delivery:<slug>` `current`, `next` = `write export`; com o docx: `done` e `next is None`;
  8. `status_to_dict(st)["next"] == asdict(stage current).next` (mais `invocation`), e o JSON mantém todas as chaves antigas;
  9. `render_status` tem uma linha por etapa com o marcador (`✓ ● ! ○`) antes da frase do próximo passo.

  Ajuste os testes que fixam a ordem antiga: `test_projeto_recem_criado_pede_a_bibliografia` vira `..._pede_a_pergunta` (e um caso novo cobre a bibliografia com a pergunta fechada); `test_sem_pergunta_pede_question` continua valendo.
- [ ] **Step 2 (implementação):** acrescente a `status.py`:

```python
StageState = Literal["done", "current", "attention", "todo"]


@dataclass(frozen=True)
class Stage:
    """Uma etapa do estudo, derivada do disco (ADR-0029)."""

    id: str
    title: str
    state: StageState
    summary: str
    next: NextStep | None = None
    scope: str | None = None
```

  `ProjectStatus` ganha `stages: tuple[Stage, ...]`. Estrutura:
  - `_raw_stages(...) -> list[tuple[str, str, bool, str, NextStep, str | None, bool]]` ou, mais legível, uma dataclass interna `_Check(id, title, done, summary, step, scope, attention=False)`. Uma função por etapa, todas puras sobre os sinais já lidos (`library`, `extracts`, `picot`, `scopes`) mais o `pj_root`:
    - `question`: `done` = `picot.closed`; `summary` = tipo e framework (ou o erro);
    - `library`: `done` = não placeholder e `entries > 0`; `summary` = `N entradas · sync AAAA-MM-DD`;
    - `reading`: `done` = `pending == 0`; `attention` = `stale > 0`; `summary` = `X sem extract · Y sem PDF · Z desatualizados`;
    - `protocol` (só se algum escopo tem `writing/protocol.md`): `done` = nenhum dos arquivos de `module_writing_files()` presentes no escopo é `is_pristine`; `summary` = os que ainda são esqueleto; `step` = `protocol sap` se o SAP é esqueleto, senão `protocol cep`. Uma etapa por escopo que tenha o módulo;
    - por escopo: `writing:<slug>` (`done` = tem draft), `review:<slug>` (só com reviews; `done` = zero eventos de reconcile), `delivery:<slug>` (só com draft; `done` = existe `build/exports/<slugify(draft)>.docx` para algum draft, usando `par.domains.write.export.slugify` e `EXT_BY_FORMAT["docx"]`, sem recomputar a regra).
  - `_stages(checks)`: a primeira não `done` vira `current` (com `next`); antes dela, `done` ou `attention` (com `next` próprio); depois dela, `todo` sem `next`. Se todas `done`, nenhuma `current`.
  - `_next` passa a ser `next((s.next for s in stages if s.state == "current"), None)`. Apague a cadeia antiga. A ordem é a da spec: `question`, `library`, `reading`, `protocol:*`, e por escopo `writing`, `review`, `delivery`.
  - `status_to_dict`: `"stages": [asdict(s) | {"next": ...com invocation}]`; `next` continua no topo.
  - `render_status`: antes de "Próximo passo", uma linha por etapa: `f"{MARK[s.state]} {s.title}{' · ' + s.scope if s.scope else ''}  {s.summary}"`. Mantenha as linhas antigas (bibliografia, papers, escopos) só se algum teste existente depender delas; se não, as etapas as substituem.
- [ ] **Step 3:** `skills/start/SKILL.md` (fonte fora do bloco gerado): se o texto da trilha disser que o primeiro passo é a bibliografia, ajuste para a pergunta. Rode `gen_indexes.py`.
- [ ] **Step 4:** suíte verde; `uv run mypy`; commit `feat(status): etapas do estudo em ProjectStatus/v1 (stages); pergunta antes da bibliografia`.

### Task 4: Tool MCP `project_status`

Arquivos: `src/par/mcp_server.py`, `tests/unit/test_mcp_server.py`.

- [ ] **Step 1 (testes vermelhos):**
  - `test_server_registers_exactly_the_review_and_paper_tools`: conjunto ganha `"project_status"`, `len(tools) == 11`;
  - `project_status` num pj recém-criado devolve `schema_version == "ProjectStatus/v1"` e `stages[0]["id"] == "question"`;
  - fora de um `pj_*` levanta `ValueError` com a mensagem pt-BR de `PjRootNotFoundError`;
  - `"project_status" not in MUTATING_TOOLS`.
- [ ] **Step 2 (implementação):**

```python
@server.tool()
def project_status(pj_path: str) -> dict[str, Any]:
    """Onde o estudo está: etapas, sinais do disco e o próximo passo (``ProjectStatus/v1``).

    Só leitura. Mesmo JSON de ``prumo status --json``; é o que o painel "Projeto" desenha."""
    registry, _ = load_skill_registry(resolve_resource("skills"), strict=False)
    return _paper_call(lambda p: status_to_dict(status.project_status(p, registry=registry)),
                       Path(pj_path).resolve())
```

  Se `PjRootNotFoundError` não for `PrumoError` nem `FileNotFoundError`, capture-o explicitamente (o contrato é `ValueError` pt-BR). Prefira mover `_skill_registry()` de `cli.py` para `status.py` (sem underscore, `skill_registry()`) e usá-lo nos dois lugares, em vez de duplicar. Atualize a docstring do módulo (contagem de tools e o domínio `status`).
- [ ] **Step 3:** suíte verde; commit `feat(mcp): tool project_status (só leitura)`.

### Task 5: Mod — painel "Projeto" no lugar do painel de revisão

Arquivos: `hooks/mods/project.tsx` (novo), `hooks/mods/review.tsx` (apagar), `hooks/mods/register.ts`, `types/index.d.ts`, `tests/mods/mods.test.tsx`.

- [ ] **Step 1 (testes vermelhos)** em `mods.test.tsx`. Mantenha os testes da pergunta do estudo; troque os do painel. Constantes `PANE` (`requestId: 'par-projeto'`, `title: 'Projeto'`) e `PROJETO` (`command: 'projeto'`). Um `STATUS` sintético (JSON `ProjectStatus/v1` com quatro etapas: `question` done, `library` done, `reading` current com `next.say = "extraia os principais pontos do paper"`, `writing:demo` todo). Casos:
  1. em `terminal` e `desktop`: uma `Text` por etapa com o título; o botão `key="next-reading"` existe e, ao pressionar, `prompt.fill` recebe `next.say`; não há botão em `writing:demo`;
  2. `$.ui.status` recebe `"Etapa 3/4 · Leitura"`;
  3. fora de um `pj_*` (`mcp.call` com `isError: true`): o painel não abre sozinho no `session.start`; `/projeto` abre e mostra a mensagem do erro;
  4. servidor fora do ar: linha com `/par:start` (como o teste atual);
  5. cada atualização faz exatamente uma `mcp.call` (`project_status`).
- [ ] **Step 2 (implementação)** de `project.tsx`, partindo da estrutura de `review.tsx` (mesmos padrões de `atom`, `ui.render`, `command.run`, `turn.complete`):
  - `atom({ plugin: 'par', key: 'project' }, { status: null, updatedAt: 0 }, { shape: 'project-1' })`;
  - `refresh($)`: `connect('prumo')` → `call(server, 'project_status', { pj_path: await $.session.cwd() })` → `JSON.parse` do texto → `update`. Erro de tool vira `error` com o texto; sem conexão, a mensagem atual com `/par:start`;
  - depois de cada `refresh` bem-sucedido: `$.ui.status(\`Etapa ${i + 1}/${n} · ${current.title}\`)`, ou `undefined` sem etapa `current`;
  - `session.start`: registra `/projeto`; faz `refresh`; abre o painel só se não houve erro (projeto PAR);
  - `turn.complete`: `refresh` (uma chamada);
  - render: botão "Atualizar"; uma linha por etapa (`✓ ● ! ○`, título, `scope`, `summary` em `dimColor`); a `current` e as `attention` ganham um `Button key={\`next-${id}\`}` que faz `$.prompt.fill({ text: next.say, mode: 'replace' })`. Nada mais: sem lista de marcas, sem estado expandido.
  - `register.ts`: `registerProject(on)` no lugar de `registerReview(on)`; docstring atualizada.
  - `types/index.d.ts`: `Stage`, `ProjectStatusJson` (só os campos que o painel usa: `stages`, `next`) e `ProjectSnapshot = { status: ProjectStatusJson | null; updatedAt: number; error?: string }`; `PluginState.par` passa a `{ project: Shaped<ProjectSnapshot> }`.
- [ ] **Step 3:** `git rm hooks/mods/review.tsx`; `claude plugin validate .` e `claude plugin test .` verdes; `wc -l hooks/mods/*` menor que na linha de base.
- [ ] **Step 4:** commit `feat(mods)!: painel "Projeto" (/projeto) com as etapas do estudo; sai o painel de revisão (/revisao)`.

### Task 6: ADR, docs e CHANGELOG

- [ ] **Step 1:** `docs/adr/adr-0043-painel-de-etapas.md` (MADR minimal, status `proposto`): contexto (os quatro defeitos da spec), decisão (etapas só no Python, `stages` no `ProjectStatus/v1`, tool `project_status`, painel fino; substitui o item 3 da ADR-0039), consequências (`/revisao` some; ordem pergunta → bibliografia; uma chamada MCP por turno). Não edite a ADR-0039.
- [ ] **Step 2:** `ARCHITECTURE.md`, linha de `hooks/`: "mods/: painel de etapas do projeto e pergunta do estudo no system prompt (ADR-0039, ADR-0043)".
- [ ] **Step 3:** `CHANGELOG.md` em `[Não publicado]`: em "Adicionado", o painel "Projeto" e a tool `project_status`; em "Mudado", `/revisao` virou `/projeto` e o primeiro passo sugerido a projeto novo é fechar a pergunta; em "Corrigido", os esqueletos do `protocol` contando como draft. Cite Princípios I e VIII, ADR-0029, ADR-0039 e ADR-0043.
- [ ] **Step 4:** `gen_indexes.py`; commit `docs: ADR-0043, ARCHITECTURE e CHANGELOG do painel de etapas`.

### Task 7: Verificação e fechamento

- [ ] **Step 1:** `uv run pytest`, ruff (check e format), `uv run mypy`, `gen_indexes.py --check`, `claude plugin validate .`, `claude plugin test .`.
- [ ] **Step 2 (aceitação da spec):**
  - num `pj_exemplo` sintético criado com `--with protocol`, `prumo status` e o painel (Desktop, `claude --plugin-dir .`) mostram a mesma etapa atual;
  - num projeto piloto com revisão ingerida, a etapa `review` mostra as mesmas contagens que `prumo status` mostrava antes (anote os números só no PR, sem identificar o projeto);
  - o painel abre sozinho num `pj_*` e não abre fora dele.
- [ ] **Step 3:** `git diff main --stat` e `git diff main` sem itens de `.claude/rules/privacy.md`.
- [ ] **Step 4:** mova este plano para `docs/superpowers/plans/archive/` com o frontmatter de fechamento (copie o de um plano arquivado: `status`, `verified`, `release`, `spec`) e o parágrafo "Fechamento"; `gen_indexes.py`; commit `docs: arquiva o plano do painel de etapas`.
- [ ] **Step 5:** abrir o PR "Painel Projeto: etapas do estudo sobre o prumo status".
