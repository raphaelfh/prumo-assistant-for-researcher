---
status: implemented
verified: 2026-09-12
release: "pendente — MINOR ⚠ Breaking (ADR-0015)"
spec: "[[2026-09-12-superficie-de-skills-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–11 implementadas em TDD no branch
> `docs/skill-surface-consolidation`. Verificação: suíte inteira verde exceto 11 testes de
> `tests/unit/write/test_review_ingest.py` que dependem de `uvx` no PATH — falham igual no
> `main` intocado (baseline 839f9a9), portanto ambientais; `ruff check`, `ruff format --check`,
> `mypy` (176 arquivos), `gen_indexes --check`, `validate_manifests` e
> `sync_manifest_version --check` limpos; smoke `prumo init` instala as 6 skills com `modes/`
> e o `doctor` não emite `[skill_obsoleta]`. Pendente: medição manual da lista-ouro no Desktop
> (≥ 27/30) e o corte do release.

# Superfície de skills — F1: consolidação em start + 5 skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar as 16 skills por `start` + `paper`/`wiki`/`protocol`/`write`/`review`, com cada skill antiga virando um modo 1:1, sem perder capacidade e com migração automática dos projetos.

**Architecture:** Cada modo mora em `skills/<skill>/modes/<mode>.md` com frontmatter próprio (reusa `parse_skill_file`). `core/skills.py` passa a carregar modos e resolver referências (`SkillRef`); `core/skill_refs.py` reescreve invocações antigas. O gerador de índices deriva do conjunto de modos o `when_to_use`, `allowed-tools`, `argument-hint`, a tabela frase→modo e os catálogos. Consumidores do nome de skill (compose, disclosure, findings, installer, doctor, update) passam a ler do registry.

**Tech Stack:** Python 3.12, Typer, Pydantic v2, PyYAML, pytest, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-09-12-superficie-de-skills-design.md` (D1, D2, D6, D7 + Emenda de implementação).

## Global Constraints

- Layering: `core/` NUNCA importa de `domains/`; domínios mutuamente independentes (exceção `write` → `protocol`).
- Fachadas finas: `cli.py` só parsing + chamada + saída via `core/output.Console`; subcomando novo envolto em `cli_run`.
- `mypy --strict`; `from __future__ import annotations` em todo módulo; value objects `@dataclass(frozen=True)`.
- Docstrings e mensagens em pt-BR com comando de correção embutido; identificadores em inglês.
- Princípio IV: valores de proveniência já gravados (`generator: wiki-query`, `extracted_model`) nunca são reescritos.
- ADRs aceitos, `CHANGELOG.md` histórico, `docs/superpowers/plans/archive/` e specs antigos NÃO são editados.
- Blocos gerados: editar a fonte e rodar `uv run python .github/scripts/gen_indexes.py` — nunca o bloco à mão.
- Nomes: skills `start`, `paper`, `wiki`, `protocol`, `write`, `review`; modos conforme tabela da Task 4.
- Release: F1 é MINOR `⚠ Breaking` (ADR-0015). Este plano NÃO corta release (versão, tag, PR ficam para o passo de release do RELEASING.md).

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/prumo_assist/core/skills.py` (modificar) | parse de modos, `SkillRef`, registry com `iter_modes`/`find_mode`/`legacy_map`/`resolve`, staleness por modo |
| `src/prumo_assist/core/skill_refs.py` (criar) | reescrita de invocações antigas em texto e num `pj_*`; diagnóstico de sobras |
| `.github/scripts/gen_indexes.py` (modificar) | tabela README e catálogo por modo; frontmatter derivado; blocos de preflight/prosa nos arquivos de modo; bloco `modes-table` no `SKILL.md` |
| `skills/<skill>/SKILL.md` (criar 5, modificar `start`) | porta da skill: descrição, regra de escolha de modo, bloco gerado |
| `skills/<skill>/modes/<mode>.md` (mover 16) | corpo do modo (ex-`SKILL.md`) |
| `skills/<skill>/{references,examples,templates}/` (mover) | material de apoio |
| `src/prumo_assist/domains/write/compose.py` (modificar) | kind → modo via `prumo.write_kind`; template em `templates/<mode>.md` |
| `src/prumo_assist/integrations/claude_code/installer.py` (modificar) | copia a árvore inteira da skill |
| `src/prumo_assist/domains/write/disclosure.py` (modificar) | agrega por `SkillRef`; tarefa vem de `prumo.disclosure_task` |
| `src/prumo_assist/domains/wiki/findings.py`, `domains/wiki/cli.py` (modificar) | `generator` default `wiki/query` |
| `src/prumo_assist/cli.py` (modificar) | `update` roda `migrate_skill_names`; `doctor` emite `[skill_obsoleta]` |
| `templates/pj_base/**`, `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/*.md` (modificar) | invocações novas |
| `docs/adr/adr-0032-superficie-por-dominio-e-modos.md` (criar) | decisão estrutural |
| `tests/fixtures/routing_phrases.toml` (criar) | lista-ouro de 30 frases (critério manual de F1) |

---

### Task 1: Modos no parser e no registry (`core/skills.py`)

**Files:**
- Modify: `src/prumo_assist/core/skills.py`
- Test: `tests/unit/core/test_skills.py`

**Interfaces:**
- Produces:
  - `SkillManifest` ganha campos `phrases: tuple[str, ...] = ()`, `legacy: tuple[str, ...] = ()`, `write_kind: str | None = None`, `disclosure_task: str | None = None`, `allowed_tools: tuple[str, ...] = ()`, `argument_hint: str | None = None`, `modes: tuple[SkillManifest, ...] = ()`.
  - `@dataclass(frozen=True) class SkillRef: skill: str; mode: str` com propriedades `slug -> "skill/mode"` e `invocation -> "prumo-assist:skill mode"`.
  - `load_modes(skill_dir: Path) -> tuple[SkillManifest, ...]`.
  - `SkillRegistry.iter_modes() -> list[tuple[SkillRef, SkillManifest]]`, `find_mode(ref: SkillRef) -> SkillManifest | None`, `legacy_map() -> dict[str, SkillRef]`, `resolve(value: str) -> SkillRef | None`.
  - `stale_guideline_warnings` passa a olhar modos também.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/unit/core/test_skills.py`:

```python
from prumo_assist.core.skills import SkillRef, load_modes


def _skill_with_modes(root: Path) -> Path:
    _write(root / "paper" / "SKILL.md", "---\nname: paper\ndescription: Acervo.\n---\n\n# paper\n")
    _write(
        root / "paper" / "modes" / "extract.md",
        "---\nname: extract\ndescription: Extrai PDF.\n"
        "allowed-tools: Read Bash(prumo paper *) Agent\n"
        'argument-hint: "[citekey]"\n'
        "prumo:\n  phrases: [\"resuma o paper X\"]\n"
        "  legacy: [paper-extract, paper-extract-all]\n"
        "  disclosure_task: structured extraction\n"
        "  requires: [cli]\n---\n\n# extract\n",
    )
    _write(
        root / "paper" / "modes" / "library.md",
        "---\nname: library\ndescription: Sync.\nprumo:\n  phrases: [\"sincroniza\"]\n"
        "  legacy: paper-manager\n---\n\n# library\n",
    )
    return root


