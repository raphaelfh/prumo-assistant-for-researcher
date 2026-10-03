---
status: approved
spec: "[[2026-10-02-ponte-zotero-minima-design]]"
release: "0.71.0 MINOR (corte único com a Spec A)"
---

# Ponte Zotero mínima — parte 0.71.0 (aposentadoria, sonda única, `connect`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** entregar a parte 0.71.0 da Spec B: saem `prumo paper sync-annotations`, `sync-notes`, `sync-all`, a tool MCP `paper_sync_all` e tudo o que só eles usavam (D2 do dono); o `doctor` passa a usar uma única sonda ao Better BibTeX e deixa de exigir o toggle "Allow other applications"; o `connect` ganha transporte próprio e mensagens que dizem a causa real (inclusive no sandbox do Claude Code); o modo `paper library` roteia "o que eu anotei" para fora do PAR, só por texto.

**Architecture:** tudo o que é Zotero e não é de domínio fica em `src/par/core/deps.py` (`zotero_base()`, `bbt_rpc_url()` e `in_claude_sandbox()`, que já vêm da 0.70.3, mais a sonda nova `_bbt_probe()`). `domains/paper/connect.py` importa de `core` e ganha um `_http_post_json` de ~10 linhas de `urllib`, com o mesmo nome de seam; `domains/paper/zotero.py` e `sync_all.py` são apagados. Nenhum domínio importa outro. As skills mudam só no texto (fonte em `skills/paper/modes/library.md`; a porta `skills/paper/SKILL.md` é regerada).

**Tech Stack:** Python 3.11/3.12, Typer, Rich (`core/output.Console`), `urllib` da stdlib (ADR-0007), FastMCP (`mcp_server.py`), pytest, ruff, mypy `--strict`.

**Spec:** `docs/superpowers/specs/2026-10-02-ponte-zotero-minima-design.md` — decisões B9, B10, B11 e B12; §Componentes "0.71.0 MINOR ⚠"; §Erros E10–E18; §Testes "0.71.0"; §"Release e migração" (bloco 0.71.0); §"Spikes e gates pré-merge" (G3). Sequência de PRs: Spec A (`2026-10-02-plugin-distribuicao-unica-design.md`) §"Release e migração" → §Sequência, **PR 3**; A16 da Spec A só referencia este trabalho.

## Global Constraints

