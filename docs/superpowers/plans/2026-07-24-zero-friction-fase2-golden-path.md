# Zero-friction Fase 2 — Golden Path Desktop/Cowork + Modo Degradado Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contrato de preflight uniforme fail-closed em todas as 16 skills (gerado, machine-owned, ADR-0019), instalação guiada com consentimento na skill `start`, e docs em duas trilhas (pesquisador sem terminal / dev) — fechando os itens 1–3 da Fase 2 do spec [[2026-07-22-zero-friction-onboarding-design]] com os 4 requisitos garimpados no spike da Fase 0.

**Architecture:** O preflight NÃO é código novo em runtime — é um bloco machine-owned (`<!-- prumo:preflight:begin/end -->`) estampado em cada `SKILL.md` pelo gerador da casa (`gen_indexes.py`, mesma infra `replace_block` + `--check` no CI), dirigido por um campo novo `requires:` no bloco `prumo:` do frontmatter (parseado por `core/skills.py`). O conteúdo do bloco compõe por classe de dependência (cli/qmd/zotero) e codifica as evidências da Fase 0: roteamento para `/prumo-assist:start` quando o CLI falta, check de drift CLI×plugin via `$CLAUDE_PLUGIN_ROOT`, visibilidade de MCP ausente, remediação por contexto (`prumo init`, nunca `make new-project`/scaffold manual). A skill `start` vira o instalador guiado (consentimento por comando). Única mudança de CLI: finding `empty-bib` (info) no `verify-refs`.

**Tech Stack:** Python 3.11 (registry + gerador), Markdown (skills/docs), pytest, sem dependência nova.

## Global Constraints

- Evidências da Fase 0 que este plano DEVE codificar (archive `2026-07-23-zero-friction-fase0-spike-desktop-cowork.md`, commit 134a0cf): (R1) preflight de versão CLI×plugin — global stale vence silencioso ("No such command 'verify-refs'" com prumo 0.62.0); (R2) ausência de MCP vira diagnóstico VISÍVEL (qmd+prumo-review somem sem erro nenhum na superfície); (R3) mensagem orientadora para acervo vazio; (R4) remediação por CONTEXTO da persona — `prumo init <pj_nome>`, NUNCA `make new-project` (monorepo do dono) nem "criar scaffold manualmente" (agente não simula trabalho do CLI — Princípio II/D1).
- D1 do spec (verbatim): "operações **exatas** (citekey, contagem, export, hash) recusam com mensagem contendo o comando de correção — nunca simuladas pelo agente"; "A skill oferece **instalar na hora, com consentimento explícito**, dentro da conversa"; "Skills de **julgamento puro** (peer-review, scientific-writing) funcionam sem CLI".
- Blocos gerados NUNCA são editados à mão (constitution VII; ADR-0009): fonte = frontmatter `requires:` + render no gerador; `gen_indexes.py --check` é o teste no CI.
- `from __future__ import annotations`; mypy --strict limpo e cobre `tests/`; dataclasses frozen; mensagens pt-BR com comando de correção; identificadores em inglês.
- Comandos abençoados (usar EXATAMENTE estes strings nas skills/docs): instalar uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`; instalar CLI: `uv tool install git+https://github.com/raphaelfh/prumo-assist.git`; atualizar CLI: `uv tool upgrade prumo-assist`; qmd (opcional): `bun install -g @tobilu/qmd`; scaffold: `prumo init pj_<nome>`; diagnóstico: `prumo doctor` (JSON: `--json`).
- Fase 2 é marco MINOR na fronteira de release — mas NÃO bumpar versão neste plano (release é ciclo separado; ADR-0015). CHANGELOG registra o marco.
- Item 4 do spec (piloto com 1 colega real, ≤15 min até primeiro output) é GATE EXTERNO humano: este plano entrega o kit de medição (T5); o piloto calibra os triggers das Fases 4–5 e NÃO bloqueia o archive deste plano.
- Bateria completa ao fim de cada task, NENHUM passo pulado: `uv run pytest` && `uv run ruff check .` && `uv run ruff format --check .` && `uv run mypy` && `uv run python .github/scripts/gen_indexes.py --check`. (T6 adiciona `validate_manifests.py`.)
- Fora de escopo: Fases 4–5 (gated), mudanças no MCP prumo-review, empacotamento do CLI, PyPI.

