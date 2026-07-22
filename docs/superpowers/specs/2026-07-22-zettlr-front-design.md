---
title: Zettlr como front humano do fluxo de escrita — Obsidian sai, Pandoc puro entra
date: 2026-07-22
status: draft
tags: [zettlr, write, editor, citations, preview, pandoc, pj-base, release-policy]
---

# Zettlr como front humano do fluxo de escrita

## Resumo executivo

Em projetos `pj_*` novos, o **Zettlr** vira a janela do humano para o manuscrito e as notas: edição com **preview vivo de citação** (citeproc in-editor), autocomplete de citekey lendo o `_references.bib` do Better BibTeX, e export oficial pelo próprio Zettlr — inclusive um **docx de trabalho com campos Zotero vivos**, via perfil de export gerado pelo prumo. O **Obsidian sai do fluxo** para projetos novos; a fonte passa a ser **Markdown Pandoc puro** (`[@key]`, links padrão, sem callouts). O prumo continua dono do pipeline (scaffold, compose, lint, export canônico com guardas) e os agentes seguem operando nos mesmos arquivos via CLI — Zettlr, humano e agentes convergem no mesmo Markdown em git, única fonte de verdade.

Isto ataca diretamente o **gap nº 1** do diagnóstico de jul/2026 (não há preview vivo; para ver citação resolvida gera-se docx) sem construir `prumo write preview`: o Zettlr *é* o preview. E simplifica estruturalmente o spec 2026-07-05 (ponte docx→CriticMarkup): em projeto novo, fonte ≈ input de export, então o transplante de marcas deixa de atravessar o `normalize_markdown` lossy.

A mudança acompanha uma **emenda de política de release** (pré-1.0): PATCH passa a cobrir tudo que é releasável; MINOR fica reservado a breaking/marco. Este feature sai como **PATCH** — o primeiro sob a política nova.

## Contexto e problema

- O diagnóstico de 2026-07-04 (memória `citation-editing-pain-2026-07`) estabeleceu: o prumo já implementa ~80% do estado da arte; docx é output-only; os gaps reais são 4, e o maior/mais barato é **preview vivo**.
- A decisão de coautores está tomada e **não é tocada aqui**: coautores usam Word, e a ponte docx→CriticMarkup tem spec próprio (2026-07-05, em revisão).
- O Obsidian carrega hoje só custo de convenção: o dono declarou que **quase não o usa** ("agentes mantêm a wiki"). O que o prende ao fluxo são `[[@key]]`, callouts e `![[...]]` — que exigem o `normalize_markdown` no export e criam a gramática divergente que o invariante I7 do spec 2026-07-05 quer eliminar.
- O Zettlr fala **sintaxe Pandoc nativa**: as três formas do autocomplete (`[@Author2015, p. 123]`, `@Author2015`, `@Author2015 [p. 123]`) são citações Pandoc padrão, e o scanner de export do prumo (`scan_citekeys`, `domains/write/export.py`) já captura todas — adotar Pandoc puro **é** adotar a convenção do Zettlr.

## Decisões travadas com o dono (2026-07-22)

1. **Papel do Zettlr:** editor do manuscrito (loop interno) + retirar o Obsidian do fluxo para simplificar.
2. **Uso real do Obsidian hoje:** quase nenhum — wiki mantida por agentes. Custo humano de remoção: baixo.
3. **Sintaxe-fonte:** Pandoc puro em tudo (manuscrito e wiki) nos projetos novos. Gramática única de citekey (fecha o I7).
4. **Export:** ambos os caminhos — o oficial do Zettlr (perfil + reference-doc) para docx de trabalho e HTML/PDF; `prumo write export` para o docx canônico de entrega, também acessível no menu do Zettlr via custom command.
5. **Migração:** **só projetos novos**. Legado fica Obsidian-flavored, intocado; sem comando de migração. (Adoção gradual em projeto legado permanece possível: o scanner é flavor-agnóstico e sintaxe mista já exporta correto hoje.)
6. **Release:** política pré-1.0 emendada (ver Componente 5); este feature = PATCH.

