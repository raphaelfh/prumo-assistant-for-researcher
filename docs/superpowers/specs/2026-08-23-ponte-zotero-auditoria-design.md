---
title: Auditoria da ponte Zotero — symlinks, resolução de PDF e superfície MCP
date: 2026-08-23
status: approved
tags: [zotero, pdfs, symlink, mcp, better-bibtex, auditoria, sota]
---

# Auditoria da ponte Zotero

## Resumo executivo

Auditoria de estado da arte das três camadas que ligam o `pj_*` ao Zotero — bib (autoexport BBT),
anotações (API local) e PDF (symlink) — com refutação adversarial de cinco frentes. **Veredito:
as camadas de bib e de anotações estão em estado da arte; a de PDF tem dois bugs de parser reais
e nenhuma cobertura de teste.** Quatro propostas de mudança estrutural foram levantadas e
**três foram refutadas** (resolução de path pela API local, cascata symlink→hardlink→cópia,
`/fulltext` como fallback de extração); uma foi aprovada com correções e postergada por falta de
tráfego (deep links `zotero://`).

As decisões tomadas: (D1) `sync-pdfs` continua offline, lendo o `.bib`, com os dois bugs
corrigidos e caracterizados por teste; (D2) deep links `zotero://` postergados com trigger;
(D3) o servidor MCP próprio estende para o núcleo do domínio `paper` e é renomeado
`prumo-review` → `prumo`; (D4) a recomendação de MCP de terceiro no onboarding troca de alvo
por motivo de confidencialidade.

## Contexto e problema

A pergunta de origem foi se o symlink `docs/references/pdfs/<citekey>.pdf` → `~/Zotero/storage/…`
e a conexão com o Zotero são estado da arte, ou se há caminho melhor ou complementar — e se um
MCP de Zotero se encaixa.

A ponte tem três camadas independentes, e elas não estão no mesmo estado de maturidade:

| Camada | Mecanismo | Arquivo |
|---|---|---|
| bib ← coleção | JSON-RPC do BBT (`autoexport.add`), com guarda anti-coleção-fantasma | `domains/paper/connect.py` |
| anotações ← biblioteca | API local (`:23119/api`), varredura única indexada por `parentItem` | `domains/paper/zotero.py` |
| PDF ← anexo | parse do campo `file = {…}` do `.bib` + `symlink_to` | `domains/paper/pdfs.py` |

## Método

Levantamento inicial (fontes primárias: doc do Zotero, doc do BBT, repositórios dos MCPs),
seguido de cinco revisores adversariais em paralelo, cada um instruído a **refutar por padrão**
e a apresentar evidência de fonte primária (arquivo:linha ou URL), um por proposta.

Duas classes de evidência aparecem abaixo e são distinguidas explicitamente:

- **[verificado]** — reproduzido nesta sessão, na árvore local ou na fonte baixada.
- **[medido pelo revisor]** — apurado por um dos revisores contra a biblioteca real ou a fonte
  upstream, não re-executado aqui.

## Achados

### A1 · O parser do campo `file` tem dois bugs reais **[verificado]**

`_extract_pdf_path_from_bib_body` ([`pdfs.py:22`](../../../src/prumo_assist/domains/paper/pdfs.py))
desescapa apenas `\:`. O Better BibTeX escapa **três** caracteres no campo `file` (`\\`, `\;`, `\:`).
Consequências reproduzidas:

| entrada | resultado |
|---|---|
| `Smith; Jones - 2024.pdf` (BBT emite `\;`) | `None` |
| `files/12/artigo.pdf` (pref "export file paths: relative") | `None` |

Ambos falham **fail-safe**: o paper cai em `missing` e a contagem do relatório diminui. Nunca
produzem symlink apontando para o arquivo errado. O segundo bug apaga *todos* os PDFs de quem
ligar paths relativos no BBT.

### A2 · `pdfs.py` não tem teste **[medido pelo revisor]**

17% de cobertura; o corpo inteiro de `sync_pdfs` (linhas 33–67) descoberto. Não existe
`tests/unit/paper/test_pdfs.py`. É o módulo menos testado do domínio `paper`, e o único cuja
lógica é heurística.

