---
title: Layout por escopo — bibliografia do projeto, escrita por estudo
date: 2026-08-08
status: draft
tags: [layout, pj_base, references, scope, studies, writing, zettlr, zotero, breaking, adr]
---

# Layout por escopo — bibliografia do projeto, escrita por estudo

## Resumo executivo

O `pj_*` tem dois topos de leitura (`docs/` e `references/`), o manuscrito não tem casa, e um projeto guarda-chuva com vários estudos não tem forma.

Esta spec separa duas coisas que hoje se confundem:

- **O projeto possui a bibliografia.** Uma `docs/references/`, servindo o projeto inteiro. Um `.bib`, um autoexport do BBT, uma pasta por paper.
- **O escopo possui a escrita.** Quatro entradas — `picot.toml`, `notes/`, `writing/`, `decisions/` — que existem uma vez no guarda-chuva e uma vez por estudo em `docs/studies/<slug>/`.

Fora de `docs/`, o estudo nunca é pasta de topo: é subpasta de diretório que já existe (`src/<slug>/`, `notebooks/<slug>/`, `content/experiments/<slug>/`). **Nascer um segundo estudo cria zero diretório novo na raiz do projeto.**

`docs/` é o workspace do Zettlr, então a bibliografia migra para dentro dele, com `notes/<citekey>/` renomeado para **`papers/<citekey>/`** — a colisão com `notes/` do escopo desaparece e o nome passa a dizer o que a pasta é.

O desenho foi validado contra a prática real do dono: o `pj_piloto_genetica` já organiza três estudos com **uma** bibliografia compartilhada, e é onde o Zettlr está aberto agora.

**Fase 1 (0.65.0, `⚠ Breaking`)**: bibliografia sob `docs/`, o escopo com um só. **Fase 2**: `docs/studies/<slug>/` e `prumo add study`.

## Contexto

### O pedido, e o erro que ele corrigiu

O dono pediu três coisas: `references/` dentro de `docs/`; *"modular e enxuto — tem que ter um racional muito importante por trás de cada diretório para existir"*; e um lugar para sub-projetos de artigo.

Uma rodada anterior cortou `writing/` e `studies/` medindo **custo de migração** ("relocaria 10 arquivos em 3 de 11"). O dono rejeitou o raciocínio: a pergunta era qual estrutura é certa, não qual é barata de migrar. **Esta spec julga pelo projeto novo** e trata migração como problema separado, agêntico.

### A evidência que fecha o desenho

`pj_piloto_genetica` já resolveu multi-estudo sozinho, sem o prumo: `studies/{00_data_preparation,01_estudo,02_triage_calculator}/`, cada um com `notebooks/`, `scripts/` e `manuscript/{manuscript.md, figures/, tables/, qc/}` — servidos por **uma** `references/` na raiz. O `openDirectory` do Zettlr aponta para dentro dessa estrutura agora.

Duas lições foram adotadas: **bibliografia compartilhada** e **o estudo carrega a análise, não só a prosa**. Uma foi rejeitada pelo dono: o estudo mora sob `docs/`, não na raiz, para preservar `docs/` como único workspace de leitura.

### Três correções ao diagnóstico inicial

1. Os diretórios "orgânicos" do `pj_piloto_ml` são **módulos documentados com gatilho** ([RPS:74-87](../../Research%20Project%20Structure.md)), não invenção.
2. `entities/` e `sources/` com zero arquivos é módulo `extended-wiki` nunca disparado.
3. ADR-0014 descreve o resolver desse módulo. Esta spec o substitui, mas ele não era letra morta.

## O racional de cada entrada

O teste: **quem escreve** · **o que acontece quando muda** · **o que quebra se juntar com o vizinho**.

**Do projeto**, uma vez:

| entrada | quem escreve | quando muda | por que existe |
|---|---|---|---|
| `docs/references/` | Zotero → `paper sync` | regenerável, descartável | a única coisa que **não é sua**; um `.bib`, um autoexport, `pdfs/` com regra de gitignore própria |
| `content/` `src/` `notebooks/` `tests/` | você | ritmo do código | dado e análise não são leitura — ficam fora do workspace |
| `build/exports/` `reviews/<slug>/` | máquina | scratch | saída regenerável, gitignored, ancorada no pj root |

**Do escopo**, uma vez por estudo:

| entrada | quem escreve | quando muda | por que não cabe no vizinho |
|---|---|---|---|
| `picot.toml` | máquina + você | exige ADR novo | governa o escopo; viaja com ele num `git mv` |
| `notes/` | você | livre | conhecimento; sem procedência, sem entrega |
| `writing/` | você; máquina exporta | **por submissão** | o produto; recebe docx de coautor, carrega `figures/` e `tables/` |
| `decisions/` | você | **append-only, imutável** | `adr.py` numera varrendo o diretório |

