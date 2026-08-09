---
title: Layout — núcleo universal, camadas com gatilho, escopos para múltiplas escritas
date: 2026-08-08
status: draft
tags: [layout, pj_base, references, scope, modules, zettlr, zotero, breaking, adr]
---

# Layout — núcleo universal, camadas com gatilho, escopos para múltiplas escritas

## Resumo executivo

Três mudanças, nesta ordem de importância:

1. **A bibliografia entra em `docs/`.** `docs/` é a **raiz única de leitura** — tudo que o pesquisador abre num editor de texto vive ali; dado, código e saída de máquina ficam fora. A bibliografia é leitura, logo mora dentro. `references/notes/<citekey>/` vira **`papers/<citekey>/`**, resolvendo a colisão com `notes/`.
2. **O núcleo serve qualquer pesquisador.** Sete entradas de conteúdo que um revisor sistemático, uma pesquisadora qualitativa, um clínico sem código, um pesquisador de ML e um doutorando em humanidades usam **todos**. Tudo que serve só a alguns vira camada com gatilho observável.
3. **A escrita mora sempre num escopo.** `docs/studies/<slug>/` com `notes/`, `writing/` e `decisions/` próprios existe desde o `init`, com um artigo ou com cinco. Uma segunda escrita — artigo, capítulo de tese, grant paralelo — é só uma pasta irmã. A bibliografia continua **uma, do projeto**.

O que o núcleo é: **o que sobra quando você tira o computador do pesquisador.** Ler, anotar, citar, escrever, exportar, registrar decisão. Coorte, notebook, PICOT e comitê de ética são camadas.

Tudo entra numa fase só — **0.65.0, `⚠ Breaking`**. Não há Fase 2: com o escopo presente desde o `init`, `prumo add study <slug>` é criar uma pasta irmã, e a máquina de promoção que uma versão anterior desta spec desenhou (manifesto, recusa por worktree suja, reescrita de links) **deixa de existir**.

## Contexto

### O pedido, e os dois erros que ele corrigiu

O dono pediu `references/` dentro de `docs/`; *"modular e enxuto — tem que ter um racional muito importante por trás de cada diretório para existir"*; lugar para sub-projetos de artigo; e, por fim, *"que a spec seja flexível e fácil para qualquer pesquisador usar e não apenas para um projeto específico"*.

Duas versões anteriores erraram, e os erros estão registrados porque explicam o desenho:

- **Erro 1 — medir custo de migração.** Cortou `writing/` e `studies/` porque "relocaria 10 arquivos em 3 de 11 projetos". Para projeto novo esse custo é zero. A pergunta era qual estrutura é certa.
- **Erro 2 — sobreajustar a um pesquisador.** A evidência veio de 11 projetos de **um** pesquisador, todos de pesquisa clínica com ML, todos com Zotero + Better BibTeX + Zettlr + Python. O resultado promoveu o módulo `ml` a obrigatório e elegeu `picot.toml` como sentinela de escopo. Quatro dos cinco arquétipos testados não formulam PICOT; três nunca abrem `src/`.

### O modelo que o repo já tem, e que a spec ignorou

[Research Project Structure.md:74-87](../../Research%20Project%20Structure.md) define **núcleo mínimo mais camadas opcionais com gatilho** — exatamente a saída pedida. Esta spec volta a esse modelo.

**Pré-requisito honesto:** o mecanismo está declarado e quase não construído. `find templates -name _module.toml` devolve **dois** módulos (`clinical`, `ml`) para oito declarados no RPS. E `templates/modules/ml/` contém apenas `.claude/make/ml.mk`, quatro rules e `eda.ipynb` — **não** contém `src/`, `tests/`, `notebooks/` nem `content/`. Mover esses quatro para o módulo significa **escrevê-los**. Enquanto isso não acontecer, a spec não pode afirmar que a camada cobre o caso.

## O núcleo — sete entradas de conteúdo

