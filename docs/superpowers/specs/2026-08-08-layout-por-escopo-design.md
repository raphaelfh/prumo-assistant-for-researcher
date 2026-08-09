---
title: Layout por escopo — cinco entradas, repetíveis por estudo
date: 2026-08-08
status: draft
tags: [layout, pj_base, references, scope, studies, writing, zettlr, zotero, breaking, adr]
---

# Layout por escopo — cinco entradas, repetíveis por estudo

## Resumo executivo

O `pj_*` tem dois topos de leitura (`docs/` e `references/`), o manuscrito não tem casa, e um projeto guarda-chuva com vários estudos não tem forma.

Esta spec define **o escopo**: cinco entradas, cada uma justificada por dono e ciclo de vida distintos. Um projeto de um artigo tem **um** escopo, em `docs/`. Um guarda-chuva tem o seu mais um por estudo, em `docs/studies/<slug>/`, com as mesmas cinco entradas. Um mecanismo, dois usos.

```
picot.toml     máquina + humano   muda só com ADR          governa o resto
references/    Zotero → sync      regenerável              a única coisa que não é sua
notes/         humano             livre                    conhecimento
writing/       humano; máquina exporta   por submissão     o produto
decisions/     humano             append-only, imutável    contador determinístico
```

`docs/` é o workspace do Zettlr, então a bibliografia migra para dentro dele: `docs/references/`, com `notes/<citekey>/` renomeado para **`papers/<citekey>/`** — a colisão com `notes/` do escopo desaparece e o nome passa a dizer o que a pasta é.

Um argumento decisivo, achado só na terceira rodada de investigação: os quatro `skills/write-*/template.md` gravam `bibliography: ../references/_references.bib` no frontmatter de todo draft, e **nenhum código escreve esse campo** — esses literais *são* o mecanismo que dá autocomplete `@` ao Zettlr. Com `writing/` e `references/` irmãos dentro de cada escopo, o caminho fica **invariante em qualquer profundidade**. Sem escopo, bibliografia por estudo exigiria um literal por slug.

**Fase 1 (0.65.0, `⚠ Breaking`)**: o escopo, com exatamente um. **Fase 2**: `docs/studies/<slug>/` e `prumo add study`.

## Contexto

### O pedido, e o erro que ele corrigiu

O dono pediu três coisas, duas vezes: `references/` dentro de `docs/`; *"modular e enxuto — tem que ter um racional muito importante por trás de cada diretório para existir"*; e um lugar para sub-projetos de artigo num projeto guarda-chuva.

Uma rodada anterior desta spec cortou `writing/` e `studies/` medindo **custo de migração** nos 11 `pj_*` existentes ("relocaria 10 arquivos em 3 de 11"). O dono rejeitou o raciocínio: a pergunta era qual estrutura é certa, não qual é barata de migrar. **Para projeto novo o custo de migração é zero.** Esta spec julga o desenho pelo projeto novo e trata migração como problema separado — agêntico, não comando.

### Três correções ao diagnóstico inicial

1. Os diretórios "orgânicos" do `pj_piloto_ml` são **módulos documentados com gatilho** ([RPS:74-87](../../Research%20Project%20Structure.md)), não invenção.
2. `entities/` e `sources/` com zero arquivos é módulo `extended-wiki` nunca disparado, não taxonomia rejeitada.
3. ADR-0014 descreve o resolver desse módulo. Esta spec **o substitui** (ver Governança), mas ele não era letra morta.

## O escopo — o racional de cada entrada

O teste: **quem escreve** · **o que acontece quando muda** · **o que quebra se juntar com o vizinho**.

| entrada | quem escreve | quando muda | por que não cabe no vizinho |
|---|---|---|---|
| `picot.toml` | máquina + humano | exige ADR novo | é config que governa o resto; precisa viajar com o escopo num `git mv` |
| `references/` | Zotero → `paper sync` | regenerável, descartável | é a única coisa que **não é sua**; tem regra de gitignore própria (`pdfs/` são symlinks) |
| `notes/` | humano | livre | prosa mutável, sem procedência e sem entrega |
| `writing/` | humano; máquina exporta | versionado **por submissão** | ciclo de entrega ≠ ciclo de conhecimento; recebe docx de coautor |
| `decisions/` | humano | **append-only, imutável** | `adr.py` numera varrendo o diretório — único subdiretório com semântica de máquina |

`_index.md`, `_log.md` e `project_guide.md` são **arquivos**, não diretórios.

**`findings/` não existe.** Finding é output de máquina com procedência ([findings.py:26](../../../src/prumo_assist/domains/wiki/findings.py)), e vive como `type: finding` numa nota de `notes/`. Não é escrita — por isso não pertence a `writing/`; não merece pasta — por isso não é `findings/`.

## Layout