---

### Task 1: Campo `requires:` no registry de skills

**Files:**
- Modify: `src/prumo_assist/core/skills.py`
- Test: `tests/unit/core/test_skills.py` (append)

**Interfaces:**
- Consumes (existente): `SkillManifest` (frozen dataclass: name, description, body, path, version, schema, determinism, agent_compat, cost_estimate, guidelines_reviewed, inputs, extra), `parse_skill_file(path) -> SkillManifest`, whitelist `extra_keys` do bloco `prumo:` (linha ~130).
- Produces (T2 consome): `VALID_REQUIRES = frozenset({"cli", "qmd", "zotero"})` (módulo-level, ao lado de `VALID_DETERMINISM`); campo `requires: tuple[str, ...] = ()` no `SkillManifest`; parse aceita string única ou lista; valor fora do canônico → `ManifestError` com a lista válida na mensagem; `requires` ENTRA na whitelist de `extra_keys` (não cai em `extra`).

- [ ] **Step 1: Testes que falham** — append em `tests/unit/core/test_skills.py`, usando o helper EXISTENTE `_write(path, content)` do topo do arquivo (mesmo padrão de `test_parses_minimal_skill`; mypy strict cobre tests/):

```python
def test_requires_lista_canonica(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: [cli, qmd]\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ("cli", "qmd")


def test_requires_string_unica(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: zotero\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ("zotero",)


def test_requires_ausente_eh_vazio(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\n---\n\nBody.\n",
    )
    assert parse_skill_file(skill).requires == ()


def test_requires_valor_invalido_manifest_error(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: D.\nprumo:\n  requires: [terminal]\n---\n\nBody.\n",
    )
    with pytest.raises(ManifestError, match="requires"):
        parse_skill_file(skill)
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/core/test_skills.py -x -q` → FAIL (`requires` inexistente / valor desconhecido caindo em `extra`).

- [ ] **Step 3: Implementar** em `core/skills.py`:

```python
VALID_REQUIRES = frozenset({"cli", "qmd", "zotero"})
```

No `SkillManifest`, após `inputs`: `requires: tuple[str, ...] = ()`. No parser, após o bloco de `inputs` e ANTES do cálculo de `extra_keys`:

```python
    requires_raw = prumo_block.get("requires")
    if requires_raw is None:
        requires: tuple[str, ...] = ()
    elif isinstance(requires_raw, str):
        requires = (requires_raw,)
    elif isinstance(requires_raw, list):
        requires = tuple(str(x) for x in requires_raw)
    else:
        raise ManifestError(f"{path}: prumo.requires deve ser string ou lista.")
    invalid = [r for r in requires if r not in VALID_REQUIRES]
    if invalid:
        raise ManifestError(
            f"{path}: prumo.requires inválido {invalid}; use {sorted(VALID_REQUIRES)}"
        )
```

Adicionar `"requires"` ao set de chaves conhecidas (whitelist de `extra_keys`) e `requires=requires` na construção do `SkillManifest`.

- [ ] **Step 4: Bateria** — `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy` → tudo verde.
- [ ] **Step 5: Commit** — `git add src/prumo_assist/core/skills.py tests/unit/core/test_skills.py && git commit -m "feat(core): campo requires no bloco prumo: das skills — base do preflight ADR-0019"`

---

### Task 2: Gerador do bloco de preflight + anotação `requires:` nas 16 skills