### A3 · `missing` colapsa dois estados distintos **[verificado]**

`pdfs.py:26` exige `endswith(".pdf") and os.path.exists(p)`. Os dois lados do `and` falham por
motivos diferentes e com remédios diferentes — "não há anexo PDF no Zotero" versus "o anexo
existe mas o arquivo não está em disco" (biblioteca em nuvem, `Download files: as needed`) —
e hoje viram a mesma linha: *"N sem PDF no Zotero"* ([`cli.py:175`](../../../src/prumo_assist/domains/paper/cli.py)).
A distinção é derivável offline, do próprio `.bib`, porque o BBT emite o path mesmo para arquivo
não baixado.

### A4 · `doctor` e `zotero_local_api_up` dão falso-positivo **[verificado]**

O `doctor` decide "API local respondendo" com `_port_open(host, port)`
([`deps.py:137`](../../../src/prumo_assist/core/deps.py)) — um TCP connect na 23119, que é a porta
do *connector server* e sobe sempre que o Zotero abre, com a API local ligada ou não.
`zotero_local_api_up` ([`deps.py:90`](../../../src/prumo_assist/core/deps.py)) sonda
`/connector/ping`, que responde pelo mesmo motivo. A API local é **opt-in** (Settings → Advanced);
com ela desligada, ambos afirmam que está de pé e os comandos de anotação tomam 403 em série.

Nota correlata: `_SUPPORTED_ZOTERO_MAJOR = 9` é **piso** (`major >= 9`), não igualdade — atualizar
para o Zotero 10 não reprova no `doctor`. **[verificado]**

### A5 · A API local devolve o caminho do PDF, e nós o descartamos **[verificado]**

Em `chrome/content/zotero/xpcom/data/item.js` (tag 9.0.6, a versão instalada nesta máquina):

```js
5902  if (this.isImportedAttachment()) {
5903      json.links.enclosure = {
5904          href: this.getLocalFileURL(),        // caminho absoluto
5905          type: this.attachmentContentType,    // qual anexo é o PDF
5906          title: this.attachmentFilename
5907      };
5908  }
…
5944  json.links.enclosure.length = await getFileSize(this);
```

`getFileSize` (`item.js:5915-5929`) engole `NotFoundError` e devolve `undefined` — logo
**`length` ausente ⟺ arquivo não está em disco**. Ou seja, a mesma resposta `/children` que o
`sync-annotations` já busca carrega, por anexo, as quatro informações que as propostas tentavam
obter por caminhos separados. `_fetch_item_data`
([`zotero.py:246`](../../../src/prumo_assist/domains/paper/zotero.py)) fica só com `entry["data"]`
e descarta `entry["links"]`.

Isto **não** foi adotado — ver D1 e "Fora do escopo".

### A6 · O pipeline de anotações nunca rodou em projeto real **[verificado]**

Varredura dos 14 `pj_*` do disco:

| artefato | quantidade |
|---|---|
| symlinks de PDF | 340, em 6 projetos |
| `_meta.md` | 61, em 1 projeto |
| `_extract.md` | 18 |
| `_annotations.md` | **0** |
| `note__*.md` | **0** |

Confirmado com o dono: anota no Zotero **muito raramente**. O caminho existe e é correto, mas é
de baixo tráfego — o que reordena a prioridade de qualquer trabalho sobre ele.

### A7 · A superfície "sem terminal" executa comandos **[verificado]**

[`docs/onboarding-pesquisador.md`](../../onboarding-pesquisador.md) se intitula "sem terminal",
mas a trilha que ele descreve roda `curl | sh`, `uv tool install`, `prumo doctor` e `prumo init`
dentro do Cowork. "Sem terminal" significa que o pesquisador não digita, não que não haja
execução. A única superfície sem execução é "chat simples sem pasta conectada" — onde o servidor
MCP também não sobe, porque é `command: "prumo"` e o CLI não está instalado.

**14 das 16 skills** declaram `Bash(...)` em `allowed-tools`. Isso conta a favor do status quo:
elas funcionam exatamente onde o MCP funcionaria.

### A8 · Paisagem MCP para Zotero **[medido pelo revisor]**

