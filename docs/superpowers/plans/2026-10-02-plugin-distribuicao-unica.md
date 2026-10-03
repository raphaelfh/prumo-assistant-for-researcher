---
status: approved
spec: "[[2026-10-02-plugin-distribuicao-unica-design]]"
release: "0.71.0 MINOR ⚠ (corte único)"
---

# Plugin como distribuição única (Spec A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o PAR passa a chegar à pesquisadora só pelo plugin. O CLI `prumo` vira `${CLAUDE_PLUGIN_ROOT}/shims/prumo`, que roda o `src/` daquela raiz num venv montado pelo `uv` a partir do `uv.lock`. Junto saem as cópias de skills/agents no `pj_*`, o pacote `integrations/`, o `uvx` em runtime, o `--deep`, o `prumo-zettlr-export`, o servidor MCP do qmd e os curingas Bash largos.

**Architecture:** um lançador POSIX (`shims/prumo`, 117 linhas) é o único caminho até o CLI. Três rotas levam a ele: o `.mcp.json` (`/bin/sh … mcp serve`), o hook `SessionStart` (põe `shims/` no PATH do Bash) e a forma `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` do bloco gerado `prumo:runtime`. A identidade é a versão: o `gen_indexes.py` carimba `__version__` no bloco das portas, e o preflight `_PF_CLI` compara com `prumo --version`. O código Python muda pouco: `core/skill_refs.py` ganha a movimentação das cópias para backup, `cli.py` perde a instalação por integration, `review.py` chama o adeu do lock por `sys.executable -I`.