**Files:**
- Modify: `.github/scripts/gen_indexes.py` (novo render + stamping loop)
- Modify: frontmatter de TODOS os `skills/*/SKILL.md` (adicionar `requires:` no bloco `prumo:`) — e os corpos ganham o bloco gerado
- Test: o próprio `uv run python .github/scripts/gen_indexes.py --check` + suite existente (registry strict roda dentro do gerador)

**Interfaces:**
- Consumes (T1): `SkillManifest.requires`; infra existente `replace_block(text, tag, body, where=)` com markers `<!-- prumo:{tag}:begin/end -->`; `_targets()`/`main()` do gerador.
- Produces: função `render_preflight(manifest: SkillManifest) -> str`; stamping idempotente: se os markers `prumo:preflight` não existirem no SKILL.md, INSERIR o bloco imediatamente após a primeira linha `# ` (H1) do corpo; se existirem, `replace_block`. O loop entra no `main()` (mesmo mecanismo de stale/--check dos demais alvos).

**Auditoria `requires:` por skill** (valores de partida, derivados do `doctor` [`required_by`] + leitura dos corpos; o implementer VERIFICA cada um contra o corpo da skill e ajusta COM EVIDÊNCIA no report — desvio justificado é esperado, silêncio não):

| skill | requires | base da derivação |
|---|---|---|
| start | `[]` | é o instalador; roda em qualquer superfície |
| peer-review | `[]` | julgamento puro (D1 nomeia) |
| scientific-writing | `[]` | julgamento puro (D1 nomeia) |
| active-learning | `[qmd]` | doctor: qmd required_by |
| wiki-query | `[qmd]` | doctor: qmd required_by |
| wiki-ingest | `[qmd]` | doctor: qmd required_by (file-ops são do agente; estrutura ausente → remediação, não requires) |
| wiki-lint | `[cli]` | `prumo wiki lint` (bridge A1) |
| paper-manager | `[cli, zotero]` | `prumo paper sync*` + Zotero local API |
| paper-extract | `[cli]` | pressupõe sync + `prumo paper sync-pdfs` |
| formulate-picot | `[cli]` | propaga via protocol (bridge A2) |
| citation-support | `[cli]` | `prumo paper verify-refs` |
| review-reconcile | `[cli]` | `prumo write review events` |
| write-paper | `[cli]` | `prumo write prep` |
| write-scientific | `[cli]` | prep/compose |
| write-projeto-cep | `[cli]` | prep/compose |
| write-statistics | `[cli]` | prep/compose |

- [ ] **Step 1: `render_preflight` no gerador** — composição por classe (texto EXATO; blocos citados compõem na ordem: header sempre; item 4 só com `qmd`; item 5 só com `zotero`; skills com `requires: []` usam a variante julgamento-puro):

Variante com dependências (header + itens 1–3 sempre que `cli` ∈ requires; para skills só-qmd sem cli, itens 1–2 saem e a numeração se ajusta — implemente a composição por concatenação de sub-blocos, cada um condicionado ao valor em `requires`):

```markdown
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
> 4. **Busca semântica (qmd):** se as tools MCP do `qmd` não estiverem no seu
>    inventário NESTA sessão, diga isso explicitamente ("busca semântica
>    indisponível — resultados via leitura direta, mais lentos/parciais") e
>    prossiga só no fallback documentado por esta skill; sem fallback, recuse a
>    operação com o hint do `prumo doctor`.
> 5. **Zotero:** confira `prumo doctor --json` → `external_deps[name=zotero].present`;
>    ausente/fechado → recuse operações que dependem dele citando o hint do doctor
>    (abrir o Zotero; instalar Better BibTeX).
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
```

Esqueleto da função no gerador (composição por sub-blocos; strings acima entram literais):