Sete projetos ativos, nenhum oficial; os devs do Zotero declaram preferir não embutir IA no core.
Quatro dos sete **devolvem o caminho em disco** do anexo — o mais adotado
([54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp), MIT, ~4,8k ★, 72 contribuidores) tem
tool dedicada `zotero_get_attachment_path` e usa embedder local (all-MiniLM) por default.

Dois deles (54yyyu, ZotPilot) obtêm o path lendo `zotero.sqlite` com `immutable=1`, que **desativa
locking e ignora o rollback journal** — com o Zotero aberto isso devolve páginas rasgadas sem
erro. O Zotero declara o schema interno instável e aponta a API local como substituto. Como
referência de arquitetura para o prumo: descartada.

O custo que importa para o `.mcp.json`: 54yyyu expõe **52 tools, ~23k tokens de definição por
request**, cobrados de toda sessão de todo consumidor do plugin.

## Decisões

### D1 · `sync-pdfs` continua offline, lendo o `.bib`

**Decisão.** Manter o `.bib` como fonte do caminho do PDF. Corrigir A1 (desescapar os três
caracteres do BBT; resolver path relativo contra o data dir do Zotero, não contra o CWD),
implementar a distinção de A3, e escrever `tests/unit/paper/test_pdfs.py` **antes** de qualquer
alteração, caracterizando o comportamento atual e os dois bugs (TDD, `.claude/rules/code.md`).

**Por quê.** `sync-pdfs` é hoje o único comando de `paper` que funciona com o Zotero fechado, e
isso é deliberado: `deps.py:171` lista o Zotero como `required_by` apenas de `sync-annotations`,
`sync-notes` e `write export --to docx`, e a mensagem do `doctor` afirma que *"o resto do prumo
funciona sem ele"*. Trocar o transporte quebraria um invariante documentado, em troca de precisão
que depende de dois gates opt-in — um deles indetectável pelo guard atual (A4).

**Rejeitado: resolver o path pela API local.** Além da regressão de disponibilidade, a resolução
ingênua remove os dois filtros implícitos que o parser aplica (`.pdf` e `os.path.exists`).
Medido na biblioteca real do dono [medido pelo revisor]: a ordem de `getAttachments()` é colação
alfabética por título dependente de locale, e `'Catalog Page'` / `'Full Text'` (HTML) ordenam
antes de `'Full Text PDF'` — **o primeiro anexo está errado em 12,2% dos itens** (64 de 526);
**26,5% dos anexos são `linked_url`**; **49,9% vivem em group libraries**, invisíveis ao
`item.attachments` do BBT sem passar `library`; e **7,8% dos PDFs estão registrados e ausentes
do disco**, para os quais o endpoint `/file` devolve 302 para caminho inexistente. O desenho
atual falha *fail-safe*; o proposto falharia *fail-wrong*.

**Correção de rota registrada.** A justificativa original desta proposta dizia que o `urllib`
recusa o redirect em `HTTPRedirectHandler.redirect_request`. Está errado: a checagem de esquema
mora em `http_error_302` [verificado]. E há endpoint melhor que o 302 —
`/items/<key>/file/view/url`, `200 text/plain` [medido pelo revisor].

### D2 · Deep links `zotero://` — postergado com trigger

**Decisão.** Não implementar agora. Registrar em "Decisões deliberadas postergadas" do
[`ROADMAP.md`](../../../ROADMAP.md) com o trigger: **quando existir um `_annotations.md` real em
algum `pj_*`**.

**Por quê.** A proposta sobreviveu a todos os ataques técnicos [medido pelo revisor]: o Zettlr
abre URI custom desde a 3.1.0 (commit `1539f754`, *"fix: Allow opening of custom protocols"*, com
teste de regressão em `test/make-valid-uri.spec.ts`); a `key` da anotação é estável sob edição e
reposicionamento; e os dados já estão em mãos, porque `fetch_annotations_index` indexa por
`parentItem` mas preserva o dict inteiro. O que a derruba é A6: zero tráfego. O custo, em
contrapartida, é permanente — ~25 tokens por anotação em todo `_annotations.md`, mais ruído
lexical no índice BM25 do qmd.

**Correções obrigatórias quando o trigger disparar**, para não repetir o desenho errado:

1. O esquema `zotero://` **não tem rota `users/<id>`** — o router registra apenas
   `library/items/:key` e `groups/:groupID/items/:key`. `ZoteroRef.library_path`
   ([`zotero.py:117`](../../../src/prumo_assist/domains/paper/zotero.py)) vale `users/13049353`;
   emitir isso produz falha silenciosa. É preciso mapear `users/<id>` → a string literal `library`.
2. **Não emitir `page=`.** O Zotero interpreta como página física 1-based; o que temos é
   `annotationPageLabel`, que é `1049` num artigo de journal e `iv` num prefácio. Passando só
   `annotation=`, o Zotero deriva a página da própria anotação.

### D3 · Estender o servidor MCP próprio e renomeá-lo

**Decisão.** Expor o núcleo do domínio `paper` como fachadas finas sobre `domains/paper/api.py`
— `sync`, `find`, `lint`, `graph`, `verify-refs`, `sync-all`, `connect` — e renomear o servidor
`prumo-review` → `prumo` no mesmo release. MINOR com "⚠ Breaking" ([ADR-0011](../../adr/adr-0011-semver-por-visibilidade.md)),
ADR novo emendando a [ADR-0017](../../adr/adr-0017-prumo-mcp-reconciliador.md). **Pré-requisito
bloqueante:** quitar antes a dívida de schema que a ADR-0017 declara e adiou (envelope
`schema_version` nos retornos), sob pena de multiplicá-la por sete.

Dos 14 subcomandos de `paper`, ficam fora `migrate-layout` (one-off), `extract-prep` (preflight
interno de skill) e `extract`.

**Por quê.** O argumento originalmente usado contra — "MCP produz contexto que evapora,
Markdown é o produto" — não se aplica a fachadas de leitura sobre operações determinísticas, e a
própria ADR-0017 já operou esse desenho com aprovação formal. O custo de contexto foi medido e é
uma ordem de grandeza menor do que eu havia argumentado: uma tool read-only tem **~8 linhas**, o
`mcp_server.py` inteiro tem **140 linhas para 4 tools**, e sete tools novas custam **~600–800
tokens** por sessão [verificado] — contra os ~23k do 54yyyu (A8). O ganho que decide: **tool MCP
é descobrível sem carregar skill**, enquanto comando Bash só existe para o agente se a prosa de
alguma skill o mencionar.

**O rename agora, e não depois.** O repo tem 0 stars, 0 forks e 0 issues [medido pelo revisor];
o breaking em `.mcp.json` custa zero hoje e custa migração de todos os consumidores depois.

**O que explicitamente *não* justifica esta decisão.** O ganho "funciona onde não há Bash" é em
boa parte ilusório (A7): o servidor exige o mesmo `prumo` instalado que o Bash exige. Quem
reabrir esta decisão não deve reciclar esse argumento.