**Tech Stack:** POSIX sh (bash 3.2 `--posix` e dash), uv ≥ 0.5.20, Python 3.12 no venv do lançador (3.11 e 3.12 no CI), Typer, PyYAML, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-02-plugin-distribuicao-unica-design.md` (Spec A, inteira: A1–A15, A17, D1, D3, D4, D5). A Spec B (`2026-10-02-ponte-zotero-minima-design.md`) é referência só onde ela fixa texto que esta spec grava (item 3 da trilha do `/par:start`).

## Global Constraints

- **Pré-condição.** O Plan 1 (Spec B, 0.70.3 PATCH) está em `main` e publicado: `core/deps.in_claude_sandbox()`, `zotero_base()`, o prefixo `mcp__plugin_par_prumo__` no `reconcile.md` e a ADR-0037 já existem. Nenhuma task daqui os recria.
- **Pré-condição dos índices.** O `gen_indexes.py` lê o disco, não o git: o bloco `kb-index` de `docs/_index.md` lista todo `docs/superpowers/plans/*.md` presente no worktree.
  - Antes da Task 1: `git ls-files docs/superpowers/plans/2026-10-02-plugin-distribuicao-unica.md docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0710.md docs/superpowers/plans/archive/2026-10-02-ponte-zotero-minima-0703.md` lista os três planos (o Plan 1 os commitou na Task 1 dele e arquivou o da 0.70.3 na Task 10 dele). Se faltar algum, commite-o num commit à parte, junto com a saída de `uv run python .github/scripts/gen_indexes.py`, antes de começar o PR 1.
  - Antes de qualquer `gen_indexes.py` (com ou sem `--check`): `git status --porcelain --untracked-files=all docs skills` não lista nenhum `??`. Arquivo não rastreado de outra frente sai do worktree (para o scratchpad) e volta depois; senão o `docs/_index.md` local cita um arquivo que o commit não leva, e o `--check` local passa enquanto o do CI falha.
- **Sequência de PRs** (Spec A §Release e migração, "Sequência"): PR 1 → PR 2 → PR 3 (= Plan 2, Spec B parte 0.71.0, plano próprio) → PR 4 → **gate S-canal** → PR 5 → corte da 0.71.0 (feito à parte pelo orquestrador, seguindo `RELEASING.md`). Não há corte parcial: se o S-canal ou o `launcher-smoke` atrasarem, a 0.71.0 espera. O `/plugin install … --marketplace` instala a `main`, então instalações novas já pegam cada PR assim que ele entra (com o número 0.70.3); quem já tem o plugin fica no cache. Faça os PRs 1–5 em sequência curta.
- **Sem bump.** Nenhuma task edita `src/par/_version.py`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` ou `CITATION.cff`. Até o corte, o bloco `prumo:runtime` carimba a versão vigente (0.70.3); o passo 3 emendado do RELEASING (Task 20) o recarimba no corte.
- **CHANGELOG só na Task 23.** Os PRs 1, 2 e 4 não tocam o `CHANGELOG.md`. Quem abre as seções de `## [Não publicado]` é o Plan 2 (PR 3, Task 8 dele): só `### Alterado` e `### Removido`, com os bullets da Spec B. A Task 23 põe os bullets da Spec A dentro dessas duas, depois dos da Spec B, cria `### Adicionado`, `### Corrigido` e `### Documentação` (nessa ordem, depois de `### Removido`) e fecha com o bloco de migração. **A lista "Migração de quem já usa" (Spec A, itens 1–7, com o Zotero da Spec B no item 7) é deste plano:** o Plan 2 não a grava, e as notas da release saem do CHANGELOG (RELEASING, passo 7, `awk` sobre `## [X.Y.Z]`).
- **Teste herdado do Plan 1.** O Plan 1 (Task 5 dele) acrescentou `test_zettlr_entry_forwards_warnings` em `tests/unit/write/test_cli.py`; a Task 10 o apaga junto com o entrypoint `zettlr_export_entry`.
- **Comandos nesta máquina (sandbox):** todo `uv …` deste plano roda com o prefixo `UV_CACHE_DIR="$TMPDIR/uvcache"`. No CI, sem prefixo. `uv lock` e o smoke do lançador precisam de rede (`pypi.org`, `files.pythonhosted.org`, `releases.astral.sh`, `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`).
- **Verificação padrão de cada task** (chamada abaixo de "verificação padrão"):
  ```bash
  uv run pytest -q
  uv run ruff check . && uv run ruff format --check .
  uv run mypy
  uv run python .github/scripts/gen_indexes.py --check
  ```
  Nos PRs 2, 4 e 5 acrescente `uv lock --check`, `uv run --with jsonschema==4.23.0 python .github/scripts/validate_manifests.py` e `python3 .github/scripts/sync_manifest_version.py --check` (o `validate_manifests.py` importa `jsonschema`, que não está no ambiente do repo).
- **Regras do repo** (`.claude/rules/code.md`): `core/` nunca importa `domains/` (`skill_refs.py` recebe nomes por parâmetro); `cli.py` só faz parsing + chamada + saída, sem `print()` (sempre `core/output.Console`); `from __future__ import annotations`; `mypy --strict`; dataclasses `frozen=True`; mensagens pt-BR com o comando de correção embutido; identificadores em inglês; testes espelham o layout; subprocess, `find_spec`, `shutil.which`, uv e Zotero sempre mockados nos seams.
- **Blocos gerados só pelo gerador.** Depois de mexer em qualquer `skills/**/modes/*.md`, `skills/*/SKILL.md` ou `agents/reader.md`, rode `uv run python .github/scripts/gen_indexes.py` e commite as portas, preflights e índices regerados no mesmo commit. Nunca edite o miolo de `prumo:preflight`, `prumo:runtime`, `prumo:skills-catalog`, `prumo:modes-table`, `kb-index` ou `adr-index` à mão. Os marcadores vazios de `prumo:runtime` entram uma vez, à mão, na Task 14.
- **Texto literal.** Mensagens, blocos do lançador, do hook, do `_PF_CLI`, do `/par:start` e do CHANGELOG são copiados da spec, sem reescrever. Onde este plano diz "texto da spec, §X", abra a seção e copie o bloco inteiro. Âncoras são por texto, nunca por número de linha: o Plan 1 e o Plan 2 deslocam linhas.
- **Arquivos protegidos.** `.claude/settings.json` (Tasks 5 e 13) e `templates/pj_base/.claude/settings.json` (Task 16) podem exigir aprovação do usuário para escrita; use a tool Edit/Write e aguarde.
- **Modo de arquivo.** `shims/prumo` e `hooks/session-start.sh` precisam de `100755` no git: `chmod 755 <arq> && git add <arq>` e confira com `git ls-files -s <arq>`.
- **Commits.** Um commit por task (Conventional Commits, assunto em pt-BR), com a suíte verde. Cada PR sai de `main` atualizado, num branch próprio, e só faz merge com o CI verde. O PR 5 só faz merge com "aprovado" explícito do dono no chat (constitution, §Governança).

## Sequência e dependências

| PR | Branch | Tasks | Depende de |
|---|---|---|---|
| 1 · cortes do repo | `feat/plugin-unico-1-cortes` | 1–7 | Plan 1 publicado (0.70.3) |
| 2 · dependências | `feat/plugin-unico-2-deps` | 8–10 | PR 1 em `main` |
| 3 · Spec B parte 0.71.0 | (Plan 2) | — | PR 2 em `main` |
| 4 · lançador | `feat/plugin-unico-4-lancador` | 11–17 | PR 3 em `main` |
| gate S-canal | — (manual, dono) | — | PR 4 em `main` |
| 5 · docs | `docs/plugin-unico-5-docs` | 18–23 | S-canal registrado |

Dentro de cada PR as tasks são sequenciais, na ordem numérica. Dependências fortes: 1 → 3; 2 → 3; 4 → 5 → 6 (mesmos arquivos do gerador e dos modos `wiki`); 8 → 9 (o `core/uvx.py` só sai depois que o `review.py` para de usá-lo); 8 → 10 (`pyproject.toml`/`uv.lock`); 11 → 12 → 13; 14 → 15 (o `start` usa o bloco runtime); 16 → 17 (o smoke checa o `settings.json`); 22 depende do resultado do S-canal.

## File Structure

| Arquivo | PR | Responsabilidade |
|---|---|---|
| `src/par/core/skill_refs.py` (modificar) | 1 | `plugin_copies`, `move_plugin_copies`; sai `legacy_installed_dirs` |
| `src/par/cli.py` (modificar) | 1 | `init` sem integration/cópias; `doctor` com `[skill_obsoleta]` único; `update` move cópias para `.prumo/legacy-copies/`; sai `_entry` |
| `src/par/__init__.py` (modificar) | 1 | sai `IntegrationError` |
| `src/par/integrations/`, `tests/unit/integrations/` (apagar) | 1 | — |
| `.github/scripts/gen_indexes.py` (modificar) | 1, 4 | sai `_PF_DRIFT`; `_PF_QMD` novo; `render_runtime`, 7 alvos `runtime`, `_PF_CLI` novo |
| `skills/**` (modificar; portas regeradas) | 1, 4 | contornos, qmd só CLI, D5, fallback de agents, passos opcionais, `start` reescrito |
| `agents/reader.md` (modificar) | 4 | bloco runtime + forma `sh` |
| `.mcp.json` (modificar) | 1, 4 | sai `qmd`; `prumo` via `/bin/sh shims/prumo` |
| `.claude/settings.json` (modificar) | 1, 4 | sai `enabledMcpjsonServers`; entra `disabledMcpjsonServers: ["prumo"]` |
| `src/par/core/deps.py`, `src/par/domains/wiki/index.py` (modificar) | 1 | textos do qmd como CLI |
| `templates/pj_base/docs/README.md` (modificar) | 1 | operações wiki como pedidos ao Claude |
| `docs/actions-by-context.md` (apagar); `docs/_index.md`, `docs/Research Project Structure.md` (modificar) | 1 | links e `.claude/skills/` |
| `pyproject.toml`, `uv.lock` (modificar) | 2 | adeu no lock, restrição da `cryptography`, sai `prumo-zettlr-export` |
| `src/par/domains/write/review.py` (modificar) | 2 | adeu por `sys.executable -I`, `_check_adeu_available` |
| `src/par/core/uvx.py`, `tests/unit/core/test_uvx.py` (apagar) | 2 | — |
| `src/par/domains/paper/verify.py`, `paper/cli.py`, `src/par/mcp_server.py` (modificar) | 2 | sai `--deep` |
| `src/par/domains/write/zettlr.py`, `write/cli.py` (modificar) | 2 | cópia do Lua no pj, linha no `.gitignore`, `profile_issues`; sai `zettlr_export_entry` |
| `templates/pj_base/.gitignore`, `templates/pj_base/docs/project_guide.md` (modificar) | 2 | perfil do Zettlr fora do git; passos 4/5/7 |
| `docs/positioning.md`, `docs/superpowers/specs/2026-07-22-zettlr-front-design.md` (modificar) | 2 | notas |
| `.github/workflows/ci.yml` (modificar) | 2, 4 | `uv lock --check`; job `launcher-smoke` |
| `shims/prumo` (criar, 100755) | 4 | lançador |
| `hooks/hooks.json`, `hooks/session-start.sh` (criar; `.sh` 100755) | 4 | PATH do Bash da sessão |
| `src/par/core/paths.py` (modificar) | 4 | mensagem de recurso ausente |
| `templates/pj_base/.claude/settings.json` (criar), `templates/pj_base/README.md` (modificar) | 4 | atualização automática (D4); setup pela aba Code |
| `tests/unit/test_launcher.py`, `tests/unit/test_plugin_layout.py`, `tests/unit/wiki/test_index.py`, `tests/unit/core/test_paths.py` (criar) | 1, 4 | testes novos |
| `README.md`, `docs/onboarding-pesquisador.md`, `RELEASING.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CLAUDE.md`, `.claude/rules/release.md` (modificar) | 5 | documentação |
| `docs/adr/adr-0038-plugin-unica-distribuicao.md` (criar), `docs/constitution.md` (modificar) | 5 | ADR-0038; emenda 1.2.3 |
| `CHANGELOG.md` (modificar) | 5 | bullets da Spec A em `[Não publicado]` e a lista única "Para atualizar (uma vez, na 0.71.0)" |

---

## PR 1 — Cortes do repo (Tasks 1–7)

Branch `feat/plugin-unico-1-cortes`, a partir de `main` com o Plan 1 já mergeado.

### Task 1: `plugin_copies` e `move_plugin_copies` (A11, núcleo)

**Files:**
- Modify: `src/par/core/skill_refs.py`
- Test: `tests/unit/core/test_skill_refs.py`

**Interfaces:**
- Consumes: nada de `domains/` (nomes chegam por parâmetro).
- Produces:
  - `plugin_copies(pj_root: Path, skill_names: Iterable[str], agent_files: Iterable[str]) -> list[str]` — caminhos POSIX relativos ao pj, sem barra final: primeiro `.claude/skills/<n>` (entradas de `.claude/skills/` que são diretório, inclusive link para diretório, com `n` em `skill_names`), depois `.claude/agents/<f>` (arquivos de `.claude/agents/` com `f` em `agent_files`); cada grupo em ordem alfabética; nada mais.
  - `move_plugin_copies(pj_root: Path, rels: Sequence[str], dest: Path) -> list[str]` — `shutil.move` de cada `rel` para `dest / Path(rel).relative_to(".claude")` (ou seja, `dest/skills/<n>` e `dest/agents/<f>`), criando os pais; depois apaga `.claude/skills` e `.claude/agents` se ficarem vazios; devolve `list(rels)`. Com `rels` vazio, não cria `dest` e devolve `[]`.

- [ ] **Step 1: Testes que falham** em `tests/unit/core/test_skill_refs.py`:
  - `test_plugin_copies_lista_so_nomes_do_par` — pj com `.claude/skills/{paper,wiki-query,minha-skill}/` e `.claude/agents/{reviewer.md,meu-agent.md}`; `skill_names={"paper","wiki-query","wiki"}`, `agent_files={"reviewer.md","reader.md"}` → `[".claude/skills/paper", ".claude/skills/wiki-query", ".claude/agents/reviewer.md"]`.
  - `test_plugin_copies_sem_claude_eh_vazio` — `tmp_path` vazio → `[]`.
  - `test_plugin_copies_ignora_arquivo_solto_em_skills` — `.claude/skills/paper` como arquivo (não diretório) não entra.
  - `test_move_plugin_copies_preserva_estrutura_e_conteudo` — depois do move, `dest/skills/paper/SKILL.md` e `dest/agents/reviewer.md` existem com os mesmos bytes; os originais sumiram; `minha-skill/` e `meu-agent.md` ficam; o retorno é `rels`.
  - `test_move_plugin_copies_apaga_diretorios_vazios` — só cópias do PAR em `.claude/skills` e `.claude/agents` → os dois diretórios somem e `.claude/` fica.
  - `test_move_plugin_copies_sem_rels_nao_cria_destino` — `rels=[]` → `[]` e `dest` não existe.
- [ ] **Step 2:** `uv run pytest tests/unit/core/test_skill_refs.py -q` → FAIL (`ImportError: cannot import name 'plugin_copies'`).
- [ ] **Step 3: Implementar** as duas funções e acrescentá-las ao `__all__`. `legacy_installed_dirs` continua até a Task 3 (o `cli.py` ainda o importa). Docstrings em pt-BR dizendo que nada é apagado e que nomes fora da lista nunca são tocados.
- [ ] **Step 4:** `uv run pytest tests/unit/core/test_skill_refs.py -q` → PASS; `uv run mypy` limpo.
- [ ] **Step 5: Commit** `feat(core): plugin_copies e move_plugin_copies — cópias do PAR no pj vão para backup`.

### Task 2: `init` sem cópias; sai o pacote `integrations/` (A11, A12)

**Files:**
- Modify: `src/par/cli.py`, `src/par/__init__.py`
- Delete: `src/par/integrations/` (pacote inteiro), `tests/unit/integrations/`
- Test: `tests/unit/test_cli_init.py`, `tests/unit/test_pj_base_integration.py`

**Interfaces:**
- Produces: `prumo init` sem `--integration/-i`; payload JSON do `init` sem a chave `integrations`; `WizardAnswers` sem o campo `integrations`; `par.__all__ == ["ConfigError", "ManifestError", "PrumoError", "__version__"]`.

- [ ] **Step 1: Testes que falham** em `tests/unit/test_cli_init.py`:
  - reescrever `test_init_creates_project_structure`: invoca `["init", str(target), "--json"]`; afirma `"integrations" not in payload`, `not (target / ".claude" / "skills").exists()` e `not (target / ".claude" / "agents").exists()`; mantém as asserções de estrutura.
  - `test_init_rejeita_flag_integration` — `["init", str(target), "--integration", "claude_code"]` → `exit_code == 2`.
  - `test_init_proximos_passos_pedem_sessao_nova` — sem `--json`; com espaços normalizados (`" ".join(result.output.split())`; o Rich quebra linha em 80 colunas), a saída contém `Abra uma sessão nova do Claude Code dentro de` e `/par:start`, e não contém `No Claude Code, comece por`.
  - `test_par_nao_exporta_integration_error` — `import par`; `not hasattr(par, "IntegrationError")` e `"IntegrationError" not in par.__all__`.
  - em `test_init_scaffold_is_pandoc_pure` e em `test_projeto_novo_nao_nasce_com_link_morto` (`test_pj_base_integration.py`), apagar o desvio que pulava `.claude/skills` (o diretório não existe mais).
- [ ] **Step 2:** `uv run pytest tests/unit/test_cli_init.py tests/unit/test_pj_base_integration.py -q` → FAIL.
- [ ] **Step 3: Implementar** (spec §Componentes, `src/par/cli.py` → `init`, `doctor`, `IntegrationError`; A12):
  - tirar `IntegrationError` do import de `par` e `from par.integrations import REGISTRY as INTEGRATIONS`;
  - `WizardAnswers`: sai `integrations`; `_wizard`: sai o passo 3 inteiro;
  - `init_command`: sai o parâmetro `integration`, `integration_list`, o bloco que carrega o registry de skills e o loop de install, e a chave `integrations` do payload; docstring "Cria um novo projeto ``pj_*`` a partir do template.";
  - `_render_next_steps`: nos três modos, a linha `cd {rel}` (hoje a 1ª dica, comum aos três) dá lugar, na mesma posição, a `"  Abra uma sessão nova do Claude Code dentro de [cyan]{rel}[/cyan] (no app: aba Code → escolher a pasta; no terminal: [cyan]cd {rel} && claude[/cyan]) e peça [cyan]/par:start[/cyan]"`. Depois dela, por modo:
    - `MODE_NEW`: ficam as linhas do `docs/project_guide.md` e do `prumo add`; sai a linha `"  No Claude Code, comece por: [cyan]/par:start[/cyan]"`;
    - `MODE_MERGE`: fica a linha do `git status`; a linha combinada `"  Ative módulos com [cyan]prumo add[/cyan]; no Claude Code: [cyan]/par:start[/cyan]."` vira `"  Ative módulos com [cyan]prumo add[/cyan]."`;
    - `MODE_FORCE`: a linha do "Conteúdo anterior foi substituído … `git status`" fica como está;
  - `doctor_command`: sai o loop `for adapter_cls in INTEGRATIONS.values()` (ele exigia `.claude/skills/`, que deixa de existir); 1ª linha da docstring: "Health-check do projeto: estrutura, cópias antigas do PAR e dependências externas.";
  - sai `_entry`; o bloco final vira `if __name__ == "__main__":\n    app()`;
  - `src/par/__init__.py`: sai a classe `IntegrationError`, a entrada no `__all__` e a menção na docstring de `PrumoError` (fica "(ConfigError, ManifestError)");
  - `git rm -r src/par/integrations tests/unit/integrations`.
- [ ] **Step 4:** `uv run pytest tests/unit/test_cli_init.py tests/unit/test_cli_doctor.py tests/unit/test_cli_update.py tests/unit/test_pj_base_integration.py -q` → PASS; `grep -rn "integrations\|IntegrationError" src tests` só acha as asserções de ausência; verificação padrão.
- [ ] **Step 5: Commit** `feat!: init sem cópias de skills e agents; sai o pacote integrations`.

### Task 3: `doctor` e `update` tratam as cópias antigas (A11)

**Files:**
- Modify: `src/par/cli.py`, `src/par/core/skill_refs.py`, `skills/write/modes/style.md`
- Test: `tests/unit/test_cli_update.py`, `tests/unit/test_cli_doctor.py`, `tests/unit/core/test_skill_refs.py`

**Interfaces:**
- Consumes: `plugin_copies`, `move_plugin_copies` (Task 1); `SkillRegistry.names()`, `SkillRegistry.legacy_map()`; `find_resource("agents")`.
- Produces (em `cli.py`):
  - `_plugin_skill_names() -> set[str]` — `registry.names()` ∪ chaves de `registry.legacy_map()` (vazio sem bundle);
  - `_plugin_agent_files() -> set[str]` — nomes de `agents/*.md` em `find_resource("agents")` (vazio se `None`);
  - `_legacy_stamp() -> str` — seam: `datetime.now().strftime("%Y%m%d-%H%M%S")`;
  - `_outside(changes: list[RefChange], rels: Sequence[str]) -> list[RefChange]` — tira as `RefChange` cujo `path` é um `rel` ou fica dentro dele (`path.startswith(rel + "/")`);
  - payload do `update` com `plugin_copies: list[str]` e `legacy_backup: str | None` (POSIX relativo ao pj, ex. `.prumo/legacy-copies/20261002-101500`).

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/test_cli_update.py` (usa `_init`; o `CliRunner` não tem TTY):
    - `test_update_move_copias_do_par_para_backup` — cria `.claude/skills/paper/SKILL.md`, `.claude/agents/reviewer.md`, `.claude/skills/minha-skill/SKILL.md` e `.claude/agents/meu-agent.md`; `update --json` → há um único diretório em `.prumo/legacy-copies/` com nome `^\d{8}-\d{6}$`, contendo `skills/paper/SKILL.md` (mesmos bytes) e `agents/reviewer.md`; os originais sumiram; `minha-skill/` e `meu-agent.md` ficam; `payload["plugin_copies"] == [".claude/skills/paper", ".claude/agents/reviewer.md"]`; `payload["legacy_backup"] == ".prumo/legacy-copies/" + <nome do diretório>`.
    - `test_update_backup_guarda_a_copia_antes_da_reescrita` — o `SKILL.md` copiado contém `/par:paper-manager`; no backup ele continua com `/par:paper-manager` (o move roda antes de `migrate_skill_names`).
    - `test_update_dry_run_so_lista_copias` — `--dry-run --json`: `plugin_copies` lista as duas, `legacy_backup is None`, nada muda de lugar e `.prumo/legacy-copies` não existe.
    - `test_update_dry_run_nao_conta_invocacao_dentro_das_copias` — a cópia `.claude/skills/paper/SKILL.md` contém `/par:paper-manager` e nenhum outro arquivo tem invocação antiga; `--dry-run --json` → `payload["skill_refs"] == []` (a cópia vai ser movida, não reescrita).
    - `test_update_sem_tty_move_copias_e_preserva_rule_customizada` — reescreve `.claude/rules/safe_outputs.md`; `update` sem `--yes` → cópias movidas e a rule byte-idêntica.
    - `test_update_yes_nao_muda_o_tratamento_das_copias` — com `--yes`, mesmo resultado para as cópias (`minha-skill/` fica).
    - `test_update_resumo_cita_o_backup` — sem `--json`, a saída com espaços normalizados (`" ".join(out.split())`) contém `cópia(s) antiga(s) do PAR saíram de .claude/ para .prumo/legacy-copies/` e `nada foi apagado`.
  - `tests/unit/test_cli_doctor.py`:
    - reescrever `test_doctor_aponta_invocacao_antiga_e_skill_instalada_velha` como `test_doctor_aponta_copias_e_invocacao_numa_issue_so`: com `.claude/skills/paper/SKILL.md` (contendo `/par:peer-review`, como numa cópia anterior à 0.70), `.claude/agents/reviewer.md`, `.claude/skills/minha-skill/` e `/par:peer-review` no `README.md` → exatamente um `[skill_obsoleta]`, que cita `.claude/skills/paper`, `.claude/agents/reviewer.md`, `README.md`, `prumo update` e `.prumo/legacy-copies/`, e não cita `minha-skill`; o trecho depois de `invocações antigas em` não contém `.claude/skills/paper/SKILL.md` (a cópia aparece uma vez só, como cópia).
    - `test_doctor_ignora_invocacao_dentro_das_copias` — só a cópia `.claude/skills/paper/SKILL.md` com `/par:peer-review`, nenhuma outra invocação → a issue cita a cópia e não contém `invocações antigas em`.
    - `test_doctor_so_invocacao_antiga_mantem_o_texto` — só a invocação → o texto atual ("o PAR agora tem 5 skills com modos … invocações antigas em README.md. Rode `prumo update` para reescrever as invocações.").
  - `tests/unit/core/test_skill_refs.py`: apagar `test_legacy_installed_dirs` e `test_legacy_installed_dirs_sem_diretorio`.
- [ ] **Step 2:** `uv run pytest tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - `doctor`: `copias = plugin_copies(target, _plugin_skill_names(), _plugin_agent_files())`. Com cópias, a issue é, literalmente (spec §Erros, "Cópias antigas no pj"): `"[skill_obsoleta] cópias antigas das skills/agents do PAR em .claude/ (" + ", ".join(copias) + ") sombreiam o plugin. Rode: prumo update — elas vão para .prumo/legacy-copies/<AAAAMMDD-HHMMSS>/, nada é apagado; se você customizou alguma, recrie-a em .claude/skills/<um-nome-seu>/"`, terminada em `"."`, ou, havendo invocações antigas, em `"; invocações antigas em " + ", ".join(antigos) + ", que o mesmo `prumo update` reescreve."`. Sem cópias e com invocações, o texto atual fica igual.
  - `update`, sem `--dry-run`: calcular `copias` e, se houver, `dest = pj_root / ".prumo" / "legacy-copies" / _legacy_stamp()` e `moved = move_plugin_copies(pj_root, copias, dest)` **antes** de `migrate_project_context` e `migrate_skill_names`; roda sempre, sem depender de `--yes` nem de TTY. Com `--dry-run`, só lista. `_confirm_diverged` não muda.
  - O `scan_skill_refs` não pula `.claude/skills/` nem `.claude/agents/`, e uma cópia anterior à 0.70 traz invocações antigas. No `doctor` (`antigos`) e no `update --dry-run` (`skill_refs`), filtre as `RefChange` cujo `path` seja um `rel` de `copias` ou comece com `rel + "/"`: a cópia aparece uma vez, como cópia, e não conta como arquivo a reescrever. Sem `--dry-run` não precisa de filtro (o move roda antes, e `.prumo/` está em `_SKIP_DIRS`). O filtro é um helper privado do `cli.py` (`_outside(changes, rels)`); `skill_refs.py` não muda por isso.
  - `_update_summary` ganha `copies: int = 0` e `backup: str | None = None` e emite **uma** linha, à frente do resto:
    - aplicado: `f"{copies} cópia(s) antiga(s) do PAR saíram de .claude/ para {backup}/ (nada foi apagado; o plugin passa a valer). Se você tinha customizado alguma, recrie-a com outro nome em .claude/skills/<um-nome-seu>/. "`;
    - `--dry-run`: `f"{copies} cópia(s) antiga(s) do PAR a mover de .claude/ para .prumo/legacy-copies/ (nada é apagado). "`;
    - "Projeto já está no padrão; nada a atualizar." só quando também não há cópias.
  - `skill_refs.py`: sai `legacy_installed_dirs` (função e `__all__`); `cli.py` deixa de importá-la.
  - `skills/write/modes/style.md`: a frase "considerar copiar a skill `write` para `.claude/skills/write/` …" passa a mandar copiar "para `.claude/skills/<um-nome-seu>/` — um nome do PAR seria tirado pelo `prumo update`"; depois `uv run python .github/scripts/gen_indexes.py`.
- [ ] **Step 4:** `uv run pytest tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py tests/unit/core/test_skill_refs.py -q` → PASS; verificação padrão.
- [ ] **Step 5: Commit** `feat: update move as cópias antigas do PAR para .prumo/legacy-copies; doctor aponta numa issue só`.

### Task 4: Sai o `_PF_DRIFT` e os contornos de drift (A7, parte de cortes)

**Files:**
- Modify: `.github/scripts/gen_indexes.py`, `skills/paper/modes/support.md`, `skills/review/modes/critique.md`, `skills/start/SKILL.md`, `skills/paper/modes/extract.md`, `skills/protocol/modes/picot.md`, `skills/wiki/modes/query.md`, `skills/wiki/modes/study.md`, `skills/review/modes/reconcile.md` (+ preflights e portas regerados)
- Test: `tests/unit/test_gen_indexes.py`, `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces: `render_preflight` com `cli` contribuindo 2 itens (`_PF_CLI`, `_PF_INIT`); `_PF_DRIFT` deixa de existir.

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/test_gen_indexes.py`: `test_preflight_cli_tem_dois_itens` — `render_preflight(_mode(registry, "paper", "extract"))` contém `> 1. ` e `> 2. `, não contém `> 3. ` nem `Drift CLI×plugin`; `test_gerador_sem_pf_drift` — `not hasattr(gen, "_PF_DRIFT")`.
  - `tests/unit/core/test_skills.py`: apagar `_bodies_calling` e `test_subcomando_recente_tem_fallback_de_subcomando_ausente`; criar `test_skills_sem_contorno_de_subcomando_ausente` — nenhum `skills/**/*.md` nem `agents/*.md` contém `No such command`.
- [ ] **Step 2:** `uv run pytest tests/unit/test_gen_indexes.py tests/unit/core/test_skills.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - `gen_indexes.py`: apagar `_PF_DRIFT`; em `render_preflight`, `parts += [_pf_item(n, _PF_CLI), _pf_item(n + 1, _PF_INIT)]` e `n += 2`; docstring "``cli`` (itens 1-2)".
  - Contornos (spec §Componentes, `skills/` e `agents/`, "Contornos de drift que saem"):
    - `paper/modes/support.md`: sai o parágrafo inteiro que começa em "Subcomando ausente (`No such command 'validate'`" e termina em "rode SÓ com consentimento.";
    - `review/modes/critique.md`: "**Sem validador** — `prumo` ausente OU subcomando ausente (`No such command 'validate'`, …) — confira à mão" vira "**Sem validador** (`prumo` ausente, como no Cowork) — confira à mão"; sai a frase "Se foi subcomando ausente, diga ao pesquisador UMA vez … a revisão não espera por isso." A validação à mão fica;
    - `start/SKILL.md`: sai só a frase "Se `status` não existir (`No such command 'status'`, … (rode SÓ com consentimento)." O resto do `start` é reescrito na Task 15.
  - Sai o bullet "O CLI `prumo` precisa estar no PATH (… `uv tool install …`)" de `paper/modes/extract.md`, `protocol/modes/picot.md`, `wiki/modes/query.md`, `wiki/modes/study.md`, e o bullet "O CLI `prumo` está no PATH (`prumo doctor`; senão `uv tool install …`)" de `review/modes/reconcile.md`.
  - `uv run python .github/scripts/gen_indexes.py` (regera os 12 preflights `cli`).
- [ ] **Step 4:** testes do Step 2 → PASS; `grep -rn "Drift CLI\|No such command" skills agents` vazio; verificação padrão.
- [ ] **Step 5: Commit** `refactor(skills): sai o _PF_DRIFT e os contornos de "No such command"`.

### Task 5: qmd só como CLI (A9)

**Files:**
- Modify: `.mcp.json`, `.claude/settings.json`, `.github/scripts/gen_indexes.py`, `skills/wiki/modes/ingest.md`, `skills/wiki/modes/query.md`, `skills/wiki/modes/study.md`, `src/par/core/deps.py`, `src/par/domains/wiki/index.py`, `templates/pj_base/docs/README.md`
- Create: `tests/unit/test_plugin_layout.py`, `tests/unit/wiki/test_index.py`
- Test: `tests/unit/core/test_deps.py`, `tests/unit/test_gen_indexes.py`, `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces: `.mcp.json` só com o servidor `prumo` (ainda `"command": "prumo"` até a Task 13); `_PF_QMD` checando `qmd --version`; hint do `DepStatus` `qmd` e mensagem de `QmdNotFoundError` novos.

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/test_plugin_layout.py` (novo; `REPO = Path(__file__).resolve().parents[2]`): `test_mcp_json_nao_declara_qmd` — `"qmd" not in json.loads((REPO / ".mcp.json").read_text())["mcpServers"]`.
  - `tests/unit/wiki/test_index.py` (novo): `test_reindex_sem_qmd_ensina_npm` — `monkeypatch.setattr("par.domains.wiki.index.shutil.which", lambda _: None)`; `pytest.raises(QmdNotFoundError)`; a mensagem contém `npm install -g @tobilu/qmd` e `prumo wiki index`.
  - `tests/unit/core/test_deps.py`: as asserções do hint do qmd passam a exigir `npm install -g @tobilu/qmd` e `bun install -g @tobilu/qmd`, e a ausência de `github.com/tobi/qmd`. Mude só as asserções do hint: não renomeie `test_qmd_present_when_on_path` nem `test_qmd_absent_includes_install_hint` e não mexa nos `patch("par.core.deps._zotero_api_root", …)` deles — o Plan 2 (PR 3, Task 5 dele) os retargeta para `_bbt_probe` ancorado nesse texto.
  - `tests/unit/test_gen_indexes.py`: `test_pf_qmd_checa_o_cli` — `gen._PF_QMD` contém `qmd --version` e não contém `command -v` nem `tools MCP`; `render_preflight(_mode(registry, "wiki", "query"))` contém `/par:start` (variante só-`qmd`).
  - `tests/unit/core/test_skills.py`: `test_skills_nao_citam_tools_mcp_do_qmd` — nenhum `skills/**/*.md` nem `agents/*.md` contém `mcp__qmd__`.
- [ ] **Step 2:** `uv run pytest tests/unit/test_plugin_layout.py tests/unit/wiki/test_index.py tests/unit/core/test_deps.py tests/unit/test_gen_indexes.py tests/unit/core/test_skills.py -q` → FAIL.
- [ ] **Step 3: Implementar** (spec A9; §Componentes, "Mensagens e textos em `src/`", "`skills/` e `agents/`" → "qmd só CLI", "`templates/pj_base/`" → `docs/README.md`):
  - `.mcp.json`: sai a entrada `qmd`; a entrada `prumo` fica como está.
  - `.claude/settings.json` do repo: sai a chave `"enabledMcpjsonServers"`; o hook `PreToolUse` do graphify fica.
  - `gen_indexes.py`: `_PF_QMD` passa ao texto da spec (A9 / §Componentes `gen_indexes.py`, bullet "`_PF_QMD` reescrito"), quebrado em linhas `\n` como as outras constantes, sem quebrar dentro de crases; `_PF_QMD_SEM_CLI` continua `_PF_QMD + " Se precisar do stack completo, roteie para `/par:start`."`.
  - `core/deps.py`: item `qmd` da docstring do módulo e `hint` do `DepStatus` `qmd`, com os textos literais da spec.
  - `wiki/index.py`: mensagem de `QmdNotFoundError` em `reindex` literal da spec ("qmd não está no PATH. Instale: npm install -g @tobilu/qmd (ou bun install -g @tobilu/qmd) e repita: prumo wiki index"); docstring do módulo "Wrapper sobre o CLI ``qmd`` …".
  - Modos `wiki`: tirar os tokens `mcp__qmd__*` do `allowed-tools` (os valores finais do D5 entram na Task 6); no corpo:
    - `ingest.md`: na busca de páginas candidatas, `qmd query "<termo>"` pelo Bash; §8 "Reindexar qmd" vira "o agente roda `qmd embed` (na 1ª vez, `prumo wiki index`)" e sai o "mostrar ao usuário o comando para rodar" com o bloco bash; no resumo final, `qmd: reindexado (ou: qmd indisponível — o agente roda prumo wiki index depois de instalado)`; em "Erros comuns", "qmd indisponível → fluxo não trava; o output diz que a reindexação não aconteceu";
    - `query.md`: o parágrafo de abertura passa a "Usa o CLI `qmd` pelo Bash (`qmd query \"<termo>\"`) para busca híbrida", sem as referências ao monorepo do autor (`/docs/wiki-schema.md` (monorepo) e `docs/operations.md` do monorepo); o pressuposto do qmd passa a "qmd instalado (`npm install -g @tobilu/qmd`) e o wiki indexado ao menos uma vez (`prumo wiki index`)"; a busca vira `qmd query "<pergunta>"` pelo Bash, e sai a linha do `mcp__qmd__search`;
    - `study.md`: `qmd query "<topic>"` pelo Bash se o qmd existir, senão `Grep` em `docs/`; em "Erros comuns", "`qmd` indisponível → fallback `Grep` + `Read` …".
  - `templates/pj_base/docs/README.md`: o bloco "Operações wiki" diz que os `/par:wiki …` são pedidos ao Claude e que `qmd query "<termo>"` é o uso opcional no terminal.
  - `uv run python .github/scripts/gen_indexes.py`.
- [ ] **Step 4:** testes do Step 2 → PASS; `grep -rn "mcp__qmd" skills agents .mcp.json` vazio; verificação padrão.
- [ ] **Step 5: Commit** `feat!: qmd só como CLI — sai o servidor MCP qmd do plugin`.

### Task 6: Curingas Bash estreitos (D5, A14)

**Files:**
- Modify: `skills/paper/modes/extract.md`, `skills/paper/modes/library.md`, `skills/wiki/modes/ingest.md`, `skills/wiki/modes/query.md`, `skills/wiki/modes/study.md` (+ `skills/paper/SKILL.md` e `skills/wiki/SKILL.md` regerados)
- Test: `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces: helper de teste `_bash_rule_matches(token: str, command: str) -> bool` com a semântica documentada: token que não começa com `Bash` (`Read`, `Agent`, `mcp__plugin_par_prumo__…` etc.) → `False`; `Bash` puro casa tudo; `Bash(<p> *)` e `Bash(<p>:*)` casam `<p>` e `<p> …` (o espaço é fronteira); `Bash(<p>*)` casa qualquer prefixo `<p>`; `Bash(<cmd>)` casa só o comando exato.
- Produces: helper de teste `_all_allowed_tools() -> list[str]` que enumera toda porta e todo modo: `reg, _ = load_skill_registry(_REPO_SKILLS, strict=True)`; `manifests = [reg.get(n) for n in reg.names()] + [m for _, m in reg.iter_modes()]`; devolve os tokens de `m.allowed_tools` de cada um.

- [ ] **Step 1: Testes que falham** em `tests/unit/core/test_skills.py`:
  - `test_semantica_do_curinga_bash` — `Bash(prumo paper sync *)` casa `prumo paper sync` e `prumo paper sync --x`, não casa `prumo paper sync-pdfs`.
  - `test_semantica_do_curinga_bash_ignora_outras_tools` — `_bash_rule_matches("Read", "prumo init x --force")` e `_bash_rule_matches("mcp__plugin_par_prumo__paper_sync", "prumo paper sync")` são `False`.
  - `test_nenhuma_regra_casa_comando_que_muda_estado_fora_do_fluxo` — parametrizado com `prumo paper connect x --create --yes`, `prumo init x --force` e `prumo update --yes`; percorre `_all_allowed_tools()`; nenhuma regra casa.
  - `test_paper_connect_fora_de_todo_frontmatter` — nenhum token de `_all_allowed_tools()` contém `paper_connect`.
- [ ] **Step 2:** `uv run pytest tests/unit/core/test_skills.py -q` → FAIL (portas `paper` e `wiki` ainda têm `Bash(prumo paper *)` e `Bash(prumo *)`).
- [ ] **Step 3: Implementar:** o `allowed-tools` dos cinco modos passa a ser exatamente o da tabela de A14 (copie célula por célula); depois `uv run python .github/scripts/gen_indexes.py`. Confira que `skills/paper/SKILL.md` não tem mais `Bash(prumo paper *)` e `skills/wiki/SKILL.md` não tem `Bash(prumo *)`. `Bash(prumo write *)` e `Bash(git *)` ficam (spec §Fora de escopo).
- [ ] **Step 4:** `uv run pytest tests/unit/core/test_skills.py tests/unit/test_gen_indexes.py -q` → PASS; verificação padrão.
- [ ] **Step 5: Commit** `fix(skills): curingas Bash estreitos — connect, init --force e update --yes voltam a pedir permissão (D5)`.

### Task 7: Sai `docs/actions-by-context.md`; docs do PR 1

**Files:**
- Delete: `docs/actions-by-context.md`
- Modify: `docs/_index.md` (fora dos blocos gerados), `docs/Research Project Structure.md`

- [ ] **Step 1:** `git rm docs/actions-by-context.md`.
- [ ] **Step 2:** `docs/_index.md`: sai a linha da tabela "Tenho um gatilho concreto, qual comando usar?" e o item "`actions-by-context.md` — playbook de bolso por gatilho." (as linhas do onboarding mudam no PR 5).
- [ ] **Step 3:** `docs/Research Project Structure.md`: a linha final "Ver também" fica só `[[journey|Canvas de jornada]]`; no diagrama do layout, `skills/` passa a "só skills próprias do projeto, com nome que não seja do PAR"; na seção `.claude/skills/`, sai o item "Cópia local das skills universais … preenchida automaticamente por `prumo init` e atualizada por `prumo doctor`", e o diretório é descrito como lugar só de skills próprias do projeto.
- [ ] **Step 4:** `uv run python .github/scripts/gen_indexes.py`; `grep -rn "actions-by-context" docs README.md ARCHITECTURE.md` só acha specs e planos antigos; verificação padrão.
- [ ] **Step 5: Commit** `docs: sai actions-by-context; .claude/skills/ só para skills próprias do projeto`.

### Fechamento do PR 1

- [ ] Verificação padrão completa.
- [ ] `git push -u origin feat/plugin-unico-1-cortes`; `gh pr create --title "feat!: plugin único — cortes do repo (PR 1/5 da 0.71.0)"` com corpo listando as Tasks 1–7 e "sem bump; CHANGELOG no PR 5".
- [ ] `gh pr checks --watch` verde → `gh pr merge --merge`; `git checkout main && git pull`.

---

## PR 2 — Dependências (Tasks 8–10)

Branch `feat/plugin-unico-2-deps`, a partir de `main` com o PR 1.

### Task 8: adeu no `uv.lock`, chamado por `sys.executable -I` (A8)

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (regerado), `src/par/domains/write/review.py`, `.github/workflows/ci.yml`
- Test: `tests/unit/write/test_review_adeu.py`, `tests/unit/write/test_review_ingest.py`

**Interfaces:**
- Produces: `_check_adeu_available() -> None` (levanta `AdeuUnavailableError` quando `importlib.util.find_spec("adeu") is None`); `_run_adeu_extract(docx_path: Path) -> str` (mesma assinatura, novo argv).
- Consumes: nada de `par.core.uvx` (o import sai).

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/write/test_review_adeu.py` — os testes do seam passam a fazer patch em `par.domains.write.review.subprocess.run`:
    - `test_run_adeu_extract_roda_o_adeu_do_lock_isolado` — argv `[sys.executable, "-I", "-m", "adeu.cli", "extract", "--json", str(docx), "-o", "-"]`, com `capture_output=True`, `text=True`, `timeout=120`;
    - parse do campo `markdown` (mantido); JSON inválido, JSON sem `markdown` e JSON que não é objeto → `AdeuUnavailableError` contendo `o formato do adeu 1.29.0 mudou? rode: prumo --version e reporte`;
    - `test_run_adeu_extract_exit_nao_zero` — `returncode=1`, stderr `"boom"` → `AdeuUnavailableError` contendo `boom` e `confira se o arquivo abre no Word e repita o ingest`;
    - `test_run_adeu_extract_timeout` — `subprocess.TimeoutExpired` → `AdeuUnavailableError` contendo `o adeu passou de 120 s lendo` e `prumo write review ingest`;
    - `test_check_adeu_available_sem_adeu` — `find_spec` devolve `None` para `"adeu"` → mensagem com `rm -rf ~/.cache/prumo && prumo --version` e `uv sync --extra dev --python 3.12`;
    - `test_check_adeu_available_com_adeu` — `find_spec` devolve um objeto → não levanta;
    - apagar `test_run_adeu_extract_uvx_not_found_raises_adeu_unavailable` e todo patch em `par.core.uvx.subprocess.run`; nenhum teste trava mais o texto `uvx adeu==1.29.0`.
  - `tests/unit/write/test_review_ingest.py`:
    - fixture `autouse` `_adeu_presente`, que delega para o `find_spec` real e só responde ao `"adeu"` (a perna 3.11 do CI não tem adeu):
      ```python
      @pytest.fixture(autouse=True)
      def _adeu_presente(monkeypatch: pytest.MonkeyPatch) -> None:
          real = importlib.util.find_spec

          def fake(name: str, package: str | None = None) -> object:
              return object() if name == "adeu" else real(name, package)

          monkeypatch.setattr(review.importlib.util, "find_spec", fake)
      ```
    - `test_ingest_fails_fast_without_uvx` vira `test_ingest_falha_cedo_sem_adeu`: `find_spec` devolve `None` → `AdeuUnavailableError` antes de carregar sidecars, mensagem com `adeu`.
  - Nos dois arquivos, todo `uvx` restante sai: a docstring de módulo de `test_review_adeu.py` ("roda `uvx adeu==1.29.0 extract …`", "via `patch(\"par.core.uvx.subprocess.run\")`") passa a descrever o adeu do lock rodado por `sys.executable -I -m adeu.cli` e o patch em `par.domains.write.review.subprocess.run`; o `args=` do helper de `CompletedProcess` e o `cmd=` dos `subprocess.TimeoutExpired` passam ao argv novo; em `test_review_ingest.py`, a docstring de módulo ("nunca roda `uvx` de verdade"), o comentário de seção "preflight 3a: uvx não disponível" e o comentário "fail-fast do preflight de uvx acima" passam a falar do adeu.
- [ ] **Step 2:** `uv run pytest tests/unit/write/test_review_adeu.py tests/unit/write/test_review_ingest.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - `pyproject.toml` (spec §Componentes "`pyproject.toml` e `uv.lock`"): `dependencies` ganha `"adeu==1.29.0; python_version >= '3.12'",  # backend de prosa do review ingest (ADR-0016)`; nova tabela `[tool.uv]` com `constraint-dependencies = ["cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'"]`. `requires-python`, `force-include` e `dynamic` não mudam. O console script `prumo-zettlr-export` só sai na Task 10.
  - `uv lock` (sem `--upgrade`). Confira, nesta ordem:
    - checagens duras: `git diff -U0 uv.lock | grep '^-version = '` vazio (nenhuma versão existente muda); `grep -n -A1 '^name = "adeu"' uv.lock` mostra `version = "1.29.0"`; a `cryptography` ganha a bifurcação 48.0.1 só para `sys_platform == 'darwin' and platform_machine == 'x86_64'` (`grep -n -A2 '^name = "cryptography"' uv.lock` mostra as duas entradas); `uv lock --check` limpo;
    - checagem informativa: `grep -c '^\[\[package\]\]' uv.lock` ≈ 99 (a spec mediu 99; o `uv lock` resolve as dependências *novas* do adeu para o que estiver mais novo no PyPI no dia, então uma diferença só em pacotes novos é aceitável).
    Depois `uv sync --extra dev`.
  - `review.py` (spec §Componentes "`src/par/domains/write/review.py`"): saem `_ADEU_TOOL`, `_ADEU_INSTALL_HINT`, `_check_uvx_on_path` e `from par.core.uvx import PinnedTool, run_pinned`; entram `import importlib.util`, `import subprocess`, `import sys` (se faltarem) e `_check_adeu_available()` com a mensagem literal da spec; `ingest()` chama `_check_adeu_available()` onde chamava `_check_uvx_on_path()`; `_run_adeu_extract` chama `subprocess.run([sys.executable, "-I", "-m", "adeu.cli", "extract", "--json", str(docx_path), "-o", "-"], capture_output=True, text=True, timeout=120)` e traduz:
    - `TimeoutExpired` → `AdeuUnavailableError(f"o adeu passou de 120 s lendo {docx_path}; repita: prumo write review ingest …")`;
    - `returncode != 0` → `AdeuUnavailableError(f"o adeu terminou com exit {rc} lendo {docx_path}. stderr:\n{proc.stderr.strip()[-2000:]}\nconfira se o arquivo abre no Word e repita o ingest.")`;
    - JSON → `"saída do adeu não é o JSON esperado (campo 'markdown') — o formato do adeu 1.29.0 mudou? rode: prumo --version e reporte; detalhe: {exc!r}"`.
    Docstrings e comentários que citam `uvx adeu==1.29.0` passam a "adeu 1.29.0, travado no uv.lock" (inclusive a de `AdeuUnavailableError` e o bloco de comentário da seção do seam). Remova imports que ficarem sem uso (`ruff`).
  - `.github/workflows/ci.yml`, job `lint-and-test`: passo novo logo depois de "Install project + dev deps", `- name: Lockfile em dia` / `run: uv lock --check`.
- [ ] **Step 4:** `uv lock --check`; `uv run pytest tests/unit/write -q` → PASS; `grep -n "uvx" src/par/domains/write/review.py tests/unit/write/test_review_adeu.py tests/unit/write/test_review_ingest.py` vazio; verificação padrão.
- [ ] **Step 5: Commit** `feat(write): adeu travado no uv.lock e rodado com sys.executable -I, sem uvx`.

### Task 9: Sai o `--deep` e o `core/uvx.py` (D3)

**Files:**
- Modify: `src/par/domains/paper/verify.py`, `src/par/domains/paper/cli.py`, `src/par/mcp_server.py`, `docs/positioning.md`
- Delete: `src/par/core/uvx.py`, `tests/unit/core/test_uvx.py`
- Test: `tests/unit/paper/test_verify.py`, `tests/unit/paper/test_cli.py`, `tests/unit/paper/test_errors.py`

**Interfaces:**
- Produces: `verify_refs(pj_path, *, page=None, refresh=False, cache_path=None, …)` sem `deep`; o dict devolvido mantém `"deep": False` (Princípio IV).

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/paper/test_verify.py`: apagar a classe `TestDeepLayer` inteira e `_REPORT_FIXTURE`; criar `test_verify_refs_report_deep_sempre_false` (`report["deep"] is False`), `test_verify_refs_sem_parametro_deep` (`"deep" not in inspect.signature(verify.verify_refs).parameters`), `test_modulo_sem_camada_profunda` (sem `REFCHECKER_PIN`, `RefcheckerUnavailableError`, `_run_refchecker`, `_findings_from_report`, `_bib_subset_text`; e `importlib.util.find_spec("par.core.uvx") is None`); inverter `test_sem_identificador_info`: a mensagem não contém `--deep` e contém `adicione o DOI no Zotero` e `prumo paper verify-refs`.
  - `tests/unit/paper/test_cli.py`: `test_verify_refs_repassa_flags` passa só `--refresh` (o fake de `verify_refs` perde o parâmetro `deep`); `test_verify_refs_sem_opcao_deep` — `--deep` → `exit_code == 2`.
  - `tests/unit/paper/test_errors.py`: sai `verify.RefcheckerUnavailableError` de `_PAPER_LEAVES`.
- [ ] **Step 2:** `uv run pytest tests/unit/paper -q` → FAIL.
- [ ] **Step 3: Implementar** (spec §Componentes "`src/par/core/uvx.py`, `verify.py`, `paper/cli.py`, `mcp_server.py` (D3)"): saem `REFCHECKER_PIN`, `_REFCHECKER_HINT`, `_REFCHECKER_TOOL`, `RefcheckerUnavailableError`, `_bib_subset_text`, `_run_refchecker`, `_findings_from_report`, o parâmetro `deep` e o ramo `if deep and deep_keys`; o comentário do `source` de `Finding` fica `"crossref" | "pubmed" | "local"`; a mensagem `no-identifier` passa a `f"entrada sem DOI/PMID{extra} — verificação nativa impossível; adicione o DOI no Zotero, deixe o Better BibTeX regravar o .bib e rode: prumo paper verify-refs"`; a docstring do módulo perde a camada profunda e a frase do `--deep`; o dict devolvido grava `"deep": False`. `paper/cli.py`: sai a opção `--deep` e o `deep=deep`. `mcp_server.py`: a docstring de `paper_verify_refs` perde a frase do `--deep`. `git rm src/par/core/uvx.py tests/unit/core/test_uvx.py`. Remova imports sem uso (`tempfile`, `Sequence`…). `docs/positioning.md`, linha "Mandar a bibliografia inteira a serviço externo": "Só DOI e PMID saem da máquina; não há camada profunda ([ADR-0018](adr/adr-0018-verificacao-referencias-apis-publicas.md))."
- [ ] **Step 4:** `uv run pytest tests/unit/paper tests/unit/test_mcp_server.py -q` → PASS; `grep -rn "uvx\|refchecker\|REFCHECKER" src skills agents pyproject.toml` vazio; `grep -rn "uvx\|refchecker\|REFCHECKER" tests` só acha as asserções de ausência de `test_modulo_sem_camada_profunda` (não as apague). `templates/` fica fora da varredura: o `uvx marimo edit` de `templates/modules/notebooks/.claude/rules/notebooks.md` é do módulo notebooks, não do PAR. Verificação padrão.
- [ ] **Step 5: Commit** `feat!: sai verify-refs --deep e o motor uvx (D3)`.

### Task 10: Sai o `prumo-zettlr-export`; o perfil do Zettlr usa a cópia do filtro no projeto (A10)

**Files:**
- Modify: `pyproject.toml`, `src/par/domains/write/zettlr.py`, `src/par/domains/write/cli.py`, `templates/pj_base/.gitignore`, `templates/pj_base/docs/project_guide.md`, `docs/superpowers/specs/2026-07-22-zettlr-front-design.md`
- Test: `tests/unit/write/test_zettlr_profile.py`, `tests/unit/write/test_cli.py`, `tests/unit/write/test_export_docx_validation.py`, `tests/unit/test_pj_base_integration.py`

**Interfaces:**
- Produces: `FILTER_RELPATH = Path("docs") / "templates" / "zotero_live_docx.lua"`; `generate_profile` copia o filtro (`shutil.copy2`) e garante a linha no `<pj>/.gitignore`; `profile_issues` com as três checagens de filtro.
- Consumes: `_zotero_live_docx_filter()` de `domains/write/export.py`.

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/write/test_zettlr_profile.py`:
    - `test_perfil_copia_o_filtro_para_o_projeto` — `pj/docs/templates/zotero_live_docx.lua` com os bytes do filtro empacotado; `filters == ["citeproc", str((pj / FILTER_RELPATH).resolve())]`;
    - `test_perfil_cria_gitignore_com_a_linha`, `test_perfil_acrescenta_linha_ao_gitignore_existente` e `test_perfil_rodado_duas_vezes_deixa_uma_linha` — a linha `docs/templates/prumo-docx.yaml` aparece exatamente uma vez, precedida do comentário;
    - `test_profile_issues_filtro_fora_do_projeto` — perfil apontando um `.lua` existente fora do pj → ``Perfil Zettlr aponta filtro fora do projeto: <caminho>. Regenere: `prumo write zettlr-profile` ``;
    - `test_profile_issues_copia_divergente` — cópia alterada → ``A cópia do filtro em docs/templates/zotero_live_docx.lua está diferente da desta versão do PAR. Regenere: `prumo write zettlr-profile` ``;
    - `test_profile_issues_filtro_inexistente` — mensagem atual mantida;
    - `test_perfil_recem_gerado_nao_tem_issue`.
  - `tests/unit/write/test_cli.py`: apagar `test_zettlr_entry_calls_canonical_docx_export`, `test_zettlr_entry_export_error_exits_cleanly`, `test_zettlr_entry_usage_error_exits_cleanly` e `test_zettlr_entry_forwards_warnings` (este último criado pelo Plan 1, Task 5); criar `test_zettlr_export_entry_nao_existe` (`not hasattr(write_cli, "zettlr_export_entry")`), `test_pyproject_sem_console_script_do_zettlr` (`tomllib` no `pyproject.toml`; `"prumo-zettlr-export" not in scripts`) e `test_zettlr_profile_mensagem_cita_o_filtro_no_projeto` (saída com espaços normalizados contém `docs/templates/zotero_live_docx.lua` e `não precisa reimportar`).
  - `tests/unit/write/test_export_docx_validation.py`: apagar `test_zettlr_export_entry_overwrites_on_second_run`.
  - `tests/unit/test_pj_base_integration.py`: `test_gitignore_do_pj_base_protege_o_essencial` exige `docs/templates/prumo-docx.yaml`.
- [ ] **Step 2:** `uv run pytest tests/unit/write/test_zettlr_profile.py tests/unit/write/test_cli.py tests/unit/test_pj_base_integration.py -q` → FAIL.
- [ ] **Step 3: Implementar** (spec A10; §Componentes "`zettlr.py` e `write/cli.py`", "`templates/pj_base/`"):
  - `zettlr.py`: `FILTER_RELPATH`; `generate_profile` copia `_zotero_live_docx_filter()` para `pj_path / FILTER_RELPATH` e escreve `"filters": ["citeproc", str((pj_path / FILTER_RELPATH).resolve())]`; depois, se nenhuma linha do `<pj>/.gitignore` (com `strip()`) for `docs/templates/prumo-docx.yaml`, acrescenta ``# perfil do Zettlr: caminhos absolutos desta máquina; regenere com `prumo write zettlr-profile` `` e a linha (garantindo `\n` antes; cria o arquivo se faltar). `profile_issues`, para cada filtro ≠ `citeproc`: inexistente → mensagem atual; senão, `Path(f).resolve() != (pj_path / FILTER_RELPATH).resolve()` → "fora do projeto"; senão, bytes ≠ filtro empacotado → "cópia divergente". Docstring do módulo: "cópia do filtro no projeto, caminho estável entre versões".
  - `write/cli.py`: sai `zettlr_export_entry` (e imports que só ele usava); a mensagem de sucesso do `zettlr-profile` passa ao texto literal da spec ("Perfil Zettlr gerado: {out} (o filtro fica em docs/templates/zotero_live_docx.lua). Importe uma vez no Zettlr (Assets Manager → defaults files). Depois de atualizar o PAR, se o `prumo doctor` avisar do perfil, rode `prumo write zettlr-profile` de novo — o caminho não muda, então não precisa reimportar.").
  - `pyproject.toml`: sai `prumo-zettlr-export = …` de `[project.scripts]`; `uv lock --check` (se acusar, `uv lock` e confira que só os metadados do projeto mudaram).
  - `templates/pj_base/.gitignore`: o comentário e a linha `docs/templates/prumo-docx.yaml` acima.
  - `templates/pj_base/docs/project_guide.md`, seção "Editor (Zettlr)": o passo 4 ganha "peça 'gera o perfil do Zettlr' (roda `prumo write zettlr-profile`) e importe" e "para entrega e coautores, peça ao Claude: 'exporta o docx canônico de <arquivo>'"; o passo 5 (custom command) sai e os seguintes são renumerados; o antigo passo 7 vira "Atualizou o PAR e o `prumo doctor` avisou do perfil? Peça 'regenera o perfil do Zettlr'; não precisa reimportar". Não toque nas linhas que o Plan 1/Plan 2 mudaram (piso do pandoc, "Keep updated").
  - `docs/superpowers/specs/2026-07-22-zettlr-front-design.md`: no fim da §4 ("CLI/entrypoint para o custom command"), a nota de uma linha literal da spec (§Documentação, bullet desse arquivo), acima da nota da Spec B.
- [ ] **Step 4:** `uv run pytest tests/unit/write tests/unit/test_cli_doctor.py tests/unit/test_cli_init.py tests/unit/test_pj_base_integration.py -q` → PASS; `grep -rn "zettlr-export\|zettlr_export_entry" src skills agents templates pyproject.toml` vazio; `grep -rn "zettlr-export\|zettlr_export_entry" tests` só acha as asserções de ausência de `test_zettlr_export_entry_nao_existe` e `test_pyproject_sem_console_script_do_zettlr`; verificação padrão + `uv lock --check`.
- [ ] **Step 5: Commit** `feat!: sai prumo-zettlr-export; o perfil do Zettlr aponta a cópia do filtro no projeto`.

### Fechamento do PR 2

- [ ] Verificação padrão + `uv lock --check` + manifests.
- [ ] Push, `gh pr create --title "feat!: plugin único — dependências (PR 2/5 da 0.71.0)"`, CI verde nas pernas 3.11 e 3.12, merge.

---

## PR 3 — Spec B, parte 0.71.0 (Plan 2)

Não faz parte deste plano. É o Plan 2 (aposentadoria de `sync-annotations`/`sync-notes`/`sync-all`, sonda `_bbt_probe`, transporte do `connect`, variantes de sandbox E11 e E15), com plano próprio em `docs/superpowers/plans/`. O PR 4 começa com o PR 3 em `main`. O item 3 da trilha do `/par:start`, que a Spec B fixa, é gravado pela Task 15 deste plano.

---

## PR 4 — Lançador (Tasks 11–17)

Branch `feat/plugin-unico-4-lancador`, a partir de `main` com os PRs 1–3.

### Task 11: `shims/prumo` (A1–A4, A15)

**Files:**
- Create: `shims/prumo` (100755, único arquivo de `shims/`), `tests/unit/test_launcher.py`

**Interfaces:**
- Produces: lançador com as saídas 127/69/73/77/78/70/71/1 e prefixo `PAR:` (spec A4, §Erros); variáveis de teste `PRUMO_CACHE_DIR` e `PRUMO_UV`.

- [ ] **Step 1: Testes que falham** em `tests/unit/test_launcher.py` (spec §Testes, "`tests/unit/test_launcher.py`"). Infraestrutura:
  - `SHELLS = ["/bin/sh"] + ([d] if (d := shutil.which("dash")) else [])`, parametrizando todo teste; `pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="lançador POSIX")`.
  - Fixture `root`: em `tmp_path / "root"`, copia `REPO / "shims" / "prumo"` (modo 755), escreve um `uv.lock` qualquer, `src/par/__init__.py` vazio e um `src/par/cli.py` falso:
    ```python
    import json, os, sys

    def app(prog_name: str) -> None:
        import yaml
        print(json.dumps({"prog": prog_name, "argv": sys.argv[1:], "env": dict(os.environ),
                          "yaml": yaml.__file__, "par": __file__}))
    ```
  - Fixture `fake_uv` (script 755 em `tmp_path / "bin" / "uv"`), controlado por variáveis:
    ```sh
    #!/bin/sh
    printf '%s|%s|%s\n' "$*" "${UV_NATIVE_TLS:-}" "${UV_SYSTEM_CERTS:-}" >>"$FAKE_UV_LOG"
    if [ -n "${FAKE_UV_TLS_ONCE:-}" ] && [ "${UV_NATIVE_TLS:-}" != 1 ]; then
      echo "error: invalid peer certificate: UnknownIssuer" >&2; exit 2
    fi
    if [ -n "${FAKE_UV_STDERR:-}" ]; then printf '%s\n' "$FAKE_UV_STDERR" >&2; exit 2; fi
    [ -z "${FAKE_UV_NO_PYTHON:-}" ] || exit 0
    mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"
    rm -f "$UV_PROJECT_ENVIRONMENT/bin/python"
    printf '#!/bin/sh\nexec "%s" "$@"\n' "$FAKE_PY" >"$UV_PROJECT_ENVIRONMENT/bin/python"
    chmod 755 "$UV_PROJECT_ENVIRONMENT/bin/python"
    ```
    O `rm -f` modela o uv real, que recria o interpretador do venv: sem ele, o `>` seguiria um link pendurado em `bin/python` e o lançador classificaria a falha do fake como 69 ou 73.
  - Helper `_run(shell, root, env, *args, cwd=None) -> subprocess.CompletedProcess[str]` que roda `[shell, str(root / "shims" / "prumo"), *args]` com um ambiente **montado do zero** (sem herdar `os.environ`, para que `SANDBOX_RUNTIME`, `WSL_DISTRO_NAME` e `WSL_INTEROP` nunca vazem): `PATH` de `os.environ`, `HOME=tmp_path/"home"`, `PRUMO_CACHE_DIR=tmp_path/"cache"`, `PRUMO_UV=<fake_uv>`, `FAKE_UV_LOG`, `FAKE_PY=sys.executable`, mais o que o teste pedir.

  Casos (nomes dos testes):
  - `test_frio_monta_venv_e_roda_o_cli` — rc 0; a saída JSON tem `prog == "prumo"` e `argv == ["--version"]`; existe `cache/venv-3.12-*/.prumo-ok`.
  - `test_quente_nao_chama_o_uv` — depois de um frio, `PRUMO_UV=/inexistente` → rc 0.
  - `test_python_quebrado_reconstroi` — depois de um frio, com `venv = next((tmp_path / "cache").glob("venv-3.12-*"))`, troca `bin/python` por um link pendurado (`(venv / "bin" / "python").unlink()` e `os.symlink(tmp_path / "sumiu" / "python", venv / "bin" / "python")`, com o diretório `sumiu` inexistente); nova chamada → rc 0 e o log do uv falso tem 2 linhas.
  - `test_classifica_falha_do_uv` — parametrizado com a tabela da spec: ``"error: Failed to parse `uv.lock`"`` → 78 e `uv self update`; `"hint: … but Python downloads are set to 'never'"` → 78 e `uv python install 3.12`; `"error: Read-only file system (os error 30)"` com `SANDBOX_RUNTIME=1` → 77 e `fora do sandbox`; o mesmo sem a variável → 73 e `chown`; `"Operation not permitted (os error 1)"` → 77; `"No space left on device"` → 73; `"error: Request failed after 3 retries\n  Caused by: dns error"` → 69 e `release-assets.githubusercontent.com`; o mesmo com `SANDBOX_RUNTIME=1` → 77. Toda saída de erro começa com `PAR: `.
  - `test_uv_sai_zero_sem_python` — `FAKE_UV_NO_PYTHON=1` → 70.
  - `test_sem_uv` — `PRUMO_UV=/inexistente`, sem stamp → 127 e `stderr.startswith("PAR: falta o uv")` (usa `PRUMO_UV`, nunca um `PATH` podado: o lançador anexa `/opt/homebrew/bin` e `/usr/local/bin`).
  - `test_windows_e_wsl` — `OS=Windows_NT`, `WSL_DISTRO_NAME=Ubuntu` e `WSL_INTEROP=/run/WSL/1_interop`, cada um → 71 e `nem no WSL`.
  - `test_raiz_sem_src` — raiz sem `src/par/cli.py` → 1 e `link simbólico`.
  - `test_tls_tenta_de_novo_com_certificados_do_sistema` — `FAKE_UV_TLS_ONCE=1` → rc 0; o log tem 2 linhas, a 1ª terminada em `||` e a 2ª em `|1|1`.
  - `test_cache_fixo_ignora_xdg` — sem `PRUMO_CACHE_DIR`, com `XDG_CACHE_HOME=tmp_path/"xdg"` → o venv nasce em `$HOME/.cache/prumo/` e `tmp_path/"xdg"` não existe ou está vazio.
  - `test_cwd_nao_sequestra` — cwd com `yaml.py`, `typer.py` (`raise SystemExit("HIJACKED")`) e `par/__init__.py` + `par/cli.py` que imprime `HIJACKED` → `HIJACKED` fora da saída; `yaml` fora do cwd; `par` dentro de `root/src`.
  - `test_ambiente_do_filho_so_ganha_sufixo_no_path` — o `env` devolvido é igual ao de entrada, exceto `PATH == env_in["PATH"] + f":{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin"`, ignorando as chaves `ignored = {"_", "SHLVL", "PWD", "OLDPWD", "__CF_USER_TEXT_ENCODING"} | ({"LC_CTYPE"} if "LC_CTYPE" not in env_in else set())`. As cinco primeiras vêm do shell e do macOS; o `LC_CTYPE` é a coerção de locale do próprio CPython (PEP 538): como o `_run` monta o ambiente sem `LANG`/`LC_*`, o Python do filho grava `LC_CTYPE` no seu `os.environ` (medido em 3.9 e 3.13; o `-I` não a desliga, porque ignora `PYTHONCOERCECLOCALE`). Não é o lançador.
  - `test_poda_venvs_velhos` — `cache/venv-3.12-velho` com `mtime` de 40 dias e `cache/venv-3.12-recente` de 10 dias (`os.utime`); um frio apaga o velho e mantém o recente e o atual.
- [ ] **Step 2:** `uv run pytest tests/unit/test_launcher.py -q` → FAIL (`shims/prumo` não existe).
- [ ] **Step 3: Implementar:** `shims/prumo` = o bloco `sh` de §Componentes, "`shims/prumo` (novo, 100755, 117 linhas, único arquivo de `shims/`)", copiado byte a byte (`wc -l shims/prumo` → 117). `chmod 755 shims/prumo && git add shims/prumo`; `git ls-files -s shims/prumo` começa com `100755`. Se o `shellcheck` existir: `shellcheck -s sh shims/prumo` limpo.
- [ ] **Step 4:** `uv run pytest tests/unit/test_launcher.py -q` → PASS em `/bin/sh` e `dash`; smoke real (rede na 1ª vez):
  ```bash
  PRUMO_CACHE_DIR="$TMPDIR/pc" UV_CACHE_DIR="$TMPDIR/uvcache" UV_PYTHON_INSTALL_DIR="$TMPDIR/uvpython" sh shims/prumo --version
  ```
  → `prumo <__version__>`; a 2ª chamada é quente. Verificação padrão.
- [ ] **Step 5: Commit** `feat: lançador shims/prumo — CLI desta raiz do plugin, venv travado no uv.lock (ADR-0038)`.

### Task 12: Hook `SessionStart` (A5)

**Files:**
- Create: `hooks/hooks.json`, `hooks/session-start.sh` (100755)
- Test: `tests/unit/test_launcher.py`, `tests/unit/test_plugin_layout.py`

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/test_launcher.py` (hook, parametrizado por shell; `CLAUDE_PLUGIN_ROOT` aponta uma raiz com `shims/prumo`):
    - `test_hook_idempotente` — 2 execuções deixam 1 linha no env file;
    - `test_hook_raiz_com_aspas_dolar_e_crase` — raiz cujo nome tem apóstrofo, `$` e crase (`tmp_path / ("r'o$o" + chr(96) + "t")`); depois do hook, `bash -c '. "$1"; command -v prumo' _ <env>` e `/bin/sh -c …` devolvem `<raiz>/shims/prumo`;
    - `test_hook_sem_env_file_sai_calado` — sem `CLAUDE_ENV_FILE` → rc 0, stdout e stderr vazios;
    - `test_hook_env_file_so_leitura_sai_calado` — env file `chmod 0o444` → rc 0 e stderr vazio.
  - `tests/unit/test_plugin_layout.py` (spec §Testes, "`tests/unit/test_plugin_layout.py`"):
    - `test_shims_so_tem_prumo` — `sorted(p.name for p in (REPO / "shims").iterdir() if p.name != ".DS_Store") == ["prumo"]`;
    - `test_modo_100755_no_git` — `git ls-files -s shims/prumo hooks/session-start.sh` (com `cwd=REPO`) → as duas linhas começam com `100755`. Guarda: `pytest.skip` quando `not (REPO / ".git").exists()` ou `shutil.which("git") is None`. Use `.exists()`, nunca `.is_dir()`: num worktree o `.git` é arquivo, e `.is_dir()` pularia o teste em silêncio;
    - `test_sem_bin_na_raiz` — `not (REPO / "bin").exists()`;
    - `test_hooks_json_so_sessionstart_em_forma_exec` — eventos == `{"SessionStart"}`, uma entrada sem `matcher`, `command == "/bin/sh"`, `args == ["${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"]`.
