# Skill `scientific-writer` — design

> Spec de brainstorming. Documenta a decisão arquitetural antes do plano de
> implementação (que sai via `superpowers:writing-plans` em seguida).

**Status:** aprovado em brainstorming, pendente revisão da spec.
**Autor:** raphaelfh + Claude (sessão 2026-04-29).
**Próximo artefato:** plano de implementação em
`docs/superpowers/plans/2026-04-29-prumo-scientific-writer-plan.md`.

---

## 1. Motivação

Hoje o `prumo-assist` cobre **revisão** (`peer-review`), **extração**
(`paper-extract`), **registro** (`wiki-ingest`), **busca** (`wiki-query`) e
**exportação** (`prumo write export/compose`). Falta a peça **drafting**:
gerar prosa científica nova ancorada no projeto.

A skill externa `claude-scientific-writer:scientific-writing` cobre a parte
genérica (IMRAD, citações, paragráfos completos), mas:

- Exige geração obrigatória de figura/graphical abstract.
- Não conhece `references/_references.bib` (citekeys Better BibTeX) — não
  produz `[[@key]]` wikilinks que o vault Obsidian do `pj_*` usa.
- Não conhece `docs/findings/`, `docs/concepts/` — não cita synthesizes
  prévias do projeto.
- Não tem voz clínica-acadêmica sóbria por default; tom é genérico.

A skill nova **não compete** com `scientific-writing`; **orquestra** ela com
contexto e convenções do projeto.

---

## 2. Escopo aprovado

### Em escopo

- Drafting de **paper section** (intro/métodos/discussão/etc) que vira parte
  de um manuscrito.
- Drafting de **finding/nota analítica** em `docs/findings/<slug>.md` —
  parágrafos curtos sintetizando "o que aprendi sobre X dos N papers".
- Três modos: `draft` (outline → prose), `brainstorm` (topic → outline +
  prose), `revise` (draft existente → revisão guiada por instrução).
- Integração opt-in com `claude-scientific-writer:literature-review` quando
  o usuário pede contexto além do acervo local.

### Fora de escopo (YAGNI)

- Geração obrigatória de figura/graphical abstract (descartada no
  pós-processamento se vier do upstream).
- Renderização Pandoc/Typst — já é `prumo write export/compose`, separada.
- Capítulo de tese inteiro / grant narrative inteira — fica pra evolução
  futura via `--style`.
- CLI determinístico `prumo write draft` — skill-only por enquanto; vira PR
  separado quando a dor de batch aparecer.
- Auto-invoke de `peer-review` ao final — chain manual, KISS.
- Múltiplos `--venue` específicos (NEJM/JAMA/Lancet) — só `--style`
  genérico em v1.

---

## 3. Arquitetura

### 3.1 Localização & artefatos

```
prumo-assist/
└── skills/
    └── scientific-writer/
        └── SKILL.md          ← único artefato (prompt + frontmatter rico)
```

Sem código Python. A skill é puramente prompt-driven, igual ao `peer-review`.
Lógica determinística (resolução de citekey, frontmatter Obsidian) fica
**dentro do prompt** com instruções precisas, sem `domains/write/draft.py`.

### 3.2 Frontmatter `prumo:`

```yaml
---
name: scientific-writer
description: "Gera prosa científica project-aware (paper section ou finding/nota analítica) — orquestra literature-review (lit lookup) + scientific-writing (drafting) + pós-processamento prumo (citekeys, frontmatter Obsidian, voz clínica). Invocar quando usuário pedir 'escreve a intro do paper', 'rascunha um finding sobre X', 'expande esse outline', 'revise essa seção pra ficar mais clínica', '/scientific-writer'. NÃO é a skill pra exportar pra DOCX/PDF (use prumo write export); NÃO é peer review (use peer-review)."
prumo:
  version: 1.0.0
  schema: ScientificDraft/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-30k tokens (depende do tamanho do output e se invoca lit-search)
  inputs:
    target: required  # path ou string-tópico
  invokes:
    - claude-scientific-writer:scientific-writing  # sempre
    - claude-scientific-writer:literature-review   # opcional via --lit-search
allowed-tools: Read, Write, Edit, Glob, Grep, Skill
---
```

