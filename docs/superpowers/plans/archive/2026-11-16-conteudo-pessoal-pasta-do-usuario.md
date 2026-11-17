---
status: implemented
verified: 2026-11-16
verification_pending: "consulta à parte livre da base numa sessão real com o plugin carregado (Task 5, Step 6): NÃO verificada"
release: "pendente — PATCH (ADR-0015)"
spec: "[[2026-11-16-conteudo-pessoal-fora-do-repo-design]]"
adr: "[[adr/adr-0044-pasta-do-usuario]]"
---

> **Fechamento (2026-11-16).** Tasks 1–5 implementadas em TDD no branch
> `claude/private-overlay-design-5e3d71`. Verificação: suíte inteira verde; `ruff check`,
> `ruff format --check`, `mypy` (186 arquivos) e `gen_indexes --check` limpos; smoke num
> `pj_piloto_usuario` com base sintética ligada por symlink (`write list-templates` mostra o degrau
> `user_dir`; `write prep` devolve `template_source: user_dir` e a guia do `kind`). A ADR-0044
> segue `proposto`, como as demais ADRs recentes, até o mantenedor aceitá-la.
>
> **Pendência de verificação manual (não feita).** A segunda metade do Step 6 da Task 5 não foi
> executada: ninguém conferiu, numa sessão real com o plugin carregado (`claude --plugin-dir .`),
> que a skill consulta a parte livre da base (`ml/`, `analise/`) e cita o arquivo usado. Só os
> caminhos determinísticos (`list-templates`, `write prep`) foram verificados. O alcance em Cowork
> e no chat do claude.ai também não foi verificado. Falta ainda o corte do release.

# Conteúdo pessoal fora do repo — base de conhecimento na pasta do usuário: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O pesquisador conecta, se quiser, uma base de conhecimento própria em `~/.config/prumo/` (pasta ou symlink). O PAR usa os templates dela (o projeto continua vencendo), lista as guias obrigatórias do `kind` no `write prep` e avisa todas as skills de que o resto da base existe para consulta.

**Architecture:** `core/paths.py::user_dir()` devolve a pasta. `domains/write/compose.py` acrescenta o candidato `user_dir` em `template_candidates`, expõe o rótulo do vencedor como `template_source` e lista as guias do `kind`. `write prep` emite as duas chaves novas. Os quatro modos que passam pelo prep ganham o passo "leia `guides`". O bloco gerado `prumo:runtime` ganha uma linha sobre a base, e a skill `start` aprende a conectá-la por symlink.

**Tech Stack:** Python 3.12, Typer, pytest, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-11-16-conteudo-pessoal-fora-do-repo-design.md` · **ADR:** ADR-0044 (proposto).

## Global Constraints

- Layering (ADR-0005): `core/paths.py` não importa `domains/`; o significado de `templates/` e `guides/` fica em `domains/write/`.
- Fachadas finas; saída só via `Console`. `mypy --strict`, `from __future__ import annotations`.
- Mensagens e docstrings em pt-BR, com o comando de correção dentro da mensagem.
- **Nome:** "pasta do usuário" / `user_dir`. Não use "overlay", que já designa `core/scaffold.py::overlay` e os módulos do `prumo add`.
- **Privacidade:** testes só com `tmp_path` e texto "Template sintético de teste" / "Guia sintética de teste". Nenhum caminho absoluto em doc, CHANGELOG ou commit.
- Princípio IV: chaves novas no JSON do prep são aditivas.
- Princípio VIII: nenhum comando, flag ou variável de ambiente nova.
- **Fora de escopo** (spec §6, cada item com trigger): guias por projeto, base fora das skills do PAR, índice ou busca na base, carimbo no `_meta`, variável de ambiente, `userConfig`, `doctor`, plugin privado. Não implemente "já que está aqui".
- Este plano não corta release. O release é PATCH (ADR-0015). `uv.lock` e `shims/prumo` não mudam.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/par/core/paths.py` (modificar) | `user_dir()` |
| `tests/unit/conftest.py` (modificar) | fixture autouse que isola a suíte da pasta real do dono |
| `src/par/domains/write/compose.py` (modificar) | candidato `user_dir`, `template_source`, `guide_paths`, campos novos em `WritePrep` |
| `src/par/domains/write/cli.py` (modificar) | `prep` emite `template_source` e `guides` |
| `skills/write/modes/{manuscript,section}.md`, `skills/protocol/modes/{cep,sap}.md` (modificar) | cadeia de template com o degrau novo; passo "leia `guides`" |
| `.github/scripts/gen_indexes.py` (modificar `render_runtime`) | linha da base de conhecimento no bloco `prumo:runtime` |
| `skills/start/SKILL.md` (modificar a fonte, fora dos blocos gerados) | frase "conecta minha base de conhecimento" |
| `ARCHITECTURE.md`, `docs/onboarding-pesquisador.md`, `CHANGELOG.md`, `src/par/core/config.py` (modificar) | documentação |