- [ ] **Step 2:** `uv run pytest tests/unit/test_launcher.py tests/unit/test_plugin_layout.py -q` → FAIL.
- [ ] **Step 3: Implementar:** `hooks/hooks.json` e `hooks/session-start.sh` = os dois blocos de §Componentes, "`hooks/hooks.json` e `hooks/session-start.sh` (novos)", byte a byte. `chmod 755 hooks/session-start.sh && git add hooks/`. `shellcheck -s sh hooks/session-start.sh` limpo, se houver shellcheck. O `validate_manifests.py` não muda.
- [ ] **Step 4:** testes → PASS; verificação padrão.
- [ ] **Step 5: Commit** `feat: hook SessionStart põe o lançador no PATH do Bash da sessão`.

### Task 13: `.mcp.json` via `/bin/sh` e dev do repo (A5, A17)

**Files:**
- Modify: `.mcp.json`, `.claude/settings.json`
- Test: `tests/unit/test_plugin_layout.py`

- [ ] **Step 1: Teste que falha:** `test_mcp_json_eh_so_o_prumo_pelo_lancador` — `json.loads(.mcp.json)` é exatamente o dict de §Componentes "`.mcp.json`"; substitui `test_mcp_json_nao_declara_qmd`.
- [ ] **Step 2:** `uv run pytest tests/unit/test_plugin_layout.py -q` → FAIL.
- [ ] **Step 3: Implementar:** `.mcp.json` = o bloco da spec. `.claude/settings.json` do repo ganha `"disabledMcpjsonServers": ["prumo"]` (o `.mcp.json` também é lido como config de projeto aqui; com o placeholder não resolvido, o servidor de projeto não deve subir). A partir daqui o dev testa o MCP com `claude --plugin-dir .` (risco R8: se a rejeição atingir o `plugin:par:prumo`, testar abrindo o `--plugin-dir <repo>` em outra pasta).
- [ ] **Step 4:** `uv run pytest tests/unit/test_plugin_layout.py tests/unit/test_mcp_server.py -q` → PASS; handshake local pelo lançador:
  ```bash
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
    | PRUMO_CACHE_DIR="$TMPDIR/pc" UV_CACHE_DIR="$TMPDIR/uvcache" UV_PYTHON_INSTALL_DIR="$TMPDIR/uvpython" /bin/sh shims/prumo mcp serve | head -1
  ```
  → `"serverInfo":{"name":"prumo","version":"<__version__>"}`. Verificação padrão.