**Projeto de um artigo** — nasce assim, nunca vê `studies/`:

```
pj_<nome>/
├── .claude/  content/  analyses/  code/
├── build/exports/   reviews/<slug>/        saídas de máquina, gitignored
└── docs/                                   ←── WORKSPACE DO ZETTLR = O ESCOPO
    ├── _index.md  _log.md  project_guide.md
    ├── picot.toml
    ├── references/
    │   ├── .gitignore          padrões NÃO ancorados — viaja com a pasta
    │   ├── _references.bib  _index.md
    │   ├── papers/<citekey>/   ex-notes/ — layout α (ADR-0008) preservado
    │   ├── pdfs/  templates/
    ├── notes/          suas páginas, inclusive findings (type: finding)
    ├── writing/        protocol.md, paper.md, cep.md, sap.md
    └── decisions/
```

**Guarda-chuva com N estudos** — o de cima ganha `studies/`:

```
docs/
├── _index.md  project_guide.md  picot.toml       pergunta ampla
├── references/  notes/  writing/  decisions/     transversais
└── studies/
    ├── mortalidade-uti/    picot.toml  references/  notes/  writing/  decisions/
    └── sepse-ml/           idem
```

Arrancar um estudo para repo próprio é `git mv` da pasta — é por isso que `picot.toml` e o `.gitignore` da bibliografia moram dentro dela.

## Raiz e escopo são dois conceitos

Hoje um resolvedor só responde às duas perguntas, e com aninhamento isso corrompe.

```python
find_pj_root(start)     # sentinela .claude/pj_config.toml — 1 por projeto
find_scope_root(start)  # sentinela picot.toml — para no MAIS PRÓXIMO
```

- **`slugify` fica ancorada no pj root**, nunca no escopo. Senão `docs/writing/paper.md` e `docs/studies/x/writing/paper.md` geram o mesmo slug, os dois escrevem em `reviews/writing__paper/`, e um `write review ingest` do estudo carrega o `citemap.json` do guarda-chuva — o pareamento citação↔ocorrência casa contra o documento errado, em silêncio.
- **`reviews/` e `build/exports/` resolvem contra o pj root**; bib, protocolo, `decisions/` e `notes/` contra o escopo.
- **`pages:` do `compose`** resolve contra o diretório do índice quando ele está sob `writing/`, e contra o pj root caso contrário. Sem isso, um índice dentro de um estudo aponta para fora dele.
- `find_scope_root` levanta `ScopeNotFoundError` em pt-BR com o comando embutido — não devolve `None` (`mypy --strict`).

**`picot.toml` sai de `.claude/`.** [picot_io.py:22](../../../src/prumo_assist/domains/protocol/picot_io.py) devolve `pj_path/".claude"/"picot.toml"` — fora do workspace e não acompanha um `git mv`. Propaga em `ops.py:67,108`, `adr.py:30,45` e na skill `formulate-picot`.

## O que muda no código

### 1 · `core/pj_layout.py`

```python
REFERENCES_RELPATH = Path("references")   # relativo ao ESCOPO
def bib_path(scope) / papers_dir(scope) / pdfs_dir(scope)
def notes_dir(scope) / writing_dir(scope) / decisions_dir(scope)
def find_pj_root(start) / find_scope_root(start) / iter_scopes(pj_root)
```

`core/note_paths.py` constrói sobre `papers_dir()`. ADR-0008 segue válido: o layout α dentro da pasta do citekey não muda.

### 2 · O lint vira por escopo

Cinco defeitos, todos silenciosos, todos medidos:

| onde | defeito | consequência |
|---|---|---|
| [lint.py:69](../../../src/prumo_assist/domains/wiki/lint.py) | `docs.rglob` engole a bibliografia | 23 → 246 páginas no `phd`; `orphan_page` 7 → 227 |
| [lint.py:70](../../../src/prumo_assist/domains/wiki/lint.py) | identidade de página por `stem` | 22 `evaluation.md` distintos já colidem hoje; órfã de um estudo conta como linkada por homônima de outro |
| [lint.py:64,87](../../../src/prumo_assist/domains/wiki/lint.py) | `.bib` ausente ou vazio desliga a checagem de citekey | `broken_citekey` 54 → 0; **5 dos 11 projetos já estão nesse estado** |
| [lint.py:177](../../../src/prumo_assist/domains/wiki/lint.py) | `multiple_primary` global | N estudos com 1 primary cada viram falso positivo estrutural |
| [lint.py:32,80](../../../src/prumo_assist/domains/wiki/lint.py) | tipagem por `parts[0]` contra `EXPECTED_DIRS` | com `studies/`, `no_frontmatter` nunca dispara |