---

### Task 1: `user_dir()` e isolamento da suíte

**Files:** `src/par/core/paths.py`, `tests/unit/conftest.py`, `tests/unit/core/test_paths.py`

```python
def user_dir() -> Path | None:
    """Pasta de conteúdo pessoal (``$XDG_CONFIG_HOME/prumo``, padrão ``~/.config/prumo``), se existir."""
    base = Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser() / "prumo"
    return base if base.is_dir() else None
```

- [ ] **Step 1: Isolar a suíte.** Em `tests/unit/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _no_real_user_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A pasta pessoal do dono (``~/.config/prumo/``) nunca entra nos testes (ADR-0044)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "_xdg_isolado"))
```

Sem ela, a pasta real do dono muda o template resolvido em `test_prep_returns_inputs_and_template`.

- [ ] **Step 2: Testes que falham** em `tests/unit/core/test_paths.py`:

```python
def test_user_dir_existente(tmp_path, monkeypatch):
    root = tmp_path / "xdg" / "prumo"; root.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert user_dir() == root

def test_user_dir_ausente_e_none():
    assert user_dir() is None

def test_user_dir_arquivo_nao_conta(tmp_path, monkeypatch):
    (tmp_path / "xdg").mkdir(); (tmp_path / "xdg" / "prumo").write_text("x", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert user_dir() is None
```

- [ ] **Step 3:** `uv run pytest tests/unit/core/test_paths.py -q`: FAIL.
- [ ] **Step 4:** Implementar; atualizar a docstring do módulo (recurso empacotado e pasta do usuário).
- [ ] **Step 5:** PASS, depois `uv run pytest -q` inteiro.
- [ ] **Step 6:** Commit `feat(core): pasta do usuário em ~/.config/prumo (ADR-0044)`.

---

### Task 2: Template da pasta do usuário e `template_source`

**Files:** `src/par/domains/write/compose.py`; testes onde já estão os de `resolve_template` (`grep -rn resolve_template tests/unit/write`) e `tests/unit/write/test_compose_prep.py`, `test_cli.py`

**Mudanças:**
- `template_candidates` devolve `project_override`, `user_dir`, `plugin_default`, nesta ordem. `user_dir` é `<user_dir()>/templates/<kind>.md`, ou `None` sem pasta.
- `WritePrep` ganha `template_source: str`: o rótulo do candidato vencedor (`"project_override" | "user_dir" | "plugin_default"`). Sem mapa de tradução: o rótulo é o valor.
- Para não resolver duas vezes, `prep()` itera os candidatos uma vez e guarda rótulo e caminho. `resolve_template` mantém assinatura e comportamento.
- Mensagem de "nenhum template" cita os três lugares: `.claude/writing_templates/<kind>.md`, `~/.config/prumo/templates/<kind>.md` ou `--template`.

- [ ] **Step 1: Testes que falham:**

```python
def _user_dir(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "xdg" / "prumo"; root.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return root

def test_usuario_vence_plugin(tmp_path, monkeypatch):
    root = _user_dir(tmp_path, monkeypatch)
    (root / "templates").mkdir()
    (root / "templates" / "paper.md").write_text("# Template sintético de teste\n", encoding="utf-8")
    pj = tmp_path / "pj_exemplo"; (pj / ".claude").mkdir(parents=True)
    assert resolve_template(pj_path=pj, kind="paper") == root / "templates" / "paper.md"

def test_projeto_vence_usuario(tmp_path, monkeypatch): ...   # os dois existem; vence writing_templates/
def test_candidatos_em_ordem(tmp_path, monkeypatch):
    _user_dir(tmp_path, monkeypatch)
    assert list(template_candidates(pj_path=tmp_path, kind="paper")) == [
        "project_override", "user_dir", "plugin_default"]
def test_sem_pasta_candidato_e_none(tmp_path):
    assert template_candidates(pj_path=tmp_path, kind="paper")["user_dir"] is None
def test_prep_template_source(tmp_path, monkeypatch): ...    # "plugin_default" sem pasta; "user_dir" com
```

