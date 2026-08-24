---
status: implemented
verified: 2026-08-24
release: "0.67.0"
spec: "[[2026-08-24-pj-instalavel-design]]"
---

# Plano — o `pj_*` é pacote instalável

Implementado numa fase só, em TDD. Registro do que entrou e da verificação que sustenta o
`status: implemented`.

## Tasks

### Task 1 — Nome de pacote e marcador `__pkg__` (`core/scaffold.py`)

- `PKG_MARKER = "__pkg__"`, `_substitute_pkg` (caminho) e `apply_pkg_name` (conteúdo).
- `pkg_name(projeto)` — remove o prefixo `pj_`, recusa resultado que não seja identificador.
- `scope_pkg_name(slug)` — remove prefixo numérico, `-` vira `_`, recusa o que não vira
  identificador.
- `overlay(..., pkg=...)` falha alto quando o template usa o marcador sem `pkg` resolvido —
  mesmo contrato do `SCOPE_MARKER`, para nunca vazar um diretório `__pkg__` no projeto.
- `apply_project_name` extraído para `_apply_placeholders`, compartilhado com `apply_pkg_name`.

### Task 2 — Templates dos módulos `code` e `notebooks`

- `code`: `src/__pkg__/__init__.py` (docstring com a convenção), `pyproject.toml` com
  `[build-system]` + `[tool.hatch.build.targets.wheel] packages`, e a rule
  `.claude/rules/code_layout.md`. `src/.gitkeep` removido.
- `notebooks`: `notebooks/__scope__/.gitkeep`, `anchor` atualizado no `_module.toml`.

### Task 3 — Fachada (`cli.py`)

- `add_command` e o laço de módulos do `init` resolvem `pkg` via `module_requires_pkg` e
  chamam `apply_pkg_name` depois do `apply_project_name`.
- Nome de projeto impróprio é recusado **antes** de copiar qualquer arquivo.

### Task 4 — `core/packaging.py` + `doctor`

Quatro checks (`projeto_nao_instalavel`, `pacote_sem_nome`, `sys_path_hack`,
`projeto_nao_sincronizado`), ligados por uma linha em `doctor_command`. `docs/` fica fora
do alcance do `sys_path_hack` de propósito: prosa que menciona `sys.path` — inclusive a
rule distribuída pelo próprio módulo `code` — não é ocorrência do defeito.

### Task 5 — Prosa

`docs/Research Project Structure.md` (tabela de módulos + seção "Onde o código mora"),
`ARCHITECTURE.md`, [ADR-0027](../../../adr/adr-0027-pj-instalavel.md), índices gerados.

## Verificação

- `uv run pytest` — 1030 testes, verde.
- `uv run ruff check .` / `ruff format --check .` / `uv run mypy` — limpos.
- `validate_manifests.py`, `sync_manifest_version.py --check`, `gen_indexes.py --check` — ok.
- **End-to-end real**, que é o que sustenta a decisão: `prumo init pj_coorte` +
  `add code` + `add notebooks` produziu `src/coorte/__init__.py` e
  `notebooks/principal/`; `uv sync` instalou o projeto em editable
  (`_editable_impl_pj_coorte.pth` + `pj_coorte-0.1.0.dist-info`); e
  `from coorte.principal.prep import build_cohort` funcionou com **`cwd=/`**, com
  `__module__` estável em `coorte.principal.prep`. `prumo doctor` no projeto veio
  `ok: true`; ao plantar um `sys.path.insert` num notebook, acusou `sys_path_hack`.

## Fora de escopo (confirmado)

Migrador determinístico (a migração é agêntica, ADR-0027 D7), config de IDE versionada,
`src/` no núcleo, e o check de "import não declarado" (ver Notas da 0.67.0 no CHANGELOG).