Conserto: `lint(scope)` chamado uma vez por escopo, mais `lint_all` que itera e etiqueta. Identidade por caminho relativo ao escopo; wikilink resolve por índice `stem → [paths]` dentro do escopo, com `ambiguous_link` novo quando houver mais de um alvo. `.bib` ausente num escopo que contém `[@key]` vira `WikiIssue("error", "bib_missing", ...)`. `WikiIssue` ganha campo opcional `scope` (default `None`, forward-only). **Nunca unir os `.bib` entre escopos** — a união destrói o autocontido e a citação cruzada só quebraria depois do `git mv`, longe da causa.

[stats.py](../../../src/prumo_assist/domains/wiki/stats.py) ganha `by_scope` e mantém `by_type` — chave nova, nunca removida.

### 3 · Findings, nos dois lados

[findings.py:16](../../../src/prumo_assist/domains/wiki/findings.py) **recria** o diretório que o desenho elimina (`mkdir` nos dois ramos) e indexa no `_index.md` do guarda-chuva. E [compose.py:178](../../../src/prumo_assist/domains/write/compose.py) só procura diretório: com findings virando `type:`, `ComposeInputs.findings == []` e `prumo write prep` entrega contexto **sem nenhum finding**, com exit 0.

Os dois mudam juntos: escrever em `<scope>/notes/<slug>.md` (o frontmatter já emite `type: finding`), varrer `<scope>/notes/**/*.md` filtrando por `type:` no `compose`, e mirar o `_index.md`/`_log.md` do escopo.

### 4 · Export nunca escreve irmão da fonte

[export.py:793](../../../src/prumo_assist/domains/write/export.py) não tem guarda de sobrescrita — diferente de [compose.py:322](../../../src/prumo_assist/domains/write/compose.py), que levanta `FileExistsError` sem `--force`. Hoje é inofensivo porque a saída cai em `build/exports`, que é scratch gitignored.

Se a saída virasse irmã da página sob `writing/`, `prumo write export` seria a **única escrita destrutiva sem guarda** do domínio, mirando o artefato mais valioso do fluxo. No `pj_piloto_imagem`, `docs/study_protocol_oficial.docx` **é** o docx devolvido pelo coautor (36 de 38 campos `ADDIN ZOTERO_ITEM`, `comments.xml` de 6 KB), está untracked, e ocupa exatamente o stem que o export usaria.

Decisão: **a saída permanece em `build/exports/`**, e `export()` ganha a mesma guarda de `compose()` de qualquer forma.

### 5 · `references/.gitignore` próprio

Padrões ancorados param de casar a cada nível novo — verificado com `git check-ignore` nas quatro formas que existem no parque. Um `references/.gitignore` com padrões **não ancorados** (`pdfs/*.pdf`, `!pdfs/.gitkeep`) viaja com a pasta e torna a promoção git-neutra. As duas linhas saem do `.gitignore` da raiz.

### 6 · Fonte do template

`templates/pj_base/`: a árvore do escopo; `.gitignore` (mais `~$*`, `**/_out/`, `.prumo/`, e `uv.lock` **fora** do ignore); `docs/_index.md`; `.claude/rules/documentation.md`, auto-carregado toda sessão. E os **quatro `skills/write-*/template.md`**, cujo `bibliography: ../../references/...` vira `../references/...` — não são `SKILL.md` e escaparam de todos os inventários anteriores.

## Bibliografia por escopo — o passo no Zotero

[connect.py:296](../../../src/prumo_assist/domains/paper/connect.py) fixa o `.bib` na raiz do projeto e [connect.py:287](../../../src/prumo_assist/domains/paper/connect.py) recusa com `AlreadyConnectedError` quando o bib tem entradas reais. No dia do segundo escopo, a única porta de entrada de bibliografia se fecharia — não por política, por guarda. E ADR-0020 põe `autoexport.remove`/`list` fora de escopo.

**Decisão do dono: N coleções no Zotero, feitas à mão.** `prumo paper connect --scope <slug>` ganha o argumento e para de recusar quando o alvo é escopo novo com bib placeholder. Cada estudo recebe sua subcoleção e seu autoexport, configurados pelo pesquisador. Zero RPC novo.

Consequência que a spec assume: **`prumo add study` não move o `.bib`.** Ele cria o escopo com bib placeholder e imprime o passo do Zotero. Mover invalidaria o autoexport, que guarda caminho absoluto — o mesmo defeito que já obriga o passo manual na Fase 1.

## Promoção — `prumo add study <slug>` (Fase 2)

Quando o segundo artigo aparece, o primeiro também desce para `studies/`, senão os níveis ficam assimétricos.