Em `test_cli.py`: `write list-templates --json` traz `user_dir` não nulo para `paper` com a pasta sintética; `write prep --json` traz `template_source`.

- [ ] **Step 2:** Rodar: FAIL.
- [ ] **Step 3:** Implementar; `write prep` emite `template_source`. Atualizar a docstring do módulo (linha da chain), a de `template_candidates` e a de `list-templates`.
- [ ] **Step 4:** `uv run pytest tests/unit/write -q`: PASS.
- [ ] **Step 5:** Commit `feat(write): template da pasta do usuário entre o do projeto e o do plugin (ADR-0044)`.

---

### Task 3: Guias no `write prep`

**Files:** `src/par/domains/write/compose.py`, `src/par/domains/write/cli.py`; `tests/unit/write/test_compose_prep.py`, `test_cli.py`

```python
def guide_paths(kind: WriteKind) -> tuple[Path, ...]:
    """Guias de leitura obrigatória para ``kind``: ``guides/<kind>/*.md``, em ordem alfabética."""
    root = user_dir()
    return () if root is None else tuple(sorted((root / "guides" / kind).glob("*.md")))
```

- `WritePrep` ganha `guides: tuple[Path, ...] = ()`; `prep()` preenche; o JSON do `write prep` ganha `"guides": [str, ...]`.
- A mensagem de sucesso só cita guias quando há alguma.

- [ ] **Step 1: Testes que falham:**

```python
def test_guias_so_do_kind_em_ordem(tmp_path, monkeypatch):
    root = _user_dir(tmp_path, monkeypatch)
    for rel in ["guides/paper/b.md", "guides/paper/a.md", "guides/statistics/x.md",
                "guides/solta.md", "ml/formato.md"]:
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("Guia sintética de teste\n", encoding="utf-8")
    got = [p.relative_to(root).as_posix() for p in guide_paths("paper")]
    assert got == ["guides/paper/a.md", "guides/paper/b.md"]  # o resto da base é consulta livre

def test_sem_pasta_sem_guias():
    assert guide_paths("paper") == ()

def test_prep_json_tem_guides(...): ...   # lista vazia sem pasta; um item com a pasta sintética
```

- [ ] **Step 2:** Rodar: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** `uv run pytest tests/unit/write -q`: PASS.
- [ ] **Step 5:** Commit `feat(write): write prep lista as guias obrigatórias do kind (ADR-0044)`.

---

### Task 4: Skills: guias obrigatórias, base para consulta e conexão

**Files:** `skills/write/modes/manuscript.md`, `skills/write/modes/section.md`, `skills/protocol/modes/cep.md`, `skills/protocol/modes/sap.md`, `.github/scripts/gen_indexes.py`, `skills/start/SKILL.md`

