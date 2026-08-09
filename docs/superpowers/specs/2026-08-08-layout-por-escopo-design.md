---
title: references/ sob docs/ — um movimento, quatro consertos de código e adequação agêntica
date: 2026-08-08
status: draft
tags: [layout, pj_base, references, zettlr, zotero, bbt, breaking, adr]
---

# `references/` sob `docs/` — um movimento, quatro consertos de código e adequação agêntica

## Resumo executivo

O `pj_*` tem dois topos de leitura: `docs/` (prosa) e `references/` (bibliografia). Esta spec unifica: **`references/` → `docs/references/`**, para que `docs/` seja o workspace do Zettlr. Nome preservado, conteúdo intacto, nenhum diretório novo, nenhuma taxonomia mexida.

**Corte limpo:** o código conhece **um** caminho. Sem fallback, sem alias, sem convivência.

**Adequação de projeto existente é conversa, não comando.** O CLI só **detecta** layout legado e falha com mensagem clara. Adequar um projeto real é heterogêneo — quatro formas diferentes de `.gitignore`, dois projetos sem git funcional, duas classes de link com regras opostas, scripts próprios do pesquisador, e um passo dentro do Zotero. Isso é julgamento, e julgamento fica agêntico, como manda a arquitetura híbrida do repo. Nenhum `prumo migrate` é especificado aqui.

A evidência de que o movimento vale: o config vivo do Zettlr tem **uma** workspace aberta, `pj_piloto_genetica/docs`. A bibliografia está hoje fora do campo de visão do editor — o movimento leva de **0 para 223** os arquivos visíveis no `pj_piloto_ml`.

Fase 1 = **0.65.0** (`⚠ Breaking`).

## Contexto

O dono: *"o diretório references deveria ficar dentro de docs"* — por navegação no Zettlr e consistência. Mandato de desenho: *"simplificar, manter só o necessário, menor curva de aprendizado"*. Corte limpo reafirmado depois de ver o preço: *"os projetos podem se readequar"*.

### Três correções ao diagnóstico inicial

Registradas porque versões anteriores desta spec construíram desenho em cima delas:

1. **Os diretórios "orgânicos" não são invenção.** `brainstorm/`, `comments/`, `qualification/`, `statistics/` e `superpowers/` no `pj_piloto_ml` são cinco **módulos documentados com gatilho** ([RPS:74-87](../../Research%20Project%20Structure.md)).
2. **`entities/` e `sources/` com zero arquivos não é rejeição.** É o módulo `extended-wiki` — gatilho *"wiki passa de ~20 páginas"* — nunca disparado.
3. **ADR-0014 não é letra morta.** `docs/wiki/findings/` é o caminho com o módulo ligado, `docs/findings/` com ele desligado. **Permanece.**

O repo já implementa "núcleo mínimo + módulos opt-in". Não há taxonomia para colapsar nem `writing/` para inventar.

## Layout

```
pj_<nome>/
├── .claude/  content/  analyses/  build/     inalterados
├── reviews/<slug>/             round-trip docx — já criado por export.py:653
│                               e review.py; fora do workspace
└── docs/                       ←── WORKSPACE DO ZETTLR
    ├── _index.md  _log.md  project_guide.md  protocol.md
    ├── decisions/   templates/   inalterados
    └── references/             ←── ÚNICA MUDANÇA
        ├── _references.bib  _index.md
        ├── notes/<citekey>/    nome preservado
        ├── pdfs/   templates/
```

## O que muda no código

Quatro consertos. Cada um foi reproduzido nos 11 `pj_*` reais — sem eles o movimento corrompe em silêncio.

### 1 · `core/pj_layout.py` — quatro símbolos, caminho único

```python
REFERENCES_RELPATH = Path("docs") / "references"

def bib_path(pj_path: Path) -> Path        # 13 call sites
def notes_dir(pj_path: Path) -> Path       #  9 call sites + stats.py:14
def pdfs_dir(pj_path: Path) -> Path        #  4 call sites
def find_pj_root(start: Path) -> Path      # walk-up, só onde o comando recebe PÁGINA
```