```
pj_<nome>/
├── README.md   CLAUDE.md
├── .claude/                    pj_config.toml — SENTINELA do projeto; rules/, skills/
├── build/exports/              saída regenerável, gitignored
│
└── docs/                       ═══ RAIZ ÚNICA DE LEITURA ═══
    ├── _index.md               catálogo
    ├── _log.md                 diário append-only
    ├── project_guide.md        objetivo, pergunta(s), escopo — em prosa livre
    ├── templates/              infra de export (reference.docx, perfil do editor)
    ├── references/             ← DO PROJETO, uma só
    │   ├── .gitignore             padrões não ancorados: viajam com a pasta
    │   ├── _references.bib  _index.md
    │   ├── papers/<citekey>/      ex-notes/ — layout α (ADR-0008) intacto
    │   └── pdfs/<citekey>.pdf     flat, symlinks, gitignored
    └── studies/<slug>/         ← ESCOPO, sempre. Um projeto tem ≥ 1
        ├── notes/                 seu pensamento
        ├── writing/               o produto (+ figures/ e tables/ ao lado)
        └── decisions/             append-only
```

**O escopo existe desde o `init`, mesmo com um artigo só.** É a decisão que apaga a promoção: quando nasce a segunda escrita, ela é uma pasta irmã — nada se move, nenhum link muda de profundidade, nenhum manifesto é preciso. E a profundidade fixa torna o caminho relativo à bibliografia **invariante** em todo escopo (§6).

Trabalho transversal a todos os escopos — preparo de dado, revisão de fundo — ganha um escopo próprio numerado, como o `pj_piloto_genetica` já faz com `00_data_preparation/`.

### O racional, testado contra cinco arquétipos

Revisor sistemático (A), pesquisadora qualitativa (B), clínico sem código (C), pesquisador de ML (D), doutorando em humanidades (E).

| entrada | nível | quem escreve | quando muda | cobertura |
|---|---|---|---|---|
| `references/` | projeto | qualquer gerenciador → `.bib` | regenerável | **5/5** — o único que não é seu |
| `_index.md` `_log.md` | projeto | máquina + você | contínuo | **5/5** — histórico de busca (A), *reflexive journal* (B), trilha de auditoria (C) |
| `project_guide.md` | projeto | você | quando o projeto muda | **5/5** — a pergunta de pesquisa **em prosa livre** mora aqui |
| `templates/` `build/exports/` | projeto | máquina | scratch | **5/5** — todos exportam |
| `notes/` | **escopo** | você | livre | **5/5** — extração p/ A, memos p/ B, fichamento p/ E |
| `writing/` | **escopo** | você; máquina exporta | por entrega | **5/5** — o único produto que todos entregam |
| `decisions/` | **escopo** | você | append-only, imutável | **5/5** — critério de elegibilidade (A), *audit trail* (B), emenda de protocolo (C) |

A linha divisória é limpa: **o projeto guarda o que é comum a todas as escritas; o escopo guarda uma escrita.**

`writing/` **não lista nomes de arquivo**. A regra é: um `.md` por entrega, com `figures/` e `tables/` ao lado. `protocol.md`, `sap.md` e `cep.md` são payload de camada.

**`findings/` não existe** — finding é output de máquina com procedência ([findings.py:26](../../../src/prumo_assist/domains/wiki/findings.py)), logo não é `writing/`; e não merece pasta, logo é `type: finding` numa nota.

**`project_guide.md` não exige hipótese.** As seções do núcleo são Objetivo, Pergunta(s) e Escopo. Hipótese entra pela camada `picot`.

## Escopo — sempre presente, resolvido por posição

```python
find_pj_root(start)     # sobe até .claude/pj_config.toml
find_scope_root(start)  # o filho direto de docs/studies/ que contém o arquivo
```