**Guarda para `connect`.** É a única operação do domínio que muta o Zotero do usuário, e a
[ADR-0020](../../adr/adr-0020-connect-autoexport-bbt.md) a trata como fronteira ("a primeira e
única chamada MUTANTE"). Como tool, mantém a validação prévia de `find_collection` antes de
qualquer chamada a `autoexport.add`, e a mensagem de erro continua afirmando "NADA foi criado".

### D4 · Trocar a recomendação de MCP no onboarding

**Decisão.** Substituir a indicação de `cookjohn/zotero-mcp` em
[`docs/onboarding-pesquisador.md:161-165`](../../onboarding-pesquisador.md) por
`54yyyu/zotero-mcp` em modo local, com embedder default local. Grounding ao vivo antes de
publicar a troca. Em qualquer caso, **no config global do usuário — nunca no `.mcp.json` do
plugin**, pelo custo de A8.

**Por quê.** Dos sete MCPs levantados, o cookjohn é o único cujo caminho de busca semântica manda
texto fatiado dos PDFs para `api.openai.com` **por default** [medido pelo revisor]. O
[`ROADMAP.md`](../../../ROADMAP.md) marca "Safe outputs — não há fronteira de confidencialidade"
como trigger **atingido**, com a justificativa "o público-alvo trabalha com dado de paciente". A
recomendação publicada aponta hoje para o pior perfil de privacidade dos sete.

**Nunca recomendar** os hospedados que exigem chave de web API do Zotero: o escopo de chave do
Zotero não desce abaixo da biblioteca, e `files` é concedido implicitamente junto com `library` —
uma chave "read-only" baixa todos os PDFs, com validade indefinida, sob custódia de terceiro
[medido pelo revisor]. Colide também com a Restrição de Tecnologia da
[`constitution`](../../constitution.md) ("sem dependência de SaaS para operação core").

## Propostas refutadas (registradas para não voltarem)

### R1 · Cascata symlink → hardlink → cópia

**Refutada.** Hardlink e cópia são funcionalmente idênticos em todos os cenários de mutação do
Zotero, e ambos desligam simultaneamente as três detecções existentes: o check `broken_pdf_link`
testa `is_symlink()` ([`lint.py:116`](../../../src/prumo_assist/domains/paper/lint.py)); o
`.exists()` de `extract_prep` devolve `True` para arquivo obsoleto; e `os.readlink` num hardlink
levanta `EINVAL`, jogando o item em `blocked` ("arquivo real, não tocamos") — onde nunca mais é
atualizado. O resultado é conteúdo desatualizado servido em silêncio, num produto que gastou a
[ADR-0018](../../adr/adr-0018-verificacao-referencias-apis-publicas.md) inteira instituindo "zero
erro silencioso de citação".

O gatilho é contínuo, não hipotético: `zotero/zotero#1685` foi fechado e shipado no Zotero 8 —
renomear o arquivo quando a metadata do pai muda é default — e o repo exige Zotero ≥ 9
[medido pelo revisor].

Somam-se: 0 usuários externos; `onboarding-pesquisador.md:82` já manda usar WSL no Windows, onde
`os.symlink` funciona sem privilégio; e a cópia introduziria um vetor novo, porque o OneDrive não
sincroniza symlink mas sincroniza cópia.

**A propriedade desejada do symlink é quebrar alto.** Isso nunca virou ADR e deveria — para que
a próxima proposta de fallback tenha de emendar uma decisão em vez de preencher um vazio.

### R2 · `/items/<key>/fulltext` como fallback do `paper-extract`

**Refutada por groundedness.** O endpoint existe na API local e aceita GET [medido pelo revisor],
mas devolve string plana sem fronteira de página. Isso quebra três contratos explícitos de
[`skills/paper-extract/SKILL.md`](../../../skills/paper-extract/SKILL.md): "cite página quando
souber" (o subagent omitiria ou inventaria), "abortar se >50% da página parece OCR corrompido"
(o guard é por página) e o skip explícito de paper sem PDF. E o `_extract.md` resultante sairia
**indistinguível** de um extraído do PDF — mesmo formato, mesmo `extracted_at`, mesmo hash de
template. É exatamente o "confirmação ativa, não silêncio" do achado de groundedness do ROADMAP,
e contradiz a [ADR-0013](../../adr/adr-0013-pdf-via-read-nativo.md).

### R3 · Ignorar `docs/references/pdfs/` no `.gitignore` do `pj_base`

**Refutada na premissa.** O diretório **já é ignorado**, por um `.gitignore` aninhado que a
proposta original não localizou: `templates/pj_base/docs/references/.gitignore` contém
`pdfs/*.pdf` + `!pdfs/.gitkeep` [verificado], com teste de regressão em
`tests/unit/test_pj_base_integration.py`. Nos `pj_*` que são repos git, `git ls-files` sobre o
diretório devolve apenas `.gitkeep` [medido pelo revisor] — não há symlink no histórico e não há
vazamento.

Pior, a "correção" proposta era regressão: `docs/references/pdfs/` é padrão de **diretório**, e o
git não permite reincluir arquivo cujo diretório-pai foi excluído — mataria o `!pdfs/.gitkeep` e o
diretório sumiria do clone. Esse dano já é observável em
`pj_piloto_genetica/.gitignore:37` [medido pelo revisor].

**O que sobra e é real:** a regra é presa à extensão, então um `.epub`, `.djvu` ou `.docx` sob
copyright arrastado para `pdfs/` **não** é ignorado. Cura: `*` + `!.gitkeep` no `.gitignore`
aninhado. Não decidido nesta spec.

## Fora do escopo (deliberado)

- **`links.enclosure` como fonte de path (A5).** Preserva-se o desenho offline de D1. Reavaliar
  se e quando `sync-all` precisar de `contentType` para escolher entre múltiplos anexos PDF, ou
  se a distinção de A3 pela via do `.bib` se mostrar insuficiente.
- **`prumo paper add <doi>` sobre a write API do Zotero 10.** O Zotero 10 trouxe escrita na API
  local com chave local e diálogo de consentimento, sem chave de web API [medido pelo revisor];
  a metade Crossref já existe no repo (`domains/paper/verify.py`). **Trigger:** `doctor` reportar
  major ≥ 10 na máquina do dono, `_SUPPORTED_ZOTERO_MAJOR` bumpado com o par BBT confirmado, e um
  grounding ao vivo do handshake `/api/local/authorize` no mesmo formato do grounding da ADR-0020.
  Seria a **segunda** chamada mutante ao acervo real e a primeira que cria itens — pede ADR
  próprio ou emenda à ADR-0020.
- **Ler `zotero.sqlite` diretamente.** Descartado em definitivo: schema declarado instável pelo
  Zotero, e `immutable=1` devolve dado errado em silêncio (A8).
- **MCP de terceiro no `.mcp.json` do plugin.** Descartado pelo custo de contexto (A8).

## Plano de implementação (alto nível)

| # | Trabalho | Tamanho | Release |
|---|---|---|---|
| 1 | `tests/unit/paper/test_pdfs.py` caracterizando o comportamento atual e os dois bugs de A1 | — | PATCH |
| 2 | Corrigir A1: desescapar `\\`, `\;`, `\:`; resolver path relativo contra o data dir do Zotero | ~10 SLOC | PATCH |
| 3 | A3: separar `missing` em `no_attachment` e `not_downloaded`, com mensagem acionável no segundo | ~5 SLOC | PATCH |
| 4 | A4: sondar endpoint `/api/…` real em `zotero_local_api_up` e no `doctor`, em vez de `_port_open` / `/connector/ping` | ~10 SLOC | PATCH |
| 5 | Quitar a dívida de schema da ADR-0017 (envelope `schema_version`) | — | MINOR |
| 6 | D3: sete tools de `paper` + rename `prumo-review` → `prumo` + ADR emendando 0017 | ~15 SLOC/tool | MINOR ⚠ Breaking |
| 7 | D4: grounding do 54yyyu em modo local e troca no onboarding | doc | não bumpa |
| 8 | ADR registrando "symlink porque quebra alto" (R1) | doc | não bumpa |

Itens 1–4 são independentes entre si e de 5–8. O item 5 é bloqueante do 6.

## Quando re-avaliar

- **D1** — se o BBT deixar de emitir `file = {…}` por default, ou se a taxa de `missing` após a
  correção de A1 continuar alta em biblioteca real.
- **D2** — quando existir um `_annotations.md` real em algum `pj_*`.
- **D3** — se o custo de definição das tools passar de ~2k tokens por sessão, ou se a dívida de
  schema voltar a crescer sem quitação.
- **D4** — a cada release maior do MCP recomendado, e imediatamente se ele mudar o embedder
  default para endpoint hospedado.

## Referências

- [Zotero Local API](https://www.zotero.org/support/dev/web_api/v3/local_api)
- [Better BibTeX — JSON-RPC](http://retorque.re/zotero-better-bibtex/exporting/json-rpc/)
- [Zotero — attachment title vs filename](https://www.zotero.org/support/kb/attachment_title_vs_filename)
- [Zotero — acesso direto ao SQLite](https://www.zotero.org/support/dev/client_coding/direct_sqlite_database_access)
- [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp)
- ADRs correlatas: [0007](../../adr/adr-0007-zotero-stdlib-urllib.md) ·
  [0013](../../adr/adr-0013-pdf-via-read-nativo.md) ·
  [0017](../../adr/adr-0017-prumo-mcp-reconciliador.md) ·
  [0018](../../adr/adr-0018-verificacao-referencias-apis-publicas.md) ·
  [0020](../../adr/adr-0020-connect-autoexport-bbt.md)