## Arquitetura

### Divisão de papéis

| Peça | Responsabilidade |
|------|------------------|
| **Zettlr** | Editar prosa; preview vivo de citação; autocomplete de citekey (lê o `.bib` do BBT); export nativo HTML/PDF; **docx de trabalho** via perfil de export do prumo. |
| **prumo** | Scaffold Zettlr-ready; compose/lint com gramática única; **docx canônico de entrega** (`write export`: lookup BBT → filtros → guardas OOXML); geração do perfil de export; doctor. |
| **Agentes/Claude** | Operam nos mesmos `.md` via CLI, como hoje. |
| **Git** | Árbitro e fonte de verdade. Nenhum estado vive no Zettlr; a config global dele (custom command, autocomplete, render citations) é setup one-time do usuário, documentado — o prumo nunca a escreve. |

### docx em dois níveis

- **Docx de trabalho (Zettlr oficial):** perfil de export (Pandoc defaults file) gerado pelo prumo com a cadeia `citeproc → zotero_live_docx.lua` + `reference-doc`. Sai docx estilizado com campos de citação vivos **embutidos** (CSL_CITATION no OOXML). Degradações aceitas: sem URI de relink com a biblioteca Zotero (o `zotero_lookup_file` é opcional no filtro) e **sem guardas** (citekey faltante passa silencioso). Uso: leitura, compartilhamento rápido, ver o texto no template Word. **Nunca é artefato de entrega.**
- **Docx canônico (`prumo write export`):** pipeline completo — scan de citekeys → lookup BBT JSON-RPC (URIs de relink) → pandoc + filtros → assert de citekey faltante → guardas pós-export (contagem de campos OOXML, bibliografia presente). É o único docx válido para coautores/submissão e o que alimenta os invariantes do spec docx→CriticMarkup.
- **Um único `reference.docx`** versionado no projeto estiliza os dois caminhos.

### Como o perfil global acha os arquivos do projeto

Não precisa achar: `bibliography:` e `csl:` viajam no **frontmatter de cada draft** (gerado pelo scaffold), e frontmatter tem precedência sobre defaults file. O perfil carrega só a cadeia de filtros (com caminho absoluto do filtro Lua, resolvido por máquina) e o reference-doc padrão.

### Fronteira de compatibilidade

Projetos legados: intocados. `normalize_markdown` (`core/obsidian.py`) continua servindo `[[@key]]`/callouts/`![[...]]` no export. A suíte existente de export/normalize é contrato de regressão.

## Componentes

### 1. `templates/pj_base` v2 (Zettlr-ready)

- Remove `.obsidian/` inteiro (config + plugin obsidian-linter).
- Templates de notas e drafts em Pandoc puro: `[@key]`, links `[texto](caminho)`, sem callouts, sem `![[...]]`.
- Todo template de draft nasce com frontmatter `bibliography:` e `csl:`.
- Entra `reference.docx` versionado no projeto (template Word único).
- Lembrete de armadilha do repo: `templates/` é force-included no wheel e resolvido por `core/paths.py` — mudanças de layout atualizam os dois lados juntos.

### 2. Perfil de export Zettlr (artefato gerado)

- Novo subcomando idempotente **`prumo write zettlr-profile`**: gera no projeto o defaults file `prumo-docx.yaml` com `reader`/`writer` (exigência do Zettlr), `citeproc` antes do filtro Lua, caminho do filtro resolvido do wheel instalado, `reference-doc` e metadados do filtro (`zotero_csl_style`).
- `prumo init` chama o subcomando no scaffold. O perfil é **gerado, não commitado no template** (caminho absoluto por máquina).
- Importar no assets manager do Zettlr = passo one-time documentado.

### 3. Gramática única de citekey (fecha o I7)