- **`notes/` mantém o nome.** [note_paths.py:71](../../../src/prumo_assist/core/note_paths.py) usa `meta.parent.name == "notes"` para distinguir o layout plano legado do α, e **311 das 438 notas ainda estão no plano** (phd 219, ovarian 92).
- `find_pj_root` só em `export`, `compose` e `review` (6 call sites), que recebem uma página. Onde há `--path` ou cwd, o valor é literal — `doctor` nunca sobe. O sentinela é `docs/references/_references.bib` e devolve o **pai de `docs/`**; sem isso `export` gravaria em `docs/build/exports` e `compose` resolveria `pages:` contra a raiz errada.
- Levanta `PjRootNotFoundError` em pt-BR — não devolve `None` (`mypy --strict` e regra de mensagens do repo).
- Fora do inventário por desenho: `stats.py:36` (`out["by_type"]["references"]` é chave JSON de saída, não caminho) e os filtros Lua (`pandoc.utils.references`, terminologia CSL).

### 2 · `wiki-lint` para de engolir a bibliografia

[lint.py:69](../../../src/prumo_assist/domains/wiki/lint.py) faz `docs.rglob("*.md")`. Com a bibliografia sob `docs/`, as notas viram páginas: `pj_piloto_ml` vai de **23 páginas / 80 issues para 246 / 246**, `orphan_page` de 7 para 227.

Conserto: excluir `REFERENCES_RELPATH` da varredura. **Consequência assumida:** o literal `"references"` não desaparece do código — vira exclusão.

### 3 · Três degradações silenciosas viram erro

| onde | hoje, depois do movimento | medido |
|---|---|---|
| [lint.py:64](../../../src/prumo_assist/domains/wiki/lint.py) + `:88` | `.bib` não encontrado → checagem de citekey vira no-op | `broken_citekey` **54 → 0** |
| [lint.py:177](../../../src/prumo_assist/domains/wiki/lint.py) | `notes_dir` ausente → `return []` → `multiple_primary` vira no-op | silencioso |
| [stats.py:14](../../../src/prumo_assist/domains/wiki/stats.py) | caminho errado → a chave `references` **some** do JSON | viola [constitution.md:62](../../constitution.md), forward-only |

Os três resolvem pelo `pj_layout`, e ausência vira `WikiIssue("error", ...)` em pt-BR — nunca degradação muda. (`stats.py` não varre recursivamente; ali o defeito é só de caminho.)

### 4 · `doctor` ganha duas checagens

- **Layout legado** — `references/` na raiz sem `docs/references/`: erro em pt-BR convidando à adequação.
- **Autoexport não reconfigurado** — `docs/references/` existe **e** `references/` reapareceu na raiz. É a assinatura exata do defeito abaixo, e sem essa guarda ele é invisível.

> **O autoexport do Better BibTeX guarda caminho absoluto.** [connect.py:297](../../../src/prumo_assist/domains/paper/connect.py) grava `str(bib.resolve())` no Zotero. Depois do movimento, o BBT continua escrevendo em `<pj>/references/_references.bib`: recria o diretório na raiz e congela o `.bib` migrado, sem erro. O prumo não reconecta — `connect.py:289` recusa quando o bib tem entradas reais, e não existe `autoexport.remove`/`list` no código ([ADR-0020](../../adr/adr-0020-connect-autoexport-bbt.md) põe reconexão fora de escopo). **O conserto é manual, no Zotero.**

`doctor` e o próprio detector de layout legado são os **únicos** pontos que toleram o layout antigo. Todo o resto falha com a mensagem de adequação.

### Fonte do template

`templates/pj_base/`, três arquivos:

- **`.gitignore`** — padrão de `pdfs/`; mais `~$*` e `**/_out/`, que consertam o lock do Word hoje versionado no `pj_piloto_imagem`; mais duas linhas vindas da auditoria de estado da arte (2026-08-09), baratas e no mesmo arquivo: **`.prumo/`** passa a ser ignorado (o `TraceWriter` grava payload de execução de LLM ali, e hoje isso iria para o histórico do git) e **`uv.lock` sai do ignore** (linha 28), restaurando a declaração de ambiente que o próprio repo já versiona para si.
- **`docs/_index.md`** — link `../references/` → `references/`.
- **`.claude/rules/documentation.md`** — auto-carregado toda sessão; sem conserto, reintroduz o caminho antigo em todo `prumo init`.