- **Pré-requisito duro:** a 0.70.3 (parte 0.70.3 da Spec B) está em `main`. Este plano consome `core/deps.zotero_base()`, `bbt_rpc_url()`, `in_claude_sandbox()`, a linha `pandoc` do doctor, a fixture `_no_real_pandoc` do `tests/unit/conftest.py` e a ADR-0037. A Task 1 confere; sem isso, pare e reporte.
- **Ordem na Spec A:** este é o PR 3 da 0.71.0. Não há dependência de código com os PRs 1 e 2 da Spec A, mas há sobreposição de arquivos: o PR 1 mexe em `core/deps.py` (docstring e hint do qmd), `tests/unit/core/test_deps.py` (asserções do qmd), `tests/unit/core/test_skills.py`, `docs/Research Project Structure.md` e `tests/unit/test_pj_base_integration.py`; o PR 2 mexe em `paper/cli.py` e `mcp_server.py` (`--deep`) e em `templates/pj_base/docs/project_guide.md`. Tire o branch de `main` depois do merge do PR 2 (a Task 1 confere). Nunca edite `docs/actions-by-context.md` (o PR 1 da Spec A o apaga) nem `skills/start/SKILL.md` (o item 3 da trilha, com o texto fixado na Spec B §Componentes 0.71.0 "Item 3 da trilha do `/par:start`", é gravado pelo PR 4 da Spec A, que reescreve a trilha inteira).
- **Números de linha da Spec B são de antes da 0.70.3 e dos PRs 1–2 da Spec A.** Localize sempre pelo texto-âncora citado aqui, nunca pelo número.
- **Sem bump de versão.** Não toque em `src/par/_version.py`, `plugin.json`, `marketplace.json` nem `CITATION.cff`. O corte da 0.71.0 é feito depois, pelo orquestrador, seguindo os 8 passos do `RELEASING.md`.
- **Layering:** `core/` nunca importa `domains/`; `domains/paper` importa `core`; nenhum domínio importa outro.
- **Fachadas finas:** `cli.py` só faz parsing, chamada do domínio e saída; todo subcomando segue envolto em `core/cli_op.cli_run(...)`; nada de `print()`, sempre `core/output.Console`.
- **Tipagem:** `from __future__ import annotations` em todo módulo; `mypy --strict` vale também para `tests/` (`pyproject.toml`: `files = ["src/par", "tests"]`), então todo teste novo é anotado (`-> None`, `monkeypatch: pytest.MonkeyPatch`, `tmp_path: Path`). Value objects são `@dataclass(frozen=True)`.
- **Mensagens:** pt-BR, com o comando de correção dentro. Os textos E10–E17 abaixo são verbatim da Spec B §Erros; `{base}` é `zotero_base()`. Strings longas são quebradas por concatenação implícita (linha ≤ 100).
- **Dependência externa só nos seams:** nenhum teste fala com o Zotero real. Seams: `par.core.deps._bbt_probe`, `par.core.deps.urllib.request.urlopen`, `par.domains.paper.connect._http_post_json`, `par.domains.paper.connect.urllib.request.urlopen`. A Task 5 acrescenta a fixture `autouse` `_no_real_bbt_probe`, que neutraliza a sonda em toda a suíte; os testes da própria sonda usam a função real guardada na coleta (`_REAL_BBT_PROBE`).
- **Sandbox do agente:** o Bash deste ambiente roda com `SANDBOX_RUNTIME=1`. Testes da variante normal não podem depender do ambiente: a fixture `autouse` `_outside_claude_sandbox` (da 0.70.3; a Task 2 a cria só se faltar) remove a variável, e os testes da variante sandbox fazem `monkeypatch.setenv("SANDBOX_RUNTIME", "1")`.
- **Rich quebra linhas em 80 colunas** fora de TTY (medido: o E17 sai em 4 linhas). Teste de CLI que confere mensagem longa compara com espaços normalizados: `" ".join(texto.split()) in " ".join(result.output.split())`.
- **Comandos** (prefixo obrigatório neste ambiente): `UV_CACHE_DIR="$TMPDIR/uvcache" uv run …`. Abreviado abaixo como `$UVR`, que é **abreviação de texto, não variável de shell**: escreva sempre o prefixo por extenso (atribuição de ambiente vinda de variável expandida não vale no shell). Ex.: `SANDBOX_RUNTIME=1 $UVR pytest` = `SANDBOX_RUNTIME=1 UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest`; `$UVR --with jsonschema==4.23.0 python …` = `UV_CACHE_DIR="$TMPDIR/uvcache" uv run --with jsonschema==4.23.0 python …`.
- **Blocos gerados** (`skills/*/SKILL.md`, `README.md`, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`) só mudam via `$UVR python .github/scripts/gen_indexes.py`.
- **ADRs aceitas são imutáveis.** As emendas às ADR-0008, ADR-0020 e ADR-0026 já estão no item 7 da ADR-0037 (entrou na 0.70.3); este plano não edita ADR nenhuma.
- **Commits:** estilo do repo (`feat(paper)!: …`, `docs: …`), mensagem em pt-BR, terminando com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Cada task fecha com a suíte verde.
- **"Verde" = sem falha nova.** A Task 1 (Step 4) anota as falhas e os skips que já existem em `main`. "Suíte verde" neste plano quer dizer: nenhuma falha nova em relação a essa linha de base, e os testes que a task criou passando.
- **Branch e PR:** um único PR para as Tasks 2–8 (sugestão de branch: `feat/ponte-zotero-minima-0710`), título "PR 3 da 0.71.0: ponte Zotero mínima (Spec B, parte 0.71.0)".

## File Structure

| Arquivo | Ação | Responsabilidade | Task |
|---|---|---|---|
| `tests/unit/conftest.py` | Modificar | fixture `autouse` `_outside_claude_sandbox` (só se a 0.70.3 não a criou) (T2); fixture `autouse` `_no_real_bbt_probe` (T5) | 2, 5 |
| `src/par/domains/paper/connect.py` | Modificar | `_http_post_json` próprio, `bbt_rpc_url()`, `_offline_msg()` (E15), Guarda 1 (E16), `EXPORT_PENDING_HINT` (E17), docstrings | 2 |
| `src/par/domains/paper/cli.py` | Modificar | dica de `exported=False` (T2); saem `sync-annotations`, `sync-notes`, `sync-all` e imports (T3) | 2, 3 |
| `tests/unit/paper/test_connect.py` | Modificar | E15 normal/sandbox, transporte, E16 | 2 |
| `tests/unit/paper/test_cli.py` | Modificar | E17 (T2); saem 2 testes, entram `--help` e "No such command" (T3) | 2, 3 |
| `src/par/domains/paper/zotero.py` | Apagar | — | 3 |
| `src/par/domains/paper/sync_all.py` | Apagar | — | 3 |
| `src/par/domains/paper/api.py` | Modificar | saem `sync_all`, `sync_annotations`, `sync_notes` | 3 |
| `src/par/domains/paper/errors.py` | Modificar | sai `ZoteroApiError` | 3 |
| `src/par/domains/paper/__init__.py` | Modificar | sai a linha `annotations` da docstring | 3 |
| `src/par/mcp_server.py` | Modificar | sai `paper_sync_all`; docstring 6 tools `paper`, prefixo do plugin | 3 |
| `tests/unit/paper/test_zotero.py`, `test_zotero_notes.py`, `test_sync_all.py`, `test_zotero_client.py` | Apagar | — | 3 |
| `tests/unit/paper/test_api.py` | Criar | superfície pública sem os nomes aposentados | 3 |
| `tests/unit/test_mcp_server.py` | Modificar | 10 tools | 3 |
| `tests/unit/core/test_cli_op.py` | Modificar | docstring do exemplo | 3 |
| `src/par/core/note_paths.py` | Modificar | sai `child_note_path`; docstring do layout | 4 |
| `src/par/domains/paper/lint.py` | Modificar | sai a regra 7 `duplicate_item_key` | 4 |
| `tests/unit/core/test_note_paths.py`, `tests/unit/paper/test_lint.py` | Modificar | — | 4 |
| `src/par/core/deps.py` | Modificar | `_BbtProbe`, `_bbt_probe()`, linha `zotero` (E10–E14), saem as sondas da API local | 5 |
| `tests/unit/core/test_deps.py`, `tests/unit/test_cli_doctor.py` | Modificar | estados da sonda e da linha `zotero` | 5 |
| `skills/paper/modes/library.md` | Modificar | roteamento B12, frase, árvore, §8, Guarda 1 | 6 |
| `skills/paper/SKILL.md` | Regerar | blocos gerados (frase nova) | 6 |
| `tests/unit/core/test_skills.py` | Modificar | guardas de texto das skills | 6 |
| `README.md`, `ARCHITECTURE.md`, `docs/Research Project Structure.md`, `docs/onboarding-pesquisador.md` | Modificar | docs da 0.71.0 | 7 |
| `templates/pj_base/docs/references/_references.bib`, `templates/pj_base/docs/project_guide.md` | Modificar | cabeçalho do `.bib`; "Keep updated" sai | 7 |
| `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md` | Modificar | `status: superseded` | 7 |
| `tests/unit/test_pj_base_integration.py` | Modificar | template novo segue placeholder | 7 |
| `CHANGELOG.md`, `docs/_index.md`, este plano | Modificar / regerar / arquivar | fechamento | 8 |

## Dependências entre tasks

Task 1 → Task 2 → Task 3 → (Task 4 ∥ Task 5) → Task 6 → Task 7 → Task 8.

- Task 3 depende da 2: o `connect` deixa de importar `zotero.py` antes de ele ser apagado.
- Tasks 4 e 5 dependem da 3: `child_note_path` e `zotero_local_api_up` só têm consumidor em `zotero.py`.
- Task 6 depende das 2 e 3 (o texto da skill cita E16/E17 e não pode citar comando apagado).
- Task 7 depende da 5 (a doc diz que o toggle saiu).

---

### Task 1: Pré-condições (sem commit)

**Files:** nenhum (só leitura).

- [ ] **Step 0: dependências de dev.** `pytest`, `mypy` e `ruff` estão em `[project.optional-dependencies] dev`, e um worktree novo não as tem (`uv run pytest` falha com "Failed to spawn: `pytest`"). Rode uma vez, como o CI:
  ```sh
  UV_CACHE_DIR="$TMPDIR/uvcache" uv sync --frozen --extra dev
  ```
- [ ] **Step 1: 0.70.3 em `main`.** Rode:
  ```sh
  grep -cE "^def (zotero_base|bbt_rpc_url|in_claude_sandbox|pandoc_path)\(" src/par/core/deps.py
  ```
  Esperado: `4`. Menos que isso → PARE e reporte "0.70.3 ausente de main; o PR 3 depende dela".
- [ ] **Step 2: ADR-0037 com as emendas.** Rode:
  ```sh
  test -f docs/adr/adr-0037-ponte-zotero-minima.md && grep -c "ADR-0008:\*\*\|ADR-0020:\*\*\|ADR-0026:\*\*\|paper_sync_all" docs/adr/adr-0037-ponte-zotero-minima.md
  ```
  Esperado: arquivo presente e contagem ≥ 4 (as três emendas do item 7 e a saída de `paper_sync_all`). Se faltar, PARE: ADR aceita é imutável, e corrigir exige decisão do dono.
- [ ] **Step 2b: PRs 1 e 2 da Spec A em `main`.** Rode:
  ```sh
  test ! -e src/par/core/uvx.py && test ! -e docs/actions-by-context.md && echo ok
  ```
  Esperado: `ok` (o PR 1 apaga `docs/actions-by-context.md`; o PR 2 apaga `core/uvx.py`). Se não imprimir `ok`, PARE e espere o merge do PR 2; se o branch já existir, faça rebase em `main` antes de abrir o PR. Os arquivos se sobrepõem (Global Constraints, "Ordem na Spec A").
- [ ] **Step 3: receita do onboarding.** `grep -n "### Perguntar ao seu Zotero" docs/onboarding-pesquisador.md`. Anote o resultado: se não houver, a Task 7 (Step 5) a inclui; o modo `library` aponta para essa seção.
- [ ] **Step 4: linha de base.** Em `main`, antes de qualquer mudança, rode:
  ```sh
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest -q
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run mypy
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff check . && UV_CACHE_DIR="$TMPDIR/uvcache" uv run ruff format --check .
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run python .github/scripts/gen_indexes.py --check
  ```
  Anote as falhas e os skips do `pytest` que já existem (os skips de "pandoc ausente" dependem do pandoc da máquina). Essa é a linha de base de "verde" (Global Constraints). Se `mypy`, `ruff` ou `gen_indexes --check` não estiverem limpos, PARE e reporte: a falha não é deste plano, e a conferência com `git diff --stat` da Task 6 (Step 4) supõe os índices em dia.
- [ ] **Step 5: fixture de sandbox.** `grep -n "_outside_claude_sandbox" tests/unit/conftest.py`. A 0.70.3 (Task 2, Step 1 do plano dela) cria essa fixture `autouse`, que faz `delenv("SANDBOX_RUNTIME")`. Se ela existir, a Task 2 pula o Step 1; só se faltar, a Task 2 a cria, com esse mesmo nome.

---

### Task 2: `connect` com transporte próprio e mensagens pela causa real (B11; E15, E16, E17)

**Files:**
- Modify: `src/par/domains/paper/connect.py`, `src/par/domains/paper/cli.py` (só o `connect_command`), `tests/unit/conftest.py` (se faltar a fixture)
- Test: `tests/unit/paper/test_connect.py`, `tests/unit/paper/test_cli.py`

**Interfaces:**
- Consumes: `par.core.deps.zotero_base() -> str`, `par.core.deps.bbt_rpc_url() -> str`, `par.core.deps.in_claude_sandbox() -> bool` (0.70.3).
- Produces:
  - `connect._http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object` (mesmo nome e assinatura do seam atual; implementação própria com `urllib`).
  - `connect._offline_msg() -> str` (substitui a constante `_OFFLINE_MSG`, que sai).
  - `connect.EXPORT_PENDING_HINT: str` (E17).
  - `connect` deixa de ter o atributo `zotero` (sai `from par.domains.paper import zotero`).

Textos verbatim (Spec B §Erros):

- **E15** (`_offline_msg()`, fora do sandbox): `O Zotero não respondeu em {base}. Abra o Zotero (com o Better BibTeX), confira com `prumo doctor` e repita o comando.`
- **E15** (dentro do sandbox, `in_claude_sandbox()`): `O sandbox do Claude Code não deixa o `prumo paper connect` falar com o Zotero em {base}. Peça para repetir o comando fora do sandbox (o Claude pede permissão). Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`.`
- **E16** (`AlreadyConnectedError`): `docs/references/_references.bib já tem entradas: conectar agora poderia sobrescrevê-lo com a coleção. Se ele já vem do Better BibTeX (confira no Zotero: Settings → Better BibTeX → Automatic export), rode: prumo paper sync`
- **E17** (`EXPORT_PENDING_HINT`): `O Better BibTeX ainda não gravou o .bib (pode levar alguns segundos). Se ele não aparecer, atualize o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins; as versões anteriores não exportam itens novos com a janela do Zotero fechada), confira em Settings → Better BibTeX → Automatic export e rode: prumo paper sync`

- [ ] **Step 1: fixture neutra de sandbox.** Confirme que `_outside_claude_sandbox` (criada pela 0.70.3) existe em `tests/unit/conftest.py`; nesse caso pule este Step. Só se ela faltar, crie-a com esse mesmo nome (nunca uma segunda fixture com outro nome):
  ```python
  @pytest.fixture(autouse=True)
  def _outside_claude_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
      """A suíte roda igual dentro e fora do sandbox do Claude Code (que define
      ``SANDBOX_RUNTIME=1``). Os testes das variantes de sandbox definem a variável."""
      monkeypatch.delenv("SANDBOX_RUNTIME", raising=False)
  ```
- [ ] **Step 2: testes que falham** em `tests/unit/paper/test_connect.py` (classe nova `TestTransporteEMensagens`, mais o ajuste de um teste existente):
  - `test_zotero_fechado` (existente, em `TestConnectCollection`): `match="abra o Zotero"` → `match="Abra o Zotero"` (o E15 abre a frase com maiúscula; o `match` diferencia caixa).
  - `test_offline_msg_usa_a_base_configurada`: `monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")`; `connect._offline_msg()` contém `"http://example.test:1234"`, `"Abra o Zotero"` e `"prumo doctor"`, e não contém `"sandbox"`.
  - `test_offline_msg_no_sandbox_ensina_excluded_commands`: `setenv("SANDBOX_RUNTIME", "1")`; o texto contém `"sandbox do Claude Code"`, `"sandbox.excludedCommands"`, `'"prumo *"'` e a base.
  - `test_zotero_fechado_no_sandbox`: `setenv("SANDBOX_RUNTIME", "1")`, `_fake_rpc({"user.groups": urllib.error.URLError("refused")})`; `connect_collection(pj, "GynOb")` levanta `ZoteroOfflineError` com `match="sandbox.excludedCommands"`.
  - `test_http_post_json_posta_no_endpoint_do_bbt`: `setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")`; `monkeypatch.setattr("par.domains.paper.connect.urllib.request.urlopen", fake)`, com o fake assinado `def fake(req: urllib.request.Request, timeout: float = 0.0) -> _FakeResp`, em que `_FakeResp` é um context manager (`__enter__` devolve `self`, `__exit__` devolve `None`) com `read() -> bytes` devolvendo `b'{"jsonrpc": "2.0", "result": []}'`. O fake guarda `req.full_url`, `json.loads(req.data)`, `req.get_header("Content-type")` e o `timeout`. Asserções: `connect.list_collections() == []`; URL `== "http://example.test:1234/better-bibtex/json-rpc"`; corpo com `method == "user.groups"` e `params == [True]`; `req.get_header("Content-type") == "application/json"`, com essa grafia: o `urllib.request.Request` normaliza o nome do header com `capitalize()`, e `req.get_header("Content-Type")` devolve `None` mesmo com a implementação certa; `timeout == 10.0`.
  - `test_connect_nao_depende_de_zotero_py`: `assert "zotero" not in vars(connect)`.
  - `test_guarda_1_diz_o_risco_real_e_o_remedio`: bib povoado (mesmo arranjo de `test_bib_povoado_recusa_sem_mutacao`); a mensagem de `AlreadyConnectedError` contém `"sobrescrevê-lo"`, `"Automatic export"` e `"prumo paper sync"`.
- [ ] **Step 3: teste de CLI que falha** em `tests/unit/paper/test_cli.py`: em `test_paper_connect_export_pendente_avisa`, troque `assert "instantes" in result.output` por
  ```python
  def _norm(text: str) -> str:
      return " ".join(text.split())

  assert _norm(connect.EXPORT_PENDING_HINT) in _norm(result.output)
  assert "9.0.65" in connect.EXPORT_PENDING_HINT
  assert "prumo paper sync" in connect.EXPORT_PENDING_HINT
  ```
  (`_norm` como helper de módulo; o Rich quebra o E17 em várias linhas.)
- [ ] **Step 4: rode e veja falhar.** `$UVR pytest tests/unit/paper/test_connect.py tests/unit/paper/test_cli.py -q` → FAIL (`AttributeError: _offline_msg`, `EXPORT_PENDING_HINT`; `match` de caixa; `"zotero" in vars(connect)`).
- [ ] **Step 5: implementar em `connect.py`.**
  - Imports: saem `from par.domains.paper import zotero`; entram `import json`, `import urllib.request` e `from par.core.deps import bbt_rpc_url, in_claude_sandbox, zotero_base`.
  - `_http_post_json` próprio:
    ```python
    def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        """POST JSON-RPC no Better BibTeX; devolve o JSON decodificado.

        Seam de transporte deste módulo: os testes fazem monkeypatch de
        ``par.domains.paper.connect._http_post_json``."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    ```
  - `_rpc` posta em `bbt_rpc_url()` (era `zotero._bbt_rpc()`) e levanta `ZoteroOfflineError(_offline_msg())` nos dois ramos de hoje (`OSError` e resposta não-dict).
  - `_OFFLINE_MSG` vira `_offline_msg()` com os dois textos E15 acima, montados com `base = zotero_base()` e escolhidos por `in_claude_sandbox()`.
  - `EXPORT_PENDING_HINT` (constante de módulo, texto E17).
  - Guarda 1 em `connect_collection`: `AlreadyConnectedError` com o texto E16.
  - Docstrings:
    - módulo (o parágrafo "O seam de transporte é o mesmo de ``zotero.py`` …"): passa a "O seam de transporte é ``_http_post_json`` (JSON-RPC do BBT em ``core.deps.bbt_rpc_url()``, sem autenticação, ``urllib`` da stdlib — ADR-0007); os testes fazem ``monkeypatch.setattr("par.domains.paper.connect._http_post_json", ...)``.";
    - `connect_collection`, Guarda 1: "reconectar às cegas duplicaria o autoexport já configurado" vira "conectar poderia sobrescrever, com a coleção, um ``.bib`` que já tem entradas";
    - `AlreadyConnectedError`: "O bib do projeto já tem entradas reais — conectar poderia sobrescrevê-lo."
- [ ] **Step 6: implementar em `paper/cli.py`** (`connect_command`): o bloco `if not r.exported:` passa a `console.info(connect.EXPORT_PENDING_HINT)`. Nada mais muda no comando.
- [ ] **Step 7: rode e veja passar.**
  ```sh
  $UVR pytest tests/unit/paper/test_connect.py tests/unit/paper/test_cli.py -q
  SANDBOX_RUNTIME=1 $UVR pytest tests/unit/paper/test_connect.py -q   # a fixture neutraliza o ambiente
  $UVR pytest -q && $UVR mypy && $UVR ruff check . && $UVR ruff format --check .
  ```
- [ ] **Step 8: commit** `feat(paper): connect com transporte próprio e mensagens pela causa real (ADR-0037)`.

---

### Task 3: Aposentadoria de `sync-annotations`, `sync-notes`, `sync-all` e `paper_sync_all` (B9, D2 do dono)

**Files:**
- Delete: `src/par/domains/paper/zotero.py`, `src/par/domains/paper/sync_all.py`, `tests/unit/paper/test_zotero.py`, `tests/unit/paper/test_zotero_notes.py`, `tests/unit/paper/test_sync_all.py`, `tests/unit/paper/test_zotero_client.py`
- Modify: `src/par/domains/paper/cli.py`, `src/par/domains/paper/api.py`, `src/par/domains/paper/errors.py`, `src/par/domains/paper/__init__.py`, `src/par/mcp_server.py`, `tests/unit/core/test_cli_op.py`
- Create: `tests/unit/paper/test_api.py`
- Test: `tests/unit/paper/test_cli.py`, `tests/unit/test_mcp_server.py`, `tests/unit/paper/test_api.py`

**Interfaces:**
- Consumes: nada novo.
- Produces (remoções da superfície pública):
  - `par.domains.paper.api.__all__` sem `sync_all`, `sync_annotations`, `sync_notes`;
  - `par.domains.paper.errors` sem `ZoteroApiError`;
  - `mcp_server.server` com 10 tools (4 de revisão, 6 de `paper`); `MUTATING_TOOLS` não muda;
  - `prumo paper` sem os três subcomandos (o Typer responde "No such command"; não entra stub).

- [ ] **Step 1: testes que falham.**
  - `tests/unit/paper/test_api.py` (novo):
    - `test_api_nao_reexporta_o_pipeline_de_anotacoes`: parametrizado em `"sync_all"`, `"sync_annotations"`, `"sync_notes"`: o nome não está em `paper_api.__all__` e `not hasattr(paper_api, nome)` (`from par.domains.paper import api as paper_api`).
    - `test_modulos_aposentados_nao_existem`: parametrizado em `"par.domains.paper.zotero"` e `"par.domains.paper.sync_all"`: `importlib.util.find_spec(mod) is None`.
    - `test_zotero_api_error_saiu`: `from par.domains.paper import errors`; `not hasattr(errors, "ZoteroApiError")`.
  - `tests/unit/paper/test_cli.py`:
    - apague `test_paper_sync_notes_cli_writes_files` e `test_paper_sync_all_cli_runs_offline_sync`;
    - `test_paper_help_nao_lista_comando_aposentado`: parametrizado em `"sync-annotations"`, `"sync-notes"`, `"sync-all"`; `runner.invoke(app, ["paper", "--help"])` com `exit_code == 0`, o nome ausente de `result.output` e `"connect"` presente;
    - `test_paper_comando_aposentado_responde_no_such_command`: mesmo parametrize; `runner.invoke(app, ["paper", cmd, str(tmp_path)])` com `exit_code == 2` e `"No such command"` em `result.output`.
  - `tests/unit/test_mcp_server.py`, `test_server_registers_exactly_the_review_and_paper_tools`: tire `"paper_sync_all"` do conjunto esperado e acrescente `assert len(tools) == 10`.
- [ ] **Step 2: rode e veja falhar.** `$UVR pytest tests/unit/paper/test_api.py tests/unit/paper/test_cli.py tests/unit/test_mcp_server.py -q` → FAIL (nomes ainda exportados, comandos ainda listados, 11 tools).
- [ ] **Step 3: implementar.**
  - `git rm src/par/domains/paper/zotero.py src/par/domains/paper/sync_all.py tests/unit/paper/test_zotero.py tests/unit/paper/test_zotero_notes.py tests/unit/paper/test_sync_all.py tests/unit/paper/test_zotero_client.py` (a cobertura de base URL já está em `test_deps.py` desde a 0.70.3).
  - `paper/cli.py`:
    - sai `zotero,` do `from par.domains.paper import (...)` e sai `from par.domains.paper.sync_all import sync_all as _sync_all`;
    - saem as funções `sync_annotations_command`, `sync_notes_command` e `sync_all_command`, com seus decorators;
    - docstring do módulo: na lista de módulos de domínio, ``zotero`` vira ``connect``.
  - `paper/api.py`: saem os imports de `sync_all` e de `sync_annotations, sync_notes` e as três entradas do `__all__`.
  - `paper/errors.py`: sai a classe `ZoteroApiError`.
  - `paper/__init__.py`: sai a linha ``- ``annotations``  — annotations + child notes do Zotero (API local)`` da docstring.
  - `mcp_server.py`:
    - sai a função `paper_sync_all`, com o decorator;
    - docstring do módulo: "(7 tools, uma delas mutante" vira "(6 tools, uma delas mutante"; "(`mcp__prumo__paper_find`)" vira "(`mcp__plugin_par_prumo__paper_find`)".
  - `tests/unit/core/test_cli_op.py`, docstring de `test_per_command_exit_code_still_applies`: a docstring inteira passa a ser, verbatim (em uma linha passaria de 100 colunas):
    ```python
        """Caso paper connect (Zotero fechado sai com 2): ``exit_code`` fixo pro
        comando inteiro continua valendo."""
    ```
    Não escreva "`exit_code=2` pro comando inteiro" ligado ao `connect`: depois desta task nenhum comando de produção usa `cli_run(exit_code=2)` (o `connect` usa `exit_codes={ZoteroOfflineError: 2, …}`).
- [ ] **Step 4: varredura.**
  ```sh
  grep -rnE "sync_annotations|sync_notes|sync_all|sync-annotations|sync-notes|sync-all|ZoteroApiError|paper\.zotero|import zotero" src tests \
    | grep -v -e tests/unit/paper/test_api.py -e tests/unit/paper/test_cli.py
  ```
  Esperado: só três sobras, que são de outras tasks: a docstring de `src/par/core/note_paths.py` (`sync-annotations`/`sync-notes`, Task 4), o `required_by` da linha `zotero` em `src/par/core/deps.py` (Task 5) e o `required_by=["paper sync-annotations"]` de `tests/unit/test_cli_doctor.py` (Task 5). Os dois arquivos excluídos pelo `grep -v` são os testes-guarda desta task, que trazem os nomes aposentados como literais nas asserções de ausência: não os apague nem os enfraqueça. Para conferir os guardas, rode a varredura sem o `grep -v`: as linhas extras devem estar só em `test_api.py` e nos parametrize de `test_cli.py`. (`skills/` e as docs mudam nas Tasks 6 e 7.)
- [ ] **Step 5: rode e veja passar.** `$UVR pytest -q && $UVR mypy && $UVR ruff check . && $UVR ruff format --check .`
- [ ] **Step 6: commit** `feat(paper)!: anotações e notas do Zotero saem do PAR (ADR-0037)`.

---

### Task 4: `child_note_path` e a regra `duplicate_item_key` saem (B9)

**Files:**
- Modify: `src/par/core/note_paths.py`, `src/par/domains/paper/lint.py`
- Test: `tests/unit/core/test_note_paths.py`, `tests/unit/paper/test_lint.py`

**Interfaces:**
- Produces: `par.core.note_paths` sem `child_note_path` (`annotations_path` fica: o `migrate-layout` ainda grava `_annotations.md`, decisão do B9); `paper.lint.lint` sem o código `duplicate_item_key`. `src/par/domains/paper/migrate.py` e `tests/unit/paper/test_migrate.py` NÃO mudam.

- [ ] **Step 1: testes que falham.**
  - `tests/unit/core/test_note_paths.py`: sai `child_note_path` do import e sai `test_child_note_path_with_itemkey_and_slug`; entra `test_child_note_path_aposentado`: `from par.core import note_paths`; `not hasattr(note_paths, "child_note_path")`. `test_annotations_path` fica.
  - `tests/unit/paper/test_lint.py`: saem `test_lint_flags_duplicate_item_key` e `test_lint_no_duplicate_when_item_keys_distinct`; entra `test_lint_nao_audita_notas_legadas_do_zotero`, com o mesmo arranjo do primeiro (duas `note__ABCD1234__*.md` com o mesmo `zotero_item_key`): nenhuma issue com `code == "duplicate_item_key"` e `report["ok"] is True`.
- [ ] **Step 2: rode e veja falhar.** `$UVR pytest tests/unit/core/test_note_paths.py tests/unit/paper/test_lint.py -q` → FAIL.
- [ ] **Step 3: implementar.**
  - `note_paths.py`: sai `child_note_path`. Na docstring do módulo, as linhas de `_annotations.md` e `note__<itemKey>__<slug>.md` viram:
    ```
    - `_annotations.md` — legado: só o `prumo paper migrate-layout` grava, ao separar o bloco de anotações de uma nota plana antiga
    - `note__*.md` — legado, só leitura
    ```
    Na mesma edição, a referência final `Spec:` / `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md` ganha o sufixo ` (superseded pela ADR-0037).`, ficando `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md (superseded pela ADR-0037).` (a Task 7 marca essa spec como `superseded`).
  - `lint.py`: sai o bullet "duplicate_item_key — …" da docstring e sai o bloco `# 7. itemKey duplicado entre child notes …` inteiro (até antes de `return _report(issues)`).
- [ ] **Step 4: rode e veja passar.**
  ```sh
  grep -rn "child_note_path\|duplicate_item_key" src tests \
    | grep -v -e tests/unit/core/test_note_paths.py -e tests/unit/paper/test_lint.py
  ```
  Esperado: vazio. Sem o `grep -v`, só aparecem as linhas dos dois testes-guarda desta task (asserções de ausência: `"child_note_path"` em `test_child_note_path_aposentado`, `"duplicate_item_key"` em `test_lint_nao_audita_notas_legadas_do_zotero`); não os apague. Depois, `$UVR pytest -q && $UVR mypy && $UVR ruff check . && $UVR ruff format --check .`
- [ ] **Step 5: commit** `refactor(paper)!: sai a auditoria de notas-filhas do Zotero e o path delas (ADR-0037)`.

---

### Task 5: Doctor com uma sonda só, `_bbt_probe` (B10; E10–E14)

**Files:**
- Modify: `src/par/core/deps.py`, `tests/unit/conftest.py` (fixture `_no_real_bbt_probe`)
- Test: `tests/unit/core/test_deps.py`, `tests/unit/test_cli_doctor.py`

**Interfaces:**
- Consumes: `zotero_base()`, `in_claude_sandbox()`, `_zotero_major()`, `_SUPPORTED_ZOTERO_MAJOR` (já em `deps.py`).
- Produces:
  ```python
  @dataclass(frozen=True)
  class _BbtProbe:
      status: int | None  # None = nada escutando
      zotero_version: str | None  # header X-Zotero-Version, presente até no 404

  def _bbt_probe(timeout: float = 2.0) -> _BbtProbe: ...  # seam; corpo em Spec B §Componentes 0.71.0, "a sonda única"
  ```
  - O `DepStatus` `zotero` mantém nome e formato; `required_by == ["paper connect", "write export --to docx (vínculo com a biblioteca)"]`; `version` = `probe.zotero_version`.
  - Saem `_zotero_api_root`, `zotero_local_api_up`, `_zotero_host_port`, `_zotero_version_header` e o `from urllib.parse import urlparse`.

Estados, nesta ordem (o primeiro que casa decide), com textos verbatim (Spec B §Erros):

| # | Condição | `present` | `detail` | `hint` |
|---|---|---|---|---|
| E10 | `status is None`, fora do sandbox | False | `nada escutando em {base}` | `Abra o Zotero 9 ou mais novo, com o Better BibTeX, e rode: prumo doctor. Só o `prumo paper connect` e o vínculo das citações do docx precisam dele; o resto do PAR funciona sem ele.` |
| E11 | `status is None` e `in_claude_sandbox()` | False | `o sandbox do Claude Code não deixa este comando falar com o Zotero em {base}` | `Peça para repetir fora do sandbox (o Claude pede permissão): prumo doctor. Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`.` |
| E14 | versão conhecida com major < 9 (qualquer `status`, inclusive 404) | False | `Zotero {v} rodando em {base} — abaixo do par suportado (Zotero 9+ com Better BibTeX)` | `Atualize para o Zotero 9+: baixe em https://www.zotero.org/download, instale e reabra o app. Depois atualize o Better BibTeX em Tools → Plugins se ele avisar (o BBT acompanha o major do Zotero).` |
| E12 | `status == 404` | False | `Zotero {v} aberto em {base}, mas o Better BibTeX não respondeu (HTTP 404)`; sem versão: `Zotero aberto em {base}, mas o Better BibTeX não respondeu (HTTP 404)` | `Sem Better BibTeX (ou ainda iniciando — aguarde e rode prumo doctor). Para instalar: baixe o .xpi em https://github.com/retorquere/zotero-better-bibtex/releases e, no Zotero, Tools → Plugins → ⚙ → Install Plugin From File. Depois rode: prumo doctor` |
| E13 | outro `status != 200` | False | `o Zotero respondeu HTTP {code} em /better-bibtex/cayw` | `Reinicie o Zotero e rode: prumo doctor` |
| ✓ | `status == 200` | True | `Better BibTeX respondendo em {base} — Zotero {v}`; sem versão: `Better BibTeX respondendo em {base} (versão não detectada)` | `""` |

- [ ] **Step 1: testes que falham** em `tests/unit/core/test_deps.py`.
  - Import: `from par.core.deps import DepStatus, _BbtProbe, check_external_deps` (sai `zotero_local_api_up`). Ao lado do `_REAL_PANDOC_VERSION = deps._pandoc_version` da 0.70.3 (que já usa `from par.core import deps`), guarde a sonda real na coleta, antes da fixture `autouse` do Step 1b: `_REAL_BBT_PROBE = deps._bbt_probe`. Helper novo:
    ```python
    def _http_error(code: int, version: str | None) -> urllib.error.HTTPError:
        headers = email.message.Message()
        if version is not None:
            headers["X-Zotero-Version"] = version
        return urllib.error.HTTPError("http://x", code, "erro", headers, None)
    ```
  - **Saem:** os 5 testes de `zotero_local_api_up` (`…_false_when_connection_refused`, `…_false_on_timeout`, `…_honors_env_override`, `…_probes_the_api_root`, `…_false_when_local_api_is_disabled`), `test_zotero_version_probe_skipped_when_api_did_not_respond`, `test_doctor_flags_zotero_absent_when_local_api_is_disabled` e o helper `_zotero_running_urlopen`.
  - **Trocam de alvo:** todo `patch("par.core.deps._zotero_api_root", …)` e `patch("par.core.deps._zotero_version_header", …)` restante (inclusive nos testes de `qmd` e nos testes da linha `pandoc` da 0.70.3) vira `patch("par.core.deps._bbt_probe", return_value=_BbtProbe(None, None))` ou o estado que o teste precisa. Fazer patch de atributo apagado levanta `AttributeError`, então apagar o teste não basta. Nesses testes (qmd e pandoc), mude só o alvo do patch e mantenha as asserções como estão em `main`: as do qmd chegam editadas pelo PR 1 da Spec A (o hint exige `npm install -g @tobilu/qmd`, sem `github.com/tobi/qmd`) e as do pandoc vêm da 0.70.3. Não cole asserções antigas nem os esboços da spec por cima.
  - **Reescritos:**
    - `test_zotero_present_when_local_api_answers` → `test_zotero_presente_com_bbt_respondendo`: `_BbtProbe(200, "9.0.6")` → `present`, `version == "9.0.6"`, `"9.0.6"` no `detail`;
    - `test_zotero_absent_hint_mentions_port_and_bbt` → `test_zotero_fechado_e10`: `_BbtProbe(None, None)` → `"23119"` no `detail`, `"Better BibTeX"` e `"prumo doctor"` no `hint`;
    - `test_zotero_check_honors_env_override`: o `seen` esperado vira `["http://example.test:1234/better-bibtex/cayw?probe=true"]`; como passa pela sonda real, o teste restaura-a com `monkeypatch.setattr("par.core.deps._bbt_probe", _REAL_BBT_PROBE)` antes de chamar `check_external_deps()`;
    - `test_zotero_supported_version_stays_present`, `test_zotero_below_floor_flags_unsupported` (`_BbtProbe(200, "8.0.2")`, `"Zotero 9+"` no `detail`, `"zotero.org/download"` no `hint`) e `test_zotero_undetectable_version_is_fail_safe` (`_BbtProbe(200, None)`, `"versão não detectada"`): só trocam o patch;
    - `test_non_http_service_on_the_port_is_not_a_live_local_api` fica (o `BadStatusLine` vira `_BbtProbe(None, None)` e o `detail` diz "nada escutando"); ganha o parâmetro `monkeypatch: pytest.MonkeyPatch` e restaura a sonda real com `monkeypatch.setattr("par.core.deps._bbt_probe", _REAL_BBT_PROBE)`, porque o `urlopen` mockado só é exercido por ela.
  - **Novos — sonda** (chamam `_REAL_BBT_PROBE(...)` direto, nunca `deps._bbt_probe`, que a fixture do Step 1b troca; com `patch("par.core.deps.urllib.request.urlopen", …)`; reuse `_FakePingResponse`):
    - `test_bbt_probe_nada_escutando`: `URLError` → `_BbtProbe(None, None)`;
    - `test_bbt_probe_timeout`: `TimeoutError` → `_BbtProbe(None, None)`;
    - `test_bbt_probe_le_versao_do_200`: `_FakePingResponse({"X-Zotero-Version": "9.0.6"}, status=200)` → `_BbtProbe(200, "9.0.6")`;
    - `test_bbt_probe_le_versao_do_404`: `_http_error(404, "9.0.6")` → `_BbtProbe(404, "9.0.6")`;
    - `test_bbt_probe_500_sem_header`: `_http_error(500, None)` → `_BbtProbe(500, None)`;
    - `test_bbt_probe_url_e_timeout`: com `PRUMO_ZOTERO_BASE=http://example.test:1234`, a URL é `http://example.test:1234/better-bibtex/cayw?probe=true` e o `timeout` recebido é `2.0`.
  - **Novos — linha `zotero`** (com `patch("par.core.deps._bbt_probe", …)` e `patch("par.core.deps._binary_on_path", return_value=None)`):
    - `test_zotero_fechado_no_sandbox_e11`: `setenv("SANDBOX_RUNTIME", "1")`, `_BbtProbe(None, None)` → `"sandbox"` no `detail`, `"sandbox.excludedCommands"` no `hint`;
    - `test_zotero_sem_bbt_e12`: `_BbtProbe(404, "9.0.6")` → `present is False`, `"HTTP 404"` e `"9.0.6"` no `detail`, `".xpi"` e `"ainda iniciando"` no `hint`;
    - `test_zotero_sem_bbt_sem_versao_e12`: `_BbtProbe(404, None)` → `detail.startswith("Zotero aberto em")`;
    - `test_zotero_http_inesperado_e13`: `_BbtProbe(500, "9.0.6")` → `"HTTP 500"` no `detail`, `hint == "Reinicie o Zotero e rode: prumo doctor"`;
    - `test_zotero_404_com_versao_antiga_e14_antes_de_e12`: `_BbtProbe(404, "8.0.1")` → `"Zotero 9+"` no `detail`, `"zotero.org/download"` no `hint`, `".xpi"` fora do `hint`;
    - `test_zotero_required_by`: `required_by == ["paper connect", "write export --to docx (vínculo com a biblioteca)"]`;
    - `test_zotero_hint_nunca_pede_o_toggle`: parametrizado em `_BbtProbe(None, None)`, `(404, None)`, `(500, None)`, `(200, "8.0.2")`, `(200, "9.0.6")` → `"Allow other applications" not in zot.hint + zot.detail`.
  - `tests/unit/test_cli_doctor.py`, `test_doctor_json_includes_external_deps`: `required_by=["paper sync-annotations"]` vira `required_by=["paper connect"]`.
- [ ] **Step 1b: nenhum teste sonda o Zotero real.** Alguns testes chamam o doctor sem trocar `check_external_deps` (`test_doctor_on_fresh_project_passes` e `test_doctor_runs_with_guideline_check` em `tests/unit/test_cli_init.py`; `test_doctor_acusa_layout_legado` e `test_doctor_acusa_studies_na_raiz` em `tests/unit/test_cli_doctor.py`). Com a sonda nova, eles fariam um GET real em `127.0.0.1:23119/better-bibtex/cayw` (até 2 s), com resultado que depende do Zotero da máquina (regra de seams, `.claude/rules/code.md`). Acrescente em `tests/unit/conftest.py`, ao lado de `_no_real_pandoc` (com `from par.core.deps import _BbtProbe` nos imports):
  ```python
  @pytest.fixture(autouse=True)
  def _no_real_bbt_probe(monkeypatch: pytest.MonkeyPatch) -> None:
      """Nenhum teste fala com o Zotero real pela sonda do doctor (regra de seams,
      `.claude/rules/code.md`). Os testes da sonda usam ``_REAL_BBT_PROBE`` de
      ``test_deps.py``; os da linha ``zotero`` fazem patch de ``_bbt_probe``."""
      monkeypatch.setattr("par.core.deps._bbt_probe", lambda timeout=2.0: _BbtProbe(None, None))
  ```
  Até o Step 3 criar `_BbtProbe` e `_bbt_probe`, essa fixture e o `_REAL_BBT_PROBE` fazem todo teste de `tests/unit` errar com `ImportError`/`AttributeError`. É o vermelho esperado: nada desta task é commitado antes do Step 7, que só roda com tudo verde.
- [ ] **Step 2: rode e veja falhar.** `$UVR pytest tests/unit/core/test_deps.py -q` → FAIL (`ImportError: _BbtProbe`).
- [ ] **Step 3: implementar em `deps.py`.**
  - `_BbtProbe` e `_bbt_probe()` exatamente como no bloco "`src/par/core/deps.py`, a sonda única" de Spec B §Componentes 0.71.0.
  - Saem `_zotero_api_root`, `_zotero_host_port`, `_zotero_version_header`, `zotero_local_api_up` e o import de `urlparse`.
  - A seção `zotero` de `check_external_deps` vira um helper privado `_zotero_status() -> DepStatus`, que lê `base = zotero_base()` e `probe = _bbt_probe()` uma vez e aplica a tabela acima na ordem E10/E11 → E14 → E12 → E13 → ✓. A ordem das entradas do retorno (`qmd`, `zotero`, `pandoc`) não muda.
  - Docstring do módulo, item Zotero: "**Zotero + Better BibTeX** — citation keys, auto-export do `.bib` (`paper connect`) e vínculo das citações do docx."
- [ ] **Step 4: varredura.** `grep -rn "_zotero_api_root\|_zotero_version_header\|_zotero_host_port\|zotero_local_api_up" src tests` → vazio.
- [ ] **Step 5: rode e veja passar.**
  ```sh
  $UVR pytest tests/unit/core/test_deps.py tests/unit/test_cli_doctor.py tests/unit/test_cli_init.py -q
  SANDBOX_RUNTIME=1 $UVR pytest tests/unit/core/test_deps.py -q
  $UVR pytest -q && $UVR mypy && $UVR ruff check . && $UVR ruff format --check .
  ```
- [ ] **Step 6: smoke no sandbox do agente** (`SANDBOX_RUNTIME=1` já vem do ambiente). Rode o doctor contra um pj descartável, não contra a raiz do repo (lá ele sai com exit 1 e "5 problema(s) estrutural(is)", porque a raiz não é um pj):
  ```sh
  rm -rf "$TMPDIR/pj_smoke_0710"
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo init "$TMPDIR/pj_smoke_0710" --yes
  UV_CACHE_DIR="$TMPDIR/uvcache" uv run prumo doctor "$TMPDIR/pj_smoke_0710" --json
  ```
  Critério do smoke: a entrada `zotero` de `external_deps` com `"sandbox do Claude Code"` no `detail` (E11) e `present: false`. Isso exercita E11 de verdade, sem mock. Num pj recém-criado o doctor sai com 0; se sair com 1, confira os `issues` (são estruturais, não desta task) e registre no PR. Se o sandbox deixar o localhost passar e o Zotero estiver aberto, a entrada sai ✓ ou E12–E14 em vez de E11: registre no PR qual saiu.
- [ ] **Step 7: commit** `feat(core)!: doctor usa uma sonda só ao Better BibTeX e não exige o toggle da API local (ADR-0037)`.

---

### Task 6: Modo `paper library` — roteamento "o que eu anotei" (B12; E18)

**Files:**
- Modify: `skills/paper/modes/library.md`
- Regenerate: `skills/paper/SKILL.md` (blocos `when_to_use` e `modes-table`; nunca à mão)
- Test: `tests/unit/core/test_skills.py`

**Interfaces:** nenhuma de código. Contrato de texto: a seção de roteamento é verbatim do bloco "**Seção de roteamento em `skills/paper/modes/library.md`** (substitui as §1b–1d)" de Spec B §Componentes 0.71.0; a linha E18 está dentro dela (item 3).

- [ ] **Step 1: testes que falham** em `tests/unit/core/test_skills.py` (raiz do repo: `Path(__file__).resolve().parents[3]`):
  - `test_nenhum_texto_do_plugin_cita_comando_zotero_aposentado`: busca recursiva, `for root in ("skills", "agents", "templates"): for md in (repo / root).rglob("*.md")` (um glob de um nível não pega `skills/paper/modes/library.md` e o teste passaria à toa); para cada termo de `("sync-annotations", "sync-notes", "sync-all", "paper_sync_all")` presente no texto, acumule `f"{md.relative_to(repo)}: {termo}"` e afirme a lista vazia, com ela na mensagem de falha. `tests/` fica de fora: os testes-guarda trazem esses termos como literais.
  - `test_library_roteia_anotacoes_para_fora_do_par`: o texto de `skills/paper/modes/library.md` contém `"### Anotações, notas e a biblioteca inteira do Zotero (fora do PAR)"` e `"Isso fica fora do PAR: o PAR não lê destaques nem notas do Zotero."`; e, pelo registry (`load_skill_registry(<raiz>/"skills", strict=True)`, modo `paper/library`), as frases incluem `"o que eu anotei no Zotero sobre este paper"` e não incluem `"importa minhas anotações do Zotero"`.
- [ ] **Step 2: rode e veja falhar.** `$UVR pytest tests/unit/core/test_skills.py -q` → FAIL.
- [ ] **Step 3: editar `skills/paper/modes/library.md`** (âncoras por texto):
  - `argument-hint`: `"[sync | update-cites | set-primary <citekey> | list | graph <citekey> | sync-bib | find <query> | connect <coleção>]"`.
  - `inputs.operation`: `required (sync | update-cites | set-primary | list | graph | sync-bib | find | connect)`.
  - Frase `- "importa minhas anotações do Zotero"` vira `- "o que eu anotei no Zotero sobre este paper"`.
  - Árvore do layout: o comentário de `_annotations.md` vira `# legado, não gerado`; o de `note__<itemKey>__<slug>.md` vira `# legado, não gerado`.
  - As seções `### 1b. \`sync-annotations\``, `### 1c. \`sync-notes\`` e `### 1d. \`sync-all\`` (do heading de 1b até antes de `### 2. \`update-cites\``) dão lugar ao bloco verbatim da Spec B citado acima, no mesmo lugar.
  - §8 `connect`, passo 6: depois do bloco com `prumo paper sync`, acrescente a frase "Se `exported` vier `false`, repasse a dica do comando (o BBT pode levar alguns segundos; BBT ≥ 9.0.65)."
  - §8, "Regras duras", o bullet que começa com "Se o `_references.bib` do projeto já tiver entradas reais, o comando recusa reconectar" vira: "- O comando recusa conectar quando o `.bib` já tem entradas, para não sobrescrevê-lo; se ele já vem do Better BibTeX, siga com `prumo paper sync`."
  - Não toque no `allowed-tools` (é do D5, Spec A) nem no bloco `prumo:preflight` (gerado).
- [ ] **Step 4: regerar.** `$UVR python .github/scripts/gen_indexes.py`. Confira com `git diff --stat` que só `skills/paper/SKILL.md` (frase nova no `when_to_use` e na `modes-table`) mudou além do modo; se o README ou o catálogo do `start` mudarem, é porque a 1ª frase ou a description mudaram — não devem.
- [ ] **Step 5: rode e veja passar.** `$UVR pytest -q && $UVR python .github/scripts/gen_indexes.py --check && $UVR ruff check . && $UVR ruff format --check .`
- [ ] **Step 6: commit** `feat(skills)!: paper library roteia "o que eu anotei" para fora do PAR (ADR-0037)`.
- [ ] **Step 7 (manual, não bloqueia):** P16 da Spec B — no Desktop, a frase "o que eu anotei no Zotero sobre este paper" cai em `paper/library` e não em `wiki/query`. Registre o resultado no PR. Registre também no PR, como pendência para o dono (a spec não lista essa linha, então não a edite aqui): o §8 `connect`, passo 1, ainda diz "o comando falha com mensagem clara e exit code 2 — não insista sem reabrir o Zotero", o que contradiz a variante de sandbox do E15 (repetir o comando fora do sandbox). Sugestão a levar ao dono: acrescentar "— se a mensagem for a do sandbox, repasse-a: repetir fora do sandbox, com permissão".

---

### Task 7: Docs, template e spec aposentada

**Files:**
- Modify: `README.md`, `ARCHITECTURE.md`, `docs/Research Project Structure.md`, `docs/onboarding-pesquisador.md`, `templates/pj_base/docs/references/_references.bib`, `templates/pj_base/docs/project_guide.md`, `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md`
- Regenerate: `docs/_index.md`
- Test: `tests/unit/test_pj_base_integration.py`

- [ ] **Step 1: teste que falha** em `tests/unit/test_pj_base_integration.py`:
  - `test_bib_do_template_segue_placeholder_e_aponta_o_connect(tmp_path)`: `runner.invoke(app, ["init", str(tmp_path / "pj_bib"), "--json"])` com `exit_code == 0`; `connect.bib_is_placeholder(target) is True` (`from par.domains.paper import connect`); o texto do `.bib` criado tem como 1ª linha `% Bibliografia do projeto — formato Better BibTeX (BBT).` e contém `"9.0.65"` e `"prumo paper connect"`, sem `"Keep updated"` e sem `"Zotero 7"`.
  - `test_project_guide_do_template_nao_manda_keep_updated`: `"Keep updated" not in (resolve_resource("templates") / "pj_base" / "docs" / "project_guide.md").read_text(encoding="utf-8")`.
- [ ] **Step 2: rode e veja falhar.** `$UVR pytest tests/unit/test_pj_base_integration.py -q` → FAIL.
- [ ] **Step 3: template.**
  - `templates/pj_base/docs/references/_references.bib` passa a ser (a 1ª linha fica idêntica: `connect.bib_is_placeholder` exige o prefixo `% Bibliografia do projeto`):
    ```
    % Bibliografia do projeto — formato Better BibTeX (BBT).
    %
    % Fluxo recomendado:
    %   1. Zotero 9+ com Better BibTeX ≥ 9.0.65
    %   2. Configurar citation key: auth.lower + year + shorttitle(1,1)
    %   3. Peça ao agente "conecta minha coleção <nome>" (roda `prumo paper connect`)
    %
    % Alternativa sem Zotero: adicionar entradas à mão, sempre com citekey
    % no formato `autorYYYYpalavra`. A skill /par:paper library cuida disso.
    ```
  - `templates/pj_base/docs/project_guide.md`: o trecho `mantido pelo Better BibTeX com "Keep updated"` vira `mantido pelo Better BibTeX (registrado por `prumo paper connect`)`. Nada mais muda neste arquivo (o piso do pandoc entrou na 0.70.3; os passos do Zettlr são da Spec A).
- [ ] **Step 4: docs.**
  - `README.md`, §"Pré-requisitos externos": a linha da tabela que começa com `| **Zotero` vira (texto da Spec B mapeado às três colunas, com o link do BBT preservado):
    ```
    | **Zotero 9+ e Better BibTeX ≥ 9.0.65** | `paper connect`; vínculo das citações no `write export --to docx` | Abra o Zotero com o [Better BibTeX](https://retorque.re/zotero-better-bibtex/) instalado (`.xpi`). O PAR fala com ele em `127.0.0.1:23119` e não precisa da opção 'Allow other applications'. Sem o Zotero, o resto do PAR funciona, e o docx sai com as citações sem vínculo. |
    ```
  - `ARCHITECTURE.md`, §"Cinco domínios + core", box `📚 paper`: saem as células `sync-`, ` annotations`, `sync-notes` e `sync-all`; `migrate-` e ` layout` sobem para as duas primeiras linhas liberadas, e as quatro linhas seguintes ficam com a célula do `paper` em branco (`│              │`), para a coluna `write` não mudar. Resultado das seis linhas, a partir da que segue `│ sync-pdfs    │ …`:
    ```
    │ migrate-     │ │              │ │            │ │              │ │   comments   │
    │  layout      │ │              │ │            │ │              │ │ disclosure   │
    │              │ │              │ │            │ │              │ │ list-        │
    │              │ │              │ │            │ │              │ │   templates  │
    │              │ │              │ │            │ │              │ │zettlr-profile│
    │              │ │              │ │            │ │              │ │              │
    ```
  - `ARCHITECTURE.md`, §"Glossário rápido", o item **Layout α** vira: "**Layout α** — `docs/references/papers/<citekey>/` com `_meta` e `_extract` (ADR-0008); `_annotations` e `note__*` como legado legível (ADR-0037)."
  - `docs/Research Project Structure.md`, linha da tabela de `docs/references/papers/<key>/`: a descrição vira "Pasta por paper, com `_meta.md` (callout estruturado: PICOT, método, …) e `_extract.md` (`_annotations.md`: legado, se existir)".
  - `docs/onboarding-pesquisador.md`, §"4. Conectar sua biblioteca": logo abaixo do heading, antes de "Com o projeto criado…", entra o parágrafo "Você precisa do Zotero 9 ou mais novo, com o Better BibTeX 9.0.65 ou mais novo (versões anteriores não exportam itens novos com a janela do Zotero fechada)."
- [ ] **Step 5: receita do onboarding (condicional à Task 1, Step 3).** Se a § "Perguntar ao seu Zotero" ainda não existe, substitua a § "Busca semântica no seu acervo do Zotero, sem terminal" (do heading até antes de "### Editando os arquivos `.md` do projeto") pelo bloco verbatim de Spec B §Componentes 0.71.0, "**Receita do onboarding**". Se já existe, não mexa.
- [ ] **Step 6: spec aposentada.** Em `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md`:
  - frontmatter: `status: approved` vira `status: superseded`, e logo abaixo entra `superseded-by: "[[2026-10-02-ponte-zotero-minima-design]]"` (mesmo formato de `2026-04-29-prumo-scientific-writer-design.md`);
  - logo abaixo do H1, uma linha em branco e a nota `> Aposentado pela ADR-0037 (0.71.0): \`sync-notes\` e as notas-filhas saem do PAR.`
- [ ] **Step 7: regerar e rodar.**
  ```sh
  $UVR python .github/scripts/gen_indexes.py      # docs/_index.md: a spec de 2026-05-03 passa a "· superseded"
  $UVR pytest -q && $UVR python .github/scripts/gen_indexes.py --check && $UVR ruff check . && $UVR ruff format --check .
  ```
- [ ] **Step 8: commit** `docs: ponte Zotero mínima na 0.71.0 — README, onboarding, template e spec de notas aposentada`.

---

### Task 8: Verificação, CHANGELOG, índices, G3 e fechamento do plano

**Files:**
- Modify: `CHANGELOG.md`
- Move: `docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0710.md` → `docs/superpowers/plans/archive/`
- Regenerate: `docs/_index.md`

- [ ] **Step 1: CHANGELOG.** Copie verbatim os três bullets do bloco "**0.71.0 MINOR ⚠** … Bullets desta spec para a entrada ⚠ do CHANGELOG" de Spec B §"Release e migração". Em `## [Não publicado]` (vazio até aqui: a 0.70.3 já foi cortada, e os PRs 1–2 da Spec A não tocam o CHANGELOG), crie só `### Alterado`, com o 2º (`prumo doctor` …) e o 3º (`prumo paper connect` …) bullets, nessa ordem, e depois `### Removido`, com o 1º (`**⚠ Breaking — anotações e notas do Zotero saem do PAR** …`). Não crie `### Adicionado`, `### Corrigido` nem `### Documentação`: a Task 23 do plano da Spec A (`2026-10-02-plugin-distribuicao-unica.md`) acrescenta essas seções e põe os bullets dela depois dos nossos. Se `## [Não publicado]` já tiver conteúdo, PARE e reporte (não era esperado). Sem bump e sem data: o corte é do orquestrador. Os passos de migração do Zotero NÃO entram aqui: já estão no item 7 da lista "Migração de quem já usa" da Spec A, que o corte publica.
- [ ] **Step 2: varredura final de nomes aposentados.**
  ```sh
  grep -rnE "sync-annotations|sync-notes|sync-all|paper_sync_all|sync_annotations|sync_notes|ZoteroApiError|zotero_local_api_up|child_note_path|duplicate_item_key" \
    src tests skills agents templates README.md ARCHITECTURE.md "docs/Research Project Structure.md" docs/onboarding-pesquisador.md \
    | grep -v -e tests/unit/paper/test_api.py -e tests/unit/paper/test_cli.py \
      -e tests/unit/core/test_note_paths.py -e tests/unit/paper/test_lint.py -e tests/unit/core/test_skills.py
  ```
  Esperado: vazio. Os cinco arquivos excluídos são os testes-guarda das Tasks 3, 4 e 6, que trazem os nomes aposentados como literais nas asserções de ausência; sem o `grep -v`, só as linhas deles aparecem a mais. Não os apague nem os enfraqueça. Fora do escopo da varredura, de propósito: `CHANGELOG.md` (histórico e o bullet novo), `ROADMAP.md:14` (histórico da 0.61.0), `docs/superpowers/` (specs e planos), `docs/adr/` (imutáveis) e `docs/actions-by-context.md` (apagado pelo PR 1 da Spec A, o que a Task 1, Step 2b, conferiu).
- [ ] **Step 3: verificação completa.**
  ```sh
  $UVR pytest -q
  $UVR ruff check . && $UVR ruff format --check .
  $UVR mypy
  $UVR python .github/scripts/gen_indexes.py --check
  $UVR --with jsonschema==4.23.0 python .github/scripts/validate_manifests.py
  $UVR python .github/scripts/sync_manifest_version.py --check
  ```
  Todos limpos.
- [ ] **Step 4: smokes automáticos** (no Bash do agente, que roda com `SANDBOX_RUNTIME=1`):
  - `$UVR prumo paper --help` não lista `sync-annotations`, `sync-notes` nem `sync-all`; `$UVR prumo paper sync-all .` sai com 2 e "No such command".
  - `$UVR python -c "import asyncio; from par import mcp_server; print(len(asyncio.run(mcp_server.server.list_tools())))"` → `10`.
  - Recrie o pj descartável (`rm -rf "$TMPDIR/pj_smoke_0710"` e `$UVR prumo init "$TMPDIR/pj_smoke_0710" --yes`, com o `.bib` no placeholder). `$UVR prumo doctor "$TMPDIR/pj_smoke_0710" --json` → exit 0 e a entrada `zotero` de `external_deps` com o E11 (`"sandbox do Claude Code"` no `detail`, `present: false`). Não rode o doctor na raiz do repo: lá ele sai com exit 1 ("5 problema(s) estrutural(is)"), porque a raiz não é um pj.
  - No mesmo pj, `$UVR prumo paper connect "prumo-smoke-inexistente-0710" --path "$TMPDIR/pj_smoke_0710"`: no sandbox sai com 2 e o E15 de sandbox; se o sandbox deixar passar o localhost e o Zotero estiver aberto, sai com 1 e "NADA foi criado". Nos dois casos, nada muta: sem `--create`, a coleção inexistente para na Guarda 2.
- [ ] **Step 5: G3 (manual, na máquina do dono, fora do sandbox; bloqueia o corte da 0.71.0).** Registre no PR:
  - `curl -si 'http://127.0.0.1:23119/better-bibtex/cayw?probe=true'` → 200, corpo `ready`, header `X-Zotero-Version`;
  - com o BBT desativado em Tools → Plugins, o mesmo `curl` → 404 **com** `X-Zotero-Version`;
  - `prumo doctor` (fora do sandbox) mostra E10 com o Zotero fechado, E12 com o BBT desativado e ✓ com os dois ativos;
  - num pj recém-criado (`prumo init pj_g3`, com o `.bib` no placeholder), `prumo paper connect "<nome que não existe>"` exercita o transporte novo só em leitura (`user.groups`) e responde "NADA foi criado".

  "Antes do merge da 0.71.0" (Spec B) é lido como antes do corte da 0.71.0. Rode antes do merge deste PR se o dono estiver disponível; se não, ele bloqueia só o corte. Falha no G3 → corrigir neste mesmo fluxo antes do corte (B10, "Quando reavaliar").
- [ ] **Step 6: fechar o plano.** `git mv docs/superpowers/plans/2026-10-02-ponte-zotero-minima-0710.md docs/superpowers/plans/archive/`. Troque o frontmatter pelo de fechamento, no formato dos planos já arquivados (por exemplo, `archive/2026-09-12-superficie-f3-status.md`): `status: implemented`, `verified: <AAAA-MM-DD>`, `release: "0.71.0 MINOR (corte único com a Spec A) — pendente do corte"`, `spec: "[[2026-10-02-ponte-zotero-minima-design]]"`. Logo abaixo, o parágrafo `> **Fechamento (<data>).** …` com as tasks entregues, o resultado do Step 3, os smokes do Step 4 e o estado do G3 e do P16. Depois `$UVR python .github/scripts/gen_indexes.py` e `$UVR python .github/scripts/gen_indexes.py --check`.
- [ ] **Step 7: commit** `docs: CHANGELOG da ponte Zotero mínima (0.71.0) e plano arquivado`. Abra o PR 3 contra `main` com a lista das tasks, os comandos do Step 3, o estado do G3 e do P16 e as pendências para o dono no corpo: o §8 passo 1 de `library.md` × E15 de sandbox (Task 6, Step 7) e o parâmetro `exit_code` de `cli_run`, que ficou sem chamador de produção depois da Task 3 (candidato ao Princípio VI, fora desta spec). Termine o corpo com `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