### 3.3 Schema `ScientificDraft/v1`

```json
{
  "schema_version": "ScientificDraft/v1",
  "draft_path": "docs/findings/combinado-fusion-tradeoffs.md",
  "artifact": "finding | paper-section",
  "style": "clinical | imaging-ai | thesis-chapter | grant",
  "mode": "draft | brainstorm | revise",
  "lit_search_invoked": false,
  "citekeys_used": ["smith2024combinado", "huang2023visual"],
  "citekeys_unresolved": [],
  "word_count": 482,
  "section_outline": ["Contexto clínico", "Limitação atual", "Insight central", "Implicações"],
  "next_steps_suggested": ["/peer-review docs/findings/combinado-fusion-tradeoffs.md --venue clinical"]
}
```

`citekeys_unresolved` é informativo: lista citekeys mencionadas no draft que
**não** existem em `references/_references.bib` (sinaliza que o usuário
precisa adicionar o paper no Zotero antes de finalizar).

---

## 4. UX (invocação)

### 4.1 Sintaxe

```
/scientific-writer <target>                       # auto-detecta modo
/scientific-writer --mode draft <outline.md>      # outline → prose
/scientific-writer --mode brainstorm "tópico"     # topic → outline + prose
/scientific-writer --mode revise <draft.md>       # draft → revisão

# flags ortogonais
--artifact paper-section | finding                # default: detecta pelo path
--style clinical | imaging-ai | thesis-chapter | grant   # mental model
--lit-search                                      # invoca literature-review
--cite-from-local-only                            # default; explicita NÃO invocar lit
--out <path>                                      # destino; default = inferido
--peer-review                                     # sugere /peer-review ao final (não auto-invoca)
```

### 4.2 Detecção automática

| Heurística | Decisão |
|---|---|
| `<target>` é `.md` existente com prosa (>30% linhas não-bullet) | `--mode revise` |
| `<target>` é `.md` existente predominantemente de bullets | `--mode draft` |
| `<target>` é string sem path | `--mode brainstorm` |
| Path inclui `docs/findings/` ou `--out` aponta lá | `--artifact finding` |
| Senão | `--artifact paper-section` |
| Sem `--style` explícito + `pj_config.toml` tem `default_style` | usa o do config |
| Senão | `--style clinical` |

### 4.3 Default de `--out`

| Artifact + mode | Default path |
|---|---|
| `finding` + `brainstorm` | `docs/findings/<slug-do-tópico>_<YYYY-MM-DD>.md` |
| `finding` + `draft` | `docs/findings/<stem-do-outline>.md` |
| `paper-section` | exige `--out` explícito (não há lugar canônico) |
| `revise` | sobrescreve o `<target>` (com backup `.md.bak`) |

---

## 5. Orquestração (fluxo)