**`findings/` não existe.** Finding é output de máquina com procedência ([findings.py:26](../../../src/prumo_assist/domains/wiki/findings.py)) — não é escrita, logo não é `writing/`; não merece pasta, logo é `type: finding` numa nota de `notes/`.

**`analyses/` e `code/` saem da spec.** Não existem em nenhum dos 11 projetos nem em nenhuma linha de código. O parque usa `src/`, `notebooks/`, `content/`, `tests/`, `build/`.

## Layout

**Projeto de um artigo** — nasce assim, nunca vê `studies/`:

```
pj_<nome>/
├── .claude/   README.md  CLAUDE.md  Makefile  pyproject.toml
├── content/{01_raw, 02_processed}/        dado, gitignored
├── src/   notebooks/   tests/
├── build/exports/   reviews/<slug>/       gitignored, ancorados no pj root
│
└── docs/                                  ═══ WORKSPACE DO ZETTLR ═══
    ├── _index.md  _log.md  project_guide.md
    ├── references/                        ← DO PROJETO
    │   ├── .gitignore                        padrões NÃO ancorados: viaja com a pasta
    │   ├── _references.bib  _index.md
    │   ├── papers/<citekey>/                 ex-notes/ — layout α (ADR-0008) intacto
    │   └── pdfs/<citekey>.pdf                symlinks → Zotero, flat, gitignored
    ├── picot.toml                         ┐
    ├── notes/                             │ ← O ESCOPO
    ├── writing/                           │   protocol.md, paper.md, cep.md, sap.md
    └── decisions/                         ┘   + figures/ e tables/ dentro de writing/
```

**Guarda-chuva com N estudos** — o eixo por estudo aparece em quatro lugares, todos dentro de diretório que já existe:

```
pj_piloto_rwd/
├── content/
│   ├── 01_raw/  02_processed/             a coorte, extraída UMA vez
│   └── experiments/<slug>/                ← saída de run do estudo
├── src/
│   ├── io_cohort.py  ...                  compartilhado
│   └── <slug>/                            ← código do estudo
├── notebooks/
│   ├── 00_data_preparation.ipynb          compartilhado
│   └── <slug>/                            ← exploração do estudo
└── docs/
    ├── references/                        UMA bibliografia, do projeto
    ├── picot.toml  notes/  writing/  decisions/     escopo guarda-chuva
    └── studies/<slug>/                    ← o ÚNICO studies/ da árvore
        └── picot.toml  notes/  writing/  decisions/
```

**A regra, numa frase:** `docs/` é o único lugar onde o estudo é uma pasta. Fora de `docs/`, o estudo é uma subpasta de um diretório que já existe.

## Raiz e escopo são dois conceitos

Hoje um resolvedor só responde às duas perguntas, e com aninhamento isso corrompe.

```python
find_pj_root(start)     # sentinela .claude/pj_config.toml — 1 por projeto
find_scope_root(start)  # sentinela picot.toml — para no MAIS PRÓXIMO
```

- **Bibliografia, `reviews/`, `build/exports` e `slugify` ancoram no pj root.** `picot.toml`, `notes/`, `writing/` e `decisions/` ancoram no escopo.
- **`slugify` no pj root é obrigatório.** Senão `docs/writing/paper.md` e `docs/studies/x/writing/paper.md` geram o mesmo slug, os dois escrevem em `reviews/writing__paper/`, e um `write review ingest` do estudo carrega o `citemap.json` do guarda-chuva — o pareamento citação↔ocorrência casa contra o documento errado, em silêncio.
- **`pages:` do `compose`** resolve contra o diretório do índice quando ele está sob `writing/`; contra o pj root caso contrário.
- `find_scope_root` levanta `ScopeNotFoundError` em pt-BR com o comando embutido — não devolve `None` (`mypy --strict`).

**`picot.toml` sai de `.claude/`.** [picot_io.py:22](../../../src/prumo_assist/domains/protocol/picot_io.py) devolve `pj_path/".claude"/"picot.toml"` — fora do workspace e não acompanha um `git mv`. Propaga em `ops.py:67,108`, `adr.py:30,45` e na skill `formulate-picot`.

## Bibliografia do projeto — por que compartilhada

A alternativa (um `.bib` por estudo) foi avaliada e descartada pelo dono, alinhada à prática dele. Três razões, todas verificadas:

1. **`sync` não tem noção de pertencimento.** [sync.py:254](../../../src/prumo_assist/domains/paper/sync.py) classifica como órfã toda pasta de citekey ausente do `.bib` carregado. A única fonte de pertencimento é a igualdade `.bib` ↔ diretório. Bibliografia compartilhada com `.bib` por escopo faria o `orphans` reportar até 219 falsos no `phd`.
2. **O Zotero cobra caro.** [connect.py:287](../../../src/prumo_assist/domains/paper/connect.py) recusa quando o bib tem entradas reais, e ADR-0020 põe `autoexport.remove`/`list` fora de escopo. `.bib` por estudo exigiria N coleções e N autoexports configurados à mão.
3. **Duplicação de extract.** Um paper citado por dois estudos geraria dois `_extract.md` do mesmo PDF, gerados independentemente — e `citation-support` julgaria contra a cópia do escopo.

Consequência assumida: **o estudo não é arrancável sozinho.** Ele leva `picot.toml`, `notes/`, `writing/`, `decisions/`, o código e os notebooks — não a bibliografia.

## `pdfs/` — o Zotero gerencia, o diretório é fronteira

Fica **flat, `pdfs/<citekey>.pdf`, gitignored, uma vez por projeto**. Não vira `papers/<citekey>/paper.pdf` e não é eliminado.

- **`pdfs/` e `papers/` indexam conjuntos diferentes.** 326 symlinks contra 85 pastas de citekey; 251 PDFs sem pasta, 10 pastas sem PDF. Um é 100% ignorado pelo git, o outro 100% versionado — donos e ciclos de vida distintos, o mesmo teste que justifica as entradas do escopo.
- **É fronteira de workspace, não cache.** `prumo paper extract-prep` emite `pdf_path` **dentro** da raiz do projeto, e `paper-extract` entrega esse caminho a um subagente que abre com `Read`. Sem o diretório, o caminho vira `~/Zotero/storage/<KEY>/<título com espaços e travessão>.pdf`, fora de qualquer `pj_*`. Nenhum projeto do parque tem bloco `permissions`, e o batch despacha ondas de 8 subagentes: seriam N prompts de permissão, ou uma concessão ampla sobre a biblioteca inteira do Zotero.
- Saúde real medida: **326 symlinks, 1 quebrado.**

## O que muda no código

### 1 · `core/pj_layout.py`

```python
def bib_path(pj_root) / papers_dir(pj_root) / pdfs_dir(pj_root)      # projeto
def notes_dir(scope) / writing_dir(scope) / decisions_dir(scope)     # escopo
def picot_path(scope)
def find_pj_root(start) / find_scope_root(start) / iter_scopes(pj_root)
```

`core/note_paths.py` constrói sobre `papers_dir()`. ADR-0008 segue válido — o layout α dentro da pasta do citekey não muda.

### 2 · O lint vira por escopo

Cinco defeitos, todos silenciosos, todos medidos:

| onde | defeito | consequência |
|---|---|---|
| [lint.py:69](../../../src/prumo_assist/domains/wiki/lint.py) | `docs.rglob` engole a bibliografia | 23 → 246 páginas no `phd`; `orphan_page` 7 → 227 |
| [lint.py:70](../../../src/prumo_assist/domains/wiki/lint.py) | identidade de página por `stem` | 22 `evaluation.md` distintos já colidem hoje |
| [lint.py:64,87](../../../src/prumo_assist/domains/wiki/lint.py) | `.bib` ausente ou vazio desliga a checagem de citekey | `broken_citekey` 54 → 0; **5 dos 11 projetos já estão nesse estado** |
| [lint.py:177](../../../src/prumo_assist/domains/wiki/lint.py) | `multiple_primary` global | com N estudos, cada um com seu paper principal, vira falso positivo |
| [lint.py:32,80](../../../src/prumo_assist/domains/wiki/lint.py) | tipagem por `parts[0]` contra `EXPECTED_DIRS` | com `studies/`, `no_frontmatter` nunca dispara |

Conserto: `lint(scope)` por escopo mais `lint_all` que itera e etiqueta; identidade por caminho relativo ao escopo; wikilink resolve por índice `stem → [paths]` dentro do escopo, com `ambiguous_link` novo. `.bib` ausente vira `WikiIssue("error", "bib_missing", ...)`. `WikiIssue` ganha campo opcional `scope` (default `None`, forward-only). Como a bibliografia é do projeto, `role: primary` passa a declarar o escopo a que se refere — sem isso `multiple_primary` não tem como contar certo.

[stats.py](../../../src/prumo_assist/domains/wiki/stats.py) ganha `by_scope` e mantém `by_type`.