## Observação · adequação agêntica

Projeto fora do layout planejado **não é caso de comando**. Quando o `prumo` é invocado ali, a mensagem de erro convida à adequação, e um agente conduz a conversa: olha o projeto, mostra o que encontrou, propõe, e executa com o pesquisador. Nada é reescrito sem ele ver.

Isto é deliberado. Adequar os 11 projetos reais exigiria, em código, tratar quatro formas de `.gitignore`, dois projetos sem git funcional, duas classes de link com regras **opostas**, scripts próprios do pesquisador e um passo fora da ferramenta. Codificar isso seria mais máquina do que problema — e erraria, porque cada projeto é diferente.

**Briefing do agente** — o que a investigação encontrou nos 11 projetos, como conhecimento, não como algoritmo:

- **Zotero, primeiro e mais urgente.** Reconfigurar o autoexport do BBT para o caminho novo. Sem isso o movimento se desfaz sozinho.
- **`.gitignore`, quatro estados.** `references/pdfs/*.pdf` + negação (7 projetos) · forma de diretório `references/pdfs/` (dois projetos) · sem padrão algum (outros dois) · extras `references/images/` e `references/_discover/` (um projeto). Prefixar toda linha `references/`, **inclusive as negações** — os `pdfs/` são 326 symlinks, e versioná-los grava caminhos absolutos da máquina.
- **Git ausente.** `pj_piloto_ml` e `pj_piloto_genetica` têm gitlink de submódulo órfão: `git mv` não roda, `mv` roda.
- **Links, duas regras opostas.** 46 wikilinks `[[references/...]]` (todos em `piloto_revisao/docs/screening/`) mudam de **prefixo**; 16 links markdown `../references/_index.md` em 8 projetos mudam de **profundidade** — uma substituição cega os manda para fora do projeto.
- **Código do pesquisador.** 32 arquivos em `.claude/scripts/` (113 ocorrências), mais `piloto_revisao/.claude/skills/systematic-review-full-screening/` que **gera** caminhos antigos a cada avaliação. Nunca tocar `.claude/skills/*/references/` quando for o namespace da própria skill — só quando `references/` for seguido de `notes|pdfs|_references|templates|images|_discover`.
- **Prosa obsoleta, não quebrada.** `Makefile` e `CLAUDE.md` citam `references` em 10 de 11 projetos, mas só em comentários; os alvos chamam `prumo`.
- **Não descer** em `.git/`, `.venv/`, `.claude/worktrees/` nem em subdiretório com `docs/` próprio — `outro_projeto/` e os worktrees têm árvores completas próprias.
- **Idempotência.** `docs/references/` já existente é no-op, nunca merge — `git mv` repetido aninha silenciosamente.

## O contrato do pesquisador

1. **Escreva `.md` onde quiser dentro de `docs/`.** Módulos opcionais têm lugar sugerido e gatilho; nenhum é obrigatório. O lint varre recursivamente.
2. **A pasta do citekey em `docs/references/notes/` vem do Zotero — não mova nem renomeie.** O YAML de metadata e os blocos delimitados são da máquina; **o corpo da nota é seu** — as 7 seções humanas de [documentation.md:70-82](../../../templates/pj_base/.claude/rules/documentation.md) são preservadas por [sync.py:112](../../../src/prumo_assist/domains/paper/sync.py), que faz merge.

Em projeto novo, nada a aprender. Em projeto existente, uma conversa de adequação e um passo no Zotero.

## Fora de escopo, com o número que justifica