def test_allowed_tools_tokeniza_parenteses_com_espaco(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    m = parse_skill_file(root / "paper" / "modes" / "extract.md")
    assert m.allowed_tools == ("Read", "Bash(prumo paper *)", "Agent")
    assert m.argument_hint == "[citekey]"
    assert m.phrases == ("resuma o paper X",)
    assert m.legacy == ("paper-extract", "paper-extract-all")
    assert m.disclosure_task == "structured extraction"


def test_legacy_string_unica_vira_tupla(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    assert parse_skill_file(root / "paper" / "modes" / "library.md").legacy == ("paper-manager",)


def test_load_modes_ordena_e_valida_nome_igual_ao_arquivo(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    modes = load_modes(root / "paper")
    assert [m.name for m in modes] == ["extract", "library"]
    _write(root / "paper" / "modes" / "bad.md", "---\nname: other\ndescription: x\nprumo:\n  phrases: [a]\n---\n")
    with pytest.raises(ManifestError, match="bad.md"):
        load_modes(root / "paper")


def test_modo_sem_frase_eh_erro(tmp_path: Path) -> None:
    _write(tmp_path / "s" / "SKILL.md", "---\nname: s\ndescription: d\n---\n")
    _write(tmp_path / "s" / "modes" / "m.md", "---\nname: m\ndescription: d\n---\n")
    with pytest.raises(ManifestError, match="phrases"):
        load_modes(tmp_path / "s")


def test_registry_anexa_modos_e_resolve_referencias(tmp_path: Path) -> None:
    reg, _ = load_skill_registry(_skill_with_modes(tmp_path))
    assert [m.name for m in reg.get("paper").modes] == ["extract", "library"]
    ref = SkillRef("paper", "extract")
    assert ref.slug == "paper/extract"
    assert ref.invocation == "prumo-assist:paper extract"
    assert reg.legacy_map()["paper-extract-all"] == ref
    for value in ("paper/extract", "prumo-assist:paper extract", "paper-extract", "prumo-assist:paper-extract"):
        assert reg.resolve(value) == ref, value
    assert reg.resolve("paper") is None
    assert reg.resolve("nada/aqui") is None
    assert reg.find_mode(ref) is not None
    assert [r.slug for r, _ in reg.iter_modes()] == ["paper/extract", "paper/library"]


def test_legacy_duplicado_entre_modos_eh_erro(tmp_path: Path) -> None:
    root = _skill_with_modes(tmp_path)
    _write(
        root / "wiki" / "SKILL.md", "---\nname: wiki\ndescription: w\n---\n"
    )
    _write(
        root / "wiki" / "modes" / "query.md",
        "---\nname: query\ndescription: q\nprumo:\n  phrases: [q]\n  legacy: paper-manager\n---\n",
    )
    with pytest.raises(ManifestError, match="paper-manager"):
        load_skill_registry(root)


def test_stale_guideline_warnings_olha_os_modos(tmp_path: Path) -> None:
    _write(tmp_path / "review" / "SKILL.md", "---\nname: review\ndescription: r\n---\n")
    _write(
        tmp_path / "review" / "modes" / "critique.md",
        "---\nname: critique\ndescription: c\nprumo:\n  phrases: [x]\n"
        '  guidelines_reviewed: "2020-01-01"\n---\n',
    )
    reg, _ = load_skill_registry(tmp_path)
    out = stale_guideline_warnings(reg, today=date(2026, 9, 12))
    assert len(out) == 1 and "review critique" in out[0]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_skills.py -q`
Expected: FAIL (`ImportError: cannot import name 'SkillRef'`).

- [ ] **Step 3: Implementar**

Em `core/skills.py`:

```python
_TOOL_TOKEN_RE = re.compile(r"[^\s(]+\([^)]*\)|\S+")


def _str_tuple(raw: object, *, field_name: str, path: Path) -> tuple[str, ...]:
    """Normaliza string-ou-lista em tupla sem duplicatas (ordem preservada)."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        raise ManifestError(f"{path}: {field_name} deve ser string ou lista.")
    return tuple(dict.fromkeys(i.strip() for i in items if i.strip()))


@dataclass(frozen=True)
class SkillRef:
    """Endereço de um modo: ``skill`` + ``mode`` (ex.: ``paper`` + ``extract``)."""

    skill: str
    mode: str

    @property
    def slug(self) -> str:
        return f"{self.skill}/{self.mode}"

    @property
    def invocation(self) -> str:
        return f"prumo-assist:{self.skill} {self.mode}"
```

No `parse_skill_file`: ler `allowed-tools` (tokenizar com `_TOOL_TOKEN_RE`), `argument-hint`, e do bloco `prumo` os campos `phrases`, `legacy`, `write_kind`, `disclosure_task`, acrescentando-os ao conjunto de chaves conhecidas (fora de `extra`).

```python
def load_modes(skill_dir: Path) -> tuple[SkillManifest, ...]:
    """Modos de uma skill: ``<skill_dir>/modes/*.md``, em ordem alfabética.

    Cada arquivo é parseado como um ``SKILL.md`` (mesmo contrato de frontmatter).
    ``name`` precisa bater com o nome do arquivo — é o endereço usado na invocação —
    e todo modo declara ao menos uma frase em ``prumo.phrases``, porque é dela que
    o gerador deriva o roteamento.
    """
    modes_dir = skill_dir / "modes"
    if not modes_dir.is_dir():
        return ()
    out: list[SkillManifest] = []
    for path in sorted(modes_dir.glob("*.md")):
        mode = parse_skill_file(path)
        if mode.name != path.stem:
            raise ManifestError(f"{path}: name '{mode.name}' difere do arquivo '{path.name}'.")
        if not mode.phrases:
            raise ManifestError(f"{path}: prumo.phrases obrigatório (ao menos uma frase) em modo.")
        out.append(mode)
    return tuple(out)
```

Em `load_skill_registry`, depois de `parse_skill_file(skill_md)`: `manifest = replace(manifest, modes=load_modes(child))` (dentro do mesmo `try`, para respeitar `strict`). Ao final, construir o registry e chamar `registry.legacy_map()` uma vez para validar duplicatas (levanta `ManifestError` citando o nome legado nos dois modos).

Métodos do `SkillRegistry`:

```python
    def iter_modes(self) -> list[tuple[SkillRef, SkillManifest]]:
        return [(SkillRef(n, m.name), m) for n in self.names() for m in self.skills[n].modes]

    def find_mode(self, ref: SkillRef) -> SkillManifest | None:
        skill = self.skills.get(ref.skill)
        if skill is None:
            return None
        return next((m for m in skill.modes if m.name == ref.mode), None)

    def legacy_map(self) -> dict[str, SkillRef]:
        out: dict[str, SkillRef] = {}
        for ref, mode in self.iter_modes():
            for old in mode.legacy:
                if old in out:
                    raise ManifestError(
                        f"nome legado '{old}' declarado em {out[old].slug} e {ref.slug}."
                    )
                out[old] = ref
        return out

    def resolve(self, value: str) -> SkillRef | None:
        raw = value.strip().removeprefix("/").removeprefix("prumo-assist:")
        for sep in ("/", " "):
            if sep in raw:
                skill, _, mode = raw.partition(sep)
                ref = SkillRef(skill.strip(), mode.strip())
                return ref if self.find_mode(ref) else None
        return self.legacy_map().get(raw)
```

`stale_guideline_warnings`: iterar `registry.names()` (skills) e `registry.iter_modes()`; rótulo `skill '<nome>'` para skill e `skill '<skill> <mode>'` para modo.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core/test_skills.py -q`
Expected: PASS (todos, inclusive os antigos).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/skills.py tests/unit/core/test_skills.py
git commit -m "feat(core): modos de skill, SkillRef e resolução de nomes legados"
```

---

### Task 2: Reescrita de invocações antigas (`core/skill_refs.py`)

**Files:**
- Create: `src/prumo_assist/core/skill_refs.py`
- Test: `tests/unit/core/test_skill_refs.py`

**Interfaces:**
- Consumes: `SkillRef` (Task 1).
- Produces:
  - `rewrite_invocations(text: str, legacy: Mapping[str, SkillRef]) -> tuple[str, int]`
  - `@dataclass(frozen=True) class RefChange: path: str; count: int`
  - `scan_skill_refs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]` (só lê)
  - `migrate_skill_names(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]` (escreve)
  - `legacy_installed_dirs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[str]`

- [ ] **Step 1: Testes que falham**

```python
"""Tests da reescrita de invocações de skills antigas (spec D6)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.skill_refs import (
    RefChange,
    legacy_installed_dirs,
    migrate_skill_names,
    rewrite_invocations,
    scan_skill_refs,
)
from prumo_assist.core.skills import SkillRef

LEGACY = {
    "paper-extract": SkillRef("paper", "extract"),
    "paper-extract-all": SkillRef("paper", "extract"),
    "paper-manager": SkillRef("paper", "library"),
    "wiki-query": SkillRef("wiki", "query"),
}


def test_reescreve_token_prefixado_preservando_barra_e_argumentos() -> None:
    out, n = rewrite_invocations("rode `/prumo-assist:paper-manager sync` e /prumo-assist:paper-extract @k", LEGACY)
    assert out == "rode `/prumo-assist:paper library sync` e /prumo-assist:paper extract @k"
    assert n == 2


def test_nome_mais_longo_vence() -> None:
    out, n = rewrite_invocations("/prumo-assist:paper-extract-all --limit 5", LEGACY)
    assert out == "/prumo-assist:paper extract --limit 5"
    assert n == 1


def test_nao_toca_valor_sem_prefixo_nem_nome_desconhecido() -> None:
    text = "generator: wiki-query\n/prumo-assist:start\nprumo-assist:wiki-queryx\n"
    assert rewrite_invocations(text, LEGACY) == (text, 0)


def test_idempotente() -> None:
    once, _ = rewrite_invocations("/prumo-assist:wiki-query", LEGACY)
    assert rewrite_invocations(once, LEGACY) == (once, 0)


def _pj(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_x"
    (pj / ".claude").mkdir(parents=True)
    (pj / "README.md").write_text("use /prumo-assist:paper-manager\n", encoding="utf-8")
    (pj / ".claude" / "pj_config.toml").write_text("# /prumo-assist:paper-extract-all\n", encoding="utf-8")
    papers = pj / "docs" / "references" / "papers" / "k"
    papers.mkdir(parents=True)
    (papers / "_extract.md").write_text("/prumo-assist:paper-extract\n", encoding="utf-8")
    (pj / ".venv").mkdir()
    (pj / ".venv" / "x.md").write_text("/prumo-assist:wiki-query\n", encoding="utf-8")
    (pj / "notes.py").write_text("# /prumo-assist:wiki-query\n", encoding="utf-8")
    return pj


def test_scan_lista_so_md_e_toml_fora_dos_excluidos(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    assert scan_skill_refs(pj, LEGACY) == [
        RefChange(".claude/pj_config.toml", 1),
        RefChange("README.md", 1),
    ]
    assert "paper-manager" in (pj / "README.md").read_text(encoding="utf-8")


def test_migrate_escreve_e_zera_o_scan(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    changes = migrate_skill_names(pj, LEGACY)
    assert [c.path for c in changes] == [".claude/pj_config.toml", "README.md"]
    assert (pj / "README.md").read_text(encoding="utf-8") == "use /prumo-assist:paper library\n"
    assert scan_skill_refs(pj, LEGACY) == []
    assert "paper-extract" in (pj / "docs/references/papers/k/_extract.md").read_text(encoding="utf-8")


def test_legacy_installed_dirs(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / ".claude" / "skills" / "wiki-query").mkdir(parents=True)
    (pj / ".claude" / "skills" / "wiki").mkdir(parents=True)
    assert legacy_installed_dirs(pj, LEGACY) == [".claude/skills/wiki-query"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_skill_refs.py -q`
Expected: FAIL (`ModuleNotFoundError: prumo_assist.core.skill_refs`).

- [ ] **Step 3: Implementar**

```python
"""Reescrita de invocações de skills antigas (spec D6, superfície por domínio).

Só o TOKEN de invocação muda — ``prumo-assist:<antigo>`` vira
``prumo-assist:<skill> <modo>``. Valor sem o prefixo (``generator: wiki-query``)
é dado de proveniência e fica como está (Princípio IV). O acervo gerado em
``docs/references/papers/`` também fica: é saída de máquina, não instrução.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.skills import SkillRef

_SUFFIXES = frozenset({".md", ".toml"})
_SKIP_DIRS = frozenset({".git", ".venv", ".prumo", "node_modules", "graphify-out", "_build"})
_SKIP_PREFIX = "docs/references/papers/"


@dataclass(frozen=True)
class RefChange:
    """Um arquivo do ``pj_*`` com ``count`` invocações antigas."""

    path: str
    count: int


def _pattern(legacy: Mapping[str, SkillRef]) -> re.Pattern[str] | None:
    if not legacy:
        return None
    names = sorted(legacy, key=len, reverse=True)
    alternation = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w-])prumo-assist:({alternation})(?![\w-])")


def rewrite_invocations(text: str, legacy: Mapping[str, SkillRef]) -> tuple[str, int]:
    """Troca cada ``prumo-assist:<antigo>`` pela invocação nova. Devolve (texto, trocas)."""
    pattern = _pattern(legacy)
    if pattern is None:
        return text, 0
    return pattern.subn(lambda m: legacy[m.group(1)].invocation, text)


def _candidates(pj_root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(pj_root.rglob("*")):
        if not path.is_file() or path.suffix not in _SUFFIXES:
            continue
        rel = path.relative_to(pj_root)
        if _SKIP_DIRS & set(rel.parts) or rel.as_posix().startswith(_SKIP_PREFIX):
            continue
        out.append(path)
    return out


def _walk(pj_root: Path, legacy: Mapping[str, SkillRef], *, write: bool) -> list[RefChange]:
    changes: list[RefChange] = []
    for path in _candidates(pj_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, count = rewrite_invocations(text, legacy)
        if not count:
            continue
        if write:
            path.write_text(new, encoding="utf-8")
        changes.append(RefChange(path.relative_to(pj_root).as_posix(), count))
    return changes


def scan_skill_refs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Arquivos com invocação antiga, sem escrever nada (``--dry-run`` e ``doctor``)."""
    return _walk(pj_root, legacy, write=False)


def migrate_skill_names(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Reescreve as invocações antigas do projeto. Idempotente."""
    return _walk(pj_root, legacy, write=True)


def legacy_installed_dirs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[str]:
    """``.claude/skills/<antigo>/`` que sobraram de um ``prumo init`` anterior.

    Não são apagados: podem ter sido customizados (a própria skill de estilo
    sugeria copiar-se para lá). O ``doctor`` aponta; a pessoa decide.
    """
    root = pj_root / ".claude" / "skills"
    if not root.is_dir():
        return []
    return [
        f".claude/skills/{d.name}" for d in sorted(root.iterdir()) if d.is_dir() and d.name in legacy
    ]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core/test_skill_refs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/skill_refs.py tests/unit/core/test_skill_refs.py
git commit -m "feat(core): reescrita de invocações de skills antigas"
```

---

### Task 3: Gerador ciente de modos (`gen_indexes.py`)

**Files:**
- Modify: `.github/scripts/gen_indexes.py`
- Test: `tests/unit/test_gen_indexes.py`

**Interfaces:**
- Consumes: `SkillManifest.modes`, `phrases`, `allowed_tools`, `argument_hint`, `SkillRegistry.iter_modes` (Task 1).
- Produces (funções puras testadas):
  - `render_skills_table(registry) -> str` — colunas `Você diz | Invocação | O que faz`; uma linha por modo + uma linha por skill sem modos.
  - `render_skills_catalog(registry) -> str` — `- `/prumo-assist:<skill> <mode>` — "<frase>" — <descrição>`.
  - `render_modes_table(skill: SkillManifest) -> str` — tabela `| Você diz | Modo |` com todas as frases.
  - `derived_frontmatter(skill: SkillManifest) -> dict[str, str]` — chaves `when_to_use`, `allowed-tools`, `argument-hint` já serializadas como texto YAML.
  - `replace_frontmatter_key(text: str, key: str, rendered: str, *, where: str) -> str` — substitui a chave (escalar ou bloco `|`) no frontmatter; insere antes de `prumo:` se ausente.
  - `render_skill_blocks(manifest)` inalterado para arquivos de modo e skills sem modos; `SKILL.md` com modos recebe `[("preflight", "", ""), ("prose", "", ""), ("modes-table", render_modes_table(skill), "")]`.

- [ ] **Step 1: Testes que falham**

Ajustar os testes existentes que usam `registry.get("scientific-writing")`, `"write-projeto-cep"`, `"write-paper"`, `"paper-extract"` para o modo equivalente via um helper, e acrescentar:

```python
def _mode(registry: Any, skill: str, mode: str) -> Any:
    from prumo_assist.core.skills import SkillRef

    found = registry.find_mode(SkillRef(skill, mode))
    assert found is not None, f"{skill}/{mode}"
    return found


def test_skills_table_tem_uma_linha_por_modo(gen: ModuleType, registry: Any) -> None:
    table = gen.render_skills_table(registry)
    assert "`/prumo-assist:paper extract`" in table
    assert "`/prumo-assist:start`" in table
    n_linhas = len(registry.iter_modes()) + sum(1 for n in registry.names() if not registry.get(n).modes)
    assert table.count("\n") + 1 == n_linhas + 2


def test_modes_table_lista_todas_as_frases(gen: ModuleType, registry: Any) -> None:
    skill = registry.get("paper")
    table = gen.render_modes_table(skill)
    for mode in skill.modes:
        for phrase in mode.phrases:
            assert phrase in table
        assert f"`{mode.name}`" in table


def test_frontmatter_derivado_une_tools_sem_duplicar(gen: ModuleType, registry: Any) -> None:
    skill = registry.get("write")
    derived = gen.derived_frontmatter(skill)
    tools = derived["allowed-tools"].removeprefix("allowed-tools: ").split(" ")
    assert "Read" in tools and tools.count("Read") == 1
    assert derived["argument-hint"].startswith('argument-hint: "[')
    assert derived["when_to_use"].startswith("when_to_use: |\n")


def test_replace_frontmatter_key_troca_bloco_e_escalar(gen: ModuleType) -> None:
    text = (
        "---\nname: x\ndescription: d\nwhen_to_use: |\n  velho\n  velho2\n"
        "allowed-tools: Read\nprumo:\n  version: 1\n---\n\nbody\n"
    )
    out = gen.replace_frontmatter_key(text, "when_to_use", "when_to_use: |\n  novo", where="x")
    out = gen.replace_frontmatter_key(out, "allowed-tools", "allowed-tools: Read Grep", where="x")
    assert "velho" not in out and "  novo\n" in out
    assert "allowed-tools: Read Grep\n" in out
    assert out.endswith("---\n\nbody\n")


def test_replace_frontmatter_key_insere_antes_de_prumo(gen: ModuleType) -> None:
    text = "---\nname: x\ndescription: d\nprumo:\n  version: 1\n---\n"
    out = gen.replace_frontmatter_key(text, "argument-hint", 'argument-hint: "[a]"', where="x")
    assert 'description: d\nargument-hint: "[a]"\nprumo:' in out


def test_skill_md_com_modos_nao_carrega_preflight(gen: ModuleType, registry: Any) -> None:
    blocks = {tag: body for tag, body, _ in gen.render_skill_blocks(registry.get("paper"))}
    assert blocks["preflight"] == "" and blocks["prose"] == ""
    assert "extract" in blocks["modes-table"]


def test_toda_frase_de_modo_eh_unica_no_plugin(registry: Any) -> None:
    vistas: dict[str, str] = {}
    for ref, mode in registry.iter_modes():
        for phrase in mode.phrases:
            assert phrase not in vistas, f"'{phrase}' em {vistas.get(phrase)} e {ref.slug}"
            vistas[phrase] = ref.slug
```

Os testes de prosa passam a usar `_mode(registry, "write", "style")` (ex-`scientific-writing`), `_mode(registry, "protocol", "cep")` (ex-`write-projeto-cep`), `_mode(registry, "write", "manuscript")` (ex-`write-paper`), `_mode(registry, "paper", "extract")`; `test_todas_as_skills_de_prosa_carregam_o_bloco` itera `registry.iter_modes()` com os slugs `write/style`, `write/manuscript`, `protocol/cep`, `write/section`, `protocol/sap`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/test_gen_indexes.py -q`
Expected: FAIL (as skills ainda não existem e as funções novas não existem). Os testes contra o repo real só passam depois da Task 4; os de funções puras (`replace_frontmatter_key`) passam já no Step 4.

- [ ] **Step 3: Implementar**

```python
def _one_line(text: str) -> str:
    return " ".join(text.split())


def render_skills_table(registry: SkillRegistry) -> str:
    lines = ["| Você diz | Invocação | O que faz |", "|---|---|---|"]
    for name in registry.names():
        skill = registry.get(name)
        if not skill.modes:
            lines.append(f"| — | `/prumo-assist:{name}` | {_one_line(skill.description)} |")
            continue
        for mode in skill.modes:
            lines.append(
                f'| "{mode.phrases[0]}" | `/prumo-assist:{name} {mode.name}` | '
                f"{_one_line(mode.description)} |"
            )
    return "\n".join(lines)


def render_skills_catalog(registry: SkillRegistry) -> str:
    lines = []
    for name in registry.names():
        skill = registry.get(name)
        if not skill.modes:
            lines.append(f"- `/prumo-assist:{name}` — {_one_line(skill.description)}")
            continue
        for mode in skill.modes:
            lines.append(
                f'- `/prumo-assist:{name} {mode.name}` — "{mode.phrases[0]}" — '
                f"{_one_line(mode.description)}"
            )
    return "\n".join(lines)


def render_modes_table(skill: SkillManifest) -> str:
    lines = ["| Você diz | Modo |", "|---|---|"]
    for mode in skill.modes:
        for phrase in mode.phrases:
            lines.append(f'| "{phrase}" | `{mode.name}` |')
    return "\n".join(lines)


def derived_frontmatter(skill: SkillManifest) -> dict[str, str]:
    tools: list[str] = []
    for mode in skill.modes:
        tools.extend(t for t in mode.allowed_tools if t not in tools)
    names = "|".join(m.name for m in skill.modes)
    when = ["when_to_use: |", f"  Modos: {', '.join(m.name for m in skill.modes)}. Frases típicas:"]
    for mode in skill.modes:
        quoted = "; ".join(f'"{p}"' for p in mode.phrases)
        when.append(f"  - {mode.name}: {quoted}")
    return {
        "when_to_use": "\n".join(when),
        "allowed-tools": "allowed-tools: " + " ".join(tools),
        "argument-hint": f'argument-hint: "[{names}] [argumentos do modo]"',
    }


def replace_frontmatter_key(text: str, key: str, rendered: str, *, where: str) -> str:
    match = _FRONT_RE.match(text)
    if not match:
        raise SystemExit(f"gen_indexes: {where} sem frontmatter.")
    lines = match.group(1).split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.startswith(f"{key}:")), None)
    new_lines = rendered.split("\n")
    if start is None:
        anchor = next((i for i, ln in enumerate(lines) if ln.startswith("prumo:")), len(lines))
        lines[anchor:anchor] = new_lines
    else:
        end = start + 1
        while end < len(lines) and (lines[end].startswith(" ") or lines[end] == ""):
            end += 1
        lines[start:end] = new_lines
    front = "---\n" + "\n".join(lines) + "\n---"
    return front + text[match.end() :]
```

`render_skill_blocks(manifest)`: se `manifest.modes` → `[("preflight", "", ""), ("prose", "", ""), ("modes-table", render_modes_table(manifest), "")]`; senão, o comportamento atual.

`main()`: no loop por skill, aplicar `replace_frontmatter_key` para cada item de `derived_frontmatter` quando `manifest.modes`; depois, para cada modo, compor `render_skill_blocks(mode)` sobre o texto do arquivo do modo com o mesmo `_sync`.

- [ ] **Step 4: Rodar os testes puros**

Run: `uv run pytest tests/unit/test_gen_indexes.py -q -k "replace_frontmatter_key or replace_block or stamp_block or strip_block or fragmento"`
Expected: PASS.

- [ ] **Step 5: Commit (junto com a Task 4, que faz os testes de repo passarem)**

---

### Task 4: Mover as 16 skills para 5 skills com modos

**Files:**
- Move (`git mv`): `skills/<antiga>/SKILL.md` → `skills/<skill>/modes/<mode>.md` conforme tabela
- Move: `skills/peer-review/references/reporting-guidelines.md` → `skills/review/references/reporting-guidelines.md`; `skills/peer-review/examples/sample_report.json` → `skills/review/examples/sample_report.json`; `skills/formulate-picot/references/operations-advanced.md` → `skills/protocol/references/operations-advanced.md`; `skills/write-paper/template.md` → `skills/write/templates/manuscript.md`; `skills/write-scientific/template.md` → `skills/write/templates/section.md`; `skills/write-statistics/template.md` → `skills/protocol/templates/sap.md`; `skills/write-projeto-cep/template.md` → `skills/protocol/templates/cep.md`
- Create: `skills/{paper,wiki,protocol,write,review}/SKILL.md`, `skills/write/modes/disclosure.md`
- Modify: `skills/start/SKILL.md`, `tests/unit/test_guidelines_present.py`

| Antiga | Nova | `legacy` | `write_kind` | `disclosure_task` |
|---|---|---|---|---|
| paper-manager | paper/library | paper-manager | — | — |
| paper-extract | paper/extract | [paper-extract, paper-extract-all] | — | structured extraction of key information from source documents |
| citation-support | paper/support | citation-support | — | — |
| wiki-ingest | wiki/ingest | wiki-ingest | — | — |
| wiki-query | wiki/query | wiki-query | — | synthesis of answers grounded in the project knowledge base |
| wiki-lint | wiki/lint | wiki-lint | — | — |
| active-learning | wiki/study | active-learning | — | synthesis of study-session findings |
| formulate-picot | protocol/picot | formulate-picot | — | — |
| write-statistics | protocol/sap | write-statistics | statistics | drafting of the statistical analysis plan |
| write-projeto-cep | protocol/cep | write-projeto-cep | projeto-cep | drafting of the research ethics submission |
| write-paper | write/manuscript | write-paper | paper | drafting of manuscript sections |
| write-scientific | write/section | write-scientific | scientific | drafting of prose sections |
| scientific-writing | write/style | scientific-writing | — | — |
| — | write/disclosure | — | — | — |
| peer-review | review/critique | peer-review | — | critical review of draft sections |
| review-reconcile | review/reconcile | review-reconcile | — | — |

Frases (`prumo.phrases`) — cada uma aparece em exatamente um modo:

| Modo | Frases |
|---|---|
| paper/library | "sincroniza minha bibliografia"; "importa minhas anotações do Zotero"; "encontra paper sobre Y"; "quem cita Z"; "marca o paper principal"; "liga o projeto à coleção do Zotero" |
| paper/extract | "resuma o paper X"; "extraia os principais pontos do paper"; "processa todos os papers novos" |
| paper/support | "as referências batem com o que eu afirmo?"; "checa se as citações sustentam as frases" |
| wiki/ingest | "adiciona esta fonte ao wiki"; "salva este link no wiki"; "registra este tutorial" |
| wiki/query | "o que a literatura diz sobre X"; "compara Y e Z"; "quais decisões tomamos sobre W" |
| wiki/lint | "audita o wiki"; "encontra páginas órfãs"; "o wiki está consistente?" |
| wiki/study | "me ensina X"; "me coloca à prova sobre Y"; "preciso fixar Z" |
| protocol/picot | "fecha a PICOT"; "formaliza a pergunta de pesquisa"; "a PICOT mudou" |
| protocol/sap | "gera o plano de análise estatística"; "justifica o tamanho amostral"; "planeja as análises de sensibilidade" |
| protocol/cep | "gera o projeto CEP"; "preciso submeter pra Plataforma Brasil" |
| write/manuscript | "escreve um draft do meu paper"; "rascunho IMRaD sobre X" |
| write/section | "escreve essa seção"; "expande este parágrafo" |
| write/style | "aplica as convenções de escrita científica"; "tira os travessões"; "passa pro inglês americano" |
| write/disclosure | "gera a declaração de uso de IA"; "disclosure de IA pro periódico" |
| review/critique | "revisa este draft"; "me dá um peer review"; "quais buracos no meu argumento" |
| review/reconcile | "reconcilia os eventos ambíguos da revisão"; "resolve as marcas sem âncora do docx" |

- [ ] **Step 1: `git mv` de todos os arquivos da tabela**

```bash
set -e
mv_mode() { mkdir -p "skills/$2/modes"; git mv "skills/$1/SKILL.md" "skills/$2/modes/$3.md"; }
mv_mode paper-manager paper library; mv_mode paper-extract paper extract; mv_mode citation-support paper support
mv_mode wiki-ingest wiki ingest; mv_mode wiki-query wiki query; mv_mode wiki-lint wiki lint; mv_mode active-learning wiki study
mv_mode formulate-picot protocol picot; mv_mode write-statistics protocol sap; mv_mode write-projeto-cep protocol cep
mv_mode write-paper write manuscript; mv_mode write-scientific write section; mv_mode scientific-writing write style
mv_mode peer-review review critique; mv_mode review-reconcile review reconcile
mkdir -p skills/review/references skills/review/examples skills/protocol/references skills/write/templates skills/protocol/templates
git mv skills/peer-review/references/reporting-guidelines.md skills/review/references/reporting-guidelines.md
git mv skills/peer-review/examples/sample_report.json skills/review/examples/sample_report.json
git mv skills/formulate-picot/references/operations-advanced.md skills/protocol/references/operations-advanced.md
git mv skills/write-paper/template.md skills/write/templates/manuscript.md
git mv skills/write-scientific/template.md skills/write/templates/section.md
git mv skills/write-statistics/template.md skills/protocol/templates/sap.md
git mv skills/write-projeto-cep/template.md skills/protocol/templates/cep.md
```

- [ ] **Step 2: Frontmatter de cada modo**

Em cada `modes/<mode>.md`: `name:` passa a ser o nome do modo; remover `when_to_use` (substituído por `prumo.phrases`); acrescentar `prumo.phrases`, `prumo.legacy` e, quando houver na tabela, `prumo.write_kind` e `prumo.disclosure_task`; `schema: PaperExtract/v1` → `schema: PaperCallout/v1`. Demais chaves (`description`, `argument-hint`, `allowed-tools`, `version`, `determinism`, `requires`, `prose`, `locale_lock`, `guidelines_reviewed`, `inputs`) ficam.

- [ ] **Step 3: Corpo dos modos — referências internas**

Reescrever invocações com a função da Task 2 sobre `skills/**/*.md`:

```bash
uv run python - <<'PY'
from pathlib import Path
from prumo_assist.core.skills import load_skill_registry
from prumo_assist.core.skill_refs import rewrite_invocations
reg, _ = load_skill_registry(Path("skills"))
for p in sorted(Path("skills").rglob("*.md")):
    new, n = rewrite_invocations(p.read_text(encoding="utf-8"), reg.legacy_map())
    if n:
        p.write_text(new, encoding="utf-8"); print(n, p)
PY
```

Depois, à mão, as menções sem prefixo que designam skill (listadas por `git grep -nE "peer-review|scientific-writing|write-paper|wiki-query|wiki-ingest|paper-manager|paper-extract|formulate-picot|review-reconcile|citation-support|wiki-lint|active-learning|write-scientific|write-statistics|write-projeto-cep" -- skills`), trocando por `` `review critique` ``, `` `write style` `` etc. Ficam como estão: `--generator wiki-query` no corpo de `wiki/query` e `--generator active-learning` em `wiki/study` passam a `--generator wiki/query` e `--generator wiki/study`; marcadores `<!-- paper-extract:begin -->` (formato de arquivo, Princípio IV); título `## [<data>] wiki-query |` do log vira `wiki/query`. Caminhos: `./template.md` → `../templates/<mode>.md`; `references/operations-advanced.md` → `../references/operations-advanced.md`; `references/reporting-guidelines.md` → `../references/reporting-guidelines.md`; `examples/sample_report.json` → `../examples/sample_report.json`. A sugestão de copiar para `.claude/skills/scientific-writing/` vira `.claude/skills/write/`.

- [ ] **Step 4: Criar `skills/write/modes/disclosure.md`**

```markdown
---
name: disclosure
description: "Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt e en)."
argument-hint: "[--lang pt|en]"
allowed-tools: Read Bash(prumo write disclosure *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1k tokens
  phrases: ["gera a declaração de uso de IA", "disclosure de IA pro periódico"]
  requires: [cli]
---

# write disclosure — declaração de uso de IA

1. Rode `prumo write disclosure --json` na raiz do `pj_*` (ou no escopo pedido).
2. Mostre o parágrafo no idioma pedido (`statement_pt` ou `statement_en`) e a tabela de ferramentas (`tools`: ferramenta, modelo, tarefa, contagem, revisão humana).
3. Se `tools` vier vazio, diga que nenhum artefato do projeto registra uso de IA. Não invente uso.
4. Nunca edite o parágrafo para acrescentar ferramenta que o comando não listou. Correção de proveniência é no artefato, não na declaração.
```

(Conferir os flags reais com `prumo write disclosure --help` antes de gravar e ajustar o passo 1.)

- [ ] **Step 5: Criar os 5 `SKILL.md`**

Modelo (repetir para cada skill com descrição própria):

```markdown
---
name: paper
description: "Acervo bibliográfico do pj_*: sincronizar com o Zotero, extrair PDFs em callout estruturado e checar se as citações sustentam as frases."
when_to_use: |
  (gerado)
argument-hint: "(gerado)"
allowed-tools: (gerado)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# paper — acervo bibliográfico

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/prumo-assist:paper extract @smith2024` → modo `extract`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
<!-- prumo:modes-table:end -->
```

Descrições:
- `paper`: a acima.
- `wiki`: "Wiki do pj_*: ingerir fontes, responder perguntas com citação, auditar a saúde do wiki e conduzir sessões de estudo ancoradas nas fontes."
- `protocol`: "Protocolo do estudo: fechar e versionar a PICOT, gerar o plano de análise estatística e o projeto para CEP/Plataforma Brasil."
- `write`: "Escrita do manuscrito: draft IMRaD, seção avulsa, convenções editoriais de escrita científica e declaração de uso de IA."
- `review`: "Revisão: crítica substantiva do draft por seção e reconciliação dos eventos ambíguos do round-trip docx↔CriticMarkup."

- [ ] **Step 6: Atualizar `skills/start/SKILL.md`**

Descrição: "Porta de entrada do prumo-assist: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review)." Roteamento no passo 1: "bibliografia → `paper`; wiki e estudo → `wiki`; PICOT, PAE e CEP → `protocol`; escrita → `write`; revisão → `review`". Passo 7: `/prumo-assist:review critique`. Linha do qmd: "`wiki query` funciona em modo degradado".

- [ ] **Step 7: `tests/unit/test_guidelines_present.py`**

Caminhos: `review/modes/critique.md`, `review/references/reporting-guidelines.md`, `protocol/modes/sap.md`; templates `write/templates/manuscript.md`, `write/templates/section.md`, `protocol/templates/sap.md`, `protocol/templates/cep.md`; os globs `*/SKILL.md` passam a `**/*.md` sob `skills/`.

- [ ] **Step 8: Gerar e verificar**

Run: `uv run python .github/scripts/gen_indexes.py && uv run python .github/scripts/gen_indexes.py --check && uv run pytest tests/unit/test_gen_indexes.py tests/unit/test_guidelines_present.py tests/unit/core -q`
Expected: índices em dia; PASS.

- [ ] **Step 9: Commit**

```bash
git add -A skills .github/scripts/gen_indexes.py tests/unit/test_gen_indexes.py tests/unit/test_guidelines_present.py README.md
git commit -m "feat(skills)!: 16 skills viram start + paper/wiki/protocol/write/review com modos"
```

---

### Task 5: Compose resolve kind → modo

**Files:**
- Modify: `src/prumo_assist/domains/write/compose.py:68-86,227-243`
- Test: `tests/unit/write/test_compose_paths.py`, `tests/unit/write/test_compose_language.py`

**Interfaces:**
- Consumes: `load_skill_registry`, `SkillManifest.write_kind`, `SkillRegistry.iter_modes` (Task 1).
- Produces: `_mode_for_kind(kind: WriteKind) -> SkillManifest | None` (privada); `locale_lock` e `template_candidates` com a mesma assinatura.

- [ ] **Step 1: Teste que falha**

Em `test_compose_paths.py`, trocar a asserção do default:

```python
def test_resolve_template_default_from_skill_bundle(tmp_path: Path) -> None:
    """O template do plugin mora em skills/<skill>/templates/<modo>.md."""
    expected = {
        "paper": "write/templates/manuscript.md",
        "scientific": "write/templates/section.md",
        "statistics": "protocol/templates/sap.md",
        "projeto-cep": "protocol/templates/cep.md",
    }
    for kind, suffix in expected.items():
        out = resolve_template(pj_path=tmp_path, kind=kind)  # type: ignore[arg-type]
        assert out.as_posix().endswith(suffix), (kind, out)
```

Em `test_compose_language.py`, garantir que `locale_lock("projeto-cep") == "pt-BR"` e `locale_lock("paper") is None` (acrescentar se não existir).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_compose_paths.py tests/unit/write/test_compose_language.py -q`
Expected: FAIL (caminho `write-paper/template.md` não existe mais).

- [ ] **Step 3: Implementar**

```python
def _mode_for_kind(kind: WriteKind) -> SkillManifest | None:
    """Modo que declara ``prumo.write_kind == kind``, lido do bundle de skills.

    Fonte única: o frontmatter do modo. Nenhum mapa ``kind -> skill`` aqui.
    ``None`` quando o bundle não está resolvível (é opcional).
    """
    from prumo_assist.core.skills import load_skill_registry

    skills_root = find_resource("skills")
    if skills_root is None:
        return None
    registry, _ = load_skill_registry(skills_root, strict=False)
    return next((m for _, m in registry.iter_modes() if m.write_kind == kind), None)


def locale_lock(kind: WriteKind) -> str | None:
    mode = _mode_for_kind(kind)
    return mode.locale_lock if mode else None


def template_candidates(*, pj_path: Path, kind: WriteKind) -> dict[str, Path | None]:
    mode = _mode_for_kind(kind)
    plugin_default = mode.path.parent.parent / "templates" / f"{mode.name}.md" if mode else None
    return {
        "project_override": pj_path / ".claude" / "writing_templates" / f"{kind}.md",
        "plugin_default": plugin_default,
    }
```

Atualizar as docstrings de `locale_lock` e `template_candidates` para citar `skills/<skill>/templates/<modo>.md` e `prumo.write_kind`.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/write -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/compose.py tests/unit/write
git commit -m "fix(write): template e trava de idioma resolvidos pelo modo (prumo.write_kind)"
```

---

### Task 6: Installer copia a skill inteira

**Files:**
- Modify: `src/prumo_assist/integrations/claude_code/installer.py`
- Test: `tests/unit/integrations/test_claude_code_installer.py` (criar, com `tests/unit/integrations/__init__.py`)

**Interfaces:**
- Consumes: `SkillRegistry`, `SkillManifest.path`.
- Produces: `ClaudeCodeIntegration.install` copia `manifest.path.parent` inteiro (`shutil.copytree(..., dirs_exist_ok=True)`).

- [ ] **Step 1: Teste que falha**

```python
"""Installer do Claude Code: a skill vai inteira, com modos e material de apoio."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.skills import load_skill_registry
from prumo_assist.integrations.claude_code.installer import ClaudeCodeIntegration


def test_install_copia_modos_references_e_templates(tmp_path: Path) -> None:
    src = tmp_path / "skills" / "write"
    (src / "modes").mkdir(parents=True)
    (src / "templates").mkdir()
    (src / "SKILL.md").write_text("---\nname: write\ndescription: w\n---\n", encoding="utf-8")
    (src / "modes" / "section.md").write_text(
        "---\nname: section\ndescription: s\nprumo:\n  phrases: [x]\n---\n", encoding="utf-8"
    )
    (src / "templates" / "section.md").write_text("# t\n", encoding="utf-8")
    registry, _ = load_skill_registry(tmp_path / "skills")

    report = ClaudeCodeIntegration().install(tmp_path / "pj", registry)

    dest = tmp_path / "pj" / ".claude" / "skills" / "write"
    assert report.installed == ["write"]
    assert (dest / "modes" / "section.md").is_file()
    assert (dest / "templates" / "section.md").is_file()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/integrations -q`
Expected: FAIL (`modes/section.md` não copiado).

- [ ] **Step 3: Implementar**

Trocar a escrita do `SKILL.md` por:

```python
            try:
                shutil.copytree(manifest.path.parent, skills_root / name, dirs_exist_ok=True)
                installed.append(name)
            except OSError as e:
                skipped.append((name, f"erro de escrita: {e}"))
```

(import `shutil`; remover `dest_dir.mkdir`/`dest_file`; docstring do módulo: "copy skills/<name>/ → pj_x/.claude/skills/<name>/, com modes/, references/ e templates/").

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/integrations tests/unit/test_cli_init.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/integrations tests/unit/integrations
git commit -m "fix(integrations): installer copia a skill inteira (modos, references, templates)"
```

---

### Task 7: Proveniência e mensagens com nomes novos

**Files:**
- Modify: `src/prumo_assist/domains/write/disclosure.py`, `src/prumo_assist/domains/wiki/findings.py`, `src/prumo_assist/domains/wiki/cli.py:147`, `src/prumo_assist/core/deps.py:6,132`, `src/prumo_assist/domains/capture/route.py:107-135`, `src/prumo_assist/domains/paper/verify.py:587`, `src/prumo_assist/domains/write/cli.py:390`, `src/prumo_assist/domains/write/review.py:2853`, `src/prumo_assist/domains/protocol/picot_io.py:32`, `src/prumo_assist/domains/wiki/lint.py:364`, `src/prumo_assist/core/note_paths.py:6`, docstrings de módulo que citam skills (`domains/*/__init__.py`, `callout.py:1`, `schemas/v1.py`, `prep.py:4`, `protocol/ops.py`, `wiki/study.py:1`, `wiki/schemas/v1.py:1`, `core/skills.py:12`)
- Test: `tests/unit/write/test_disclosure.py`, `tests/unit/wiki/test_findings.py`, `tests/unit/capture/test_route.py`

**Interfaces:**
- Consumes: `SkillRegistry.resolve`, `find_mode`, `SkillManifest.disclosure_task` (Task 1); skills movidas (Task 4).
- Produces: `AIToolUse.tool` passa a `prumo-assist:<skill> <mode>` quando o valor resolve; valor desconhecido mantém o comportamento atual.

- [ ] **Step 1: Testes que falham**

```python
def test_legado_e_novo_agregam_numa_linha(tmp_path: Path) -> None:
    notes = tmp_path / "docs" / "studies" / "principal" / "notes"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text("---\ntype: finding\ngenerator: wiki-query\nadded: '2026-05-01'\n---\n", encoding="utf-8")
    (notes / "b.md").write_text("---\ntype: finding\ngenerator: wiki/query\nadded: '2026-05-02'\n---\n", encoding="utf-8")

    disc = generate_disclosure(root=tmp_path)

    assert len(disc.tools) == 1
    assert disc.tools[0].tool == "prumo-assist:wiki query"
    assert disc.tools[0].count == 2
    assert disc.tools[0].task == "synthesis of answers grounded in the project knowledge base"


def test_skill_desconhecida_mantem_o_valor(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text("---\ngenerator: minha-skill\n---\n", encoding="utf-8")
    disc = generate_disclosure(root=tmp_path)
    assert disc.tools[0].tool == "prumo-assist:minha-skill"
    assert disc.tools[0].task == "assistive text generation"
```

Atualizar as asserções existentes: `tool == "prumo-assist:paper extract"` (linha 77). `rec.skill == "paper-extract"` em `_record_from_fm` continua (o registro é cru; a canonização é no `_aggregate`).

`test_findings.py`: novo teste `archive_as_finding` sem `generator` grava `generator: wiki/query` e o log `## [data] wiki/query | finding arquivado`.

`test_route.py:42`: `assert "wiki ingest" in out.suggestion`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_disclosure.py tests/unit/wiki/test_findings.py tests/unit/capture/test_route.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

`disclosure.py` — remover `_TASK_BY_SKILL`; em `_aggregate`:

```python
def _canonical(skill: str, registry: SkillRegistry | None) -> tuple[str, str]:
    """(rótulo da ferramenta, tarefa) para um valor de proveniência, legado ou novo."""
    ref = registry.resolve(skill) if registry else None
    mode = registry.find_mode(ref) if registry and ref else None
    if ref is None:
        tool = skill if skill.startswith("prumo-assist") else f"prumo-assist:{skill}"
        return tool, _DEFAULT_TASK
    return ref.invocation, (mode.disclosure_task if mode and mode.disclosure_task else _DEFAULT_TASK)


def _load_registry() -> SkillRegistry | None:
    root = find_resource("skills")
    if root is None:
        return None
    registry, _ = load_skill_registry(root, strict=False)
    return registry
```

`_aggregate(records, registry)` agrupa por `(tool, model)` depois de `_canonical`; `generate_disclosure` passa `_load_registry()`. Docstring do módulo cita a canonização por `SkillRef`.

`findings.py` e `wiki/cli.py`: default `"wiki/query"`; docstring `(\"wiki/query\" ou \"wiki/study\")`.

`deps.py`: `required_by=["wiki query", "wiki ingest", "wiki study"]`, docstring idem.

`route.py`: "Use a skill `wiki ingest` …", `next_command="(no agent-host: /prumo-assist:wiki ingest <url>)"`, "a skill `/prumo-assist:paper extract <citekey>`".

Mensagens: `verify.py` "(ou /prumo-assist:paper library sync)"; `write/cli.py` e `review.py` "/prumo-assist:review reconcile"; `picot_io.py` "Rode `/prumo-assist:protocol picot init` primeiro."; `lint.py` "(candidato a /prumo-assist:wiki ingest)".

Docstrings: trocar o nome de skill citado pelo `skill modo` correspondente, sem mudar marcadores de formato (`<!-- paper-extract:begin -->`, `source: prumo-paper-extract` permanecem — Princípio IV).

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/write tests/unit/wiki tests/unit/capture tests/unit/paper tests/unit/protocol -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: proveniência canonizada por SkillRef e mensagens com os nomes novos"
```

---

### Task 8: `prumo update` migra e `doctor` aponta sobras

**Files:**
- Modify: `src/prumo_assist/cli.py` (`update_command`, `_update_summary`, `doctor_command`)
- Test: `tests/unit/test_cli_update.py`, `tests/unit/test_cli_doctor.py`

**Interfaces:**
- Consumes: `scan_skill_refs`, `migrate_skill_names`, `legacy_installed_dirs`, `RefChange` (Task 2); `SkillRegistry.legacy_map` (Task 1).
- Produces: payload do `update` ganha `"skill_refs": [{"path": str, "count": int}]`; `doctor` ganha issue `[skill_obsoleta]`.

- [ ] **Step 1: Testes que falham**

`test_cli_update.py`:

```python
def test_update_reescreve_invocacoes_antigas(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("use /prumo-assist:paper-manager sync\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(encoding="utf-8") == "use /prumo-assist:paper library sync\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_dry_run_lista_invocacoes_sem_escrever(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("/prumo-assist:wiki-query\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(encoding="utf-8") == "/prumo-assist:wiki-query\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_nao_reescreve_proveniencia(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    nota = pj / "docs" / "studies" / "principal" / "notes" / "f.md"
    nota.write_text("---\ntype: finding\ngenerator: wiki-query\n---\n", encoding="utf-8")

    runner.invoke(app, ["update", str(pj), "--json"])

    assert "generator: wiki-query" in nota.read_text(encoding="utf-8")
```

`test_cli_doctor.py`:

```python
def test_doctor_aponta_invocacao_antiga_e_skill_instalada_velha(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    assert runner.invoke(app, ["init", str(pj), "--json"]).exit_code == 0
    (pj / "README.md").write_text("/prumo-assist:peer-review\n", encoding="utf-8")
    (pj / ".claude" / "skills" / "peer-review").mkdir(parents=True)
    (pj / ".claude" / "skills" / "peer-review" / "SKILL.md").write_text("x", encoding="utf-8")

    res = runner.invoke(app, ["doctor", str(pj), "--json"])

    issues = json.loads(res.output)["issues"]
    obsoleta = [i for i in issues if i.startswith("[skill_obsoleta]")]
    assert len(obsoleta) == 1
    assert "README.md" in obsoleta[0] and "prumo update" in obsoleta[0]
    assert ".claude/skills/peer-review" in obsoleta[0]
```

(Se `test_cli_doctor.py` mocka `check_external_deps`, reusar o mesmo fixture/monkeypatch dos testes vizinhos.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py -q`
Expected: FAIL (`KeyError: 'skill_refs'`; issue ausente).

- [ ] **Step 3: Implementar**

Helper em `cli.py` (fachada — só compõe chamadas de `core`):

```python
def _legacy_skill_map() -> dict[str, SkillRef]:
    """Nomes antigos → modo novo, lidos do bundle de skills (vazio sem bundle)."""
    skills_dir = _resolve_skills_dir()
    if skills_dir is None:
        return {}
    registry, _ = load_skill_registry(skills_dir, strict=False)
    return registry.legacy_map()
```

`update_command`: `legacy = _legacy_skill_map()`; em dry-run `skill_refs = scan_skill_refs(pj_root, legacy)`; senão `skill_refs = migrate_skill_names(pj_root, legacy)` (depois de `migrate_project_context`, antes do reflow). Payload `"skill_refs": [asdict(c) for c in skill_refs]`; `_update_summary(..., skill_refs=len(skill_refs))` acrescenta "N arquivo(s) com invocação antiga reescrita(s). " (ou "a reescrever" em dry-run) e deixa de dizer "nada a atualizar" quando houver.

`doctor_command`, depois de `standard_issues`:

```python
    legacy = _legacy_skill_map()
    antigos = [c.path for c in scan_skill_refs(target, legacy)]
    instalados = legacy_installed_dirs(target, legacy)
    if antigos or instalados:
        partes = []
        if antigos:
            partes.append(f"invocações antigas em {', '.join(antigos)}")
        if instalados:
            partes.append(
                f"skills antigas instaladas em {', '.join(instalados)} — apague-as depois de "
                "conferir se não há customização"
            )
        issues.append(
            "[skill_obsoleta] o prumo-assist agora tem 5 skills com modos "
            "(paper, wiki, protocol, write, review): "
            + "; ".join(partes)
            + ". Rode `prumo update` para reescrever as invocações."
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py tests/unit/test_cli_init.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_update.py tests/unit/test_cli_doctor.py
git commit -m "feat(cli): prumo update reescreve invocações antigas; doctor aponta [skill_obsoleta]"
```

---

### Task 9: Templates e documentação com os nomes novos

**Files:**
- Modify: `templates/pj_base/**`, `templates/modules/**` (onde houver), `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/actions-by-context.md`, `docs/onboarding-pesquisador.md`, `docs/Research Project Structure.md`, `.github/scripts/prose_conventions.md`
- Test: `tests/unit/test_pj_base_integration.py`

- [ ] **Step 1: Teste que falha**

Em `test_pj_base_integration.py`, trocar a asserção da linha 119 e acrescentar a guarda:

```python
    assert "/prumo-assist:paper library" in (target / "README.md").read_text()


def test_scaffold_nao_carrega_invocacao_antiga(tmp_path: Path) -> None:
    from prumo_assist.core.paths import resolve_resource
    from prumo_assist.core.skill_refs import scan_skill_refs
    from prumo_assist.core.skills import load_skill_registry

    registry, _ = load_skill_registry(resolve_resource("skills"))
    for base in ("pj_base", "modules"):
        assert scan_skill_refs(resolve_resource("templates") / base, registry.legacy_map()) == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/test_pj_base_integration.py -q`
Expected: FAIL.

- [ ] **Step 3: Reescrever com a função e revisar à mão**

```bash
uv run python - <<'PY'
from pathlib import Path
from prumo_assist.core.skills import load_skill_registry
from prumo_assist.core.skill_refs import rewrite_invocations
legacy = load_skill_registry(Path("skills"))[0].legacy_map()
alvos = [*Path("templates").rglob("*.md"), *Path("templates").rglob("*.toml"), *Path("templates").rglob("*.bib"),
         Path("README.md"), Path("ARCHITECTURE.md"), Path("ROADMAP.md"),
         Path("docs/actions-by-context.md"), Path("docs/onboarding-pesquisador.md"),
         Path("docs/Research Project Structure.md"), Path(".github/scripts/prose_conventions.md")]
for p in alvos:
    t = p.read_text(encoding="utf-8"); new, n = rewrite_invocations(t, legacy)
    if n: p.write_text(new, encoding="utf-8"); print(n, p)
PY
```

À mão: `templates/pj_base/docs/README.md` (`/prumo-assist:wiki-*` → `/prumo-assist:wiki <modo>`); `pj_config.toml` (comentário do batch → `/prumo-assist:paper extract --all`); `.bib` (comentário); `ARCHITECTURE.md` (fluxo de dados cita `skills/paper/modes/extract.md`; layout `skills/` → "start + 5 skills por domínio, cada uma com `modes/`"; glossário "Modo"); `ROADMAP.md` (achado Groundedness aponta `skills/paper/modes/support.md`; entradas históricas da tabela de releases ficam); `prose_conventions.md` (aponta `skills/write/modes/style.md`); menções sem prefixo em `docs/*.md` que designam skill.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run python .github/scripts/gen_indexes.py --check && uv run pytest tests/unit/test_pj_base_integration.py tests/unit/test_guidelines_present.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates README.md ARCHITECTURE.md ROADMAP.md docs .github/scripts tests/unit/test_pj_base_integration.py
git commit -m "docs: templates e documentação com a superfície por domínio"
```

---

### Task 10: ADR-0032, lista-ouro, CHANGELOG e emenda do spec

**Files:**
- Create: `docs/adr/adr-0032-superficie-por-dominio-e-modos.md`, `tests/fixtures/routing_phrases.toml`, `tests/unit/test_routing_phrases.py`
- Modify: `CHANGELOG.md` (seção `[Não publicado]`), `docs/superpowers/specs/2026-09-12-superficie-de-skills-design.md` (seção "Emenda de implementação")

- [ ] **Step 1: Teste da lista-ouro (integridade, não roteamento)**

```python
"""A lista-ouro de roteamento aponta só para modos que existem (spec, critério de F1).

O roteamento em si é medido à mão no Desktop — este teste só impede que a
lista apodreça quando um modo muda de nome.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from prumo_assist.core.paths import resolve_resource
from prumo_assist.core.skills import load_skill_registry

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "routing_phrases.toml"


def test_lista_ouro_tem_30_frases_e_modos_existentes() -> None:
    data = tomllib.loads(_FIXTURE.read_text(encoding="utf-8"))
    registry, _ = load_skill_registry(resolve_resource("skills"))
    casos = data["case"]
    assert len(casos) == 30
    frases_frontmatter = {p for _, m in registry.iter_modes() for p in m.phrases}
    for caso in casos:
        assert registry.resolve(caso["expected"]) is not None, caso
        assert caso["phrase"] not in frases_frontmatter, caso["phrase"]
```

Fixture com 30 `[[case]]` `phrase`/`expected` (`skill/mode`), frases diferentes das do frontmatter, cobrindo os 16 modos (≥1 cada) e 5 frases cujo modo exige passo que só existe no arquivo do modo (marcadas `needs_mode_file = true`).

- [ ] **Step 2: ADR-0032** (MADR minimal, Status aceito, Data 2026-09-12, Origem: spec). Contexto: fricção de escolha entre 16 skills; Decisão: start + 5 skills por domínio, modo 1:1 com metadados no frontmatter do arquivo do modo, gerador deriva roteamento, migração por `prumo update` sem alias, proveniência legada resolvida por `SkillRef`; Consequências: breaking de invocação; `.claude/skills/<antigo>/` não é apagado; mudança de nome de modo exige `legacy`.

- [ ] **Step 3: CHANGELOG** — em `[Não publicado]`, bloco "⚠ Breaking" com tabela antigo → novo, `prumo update`, `[skill_obsoleta]`, installer, compose, disclosure; citar Princípios I, IV, VII e ADR-0032.

- [ ] **Step 4: Emenda do spec** — seção "Emenda de implementação (F1)":
  1. Metadados do modo moram no frontmatter de `modes/<mode>.md` (reuso de `parse_skill_file`; `SKILL.md` fica pequeno), não numa lista `prumo.modes`.
  2. `start` continua sem `modes/` (roteador curto); `status` entra como seção em F3.
  3. Campos novos no frontmatter do modo: `prumo.write_kind` (compose) e `prumo.disclosure_task` (disclosure) — fonte única.
  4. Templates de escrita em `skills/<skill>/templates/<modo>.md`.
  5. Critério de disclosure: mesma contagem e mesmas tarefas; o rótulo passa ao nome novo.
  6. A exclusão de "blocos machine-owned" na migração cai: o único lugar com blocos gerados no `pj_*` é `docs/references/papers/`, já excluído.
  7. `.claude/skills/<antigo>/` não é apagado por `update` (pode ter customização); `doctor` aponta.

- [ ] **Step 5: Rodar índices e testes, commit**

```bash
uv run python .github/scripts/gen_indexes.py
uv run pytest tests/unit/test_routing_phrases.py -q
git add docs tests/fixtures tests/unit/test_routing_phrases.py CHANGELOG.md
git commit -m "docs: ADR-0032, lista-ouro de roteamento e emenda do spec de superfície"
```

---

### Task 11: Verificação completa

- [ ] **Step 1:** `uv run pytest -q` — Expected: tudo PASS.
- [ ] **Step 2:** `uv run ruff check . && uv run ruff format --check .` — Expected: limpo (rodar `ruff format` nos arquivos tocados se preciso).
- [ ] **Step 3:** `uv run mypy` — Expected: `Success`.
- [ ] **Step 4:** `uv run python .github/scripts/gen_indexes.py --check && uv run python .github/scripts/validate_manifests.py && uv run python .github/scripts/sync_manifest_version.py --check` — Expected: em dia.
- [ ] **Step 5:** `git grep -nE "prumo-assist:(active-learning|citation-support|formulate-picot|paper-extract|paper-manager|peer-review|review-reconcile|scientific-writing|wiki-ingest|wiki-lint|wiki-query|write-paper|write-projeto-cep|write-scientific|write-statistics)" -- . ':!CHANGELOG.md' ':!docs/adr' ':!docs/superpowers'` — Expected: vazio.
- [ ] **Step 6:** Smoke: `uv run prumo init /tmp/<scratch>/pj_smoke --json` → `.claude/skills/paper/modes/extract.md` existe; `uv run prumo skills --json` lista 6 skills; `uv run prumo doctor <pj_smoke> --json` sem `[skill_obsoleta]`.
- [ ] **Step 7:** `graphify update .` (se `graphify-out/` existir).
- [ ] **Step 8:** Critério manual de roteamento (≥27/30 no Desktop) registrado como pendente para o pesquisador — não automatizável aqui.