- O scanner canônico (`scan_citekeys`) passa a ser usado também pelo `compose` — morre o regex divergente de `compose.py` (`_extract_citekeys_used`, que só entende `[[@key]]` e trunca chave composta).
- `wiki lint` valida existência de citekey nas **duas** sintaxes (flavor-agnóstico), contra o `.bib`, para legado e novo igualmente.

### 4. CLI/entrypoint para o custom command

- `write export` já aceita o path posicional (assinatura atual). Garantir entrypoint invocável pelo campo de comando do Zettlr; se o campo não aceitar argumentos, ship de console-script fino (ex. `prumo-zettlr-export`) — verificação empírica no plano.
- `prumo doctor` ganha check: perfil gerado existe e o caminho do filtro dentro dele resolve; mensagem de erro embute o fix (`prumo write zettlr-profile`).

### 5. Docs, roadmap e release

- **Política de versão emendada (pré-1.0, "fricção mínima"):** enquanto `0.x`, PATCH cobre tudo que é releasável — inclusive subcomando/skill novo; MINOR fica reservado a breaking ("⚠ Breaking") ou fechamento de fase/marco do ROADMAP. Semântica: MINOR = "leia o changelog antes de atualizar"; PATCH = "atualize sem medo".
- O princípio do ADR-0011 permanece (versão = interface pública; bump só quando o consumidor precisa saber) — muda só o mapeamento pré-1.0. Registrar em **ADR novo** (MADR minimal) que supersede o ADR-0011 nesse ponto; emendar `RELEASING.md` e `.claude/rules/release.md`. Fonte única (`_version.py`) e sync de manifests (Princípio VII) intocados.
- **Este feature sai como PATCH** sob a política nova.
- Guia one-time de setup do Zettlr no `docs/project_guide.md` do pj_base: instalar, abrir a pasta como workspace, importar o perfil, registrar o custom command, ligar "render citations", escolher a forma do autocomplete e **ativar o reload automático de mudanças externas** (convivência com agentes).
- README/ARCHITECTURE atualizados; ROADMAP anota `prumo write preview` como **superado pelo Zettlr** para projetos novos.

## Fluxo de dados

1. **Scaffold:** `prumo init` gera o pj Zettlr-ready (templates Pandoc puro, frontmatter, `reference.docx`, `prumo-docx.yaml`).
2. **Setup one-time (humano):** workspace no Zettlr + importar perfil + custom command + render citations + reload automático.
3. **Escrita:** humano no Zettlr; agentes via CLI; git arbitra.
4. **Exports:** botão Zettlr + perfil → docx de trabalho; custom command/CLI → docx canônico com guardas; HTML/PDF → export nativo Zettlr (citeproc + CSL do frontmatter).

Sentido único: `.md` (fonte, git) → `.bib` (BBT "keep updated") → artefatos (docx/html/pdf, descartáveis). Nada volta do Zettlr para o prumo — ele só lê e escreve `.md`.

## Tratamento de erros e degradações

| Situação | Comportamento |
|----------|---------------|
| Perfil ausente / filtro não resolve (wheel reinstalado) | `prumo doctor` acusa; mensagem embute `prumo write zettlr-profile`. |
| Zotero/BBT fechado — caminho canônico | Falha alta (`ZoteroNotRunningError`), como hoje. |
| Zotero/BBT fechado — caminho Zettlr | Degrada documentado: preview funciona offline (`.bib` estático); docx de trabalho sai sem URI de relink. |
| `.bib` stale | Gap nº 2 do diagnóstico, fora deste escopo; anotado como limitação no guia. |
| Citekey inexistente | Preview do Zettlr mostra a chave crua (feedback imediato); export canônico falha alto; docx de trabalho passa silencioso — por isso nunca é entrega. |
| Concorrência humano×agente | Reload automático do Zettlr + git; sem lock novo. |
| Pandoc embutido do Zettlr < 3.0 | O filtro exige `pandoc.json` (Pandoc ≥ 3.0); guia fixa versão mínima do Zettlr. Doctor não introspecta o Pandoc do Zettlr — limitação aceita. |