- [ ] **Step 5: Commit** `feat: o MCP do plugin sobe pelo lançador; o dev do repo rejeita o .mcp.json como servidor de projeto`.

### Task 14: Bloco `prumo:runtime` e `_PF_CLI` novo (A6, A7, A9)

**Files:**
- Modify: `.github/scripts/gen_indexes.py`; marcadores vazios em `skills/{paper,protocol,review,wiki,write}/SKILL.md`, `skills/start/SKILL.md` e `agents/reader.md`; `skills/paper/modes/extract.md`, `skills/paper/modes/support.md`, `skills/review/modes/critique.md` (fallback de agents); `agents/reader.md` (linha do Bash); `skills/wiki/modes/ingest.md`, `skills/wiki/modes/query.md` (passos opcionais); + 7 blocos runtime e 12 preflights regerados
- Test: `tests/unit/test_gen_indexes.py`, `tests/unit/test_agents.py`, `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces (em `gen_indexes.py`): `from par._version import __version__  # noqa: E402` no topo (global do módulo, lida na hora da chamada); `render_runtime() -> str`; `_targets()` com 7 tuplas `(path, "runtime", render_runtime())`; `_PF_CLI` novo; docstring do módulo listando `src/par/_version.py → bloco prumo:runtime`.

- [ ] **Step 1: Testes que falham** (spec §Testes, "`tests/unit/test_gen_indexes.py`", "`test_agents.py`", "`core/test_skills.py`"):
  - `test_render_runtime_carimba_versao_e_raiz` — contém `f"**PAR {__version__}**"` e `${CLAUDE_PLUGIN_ROOT}` (com chaves) e `/shims/prumo`;
  - `test_os_sete_alvos_tem_o_bloco_runtime` — os 7 arquivos contêm `<!-- prumo:runtime:begin -->` e `f"**PAR {__version__}**"`;
  - `test_check_acusa_runtime_desatualizado` — `monkeypatch.setattr(gen, "__version__", "9.9.9")`, `monkeypatch.setattr(sys, "argv", ["gen_indexes.py", "--check"])`; `gen.main() == 1` e a saída (`capsys`) cita `skills/paper/SKILL.md` e `agents/reader.md` (o `--check` nunca escreve);
  - `test_preflight_cli_novo` — para `paper/extract`: 2 itens; contém `PAR: falta o uv`, `/shims/prumo`, `(b)–(d)` e `fora do sandbox`; `uv tool uninstall prumo-assistant-for-researcher` aparece exatamente uma vez; não contém `Drift CLI×plugin`, `uv tool install` nem `uv tool upgrade`;
  - `tests/unit/test_agents.py`: `test_reader_tem_bloco_runtime` — `agents/reader.md` tem os marcadores logo depois do frontmatter e a frase ``(ou da forma `sh` do bloco PAR acima)``;
  - `tests/unit/core/test_skills.py`: `test_plugin_root_sempre_com_chaves` — nenhum `skills/**/*.md` nem `agents/*.md` casa `re.search(r"\$CLAUDE_PLUGIN_ROOT", texto)` (só `${CLAUDE_PLUGIN_ROOT}` é substituído ao carregar).