```python
def render_preflight(manifest: SkillManifest) -> str:
    reqs = set(manifest.requires)
    if not reqs:
        return _PREFLIGHT_PURE  # variante julgamento puro (string literal abaixo)
    parts = [_PREFLIGHT_HEADER]  # linha "> **Preflight (contrato ADR-0019)...**" + ">"
    n = 1
    if "cli" in reqs:
        parts += [_pf_item(n, _PF_CLI), _pf_item(n + 1, _PF_DRIFT), _pf_item(n + 2, _PF_INIT)]
        n += 3
    if "qmd" in reqs:
        parts.append(_pf_item(n, _PF_QMD))
        n += 1
    if "zotero" in reqs:
        parts.append(_pf_item(n, _PF_ZOTERO))
        n += 1
    parts.append(_PREFLIGHT_FOOTER)  # parágrafo "Recusar-se a operar..."
    return "\n".join(parts)
```

(`_pf_item(n, texto)` prefixa `> {n}. ` e re-indenta as linhas de continuação com `>    `; os textos `_PF_*` são EXATAMENTE os itens 1–5 do bloco acima, sem o número. Skills só-qmd sem `cli` — hoje: wiki-query/wiki-ingest/active-learning — ganham itens renumerados a partir de 1, e o item de qmd nesse caso INCLUI a frase de roteamento "se precisar do stack completo, roteie para /prumo-assist:start".)

Variante julgamento puro (`requires: []`):

```markdown
> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
```

- [ ] **Step 2: Stamping idempotente** — nova função no gerador:

```python
def stamp_preflight(text: str, body: str, *, where: str) -> str:
    begin = "<!-- prumo:preflight:begin -->"
    if begin in text:
        return replace_block(text, "preflight", body, where=where)
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            block = f"\n{begin}\n{body.strip()}\n<!-- prumo:preflight:end -->\n"
            return "".join(lines[: i + 1]) + block + "".join(lines[i + 1 :])
    raise SystemExit(f"gen_indexes: {where} sem H1 — não sei onde inserir o preflight")
```

Integrar no `main()`: além dos `_targets()`, iterar `load_skill_registry(REPO / "skills", strict=True)` e aplicar `stamp_preflight` por skill (respeitando `--check` do mesmo jeito: diff → stale).

- [ ] **Step 3: Anotar `requires:` nos 16 frontmatters** conforme a tabela (com auditoria: leia cada corpo; ajuste com evidência no report). Rodar `uv run python .github/scripts/gen_indexes.py` → todos os SKILL.md ganham o bloco.
- [ ] **Step 4: Verificar** — `uv run python .github/scripts/gen_indexes.py --check` limpo; `git diff --stat` mostra os 16 SKILL.md + gerador; NENHUM bloco editado à mão. Bateria completa.
- [ ] **Step 5: Commit** — `git add .github/scripts/gen_indexes.py skills/ && git commit -m "feat(skills): preflight uniforme gerado (ADR-0019) — requires: dirige bloco machine-owned em 16 skills"`

---

### Task 3: Finding `empty-bib` no verify-refs (R3)

**Files:**
- Modify: `src/prumo_assist/domains/paper/verify.py` (função `verify_refs`)
- Test: `tests/unit/paper/test_verify.py` (append em `TestVerifyRefs`)

**Interfaces:**
- Consumes: `Finding`, `verify_refs` (Fase 4 da ponte — kinds existentes incl. `duplicate-citekey`).
- Produces: kind novo `empty-bib` (level info, source local) emitido quando `parse_bib` devolve lista vazia; entra na tabela de kinds do ADR-0018? NÃO — ADR imutável; o kind novo é documentado no CHANGELOG (T6).

- [ ] **Step 1: Teste que falha**:

```python
    def test_bib_vazio_emite_info_orientadora(self, tmp_path: Path) -> None:
        (tmp_path / "references").mkdir(parents=True)
        (tmp_path / "references" / "_references.bib").write_text("", encoding="utf-8")
        report = verify.verify_refs(tmp_path, cache_path=tmp_path / "c.json")
        assert report["checked"] == 0
        [finding] = report["findings"]
        assert finding["kind"] == "empty-bib" and finding["level"] == "info"
        assert "Zotero" in finding["message"] and "prumo paper sync" in finding["message"]
```