| descartado | por quê |
|---|---|
| rename `notes/` → `paper-notes/` | quebra [note_paths.py:71](../../../src/prumo_assist/core/note_paths.py) para **311 de 438** notas em layout plano; +46 wikilinks e 32 scripts |
| colapsar `concepts\|entities\|sources\|findings` | o `pj_base` **já não os cria**; no legado são 9 `.md` em 4 projetos; o lint varre recursivo |
| diretório `writing/` | relocaria 10 arquivos em 3 de 11 projetos; `export` já tem `--out`. O problema real são 2 linhas de `.gitignore` |
| mover `picot.toml` | existe em **1 de 11** projetos |
| filtrar findings por `type:` | `type:` está em **8 de 167** `.md` sob `docs/` — acharia menos, não mais |
| substituir ADR-0014 | descreve o resolver do módulo `extended-wiki`. Permanece |
| comando `prumo migrate` | adequação é julgamento heterogêneo; ver a observação acima |
| alias / resolver com fallback | avaliado e descartado pelo dono: *"os projetos podem se readequar"* |
| `autoexport.remove`/`list` | follow-up gated que o próprio ADR-0020 previu |

## Fase 2 — registrada, não desenhada

Projetos guarda-chuva com N estudos: nenhum dos 11 tem dois hoje. Restrições já apuradas: ADR-0020 amarra **um** autoexport a **um** `.bib` por coleção; já existem árvores aninhadas legítimas que qualquer descoberta multi-escopo precisa distinguir de estudo; o módulo `versioned-milestones` já cobre entrega formal versionada. Entrada no `ROADMAP.md`, não spec.

## Governança

- **ADR-0022** (novo): `references/` sob `docs/`, caminho único sem convivência; a varredura do wiki exclui a bibliografia; o autoexport do BBT exige reconfiguração manual; adequação de projeto legado é agêntica. Não altera ADR-0008 nem ADR-0014.
- **Emenda formal à constitution**: [constitution.md:65](../../constitution.md) cita `references/notes/` como exemplo do Princípio IV → `docs/references/notes/`, com Sync impact report. O princípio não muda. O relatório registra que o conserto de `stats.py:14` é o que impede a remoção da chave `references` do payload, proibida por `constitution.md:62`.
- **Release**: 0.64.1 → **0.65.0**, MINOR por ser breaking ([ADR-0015](../../adr/adr-0015-pre-1-0-patch-para-releasavel.md)). CHANGELOG com `⚠ Breaking` e o passo do Zotero.
- **Prosa**: 15 `SKILL.md` com 62 ocorrências, mais `ARCHITECTURE.md`, `README.md`, `Research Project Structure.md`, `actions-by-context.md`, `onboarding-pesquisador.md`, 3 canvases e `templates/pj_base/`.

## Testes

TDD: `tests/unit/core/test_pj_layout.py` (novo) → `core/` → `domains/` → CLI → `tests/unit/test_pj_base_integration.py`. Fixtures de `tests/unit/conftest.py:45-62` passam a montar a raiz sobre `docs/references/`.

- Lint sobre projeto migrado devolve o mesmo número de páginas que antes.
- `.bib` ausente vira `error`, não silêncio; citekey quebrada e `multiple_primary` continuam detectadas; `stats()` mantém a chave `references` com o mesmo valor.
- `export` a partir de uma página resolve a raiz como o **pai de `docs/`**.
- `doctor` erra em layout legado, e erra quando `references/` reaparece na raiz de projeto migrado.
- Todo comando exceto `doctor` falha em pt-BR convidando à adequação, em projeto legado.
- As 124 ocorrências em 30 arquivos de teste migram junto.

## Critérios de aceitação

1. Inventário **nominal** de literais de layout autorizados fora de `core/pj_layout.py` — lista, não `grep` vazio. `stats.py:36` e a exclusão do conserto 2 estão nela por desenho.
2. `prumo init` produz `docs/references/` e nenhum diretório novo em relação ao `pj_base` de hoje.
3. Lint e `stats` sobre `pj_piloto_imagem` migrado devolvem os mesmos números de antes.
4. Em projeto não migrado, `prumo paper sync` falha com a mensagem de adequação e `prumo doctor` funciona.
5. `uv run pytest`, `uv run ruff check .`, `uv run mypy` limpos.
6. *(manual, fora do CI)* Zettlr com workspace em `docs/` mostra as notas de bibliografia — hoje mostra zero.