- [ ] **Step 2:** `uv run pytest tests/unit/test_gen_indexes.py tests/unit/test_agents.py tests/unit/core/test_skills.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - Marcadores vazios `<!-- prumo:runtime:begin -->` / `<!-- prumo:runtime:end -->` (cada um na sua linha, com uma linha em branco antes e depois): logo abaixo do H1 nas 5 portas e no `start` (no `start`, acima do bloco `prumo:preflight`); logo depois do frontmatter em `agents/reader.md`.
  - `render_runtime()` devolve o bloco de §Componentes "`.github/scripts/gen_indexes.py`", bullet "Novo `render_runtime()`", com `{__version__}` no lugar de `0.71.0` (num f-string, escreva `${{CLAUDE_PLUGIN_ROOT}}`).
  - `_PF_CLI` = o bloco markdown do bullet "`_PF_CLI` reescrito", sem o prefixo `> 1. ` da 1ª linha e sem o `>    ` das seguintes (o `_pf_item` os recoloca); confira que o preflight renderizado de `paper/extract` reproduz o bloco da spec.
  - Fallback de agents em `paper/modes/extract.md`, `paper/modes/support.md` e `review/modes/critique.md`: "(em `$CLAUDE_PLUGIN_ROOT/agents/` ou `.claude/agents/`)" vira "(na pasta da linha *Agents* do bloco PAR da porta)".
  - `agents/reader.md`: "Nunca use Bash para outra coisa além de `prumo paper extract`." vira "Nunca use Bash para outra coisa além de `prumo paper extract` (ou da forma `sh` do bloco PAR acima)."
  - `wiki/modes/ingest.md` (passo de indexação) e `wiki/modes/query.md` (arquivamento com `prumo wiki finding`) ganham a frase literal da spec (§Componentes, `skills/` e `agents/`, "Passos opcionais com `prumo` nos modos só-`qmd`"): "use `prumo`; se ele não existir nesta sessão, use a forma `sh` do bloco PAR da porta. Se a saída trouxer uma linha `PAR:`, repasse-a e siga sem este passo".
  - `uv run python .github/scripts/gen_indexes.py`.
- [ ] **Step 4:** testes do Step 2 → PASS; `gen_indexes --check` limpo; verificação padrão.
- [ ] **Step 5: Commit** `feat: bloco prumo:runtime carimba a versão nas portas; o preflight confere superfície e versão`.

### Task 15: `/par:start` reescrito; mensagem de recurso ausente (A7, A15, §Fluxo)

**Files:**
- Modify: `skills/start/SKILL.md` (corpo humano), `src/par/core/paths.py`
- Create: `tests/unit/core/test_paths.py`
- Test: `tests/unit/core/test_skills.py`

- [ ] **Step 1: Testes que falham.**
  - `tests/unit/core/test_skills.py`:
    - `test_skills_nao_mandam_instalar_cli_a_parte` — nenhum `skills/**/*.md` nem `agents/*.md` contém `uv tool install` ou `uv tool upgrade` (`uv tool uninstall` é permitido);
    - `test_start_cobre_superficie_uv_e_tools` — o corpo do `start`, com espaços normalizados (o texto da spec quebra linhas no meio das frases), contém `PAR: falta o uv`, `mcp__plugin_par_prumo__`, `uv tool uninstall prumo-assistant-for-researcher`, `curl -LsSf https://astral.sh/uv/install.sh | sh`, `Better BibTeX ≥ 9.0.65`, `npm install -g @tobilu/qmd` e `nunca ofereça instalar o CLI à parte`.
  - `tests/unit/core/test_paths.py`: `test_recurso_ausente_ensina_a_reinstalar_o_plugin` — `monkeypatch.setattr("par.core.paths.find_resource", lambda _n: None)`; `pytest.raises(ConfigError)` com `/plugin install par@prumo-assistant-for-researcher` e `uv run prumo`.
- [ ] **Step 2:** `uv run pytest tests/unit/core/test_skills.py tests/unit/core/test_paths.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
  - `skills/start/SKILL.md`: tudo entre o fim do bloco `prumo:preflight` e o heading `## Catálogo completo (gerado — não editar à mão)` passa a ser o conteúdo do bloco markdown (cercado por quatro crases) de §Fluxo, "`/par:start` reescrito", copiado literalmente (o item 3 da trilha é o texto da Spec B, já embutido ali, numa linha só). Frontmatter (`requires: []`), H1, bloco runtime, preflight e catálogo ficam.
  - `core/paths.py`: a mensagem de `resolve_resource` passa ao texto literal da spec (§Componentes, "Mensagens e textos em `src/`", `core/paths.py`).
  - `uv run python .github/scripts/gen_indexes.py`.
- [ ] **Step 4:** testes → PASS; `grep -rn "uv tool install\|uv tool upgrade" skills agents src templates` vazio; verificação padrão.
- [ ] **Step 5: Commit** `feat(start): a porta de entrada checa superfície, versão e uv, e nunca oferece o CLI à parte`.

### Task 16: Atualização automática pelo template (D4, A13)

**Files:**
- Create: `templates/pj_base/.claude/settings.json`
- Modify: `templates/pj_base/README.md`
- Test: `tests/unit/test_plugin_layout.py`, `tests/unit/test_cli_init.py`, `tests/unit/test_cli_update.py`

- [ ] **Step 1: Testes que falham.**
  - `test_plugin_layout.py`: `test_settings_do_template_liga_o_auto_update` — `json.loads(templates/pj_base/.claude/settings.json)` é exatamente o dict de A13.
  - `test_cli_init.py`: `test_init_traz_settings_do_template` — depois do `init`, `.claude/settings.json` tem os mesmos bytes do template.
  - `test_cli_update.py`: `test_update_acrescenta_settings_ausente` (apaga o arquivo; `update --json` → `".claude/settings.json" in payload["copied"]`) e `test_update_nao_toca_settings_existente` (conteúdo próprio; `update --yes` → byte-idêntico).
- [ ] **Step 2:** `uv run pytest tests/unit/test_plugin_layout.py tests/unit/test_cli_init.py tests/unit/test_cli_update.py -q` → FAIL.
- [ ] **Step 3: Implementar:** `templates/pj_base/.claude/settings.json` = o JSON de A13 (sem código novo: `init` copia pelo overlay; `update` traz como arquivo ausente; `COMPARE_PREFIX` não muda). `templates/pj_base/README.md`: §Setup perde o bloco bash (`uv sync` e `/plugin install … MCP qmd`) e passa a "Abra este projeto no app Claude, aba Code (ou `claude` no terminal), e peça `/par:start`."; §Evoluir vira "peça ao Claude", por exemplo "ativa o módulo clínico" (roda `prumo add clinical`), com os outros módulos no mesmo formato.
- [ ] **Step 4:** testes → PASS; verificação padrão.
- [ ] **Step 5: Commit** `feat(template): .claude/settings.json liga a atualização automática do PAR no projeto (D4)`.

### Task 17: Job `launcher-smoke` no CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1:** Acrescentar o job sob `jobs:`, no mesmo nível de `lint-and-test` (spec §Componentes, "CI", `launcher-smoke`). O contexto `runner` não vale em `jobs.<id>.env`, por isso as variáveis vão para `$GITHUB_ENV` num passo:
  ```yaml
  launcher-smoke:
    runs-on: ${{ matrix.os }}
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, macos-15-intel]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Ambiente do smoke
        run: |
          echo "PRUMO_CACHE_DIR=$RUNNER_TEMP/pc" >> "$GITHUB_ENV"
          echo "ROOT=$RUNNER_TEMP/root" >> "$GITHUB_ENV"
          echo "WANT=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/par/_version.py)" >> "$GITHUB_ENV"
      - name: ShellCheck
        if: runner.os == 'Linux'
        run: shellcheck -s sh shims/prumo hooks/session-start.sh
      - name: Raiz do plugin só de leitura (arquivos versionados, modo preservado)
        run: |
          mkdir -p "$ROOT"
          git archive --format=tar HEAD | tar -x -C "$ROOT"
          chmod -R a-w "$ROOT"
      - name: --version em sh (frio e quente)
        run: |
          test "$(sh "$ROOT/shims/prumo" --version)" = "prumo $WANT"
          test "$(sh "$ROOT/shims/prumo" --version)" = "prumo $WANT"
      - name: --version no outro shell POSIX
        run: |
          if [ "$RUNNER_OS" = Linux ]; then alt="bash --posix"; else alt=/bin/dash; fi
          test "$($alt "$ROOT/shims/prumo" --version)" = "prumo $WANT"
      - name: Remonta offline
        run: |
          rm -rf "$PRUMO_CACHE_DIR"/venv-*
          test "$(UV_OFFLINE=1 sh "$ROOT/shims/prumo" --version)" = "prumo $WANT"
      - name: Handshake MCP (serverInfo.version)
        timeout-minutes: 3
        run: |
          python3 - <<'PY'
          import json, os, subprocess
          p = subprocess.Popen(["sh", os.environ["ROOT"] + "/shims/prumo", "mcp", "serve"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
          req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "smoke", "version": "0"}}}
          p.stdin.write(json.dumps(req) + "\n"); p.stdin.flush()
          got = json.loads(p.stdout.readline())["result"]["serverInfo"]["version"]
          p.kill()
          assert got == os.environ["WANT"], (got, os.environ["WANT"])
          print("serverInfo.version =", got)
          PY
      - name: init cria settings.json e nenhuma cópia
        # Pelo lançador do checkout gravável, não pelo $ROOT: o init copia o template com
        # shutil.copytree (copy2 preserva o modo), e um template 0444/0555 faria o
        # apply_project_name falhar com PermissionError. Mesmo uv.lock e mesmo shim, logo a
        # mesma chave e o mesmo venv já montado acima (caminho quente).
        run: |
          cd "$RUNNER_TEMP"
          sh "$GITHUB_WORKSPACE/shims/prumo" init pj_smoke --yes
          test -f pj_smoke/.claude/settings.json
          test ! -e pj_smoke/.claude/skills
          test ! -e pj_smoke/.claude/agents
      - name: Hook põe o lançador no PATH
        run: |
          : >"$RUNNER_TEMP/env"
          CLAUDE_PLUGIN_ROOT="$ROOT" CLAUDE_ENV_FILE="$RUNNER_TEMP/env" sh "$ROOT/hooks/session-start.sh"
          test "$(bash -c '. "$1"; command -v prumo' _ "$RUNNER_TEMP/env")" = "$ROOT/shims/prumo"
      - name: Devolve escrita à raiz (limpeza do runner)
        if: always()
        run: chmod -R u+w "$RUNNER_TEMP/root" || true
  ```
  (O `git archive HEAD` equivale à cópia de `git ls-files` num checkout limpo e preserva o `100755`. A raiz só de leitura vale para `--version`, a remontagem offline, o handshake MCP e o hook; o `init` roda pelo checkout gravável, como explica o comentário do passo. Endurecer o `init` contra template só de leitura — `chmod u+w` recursivo depois do `copytree`, `shutil.copyfile` no lugar de `copy2` no `generate_profile` — fica fora deste plano: a spec não pede, e o cache de plugins do Claude Code é gravável; é decisão do dono.)
- [ ] **Step 2:** `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`; verificação padrão.
- [ ] **Step 3: Commit** `ci: job launcher-smoke (ubuntu, macOS arm64 e macOS Intel)`.
- [ ] **Step 4: Gate do Mac Intel.** Um label sem runner não falha: o job fica "Queued" até o limite de fila do GitHub (24 h), e o `timeout-minutes` não conta tempo de fila. Por isso, com prazo: se o leg `macos-15-intel` ainda estiver "Queued" 30 minutos depois que os outros legs terminaram (`gh run view <run-id> --json jobs`), cancele o run (`gh run cancel <run-id>`) e siga o caminho "sem runner". Nesse caso, ou se a perna falhar por falta de wheel, tire o leg da matriz num commit `ci: launcher-smoke sem Mac Intel (sem runner)` e registre no corpo do PR "Mac Intel: não suportado"; a Task 18 e a Task 23 levam isso ao README e ao CHANGELOG. Falha nos outros legs se corrige antes do merge.

### Fechamento do PR 4

- [ ] Verificação padrão + `uv lock --check` + manifests + `shellcheck` local, se houver.
- [ ] Push, `gh pr create --title "feat!: plugin único — lançador (PR 4/5 da 0.71.0)"`; CI verde, inclusive os três legs do `launcher-smoke` (ou dois, com o Intel declarado); merge. A janela de exposição começa no merge do PR 1, não aqui: instalações novas pelo marketplace pegam a `main` (sem o MCP do qmd, com D5, com o número 0.70.3) desde então; o PR 4 só acrescenta o lançador, que é a janela descrita na spec (§Spikes e gates pré-corte). Quem já tem o plugin fica no cache até a versão mudar. Siga sem pausa para o S-canal e o PR 5.

---

## Gate S-canal (manual, máquina do dono; depois do merge do PR 4, antes do PR 5 e do bump)

Não é task de agente. O orquestrador pede ao dono e registra o resultado (vai para o PR 5 e para a ADR-0038). Pré-condição: `/plugin uninstall par` e apagar `~/.claude/plugins/cache/prumo-assistant-for-researcher/par/`.

Na aba Code do Desktop:

1. `/plugin install par --marketplace raphaelfh/prumo-assistant-for-researcher` instala.
2. Numa sessão nova, `command -v prumo` → `<raiz>/shims/prumo` (o hook em forma exec rodou).
3. Aparecem as tools `mcp__plugin_par_prumo__*`.
4. `prumo --version` = versão do bloco runtime.
5. Com o sandbox do Bash ligado, o 1º `prumo` depois do MCP funciona.
6. Num pj com o `settings.json` do template, o auto-update aparece ligado em + → Plugins.

Se falhar (spec §Spikes e gates pré-corte):
- (1) → a trilha do README (Task 18) e do onboarding (Task 19) usa a interface (+ → Plugins → Add plugin), com 1 passo a mais.
- (2) → antes do PR 5, um PR curto troca o `hooks/hooks.json` para a forma shell com o placeholder entre aspas duplas (`"command": "/bin/sh \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\""`, sem `args`) e ajusta `test_hooks_json_so_sessionstart_em_forma_exec`.
- (6) → a Task 15 ganha, num PR curto antes do PR 5, a instrução de ligar "Enable auto-update" no `/par:start`.

O S-cowork e o S-sync são opcionais e não bloqueiam nada.

---

## PR 5 — Documentação, ADR-0038 e constitution 1.2.3 (Tasks 18–23)

Branch `docs/plugin-unico-5-docs`, a partir de `main` com o PR 4 e o S-canal registrado. Merge só com aprovação explícita do dono (constitution).

### Task 18: README

**Files:** Modify `README.md`

- [ ] Aplicar a spec §Componentes, "Documentação", bullet `README.md`, com âncoras por seção (a Spec B já mexeu em §"Pré-requisitos externos"):
  - §"Para pesquisadores (Desktop/Cowork, sem terminal)" vira §"Para pesquisadores (app Claude, aba Code)", com a trilha de 3 passos da spec (o passo 2 usa o texto do S-canal: `/plugin install …` se o item (1) passou; senão + → Plugins → Add plugin); o link `#para-pesquisadores-desktopcowork-sem-terminal` de §Instalação passa a `#para-pesquisadores-app-claude-aba-code`;
  - superfícies: Cowork e chat só com julgamento; Windows (inclusive WSL) sem suporte; Mac Intel conforme o gate da Task 17;
  - atualização: saem o bloco `uv tool install …`, o "Atualizar depois: `uv tool upgrade …`" e o `/reload-plugins` de §Releases; fica a frase da spec ("o PAR se atualiza sozinho nos projetos criados ou atualizados a partir da 0.71.0; …");
  - dependências: qmd como CLI em §MCP (sai o servidor) e na linha `qmd` de §"Pré-requisitos externos" (`npm install -g @tobilu/qmd`); `uv` sem piso numérico. Em §MCP, o bullet do `qmd` dá lugar a um bullet do servidor `prumo`: sobe pelo lançador (`/bin/sh ${CLAUDE_PLUGIN_ROOT}/shims/prumo mcp serve`), as tools aparecem como `mcp__plugin_par_prumo__*` e não há nada a instalar além do `uv`; abaixo dele, a nota "qmd é CLI opcional (ver [Pré-requisitos externos](#pré-requisitos-externos)); não há servidor MCP do qmd no plugin.";
  - dev: a nota de `PRUMO_ZOTERO_BASE` marcada como variável de dev;
  - §Desinstalar (nova): `/plugin uninstall par`; `rm -rf ~/.cache/prumo`; e, só se nada mais os usa, `uv cache clean` e `uv python uninstall 3.12` (~70 MB).
- [ ] `uv run python .github/scripts/gen_indexes.py --check`; `grep -n "uv tool\|reload-plugins\|Desktop/Cowork" README.md` vazio.
- [ ] Commit `docs(readme): trilha pela aba Code, plugin como única distribuição, desinstalação limpa`.

### Task 19: Onboarding e `docs/_index.md`

**Files:** Modify `docs/onboarding-pesquisador.md`, `docs/_index.md` (fora dos blocos gerados)

- [ ] `docs/onboarding-pesquisador.md`: todos os itens da spec §Documentação, bullet `docs/onboarding-pesquisador.md` (`title:` do frontmatter, `cowork` fora das `tags`, H1, introdução e §1, §2, §3, §6 "Busca no seu wiki", §6 "Conectores de literatura", §"Trilha dev", §"Kit do piloto"), com âncoras por seção (a Spec B reescreveu parte da §4 e da §6). Se o S-canal (1) falhou, a §1 usa a trilha pela interface. A lista da spec não cita a §5 "O que é opcional (e o que não é)", mas o bullet dela ("qmd … exige `bun` instalado") contradiria A9 e as §3/§6 novas: ele passa a "**qmd** (busca semântica no seu wiki) é opcional — `npm install -g @tobilu/qmd` (ou bun); na aba Code o próprio Claude roda a busca." Depois, `grep -n "bun" docs/onboarding-pesquisador.md` deve achar só o "(ou bun)" da §5; outro acerto que não venha da Spec B (§4 e receita do 54yyyu) é resto da trilha antiga e segue a mesma troca para `npm install -g @tobilu/qmd`.
- [ ] `docs/_index.md`: as duas frases do onboarding passam ao texto da spec ("Sou pesquisador — como começo pelo app Claude (aba Code)?" e "… — trilha do pesquisador pelo app Claude (aba Code) + kit do piloto da Fase 2.").
- [ ] `uv run python .github/scripts/gen_indexes.py` (o `kb-index` pega o `title:` novo); verificação padrão.
- [ ] Commit `docs(onboarding): trilha do pesquisador pelo app Claude, aba Code`.

### Task 20: RELEASING, regra de release e CLAUDE.md

**Files:** Modify `RELEASING.md`, `.claude/rules/release.md`, `CLAUDE.md`

- [ ] `RELEASING.md`: spec §Release e migração, "`RELEASING.md` (muda só a documentação, sem bump)" — regra-mãe; passo 3 com o bloco `uv run` dos dois scripts; passo 4 com `uv run python .github/scripts/gen_indexes.py --check`; passo 6 com `git add … skills agents`; passo 8 e §"Como consumidores aplicam" com o texto novo (saem `/reload-plugins` e `uv tool upgrade`); nota nova no passo 2 sobre `uv.lock`/`shims/prumo` e os ~60 MB.
- [ ] `.claude/rules/release.md`: depois da linha da fonte única de versão, a linha literal da spec ("A versão no bloco `prumo:runtime` (portas, `start`, `agents/reader.md`) é escrita só pelo `gen_indexes.py` (RELEASING, passos 3, 4 e 6).").
- [ ] `CLAUDE.md`, §"Armadilhas deste repo": os três bullets alterados e os três novos da spec §Documentação, bullet `CLAUDE.md`, literais.
- [ ] Commit `docs(release): gen_indexes carimba a versão; consumidores abrem uma sessão nova`.

### Task 21: ARCHITECTURE e ROADMAP

**Files:** Modify `ARCHITECTURE.md`, `ROADMAP.md`

- [ ] `ARCHITECTURE.md` (âncoras por texto): spec §Documentação, bullet `ARCHITECTURE.md` — box do core sem `uvx`; linha do `.mcp.json`; `shims/` e `hooks/` no mapa; sai `integrations/`; nota de `agents/`; item 3 de §"Como contribuir"; sai "Integration" do glossário.
- [ ] `ROADMAP.md`: spec §ADRs e emendas, "ROADMAP" — célula de status da linha `| F5 |`, bullet "**Sem multi-host.**" e a entrada nova "**Sem Windows**", literais.
- [ ] `grep -n "integrations\|BaseIntegration\|uvx" ARCHITECTURE.md` vazio; verificação padrão.
- [ ] Commit `docs: ARCHITECTURE e ROADMAP com o lançador, sem integrations, F5 reaberta e entregue`.

### Task 22: ADR-0038 e constitution 1.2.3

**Files:** Create `docs/adr/adr-0038-plugin-unica-distribuicao.md`; Modify `docs/constitution.md`

- [ ] ADR-0038 no formato das ADRs do repo (H1 `# ADR-0038 — O plugin é a única distribuição: launcher roda o CLI desta raiz, travado no uv.lock`; `- Status:`, `- Data:` do PR, `- Origem: [[2026-10-02-plugin-distribuicao-unica-design]]`; seções Contexto, Decisão, Consequências), com todo o conteúdo de spec §ADRs e emendas, "ADR-0038 (nova)": contexto; decisão A1–A15 e A17 (A16 só aponta a Spec B); trade-off do `CLAUDE_PLUGIN_DATA` e a limpeza na desinstalação; "Supersede em parte" (ADR-0019, 0017, 0026, 0026:23, 0033:21, 0032:25, 0018, 0034:17 e a spec do Zettlr); "Complementa" (ADR-0010, ADR-0026:29); alternativas rejeitadas. **Status:** `aceito` se o S-canal e o `launcher-smoke` (com o leg Intel, ou com o Mac Intel declarado sem suporte) estão verdes no registro do gate; senão `proposta`, e o corte da 0.71.0 espera.
- [ ] `docs/constitution.md` (spec §ADRs e emendas, "Constitution 1.2.2 → 1.2.3 (PATCH)"): linhas de Distribuição e Stack externa, Princípio III sem "via seu `BaseIntegration`", Princípio I intocado, entrada nova no topo do Sync impact report (1ª linha com a data do merge; a 1.2.2 passa a "Anterior:"), e "Versão atual: **1.2.3** (<data do merge>)".
- [ ] `uv run python .github/scripts/gen_indexes.py` (o `adr-index` pega a ADR-0038); verificação padrão.
- [ ] Commit `docs(adr): ADR-0038 e constitution 1.2.3 — o plugin é a única distribuição`.
- [ ] **Revisão humana obrigatória:** o PR 5 só faz merge com "aprovado" explícito do dono no chat, citando a emenda da constitution.

### Task 23: Verificação final, CHANGELOG e índices

**Files:** Modify `CHANGELOG.md`; Move `docs/superpowers/plans/2026-10-02-plugin-distribuicao-unica.md` → `docs/superpowers/plans/archive/`

- [ ] **CHANGELOG — bullets:** em `## [Não publicado]`, os bullets do bloco de spec §Release e migração, "Notas do CHANGELOG (parte da Spec A; a Spec B traz as dela)", copiados literalmente. O Plan 2 (PR 3) já abriu `### Alterado` e `### Removido` com os bullets da Spec B: os da Spec A entram nessas duas, depois dos da Spec B (sem seção duplicada). Em seguida, depois de `### Removido` e nesta ordem, crie `### Adicionado`, `### Corrigido` e `### Documentação` com os bullets da Spec A. Se alguma dessas três já existir, use-a. Se o gate da Task 17 tirou o Mac Intel, o bullet "Mac Intel: `cryptography` < 49 …" de "Corrigido" dá lugar, em "Alterado", a "**⚠ Breaking — Mac Intel declarado sem suporte** (sem runner de CI para validar o lançador)".
- [ ] **CHANGELOG — migração:** depois de `### Documentação`, ainda em `## [Não publicado]`, a seção `### Para atualizar (uma vez, na 0.71.0)` com a lista de spec §Release e migração, "Migração de quem já usa": a frase de abertura sobre a ordem ("A ordem importa: o perfil do Zettlr é regenerado antes de remover o CLI antigo, …") e os itens 1–7 copiados literalmente, na ordem da spec (Zettlr no item 3, antes do `uv tool uninstall` do item 4; Zotero da Spec B no item 7). É daqui que as notas da release saem (RELEASING, passo 7); o Plan 2 não grava esta lista. Se o gate da Task 17 tirou o Mac Intel, nada muda nesta lista.
- [ ] **Arquivar este plano:** `git mv` para `docs/superpowers/plans/archive/`, com frontmatter de fechamento no formato dos arquivados (`status: implemented`, `verified: <data>`, `release: "pendente — 0.71.0 MINOR ⚠ (corte único, RELEASING.md)"`, `spec: "[[2026-10-02-plugin-distribuicao-unica-design]]"`) e o parágrafo `> **Fechamento (<data>).** …` resumindo o que foi entregue, o resultado do S-canal e do `launcher-smoke`.
- [ ] **Índices:** `uv run python .github/scripts/gen_indexes.py`.
- [ ] **Verificação completa:**
  ```bash
  uv run pytest -q
  uv run ruff check . && uv run ruff format --check .
  uv run mypy
  uv run python .github/scripts/gen_indexes.py --check
  uv lock --check
  uv run --with jsonschema==4.23.0 python .github/scripts/validate_manifests.py
  python3 .github/scripts/sync_manifest_version.py --check
  ```
  e as varreduras de código e texto de produto (todas vazias): `grep -rn "uv tool install\|uv tool upgrade" skills agents src templates`; `grep -rn "integrations\|IntegrationError\|uvx\|refchecker\|zettlr-export\|zettlr_export_entry" src skills agents pyproject.toml`; `grep -rn "mcp__qmd__\|No such command" skills agents`; `grep -rn "\$CLAUDE_PLUGIN_ROOT" skills agents | grep -v '\${CLAUDE_PLUGIN_ROOT}'`. Em `tests`, `grep -rn "integrations\|IntegrationError\|uvx\|refchecker\|zettlr-export\|zettlr_export_entry" tests` só acha as asserções de ausência das Tasks 2, 9 e 10 (`test_par_nao_exporta_integration_error`, `test_init_creates_project_structure`, `test_modulo_sem_camada_profunda`, `test_zettlr_export_entry_nao_existe`, `test_pyproject_sem_console_script_do_zettlr`); não as apague. `templates/` fica fora da 2ª varredura por causa do `uvx marimo edit` do módulo notebooks, que não é do PAR.
- [ ] **Smoke pelo lançador:**
  ```bash
  export PRUMO_CACHE_DIR="$TMPDIR/pc" UV_CACHE_DIR="$TMPDIR/uvcache" UV_PYTHON_INSTALL_DIR="$TMPDIR/uvpython"
  sh shims/prumo --version                                   # prumo <__version__>
  sh shims/prumo init "$TMPDIR/pj_final" --yes --json        # sem "integrations"
  test -f "$TMPDIR/pj_final/.claude/settings.json" && test ! -e "$TMPDIR/pj_final/.claude/skills"
  sh shims/prumo doctor "$TMPDIR/pj_final" --json            # "ok": true
  sh shims/prumo update "$TMPDIR/pj_final" --dry-run --json  # "plugin_copies": []
  ```
- [ ] Commit `docs: CHANGELOG da 0.71.0 (Spec A); arquiva o plano`.

### Fechamento do PR 5

- [ ] Push, `gh pr create --title "docs: plugin único — docs, ADR-0038 e constitution 1.2.3 (PR 5/5 da 0.71.0)"`, com o registro do S-canal no corpo; CI verde; aprovação explícita do dono; merge.
- [ ] Entrega ao orquestrador: `main` pronto para o corte da 0.71.0 pelos 8 passos do `RELEASING.md` emendado (o bump recarimba o bloco runtime pelo passo 3).