- [ ] **Step 2: Ver falhar** — `uv run pytest tests/unit/paper/test_verify.py::TestVerifyRefs -x -q`.
- [ ] **Step 3: Implementar** — em `verify_refs`, logo após `entries = parse_bib(...)`:

```python
    if not entries:
        findings.append(  # mover a inicialização de `findings` para ANTES deste ponto
            Finding(
                citekey="_references.bib",
                level="info",
                kind="empty-bib",
                message=(
                    "acervo vazio — adicione referências no Zotero (coleção do projeto) "
                    "e rode `prumo paper sync` (ou /prumo-assist:paper-manager sync) "
                    "para popular o bib antes de verificar."
                ),
                source="local",
            )
        )
```

(Atenção à ordem: `findings: list[Finding] = []` precisa ser declarado antes; o resto do fluxo segue — scope vazio, checked 0, summary conta 1 info.)

- [ ] **Step 4: Bateria completa.**
- [ ] **Step 5: Commit** — `git add src/prumo_assist/domains/paper/verify.py tests/unit/paper/test_verify.py && git commit -m "feat(paper): finding empty-bib orientador no verify-refs (R3 da Fase 0)"`

---

### Task 4: Skill `start` vira instalação guiada + extermínio das remediações de dono (R4)

**Files:**
- Modify: `skills/start/SKILL.md` (corpo reescrito; frontmatter ganha `requires: []` já na T2; PRESERVAR intacto o bloco gerado `<!-- prumo:skills-catalog:begin/end -->` e o de preflight)
- Modify: `skills/wiki-ingest/SKILL.md` linha ~27; `skills/paper-manager/SKILL.md` linha ~26; frontmatter `description` de `skills/paper-extract/SKILL.md` (o `make sync-pdfs`)
- Test: `uv run python .github/scripts/gen_indexes.py --check` (description do paper-extract muda → README/catálogo regeneram) + grep de extermínio

**Interfaces:** consome os comandos abençoados das Global Constraints (strings EXATAS).

- [ ] **Step 1: Reescrever o corpo do `start`** (entre o frontmatter e o "## Catálogo completo", substituindo o texto humano atual; manter o H1):

```markdown
# prumo-assist: por onde começar

Você é a porta de entrada E o instalador guiado. Primeiro descubra o estado:

1. Rode `prumo doctor --json` (se `prumo` existir). Três cenários:
   - **Tudo OK** → pergunte em 1 linha o que a pessoa quer fazer e roteie
     (bibliografia → paper-manager/paper-extract; wiki → wiki-ingest/query/lint;
     escrita → scientific-writing/peer-review/write-*). Não execute a tarefa
     você mesmo.
   - **`prumo` NÃO existe** → ofereça a instalação guiada abaixo.
   - **Superfície sem execução de comandos** (chat puro) → aponte a trilha do
     pesquisador: `docs/onboarding-pesquisador.md` no repositório do plugin.

## Instalação guiada (com consentimento POR COMANDO — nunca rode sem um "sim")

Explique o que cada passo faz ANTES de rodar; peça consentimento explícito;
mostre a saída; siga só se funcionou:

1. **uv** (gerenciador Python): `command -v uv` — ausente? →
   `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **CLI prumo**: `uv tool install git+https://github.com/raphaelfh/prumo-assist.git`
   (atualização depois: `uv tool upgrade prumo-assist`)
3. **Diagnóstico**: `prumo doctor` — Zotero fechado/ausente? Oriente: instalar o
   Zotero (zotero.org) + plugin Better BibTeX, abrir o app. NÃO é bloqueante para
   escrita/julgamento; é necessário para sincronizar bibliografia.