- **Sem arquivo sentinela.** O escopo é posição na árvore: todo filho direto de `docs/studies/` é um escopo, sempre. Nada a criar, nada a perder num `git mv`.
- **Segunda escrita = pasta irmã.** Nada se move, nenhum link muda de profundidade, nenhum manifesto de promoção é preciso. Esta é a razão de o escopo existir desde o `init`.
- **Bibliografia, `reviews/`, `build/exports` e `slugify` ancoram no pj root.** `notes/`, `writing/` e `decisions/` ancoram no escopo.
- **`slugify` no pj root** produz `studies__<slug>__writing__paper` — único por construção, então dois escopos nunca colidem em `reviews/`.
- **`pages:` do `compose`** resolve contra o diretório do índice quando ele está sob `writing/`.
- **`picot.toml` é opcional e mora na raiz do escopo** quando a camada `picot` está ativa. Não é sentinela de nada.

O eixo é "unidade de escrita", não "estudo clínico": serve capítulo de tese, submissão paralela, grant. O nome `studies/` fica por familiaridade; a semântica é neutra.

**O slug do primeiro escopo** é sugerido pelo wizard a partir do nome do projeto e aceito com Enter — é a única pergunta nova que o `init` ganha.

### Bibliografia é do projeto, não do escopo

Verificado, e é o que a prática do dono já faz — `pj_piloto_genetica` serve três estudos com uma `references/`:

1. **`sync` não tem noção de pertencimento.** [sync.py:254](../../../src/prumo_assist/domains/paper/sync.py) classifica como órfã toda pasta de citekey ausente do `.bib` carregado. Bibliografia compartilhada com `.bib` por escopo reportaria até 219 falsos órfãos no `phd`.
2. **`.bib` por escopo exigiria N coleções no Zotero à mão** — [connect.py:287](../../../src/prumo_assist/domains/paper/connect.py) recusa quando o bib tem entradas reais, e ADR-0020 põe `autoexport.remove`/`list` fora de escopo.
3. **Duplicaria `_extract.md`** do mesmo PDF, e `citation-support` julgaria contra a cópia do escopo.

Consequência assumida: o escopo leva `notes/`, `writing/` e `decisions/` — não a bibliografia.

## Camadas — gatilho observável, nunca "quando precisar"

| camada | gatilho observável | o que adiciona | existe? |
|---|---|---|---|
| `code` | primeiro `.py` no projeto | `src/`, `tests/`, `pyproject.toml` | **a escrever** |
| `data` | primeiro dataset | `content/{01_raw,02_processed}/` + regra de gitignore | **a escrever** |
| `notebooks` | primeira exploração interativa | `notebooks/` | **a escrever** |
| `ml` | `prumo add ml` | rules de stack e governança, `eda.ipynb` | existe |
| `picot` | pergunta comparativa formalizada | `picot.toml` no escopo, seção Hipótese | parcial |
| `clinical` | participantes humanos, comitê de ética | `writing/protocol.md`, `sap.md` | existe (ver abaixo) |
| `clinical-br` | submissão a CEP/CONEP | `writing/cep.md`, templates da Plataforma Brasil | **a separar** |
| ~~`studies`~~ | — | virou núcleo: o escopo existe sempre | núcleo |
| `zotero` | Local API detectada em `127.0.0.1:23119` | `paper connect`, sync de annotations, symlinks de PDF | existe |
| `editor-profile` | `prumo write zettlr-profile` invocado | perfil de export do editor | existe |
| `extended-wiki`, `brainstorm-pipeline`, `peer-review-loop`, `versioned-milestones`, `specify-workflow` | ver [RPS:74-87](../../Research%20Project%20Structure.md) | — | **prosa apenas** |

**`clinical` precisa mudar o anchor junto.** [`_module.toml`](../../../templates/modules/clinical/_module.toml) declara `anchor = "docs/protocol.md"`. Com o manuscrito em `writing/`, sem mudar o anchor o `prumo add clinical` recria um segundo `protocol.md` na raiz de `docs/`.

Arquétipos sem camada hoje: **revisão sistemática** (triagem, critérios de elegibilidade, PRISMA), **qualitativa** (corpus, códigos, memos), **tese longa** (partes ordenadas). São os três buracos que um pesquisador novo teria de inventar à mão — que foi exatamente como o dono inventou `studies/`. Entram no ROADMAP com gatilho.

## Independência de ferramenta