```
1. Parse args + auto-detect (mode, artifact, style, out)

2. Carregar contexto local
   a. Parsear references/_references.bib via Read + parse manual no prompt
      (formato BBT é estável e o arquivo cabe em contexto até ~500 papers).
      Construir mapa citekey → {title, authors, year}. Não chamamos
      core/bib.py: SKILL roda no agent-host, não tem `prumo` no PATH
      garantido. Se o acervo crescer >500 entries, considerar adicionar
      `Bash` ao allowed-tools e invocar `prumo paper find` em PR futuro.
   b. Se --artifact=finding e existir docs/findings/, listar findings
      relacionados via Glob + Read da seção frontmatter (heurística:
      keyword match no `title` ou `tags`).
   c. Se existir docs/concepts/, listar concepts relacionados (mesma
      heurística).

3. Lit-search (opt-in)
   if --lit-search:
     Skill('claude-scientific-writer:literature-review',
           query=<tópico ou title do outline>,
           scope='biomedical' | 'imaging-ai' (mapped from --style))
     ↓ recebe lista de papers (DOI, title, abstract, key findings)
     concat com refs locais; marcar quais são "novos" (não estão em .bib)

4. Drafting bruto
   Skill('claude-scientific-writer:scientific-writing',
         outline=outline,
         refs=resolved_refs,
         style=style,
         mode=mode,
         constraints={
           no_figures: true,
           no_graphical_abstract: true,
           target_word_count: <inferido por artifact>,
           tone: 'clinical-academic-sober'
         })
   ↓ recebe prosa em markdown

5. Pós-processamento prumo (no próprio prompt da nossa skill)
   a. Resolver citações de prosa → wikilinks Obsidian:
        "[Smith et al., 2024]" → "[[@smith2024combinado]]"
        usar mapa de citekey do passo 2.a
        listar não-resolvidas em citekeys_unresolved
   b. Remover qualquer instrução residual sobre figuras
      (paragráfos tipo "Figure 1 shows...") se o output trouxe
   c. Aplicar frontmatter Obsidian:
        finding:
          ---
          title: "{slug}"
          date: {YYYY-MM-DD}
          tags: [finding, {style}]
          related: [[{linked-concept-1}]], [[{linked-concept-2}]]
          ---
        paper-section:
          ---
          title: "{section-name}"
          parent: [[{manuscript-name}]]
          section: {intro|methods|...}
          status: draft
          ---
   d. Encurtar prosa (artifact=finding only):
        target 3-8 paragráfos / ~400-700 palavras
        cortar redundância, manter argumento central

6. Escrever em --out (criar dir se faltar; backup se revise)

7. Emitir ScientificDraft/v1 + trace
   a. Inline em <!-- _meta { ... } --> no topo (logo abaixo do
      frontmatter Obsidian) — paridade com peer-review.
   b. Imprimir o JSON estruturado no stdout do output da skill (último
      bloco). Quem quiser persistir em .prumo/traces/YYYY-MM-DD.jsonl
      faz via hook ou Bash externo. Não chamamos core/provenance da
      skill (mesmo motivo do 2.a). PR futuro pode adicionar `Bash` +
      shell-out pra registrar o trace.

8. Imprimir resumo + sugestões
   a. Resumo: word count, # citekeys usados, # não-resolvidas (se >0,
      avisar pra adicionar ao Zotero)
   b. Sugestões:
      - "/peer-review {out_path} --venue {style-mapped}" (se --peer-review)
      - "/prumo write export {out_path} --to docx" (se artifact=paper-section)
      - "/wiki-ingest --already-written {out_path}" (se artifact=finding —
        registra como source no _index)
```

---

## 6. Integrações

| Componente | Papel |
|---|---|
| `references/_references.bib` | source-of-truth de citekeys; lido via Read + parse manual no prompt pra resolver `[[@key]]` (parser BBT inline; ver §5 step 2.a) |
| `docs/findings/` | destino default quando `--artifact finding` |
| `docs/concepts/` | contexto se houver concept relacionado (heurística simples) |
| `pj_config.toml` (do `pj_*`) | `default_style`, `default_artifact` (opcional v1.1) |
| `claude-scientific-writer:literature-review` | invocado opt-in via `--lit-search` |
| `claude-scientific-writer:scientific-writing` | sempre invocado pra drafting bruto |
| `peer-review` (prumo) | sugerido como próximo passo (nunca auto-chamado) |
| `wiki-ingest` (prumo) | sugerido como próximo passo se artifact=finding |
| `core/provenance` (prumo) | **não** chamado direto da skill; trace é emitido inline no output (`<!-- _meta { ... } -->` + JSON no stdout). Persistência em `.prumo/traces/` fica como evolução futura via hook ou `Bash` adicionado ao allowed-tools |

---

## 7. Testes

Como SKILL.md é prompt puro, testes são **golden** (input → expected output
shape):

| Teste | Input | Validação |
|---|---|---|
| `test_draft_finding_local_only` | outline curto + bib pequeno | output tem frontmatter Obsidian; citekeys batem com bib; word_count em [400, 700]; sem figura |
| `test_brainstorm_paper_section` | string-tópico + --artifact paper-section --style clinical | output tem frontmatter `parent`/`section`; tom clínico-sóbrio |
| `test_revise_existing` | draft existente + revision instruction | output tem `.bak` salvo; mudanças refletem instrução |
| `test_unresolved_citekey_warns` | outline cita autor não no .bib | `citekeys_unresolved` contém o nome; aviso no resumo |
| `test_lit_search_opt_in` | --lit-search flag | invokes count = 2 (lit-review + scientific-writing); refs novas marcadas |