4. **qmd (OPCIONAL — busca semântica)**: exige `bun`. Se a pessoa não tem bun,
   diga que é opcional e PULE (wiki-query funciona em modo degradado por leitura
   direta). Quem quiser: `bun install -g @tobilu/qmd`.
5. **Projeto**: `prumo init pj_<nome>` na pasta que a pessoa designar.
6. **Primeiro output em minutos**: peça um trecho de draft e rode
   `/prumo-assist:peer-review` — funciona sem NADA do stack (julgamento puro).

Regras duras: nunca simule saída de comando que falhou; nunca crie scaffold
manualmente (`prumo init` é o único caminho); nunca cite tooling do monorepo do
autor (`make ...`) — a pessoa instalou um plugin, não clonou um repositório.
```

- [ ] **Step 2: Extermínio das remediações de dono** (as 3 ocorrências reais):
  - `skills/wiki-ingest/SKILL.md:27` → trocar a linha inteira por: `- Se faltar estrutura, orientar \`prumo init pj_<nome>\` (via /prumo-assist:start se o CLI não existir). NUNCA criar o scaffold manualmente — o agente não simula trabalho do CLI.`
  - `skills/paper-manager/SKILL.md:26` → `Pressuposto: o diretório corrente é um \`pj_*\` com a estrutura padrão em \`references/\`. Se \`references/\` não existir, orientar \`prumo init pj_<nome>\` (via /prumo-assist:start se o CLI não existir) — nunca retrofit manual.`
  - `skills/paper-extract/SKILL.md` frontmatter `description`: trocar `make sync-pdfs` por `prumo paper sync-pdfs`.
- [ ] **Step 3: Grep de extermínio** — `grep -rn "make new-project\|make sync-pdfs\|scaffold manualmente\|retrofitar manualmente" skills/ templates/` → as únicas ocorrências restantes devem ser as NEGAÇÕES ("NUNCA criar o scaffold manualmente"). Se aparecer eco em `templates/pj_base/`, corrigir com o mesmo padrão e reportar.
- [ ] **Step 4: Regenerar + bateria** — `uv run python .github/scripts/gen_indexes.py` (description nova do paper-extract propaga ao README/catálogo) + bateria completa.
- [ ] **Step 5: Commit** — `git add skills/ README.md docs/_index.md && git commit -m "feat(skills): start vira instalação guiada com consentimento; remediação por contexto (R4) em wiki-ingest/paper-manager/paper-extract"`

---

### Task 5: Docs em duas trilhas + kit do piloto

**Files:**
- Create: `docs/onboarding-pesquisador.md`
- Modify: `README.md` (nova seção "Para pesquisadores (Desktop/Cowork, sem terminal)" FORA dos blocos gerados, antes da seção da trilha dev existente; a trilha dev permanece intacta e ganha o comando de instalação do CLI que hoje falta)
- Test: `gen_indexes --check` (docs/_index regenerado) + leitura cética

**Conteúdo obrigatório de `docs/onboarding-pesquisador.md`** (pt-BR, tom para clínico sem terminal; TODO fato checado contra o repo/evidência da Fase 0 — regra da casa pós-F4-T6: docs mentem fácil):
1. **Instalar o plugin in-app:** fluxo de plugins → "Add from a repository" → `raphaelfh/prumo-assist`; o que esperar do catálogo (nome, versão atual, contagem de skills — NÃO hardcode o número: escreva "as skills listadas no catálogo").
2. **Primeiro valor em minutos, sem instalar nada:** `/prumo-assist:peer-review` num trecho de draft (julgamento puro; evidência do spike: rodou sem stack em duas superfícies).
3. **Quando pedir mais:** o preflight (ADR-0019) vai recusar operação exata e oferecer `/prumo-assist:start` — a instalação guiada acontece DENTRO da conversa, com consentimento por comando (Cowork executa na pasta designada).
4. **O que é opcional:** qmd/busca semântica (exige bun — pode pular); Zotero é necessário só para bibliografia.
5. **Kit do piloto (item 4 do spec, medido pelo dono com 1 colega):** cronômetro do link→primeiro output (meta ≤15 min); anotar onde travou; capturar como o pedido de consentimento aparece na UI; resultado calibra as Fases 4–5.
6. Link cruzado para a trilha dev (README) e vice-versa.