O contrato real é **BibTeX, não Zotero**: [sync.py](../../../src/prumo_assist/domains/paper/sync.py) lê `references/_references.bib` e nada mais. Quem usa Mendeley, Paperpile, EndNote ou JabRef aponta o `.bib` e tem o núcleo inteiro. O que é exclusivo do Better BibTeX — `paper connect`, sync de annotations, symlinks de PDF — vira camada `zotero`, declarada como tal.

| acoplamento | hoje | passa a ser |
|---|---|---|
| **Editor** | "`docs/` é o workspace do Zettlr" | "`docs/` é a raiz única de leitura" — vale para Obsidian, VS Code, Typora, Vim, ou nenhum |
| **Zotero** | pressuposto do acervo | camada `zotero`; sem ela, `.bib` apontado à mão |
| **pandoc/typst** | dependência não declarada, dica só de macOS | entram em `check_external_deps` com hint por plataforma, **antes** do primeiro export |
| **docx com campos vivos** | default do export | `--to docx` sem Zotero produz citação renderizada + aviso do que se perde |
| **CSL** | só `~/Zotero/styles/` | cascata: `--csl` → `pj_config` → `~/Zotero/styles/` → 2-3 CSL embarcados no wheel |
| **git** | `add study` recusa sem git | git é **proteção** opcional: sem ele, grava o manifesto e prossegue com aviso alto |
| **Python** | `pyproject.toml` no `pj_base` | camada `code` |
| **nome do projeto** | prefixo `pj_` **validado** | default sugerido pelo wizard; identidade real é `.claude/pj_config.toml` |

## O que muda no código

### 1 · `core/pj_layout.py`

```python
def bib_path(pj_root) / papers_dir(pj_root) / pdfs_dir(pj_root)      # projeto
def notes_dir(scope) / writing_dir(scope) / decisions_dir(scope)     # escopo
def find_pj_root(start) / find_scope_root(start) / iter_scopes(pj_root)
```

Nenhum dos dois resolvedores existe hoje — são custo novo, escritos juntos, com teste de aninhamento. `core/note_paths.py` constrói sobre `papers_dir()`; ADR-0008 segue válido.

### 2 · O lint vira por escopo, e afrouxa onde era clínico demais

| onde | defeito | conserto |
|---|---|---|
| [lint.py:69](../../../src/prumo_assist/domains/wiki/lint.py) | `docs.rglob` engole a bibliografia: 23 → 246 páginas no `phd` | excluir `references/` da varredura |
| [lint.py:70](../../../src/prumo_assist/domains/wiki/lint.py) | identidade por `stem` — 22 `evaluation.md` já colidem hoje | caminho relativo ao escopo; `ambiguous_link` novo |
| [lint.py:64,87](../../../src/prumo_assist/domains/wiki/lint.py) | `.bib` ausente desliga a checagem de citekey em silêncio | `bib_missing` **warning**, só quando há `[@citekey]` no escopo |
| [lint.py:177](../../../src/prumo_assist/domains/wiki/lint.py) | `multiple_primary` global | **desligado por default**; liga quando o escopo declara ter paper principal |
| [lint.py:32,80](../../../src/prumo_assist/domains/wiki/lint.py) | tipagem por `parts[0]` contra `EXPECTED_DIRS` | tipar pelo diretório-pai; ausência vira erro, nunca no-op |

`bib_missing` é warning e não erro porque um projeto sem bibliografia é legítimo no dia 1 e permanente para quem não cita. `multiple_primary` fica desligado porque um revisor sistemático tem N estudos incluídos e **zero** primários.

[stats.py](../../../src/prumo_assist/domains/wiki/stats.py) ganha `by_scope` e mantém `by_type`.

### 3 · Findings, nos dois lados

[findings.py:16](../../../src/prumo_assist/domains/wiki/findings.py) **recria** o diretório que o desenho elimina; [compose.py:178](../../../src/prumo_assist/domains/write/compose.py) só procura diretório, então `prumo write prep` entregaria contexto **sem nenhum finding**, com exit 0. Mudam juntos: escrever em `<scope>/notes/<slug>.md`, varrer `<scope>/notes/**/*.md` filtrando `type:`.