### 3 · Findings, nos dois lados

[findings.py:16](../../../src/prumo_assist/domains/wiki/findings.py) **recria** o diretório que o desenho elimina e indexa no `_index.md` do guarda-chuva. E [compose.py:178](../../../src/prumo_assist/domains/write/compose.py) só procura diretório: com findings virando `type:`, `ComposeInputs.findings == []` e `prumo write prep` entrega contexto **sem nenhum finding**, com exit 0.

Mudam juntos: escrever em `<scope>/notes/<slug>.md`, varrer `<scope>/notes/**/*.md` filtrando `type:`, e mirar o `_index.md`/`_log.md` do escopo.

### 4 · Figuras no export — hoje somem em silêncio

`writing/figures/` só funciona com conserto. [export.py:800](../../../src/prumo_assist/domains/write/export.py) grava o markdown normalizado num diretório **temporário**, `_build_pandoc_cmd` nunca passa `--resource-path`, e `_run_pandoc_checked` chama `subprocess.run` sem `cwd`. Verificado com pandoc 3.9.0.2: rodando de fora do diretório da página, `![](figures/x.png)` produz `[WARNING] Could not fetch resource`, **exit 0**, docx sem nenhuma imagem e sem aviso ao usuário.

Conserto: `--resource-path` apontando para o diretório da página, mais `_assert_no_missing_resource` sobre o stderr — o mesmo padrão que `_assert_no_citeproc_missing` já aplica a citekey ausente.

### 5 · Export nunca escreve irmão da fonte

[export.py:793](../../../src/prumo_assist/domains/write/export.py) não tem guarda de sobrescrita, diferente de [compose.py:322](../../../src/prumo_assist/domains/write/compose.py). A saída permanece em `build/exports/`, e `export()` ganha a mesma guarda: no `pj_piloto_imagem`, `docs/study_protocol_oficial.docx` **é** o docx devolvido pelo coautor, untracked, ocupando exatamente o stem que um export irmão usaria.

### 6 · O campo `bibliography` passa a ser calculado

Os quatro `skills/write-*/template.md` gravam `bibliography: ../../references/_references.bib` e **nenhum código escreve esse campo** — esses literais *são* o mecanismo do autocomplete `@` do Zettlr. Com a bibliografia no projeto e o escopo em profundidade variável, nenhum literal serve aos dois níveis.

Conserto: o `prumo` calcula o caminho relativo e escreve o campo ao criar o draft. Some a fragilidade e o template deixa de carregar caminho.

### 7 · `references/.gitignore` próprio

Padrões ancorados param de casar a cada nível — verificado com `git check-ignore` nas quatro formas do parque. Um `references/.gitignore` com padrões **não ancorados** (`pdfs/*.pdf`, `!pdfs/.gitkeep`) viaja com a pasta. As duas linhas saem do `.gitignore` da raiz.

### 8 · Fonte do template

`templates/pj_base/` passa a nascer com `src/`, `tests/`, `notebooks/` e `content/` — hoje inexistentes, e é por isso que o `outro_projeto` reinventou o esqueleto à mão. Mais `.gitignore` (com `~$*`, `**/_out/`, `.prumo/`, e `uv.lock` **fora** do ignore), `docs/_index.md` e `.claude/rules/documentation.md`.

## Promoção — `prumo add study <slug>` (Fase 2)

Quando o segundo artigo aparece, o primeiro também vira escopo, senão os níveis ficam assimétricos. Move apenas `picot.toml`, `notes/`, `writing/` e `decisions/`; a bibliografia **não se move**.

- **Recusa** worktree suja ou sem git, salvo `--force`. Medido: 2 dos 11 projetos não têm git funcional e 5 estão sujos agora.
- Grava `docs/studies/_promotion.json` (origem→destino + sha256) **antes** de qualquer `mv`.
- Idempotente: `docs/studies/` existente significa já promovido.
- Cria `src/<slug>/`, `notebooks/<slug>/` e `content/experiments/<slug>/` vazios só quando pedido.

## Adequação de projeto existente — agêntica

Projeto fora do layout não é caso de comando. O CLI detecta e falha com mensagem clara; um agente conduz a conversa e executa com o pesquisador.

Codificar isso seria mais máquina que problema: quatro formas de `.gitignore`, dois projetos sem git, duas classes de link com regras **opostas** (46 wikilinks mudam de prefixo, 16 links relativos mudam de profundidade), 32 scripts em `.claude/scripts/`, uma skill geradora que emite caminhos antigos a cada avaliação, e o passo do autoexport dentro do Zotero — [connect.py:297](../../../src/prumo_assist/domains/paper/connect.py) grava caminho absoluto, e o BBT recria `references/` na raiz se ele não for reconfigurado.