- **Recusa** worktree suja ou sem git, salvo `--force` explícito. Medido: 2 dos 11 projetos não têm git funcional e 5 estão sujos agora — `git checkout .` como desfazer destruiria trabalho.
- Grava `docs/studies/_promotion.json` (origem→destino + sha256 por arquivo) **antes** de qualquer `mv`.
- Idempotente: `docs/studies/` existente significa já promovido; nunca reencosta no guarda-chuva.
- O guarda-chuva **mantém** `project_guide.md`, `decisions/` transversais e `references/` de background. O que desce é o que é do estudo.
- Relatório com os links que mudam de profundidade e o passo do Zotero.

## Adequação de projeto existente — agêntica

Projeto fora do layout não é caso de comando. O CLI detecta e falha com mensagem clara; um agente conduz a conversa, mostra o que encontrou e executa com o pesquisador.

Codificar isso seria mais máquina que problema: quatro formas de `.gitignore`, dois projetos sem git, duas classes de link com regras **opostas** (46 wikilinks mudam de prefixo, 16 links relativos mudam de profundidade), 32 scripts próprios em `.claude/scripts/`, uma skill geradora que emite caminhos antigos a cada avaliação, e um passo dentro do Zotero. O briefing completo dessa conversa está registrado no [ADR-0022](../../adr/) e no relatório da investigação.

## O contrato do pesquisador

1. **`notes/` é seu, `writing/` é o produto, `references/` vem do Zotero.** Três palavras, e a dúvida "isso é nota ou é escrita?" se resolve por "isso vai virar entrega?".
2. **Não mova nem renomeie pasta de citekey.** O YAML de metadata e os blocos delimitados são da máquina; **o corpo da nota é seu** — as 7 seções humanas de [documentation.md:70-82](../../../templates/pj_base/.claude/rules/documentation.md) são preservadas por [sync.py:112](../../../src/prumo_assist/domains/paper/sync.py), que faz merge.

Errar de escopo não quebra nada: o lint acusa e o arquivo continua legível. Quebra só quem move pasta de citekey ou edita dentro de bloco delimitado.

## Fora de escopo, com o número que justifica

| descartado | por quê |
|---|---|
| colapsar `concepts\|entities\|sources` | o `pj_base` já não os cria; `extended-wiki` é módulo opt-in com gatilho |
| `writing/_out/` como terceiro destino | `build/exports` e `reviews/` já existem e bastam; um terceiro seria destrutivo (§4) |
| unir os `.bib` entre escopos no lint | destrói o autocontido; a quebra apareceria só depois do `git mv` |
| `autoexport.remove`/`list` | decisão do dono: N coleções à mão. Segue como follow-up gated do ADR-0020 |
| convivência de layouts | corte limpo, reafirmado pelo dono: *"os projetos podem se readequar"* |

## Governança

- **ADR-0022** — o escopo e suas cinco entradas; `references/` sob `docs/`; `papers/` no lugar de `notes/`; raiz e escopo como resolvedores distintos.
- **ADR-0023** — findings como `type:` em `notes/`, **substituindo ADR-0014**. Exige atualização coordenada da prosa de todas as skills que citam findings, como o próprio 0014 previa.
- **ADR-0024** (Fase 2) — `studies/`, promoção e uma coleção do Zotero por escopo.
- **Emenda à constitution**: [constitution.md:65](../../constitution.md) cita `references/notes/` → `docs/references/papers/`, com Sync impact report.
- **Release**: 0.64.1 → **0.65.0**, MINOR por ser breaking (ADR-0015).

## Testes

TDD: `test_pj_layout.py` (novo) → `core/` → `domains/` → CLI → `test_pj_base_integration.py`. Fixtures de `tests/unit/conftest.py:45-62` montam a raiz sobre o escopo.

Um teste por defeito medido: lint devolve a mesma contagem de páginas depois do movimento · `.bib` ausente vira `error` e não silêncio · duas páginas homônimas em escopos diferentes recebem issues distintas · `multiple_primary` conta por escopo · `stats` mantém `by_type` e ganha `by_scope` · `compose` acha findings por `type:` · `export` recusa sobrescrever sem `--force` · `git check-ignore` confirma o PDF ignorado em qualquer profundidade · `slugify` de dois escopos não colide · comando em projeto legado falha em pt-BR convidando à adequação.

## Critérios de aceitação

1. Inventário **nominal** de literais de layout autorizados fora de `core/pj_layout.py` — lista, não `grep` vazio.
2. `prumo init` produz o escopo completo e nenhum `studies/`.
3. Um `.md` sob `docs/writing/` exporta com o `bibliography` do frontmatter resolvendo, sem edição manual.
4. Lint e `stats` sobre projeto migrado devolvem os mesmos números de antes.
5. Em projeto não migrado, todo comando exceto `doctor` falha convidando à adequação; `doctor` funciona.
6. `uv run pytest`, `uv run ruff check .`, `uv run mypy` limpos.
7. *(manual)* Zettlr com workspace em `docs/` mostra bibliografia, notas e manuscritos numa árvore só.