### 4 · Figuras no export — hoje somem em silêncio

[export.py:800](../../../src/prumo_assist/domains/write/export.py) grava num diretório temporário, `_build_pandoc_cmd` nunca passa `--resource-path`, e `_run_pandoc_checked` não define `cwd`. Verificado com pandoc 3.9.0.2: `[WARNING] Could not fetch resource`, **exit 0**, docx sem imagem nenhuma. Sem conserto, `writing/figures/` seria um diretório cuja única justificativa é falsa no entregável.

### 5 · Export nunca escreve irmão da fonte

A saída permanece em `build/exports/`, e [export.py:793](../../../src/prumo_assist/domains/write/export.py) ganha a guarda de sobrescrita que [compose.py:322](../../../src/prumo_assist/domains/write/compose.py) já tem: no `pj_piloto_imagem`, `docs/study_protocol_oficial.docx` **é** o docx devolvido pelo coautor, untracked, ocupando exatamente o stem que um export irmão usaria.

### 6 · O campo `bibliography` continua literal — e agora é invariante

Os quatro `skills/write-*/template.md` gravam `bibliography: ../../references/_references.bib`, e **nenhum código escreve esse campo** — esses literais *são* o mecanismo que dá autocomplete de citação ao editor.

Como todo draft mora em `docs/studies/<slug>/writing/`, a bibliografia está **sempre** a três níveis: `../../../references/_references.bib`. Um único literal serve a todos os escopos, hoje e quando o quinto nascer. Basta corrigir a profundidade nos quatro arquivos — eles não são `SKILL.md` e escaparam de todos os inventários anteriores.

Foi o escopo desde o `init` que tornou isso possível: com escopo opcional, a profundidade variava e o campo teria de ser calculado em código.

### 7 · `references/.gitignore` próprio

Padrões ancorados param de casar a cada nível — verificado com `git check-ignore` nas quatro formas do parque. Padrões **não ancorados** (`pdfs/*.pdf`, `!pdfs/.gitkeep`) viajam com a pasta.

### 8 · `pdfs/` fica como está

Flat, gitignored, uma vez por projeto. `pdfs/` (326 symlinks, 1 quebrado) e `papers/` (85 pastas) indexam **populações diferentes** — 251 PDFs sem pasta, 10 pastas sem PDF. E o diretório é **fronteira de workspace**: `paper extract-prep` emite `pdf_path` dentro da raiz do projeto para o subagente ler com `Read`; sem ele o caminho cai em `~/Zotero/storage/`, fora de qualquer `pj_*`, e o batch de 8 subagentes vira N prompts de permissão.

## Adequação de projeto existente — agêntica

Projeto fora do layout não é caso de comando. O CLI detecta e falha com mensagem clara; um agente conduz a conversa e executa com o pesquisador. Codificar isso seria mais máquina que problema: quatro formas de `.gitignore`, dois projetos sem git, duas classes de link com regras **opostas** (46 wikilinks mudam de prefixo, 16 links relativos mudam de profundidade), 32 scripts em `.claude/scripts/`, uma skill geradora que emite caminhos antigos, e o passo do autoexport dentro do Zotero — [connect.py:297](../../../src/prumo_assist/domains/paper/connect.py) grava caminho absoluto, e o BBT recria `references/` na raiz se ele não for reconfigurado.

`prumo doctor` erra quando `docs/references/` existe **e** `references/` reapareceu na raiz: assinatura exata do autoexport não reconfigurado.

## O contrato do pesquisador

1. **`notes/` é seu, `writing/` é o produto, `references/` vem do seu gerenciador.** A dúvida "isso é nota ou é escrita?" se resolve por "isso vai virar entrega?".
2. **Não mova nem renomeie pasta de citekey.** O YAML de metadata e os blocos delimitados são da máquina; **o corpo da nota é seu** — [sync.py:112](../../../src/prumo_assist/domains/paper/sync.py) faz merge, não sobrescrita.
3. **O resto aparece quando você precisa.** Nenhum diretório de código, dado ou ética num projeto que não os tem.