`prumo doctor` erra quando `docs/references/` existe **e** `references/` reapareceu na raiz: é a assinatura exata do autoexport não reconfigurado.

## O contrato do pesquisador

1. **`notes/` é seu, `writing/` é o produto, `references/` vem do Zotero.** A dúvida "isso é nota ou é escrita?" se resolve por "isso vai virar entrega?".
2. **Não mova nem renomeie pasta de citekey.** O YAML de metadata e os blocos delimitados são da máquina; **o corpo da nota é seu** — as 7 seções humanas de [documentation.md:70-82](../../../templates/pj_base/.claude/rules/documentation.md) são preservadas por [sync.py:112](../../../src/prumo_assist/domains/paper/sync.py), que faz merge.
3. **Fora de `docs/`, o estudo é subpasta do que já existe.** Nenhum diretório novo na raiz quando o segundo estudo nasce.

Errar de escopo não quebra nada: o lint acusa e o arquivo continua legível. Quebra só quem move pasta de citekey ou edita dentro de bloco delimitado.

## Fora de escopo, com o número que justifica

| descartado | por quê |
|---|---|
| `.bib` por estudo | `sync` reportaria até 219 órfãos falsos; N coleções no Zotero à mão; `_extract.md` duplicado |
| `pdfs/` por citekey ou eliminado | 326 PDFs contra 85 pastas — populações distintas; e o diretório é fronteira de workspace para o `Read` do subagente |
| `studies/` na raiz do projeto | rejeitado pelo dono: `docs/` continua sendo o único topo de leitura |
| `analyses/` e `code/` | não existem em nenhum dos 11 projetos nem em nenhuma linha de código |
| colapsar `concepts\|entities\|sources` | o `pj_base` já não os cria; `extended-wiki` é módulo opt-in com gatilho |
| `writing/_out/` | `build/exports` e `reviews/` bastam; um terceiro destino seria destrutivo (§5) |
| `autoexport.remove`/`list` | segue follow-up gated do ADR-0020 |
| convivência de layouts | corte limpo, reafirmado: *"os projetos podem se readequar"* |

## Governança

- **ADR-0022** — bibliografia do projeto sob `docs/`; `papers/` no lugar de `notes/`; o escopo e suas quatro entradas; raiz e escopo como resolvedores distintos.
- **ADR-0023** — findings como `type:` em `notes/`, **substituindo ADR-0014**, com atualização coordenada da prosa das skills.
- **ADR-0024** (Fase 2) — `studies/`, promoção, e o eixo por estudo fora de `docs/`.
- **Emenda à constitution**: [constitution.md:65](../../constitution.md) → `docs/references/papers/`, com Sync impact report.
- **Release**: 0.64.1 → **0.65.0**, MINOR por ser breaking (ADR-0015).

## Testes

TDD: `test_pj_layout.py` (novo) → `core/` → `domains/` → CLI → `test_pj_base_integration.py`. Fixtures de `tests/unit/conftest.py:45-62` separam pj root de escopo.

Um teste por defeito medido: lint devolve a mesma contagem de páginas depois do movimento · `.bib` ausente vira `error` · páginas homônimas em escopos diferentes recebem issues distintas · `stats` mantém `by_type` e ganha `by_scope` · `compose` acha findings por `type:` · export com `figures/` embute a imagem e falha alto quando ela falta · `export` recusa sobrescrever sem `--force` · `git check-ignore` confirma o PDF ignorado em qualquer profundidade · `slugify` de dois escopos não colide · o campo `bibliography` calculado resolve dos dois níveis.

## Critérios de aceitação

1. Inventário **nominal** de literais de layout autorizados fora de `core/pj_layout.py` — lista, não `grep` vazio.
2. `prumo init` produz o projeto com `src/`, `tests/`, `notebooks/`, `content/` e o escopo em `docs/`, sem `studies/`.
3. Um `.md` sob `docs/writing/` com `![](figures/x.png)` exporta com a imagem embutida; a mesma página sem a imagem **falha**, não sai silenciosa.
4. Lint e `stats` sobre projeto migrado devolvem os mesmos números de antes.
5. Em projeto não migrado, todo comando exceto `doctor` falha convidando à adequação; `doctor` funciona.
6. `uv run pytest`, `uv run ruff check .`, `uv run mypy` limpos.
7. *(manual)* Zettlr com workspace em `docs/` mostra bibliografia, notas e manuscritos numa árvore só.