Diretório `skills/scientific-writer/tests/golden/` (paridade com
`peer-review/tests/golden/` quando este existir — hoje peer-review não
tem golden ainda; vai ser PR paralelo).

---

## 8. Riscos & contingências

| Risco | Mitigação |
|---|---|
| Upstream `scientific-writing` muda contrato e quebra orquestração | Pinning por versão no frontmatter; fallback documentado pra "drafting interno" se Skill falhar |
| `literature-review` retorna formato diferente do esperado | Validação no pós; se shape divergir, log warning + degradar pra modo local-only |
| Citekey resolution erra (autor com sobrenome comum) | Heurística conservadora: match exato em `.bib`; em caso de dúvida, deixa `[Smith 2024]` literal e adiciona em `citekeys_unresolved` |
| Output de `scientific-writing` traz figuras forçadas | Pós-processamento remove blocos `![figure]` e textos "Figure N shows..." |
| Prompt fica grande demais (>10k tokens) | Particionar: 1 chamada Skill = 1 etapa; não inflar o SKILL.md com exemplos extensos |
| Voz clínica-sóbria não emerge consistentemente | Adicionar 2-3 paragráfos-exemplo curtos no SKILL.md como few-shot |

---

## 9. Plano de roll-out

1. **PR único** (não dividir em PR0/PR1) — escopo cabe em ~1 dia de trabalho.
2. Adicionar `skills/scientific-writer/SKILL.md`.
3. Adicionar `skills/scientific-writer/tests/golden/<5 cenários>.md`
   (input + expected shape do output).
4. Atualizar `CHANGELOG.md` em `[Não publicado]`:
   - **Adicionado:** skill `scientific-writer`.
5. **Não** bumpa plugin manifest (mantém v0.1.1) — coerente com decisão de
   decoupling do v0.2.0 do package.
6. **Próximo release**: `v0.3.0` do package Python quando juntar com PR4
   (`clinical-checklists`) ou outra adição.

---

## 10. Decisões deliberadamente NÃO tomadas

- **Não definimos `--venue` específico** (NEJM/JAMA/Lancet). `--style`
  genérico cobre 90% dos casos. Se virar dor real, adiciona em v1.x.
- **Não auto-invocamos `peer-review`** ao final do drafting. Cada skill é
  testável em isolamento; loop é responsabilidade do usuário.
- **Não criamos `prumo write draft` CLI**. Skill-only. Quando dor de batch
  (200 findings) aparecer, vira shellout `claude -p`.
- **Não tocamos `core/`**. Toda a inteligência fica no SKILL.md. Se
  resolução de citekey ficar complexa demais pro prompt, aí sim move pra
  `core/citekey_resolver.py` em PR separado.
- **Não criamos schemas Pydantic em `domains/write/schemas/`**. O
  `ScientificDraft/v1` vive como JSON contract no SKILL.md, igual o
  `PeerReviewReport/v1` do peer-review.

---

## 11. Critério de sucesso

A skill é **bem-sucedida** quando:

1. `/scientific-writer "tradeoffs entre fusão early vs late em combinado"`
   produz finding em `docs/findings/` com 5 paragráfos, citekeys do
   `_references.bib` resolvidos como `[[@key]]`, frontmatter Obsidian
   válido, voz clínica-sóbria.
2. `/scientific-writer --mode draft outline.md --artifact paper-section
   --out docs/manuscripts/intro.md` produz seção de paper coerente, sem
   figura forçada, com `parent` apontando pro manuscrito.
3. `/scientific-writer --mode revise intro.md` aplica instrução de revisão
   sem perder citekeys e gera `.bak` do anterior.
4. `--lit-search` traz papers novos (não no `.bib`) e os marca como tal,
   sugerindo `/paper-manager add` pra incorporar ao acervo.
5. Schema `ScientificDraft/v1` é emitido válido em todos os 3 modos.