**README:** seção nova de ~10 linhas apontando para o doc acima + na trilha dev existente adicionar a linha de instalação do CLI (`uv tool install git+https://github.com/raphaelfh/prumo-assist.git`) — hoje o README não documenta NENHUM comando de instalação do CLI (verificado 2026-07-24).

- [ ] Steps: escrever doc → atualizar README → `uv run python .github/scripts/gen_indexes.py` → bateria → self-fact-check (cada comando citado existe? cada claim bate com a evidência da F0?) → commit `docs: trilha do pesquisador (Desktop/Cowork) + kit do piloto da Fase 2; instalação do CLI na trilha dev`

---

### Task 6: ADR-0019 + CHANGELOG + bateria final

**Files:**
- Create: `docs/adr/adr-0019-preflight-uniforme-skills.md` (MADR minimal da casa: Contexto/Decisão/Consequências, prosa pt-BR, status aceito — 3 seções, SEM seção "alternativas"; ver ADR-0016/0017/0018 como molde)
- Modify: `CHANGELOG.md` ("Não publicado")
- Regenerar índices; bateria final completa + `validate_manifests.py`

**Conteúdo obrigatório do ADR-0019:** Contexto — evidência da Fase 0 (drift silencioso do CLI global; MCPs ausentes sem erro; remediação de monorepo vazando para persona; D1 exige fail-closed + instalação guiada). Decisão — contrato de preflight uniforme GERADO (machine-owned, `requires:` no frontmatter como fonte, `gen_indexes.py` como gerador e `--check` no CI como enforcement; conteúdo por classe cli/qmd/zotero; roteamento para `start`; drift check via `$CLAUDE_PLUGIN_ROOT` com fallback silencioso; julgamento puro declarado). Consequências — skill nova PRECISA declarar `requires:` (registry valida; esquecer = bloco de julgamento-puro por default `()`, o que é visível no review); o bloco não é editável à mão; a skill `start` é o único caminho de instalação; o piloto da Fase 2 mede o contrato no mundo real e calibra Fases 4–5.

**CHANGELOG ("Não publicado"):** Added — contrato de preflight uniforme nas 16 skills (ADR-0019) + campo `requires:` no registry; skill `start` reescrita como instalação guiada com consentimento; `docs/onboarding-pesquisador.md` (trilha sem-terminal) + instalação do CLI na trilha dev; finding `empty-bib` no `verify-refs`. Changed — remediações de contexto (`prumo init` no lugar de tooling do monorepo) em wiki-ingest/paper-manager/paper-extract. Marco — Fase 2 do zero-friction (itens 1–3; piloto pendente do dono).

- [ ] Steps: ADR → CHANGELOG → `uv run python .github/scripts/gen_indexes.py` → bateria FINAL: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check && uv run python .github/scripts/validate_manifests.py` → commit `docs+feat(skills): ADR-0019 contrato de preflight uniforme + CHANGELOG do marco Fase 2`

---

## Self-review (contra o spec §Fase 2 + evidência F0)

- Item 1 (preflight uniforme + ADR): T1+T2+T6 ✓ (R1 drift no bloco item 2; R2 MCP visível no item 4; R4 remediação no item 3)
- Item 2 (instalação guiada via start; demais roteiam): T4 (start) + T2 (bloco item 1 roteia) ✓
- Item 3 (docs duas trilhas com material da F0): T5 ✓ (R3 coberto por T3 no CLI)
- Item 4 (piloto ≤15 min): kit em T5; GATE EXTERNO documentado nas Global Constraints ✓