## Testes

Padrão do repo: `tests/unit/<domínio>/`, deps externas mockadas nos seams, TDD.

- **Scanner canônico no compose** — regressão do truncamento de chave composta; três formas Pandoc; chaves com `: . # -` etc.; e-mails ignorados; code blocks pulados; captura dentro de `[[@key]]`/`[[@key|alias]]` fixada por teste (flavor-agnóstico).
- **`wiki lint` flavor-agnóstico** — fixtures com sintaxes mistas; citekey presente/ausente validado igual nas duas.
- **`write zettlr-profile`** — YAML com `reader`/`writer`; `citeproc` antes do filtro; caminho do filtro resolvido e existente; `reference-doc` do projeto; idempotência.
- **`doctor`** — perfil ausente/filtro quebrado ⇒ erro com comando de correção embutido.
- **Scaffold do `init`** — sem `.obsidian/`; frontmatter `bibliography:`/`csl:` nos drafts; nenhum template com `[[@`, `![[` ou `> [!`; `reference.docx` presente.
- **Regressão:** suíte de `export` e `normalize_markdown` intocada e verde.
- **Fora do CI (checklist manual no plano):** abrir pj novo no Zettlr; autocomplete funciona; citação renderiza; docx sai pelo perfil importado; custom command dispara `prumo write export` com guardas.

## Fora de escopo

- Migração de projetos legados (sem comando; adoção gradual manual permanece possível).
- `prumo write preview` (superado para projetos novos; não será construído neste ciclo).
- Correção do `.bib` stale (gap nº 2 do diagnóstico).
- Tudo de coautores/CriticMarkup (spec 2026-07-05, trilha própria).
- Escrever config global do Zettlr programaticamente (rejeitado: formato interno sem API estável).
- Abstração multi-editor (`domains/editor/`): rejeitada — "editor é commodity" (achado de jul/2026) + YAGNI do ROADMAP.

## Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Formato dos defaults files do Zettlr muda entre versões | Perfil é gerado (re-gerável); exigência conhecida (`reader`+`writer`) testada; guia fixa versão mínima. |
| Caminho absoluto do filtro quebra em reinstall/update do wheel | `doctor` detecta; `zettlr-profile` regenera. |
| Campo de custom command não aceita argumentos | Console-script dedicado (verificação empírica no início do plano). |
| Preview do Zettlr é sempre Chicago in-text (não o CSL do journal) | Limitação cosmética documentada; o que importa no loop interno é ver a citação resolver para a obra certa. O CSL real aparece nos exports. |
| Docx de trabalho circular como se fosse entrega | Guia e mensagens deixam explícito o caminho canônico; guardas só existem nele. |

## Relação com o spec 2026-07-05 (docx→CriticMarkup)

Complementar, sem sobreposição de escopo. Impacto positivo: em projetos novos, fonte Pandoc pura ⇒ source ≈ input de export ⇒ o mapa de spans/transplante da ponte docx→CriticMarkup aproxima-se da identidade (o caminho legado continua precisando do mapa completo). O invariante **I7 (gramática única de citekey)** daquele spec é implementado por este.

## Referências

- Zettlr docs: `docs.zettlr.com/en/editor/citations/`, `/en/file-manager/projects/`, `/en/export/defaults-files/`, `/en/export/custom-commands/`.
- Código: `domains/write/export.py` (scanner, lookup BBT, guardas), `_filters/zotero_live_docx.lua` (lookup opcional — cabeçalho), `domains/write/compose.py` (regex divergente a remover), `core/obsidian.py` (normalize, caminho legado).
- Memória de projeto: `citation-editing-pain-2026-07` (diagnóstico e decisões de jul/2026).