Errar de escopo não quebra nada: o lint acusa e o arquivo continua legível.

## Fora de escopo, com o número que justifica

| descartado | por quê |
|---|---|
| `src/`, `tests/`, `notebooks/`, `content/` no `pj_base` | 4 de 5 arquétipos nunca os abrem — vão para camadas `code`, `data`, `notebooks` |
| `picot.toml` como sentinela | 4 de 5 arquétipos não formulam PICOT; escopo passa a ser implícito por posição |
| `scope.toml` como sentinela novo | +1 conceito para todo mundo resolver um problema de alguns; posição basta |
| `.bib` por escopo | `sync` reportaria até 219 órfãos falsos; N coleções no Zotero à mão |
| `pdfs/` por citekey ou eliminado | populações distintas (326 × 85); é fronteira de workspace para o `Read` |
| `analyses/` e `code/` | não existem em nenhum dos 11 projetos nem em nenhuma linha de código |
| `writing/_out/` | `build/exports` e `reviews/` bastam; um terceiro destino seria destrutivo (§5) |
| convivência de layouts | corte limpo, reafirmado: *"os projetos podem se readequar"* |

## Governança

- **ADR-0022** — `docs/` como raiz única de leitura; bibliografia do projeto dentro dela; `papers/`; núcleo universal e camadas com gatilho; escopo implícito por posição.
- **ADR-0023** — findings como `type:` em `notes/`, **substituindo ADR-0014**.
- **ADR-0024** — o escopo (`docs/studies/<slug>/`) presente desde o `init`, resolvido por posição, com a bibliografia fora dele.
- **[Research Project Structure.md](../../Research%20Project%20Structure.md) é a fonte do catálogo de camadas** e precisa ser atualizada junto: hoje promete `findings/` e lista oito módulos, dos quais dois existem.
- **Emenda à constitution**: [constitution.md:65](../../constitution.md) → `docs/references/papers/`, com Sync impact report.
- **Release**: 0.64.1 → **0.65.0**, MINOR por ser breaking (ADR-0015).

## Testes

TDD: `test_pj_layout.py` (novo) → `core/` → `domains/` → CLI → `test_pj_base_integration.py`.

Um teste por defeito medido: `prumo init` sem camada nenhuma produz **zero** diretório de código, e `prumo doctor` sai 0 · lint devolve a mesma contagem de páginas depois do movimento · `.bib` ausente sem citação **não** emite nada; com citação emite warning · `multiple_primary` não dispara sem declaração · páginas homônimas em escopos diferentes recebem issues distintas · `compose` acha findings por `type:` · export com `figures/` embute a imagem e **falha alto** quando ela falta · `export` recusa sobrescrever sem `--force` · `git check-ignore` confirma o PDF ignorado em qualquer profundidade · `slugify` de dois escopos não colide · `prumo add clinical` não cria um segundo `protocol.md`.

## Critérios de aceitação

1. Inventário **nominal** de literais de layout autorizados fora de `core/pj_layout.py`.
2. `prumo init` produz o núcleo com **um** escopo em `docs/studies/<slug>/` e nenhum `src/`, `content/`, `notebooks/` ou `pyproject.toml`.
2b. `prumo add study <outro>` cria a pasta irmã e **não toca** em nada existente — nenhum arquivo movido, nenhum link reescrito.
3. Um projeto sem Zotero, sem Python e sem git completa: apontar `.bib` → escrever em `writing/` → exportar. `doctor` avisa o que falta **antes** do primeiro export, com hint da plataforma detectada.
4. Um `.md` com `![](figures/x.png)` exporta com a imagem embutida; sem a imagem, **falha**.
5. Em projeto não migrado, todo comando exceto `doctor` falha convidando à adequação.
6. `uv run pytest`, `uv run ruff check .`, `uv run mypy` limpos.
7. *(manual)* Um editor de Markdown apontado para `docs/` mostra bibliografia, notas e manuscritos numa árvore só.