- [ ] **Step 1:** Na frase que descreve o override de template, a cadeia vira: "Override por projeto: `<pj>/.claude/writing_templates/<kind>.md`. Template pessoal, para todos os projetos: `~/.config/prumo/templates/<kind>.md`. Override ad hoc: `--template <path>`."
- [ ] **Step 2:** No passo que lê `template_path` do JSON do prep: "Se `guides` não estiver vazio, leia cada arquivo com `Read`, na ordem dada, antes de escrever. Guia orienta método, estilo e estrutura; não autoriza citar fora do acervo nem sobrepõe a citação strict. Se uma guia contradisser este modo, siga o modo e diga ao usuário qual guia foi ignorada e por quê. Se `template_source` for `user_dir`, diga ao usuário que o template veio da pasta pessoal, não do projeto."
- [ ] **Step 3: Linha no bloco `prumo:runtime`.** Em `render_runtime()` de `.github/scripts/gen_indexes.py`, acrescente um item: "Base de conhecimento do pesquisador: `~/.config/prumo/`, se existir. Consulte-a (liste as pastas, leia o que for pertinente) quando a tarefa envolver redação, método, análise de dados ou machine learning, e diga ao usuário qual arquivo usou." Antes, escreva em `tests/unit/test_gen_indexes.py` (ao lado de `test_render_runtime_carimba_versao_e_raiz`) um teste que exige `~/.config/prumo/` e "Base de conhecimento" em `gen.render_runtime()`, e veja falhar.
- [ ] **Step 4: Conexão pela `start`.** Em `skills/start/SKILL.md`, fora dos blocos gerados, acrescente a seção "Base de conhecimento pessoal": a pedido ("conecta minha base de conhecimento em `<caminho>`"), confira que o caminho é uma pasta; se `~/.config/prumo` não existir, rode `ln -s "<caminho>" ~/.config/prumo`; se existir, não toque e diga para onde aponta. Explique as duas pastas com significado (`templates/<kind>.md`, `guides/<kind>/`) e que o resto é livre. Confira se o `allowed-tools` derivado da `start` cobre `ln` e `test`; se o frontmatter for gerado, mude a fonte, não o bloco.
- [ ] **Step 5:** `uv run python .github/scripts/gen_indexes.py`, depois `--check`. O bloco muda nas 5 portas, no `start` e em `agents/reader.md`: commite o resultado gerado.
- [ ] **Step 6:** `uv run pytest tests/unit/core/test_skills.py -q` e os testes do gerador, se existirem.
- [ ] **Step 7:** Commit `docs(skills): base de conhecimento pessoal nas skills (ADR-0044)`.

---

### Task 5: Documentação, verificação e fechamento

- [ ] **Step 1:** `ARCHITECTURE.md`: `paths` no bloco do `core/` passa a "recursos empacotados + pasta do usuário"; glossário ganha **Pasta do usuário** (`~/.config/prumo/`: base de conhecimento pessoal, com `templates/` e `guides/<kind>/` reconhecidos pelo PAR, ADR-0044).
- [ ] **Step 2:** `docs/onboarding-pesquisador.md`: seção curta "Sua base de conhecimento", com o layout (duas pastas com significado, o resto livre), a ordem projeto > pessoal > plugin, como conectar uma base que já existe (pela `start` ou com o `ln -s`), como congelar um template no projeto e o aviso de que fora do computador o alcance não foi verificado. Exemplos inventados.
- [ ] **Step 3:** `CHANGELOG.md` em `[Não publicado]` → `Adicionado`. Cite o Princípio VIII e a ADR-0044; diga que o ambiente do lançador não é baixado de novo.
- [ ] **Step 4:** `core/config.py`: o comentário da cascata passa a dizer que `~/.config/prumo/` já é a pasta do usuário (ADR-0044) e que `config.toml` ali segue não implementado.
- [ ] **Step 5: Verificação:**
  - `uv run pytest -q`
  - `uv run ruff check . && uv run ruff format --check .`
  - `uv run mypy`
  - `uv run python .github/scripts/gen_indexes.py --check`
- [ ] **Step 6: Smoke** num `pj_piloto_usuario` temporário, com `XDG_CONFIG_HOME` apontando para uma pasta sintética: `uv run prumo write list-templates --json` e `uv run prumo write prep --kind paper --json`. Numa sessão com o plugin carregado (`claude --plugin-dir .`), peça um parágrafo de métodos e confira que a skill cita um arquivo sintético de `ml/` da base.
- [ ] **Step 7: Privacidade:** o diff contra `main` não contém caminho absoluto de máquina nem conteúdo real.
- [ ] **Step 8: Fechamento:** ADR-0044 passa a `aceito`; spec a `status: approved`; este plano vai para `plans/archive/` com o frontmatter de fechamento; `gen_indexes.py`. Commit `docs: fecha o plano da pasta do usuário`. Sem push nem release sem pedido.

## Riscos

- **Colisão de número de ADR:** se a sessão principal criar a ADR-0044 antes, renumere esta e os links.
- **Conflito em `compose.py`:** a escolha de idioma no início pode mexer em `WritePrep`. Rebase antes da Task 2 se aquele trabalho já estiver no `main`.
