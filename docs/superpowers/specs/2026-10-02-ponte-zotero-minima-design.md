---
title: Ponte Zotero mínima — anotações e notas saem do PAR; BBT só no connect e no lookup do docx; MCP de Zotero de terceiro como complemento opcional
date: 2026-10-02
status: draft
tags: [zotero, better-bibtex, docx, word, pandoc, doctor, mcp, aposentadoria, adr-0037]
---

# Ponte Zotero mínima

## Resumo executivo

O PAR fala com o Zotero por quatro caminhos: o auto-export do `.bib` pelo Better BibTeX (BBT),
registrado pelo `connect`; o lookup do docx; anotações e notas pela API local; e a sonda do
doctor. O terceiro nunca gerou um arquivo em projeto real. Esta spec encolhe a ponte ao que entrega
valor e corrige três defeitos do export docx que hoje atingem **todo** export padrão.

Duas entregas:

- **0.70.3 PATCH** (sem breaking): o docx sai com `uris` sempre presente e sempre array, e o
  Refresh do Zotero no Word deixa de quebrar com TypeError. O lookup do vínculo volta a funcionar,
  porque o export para de mandar `library=""` ao BBT. O export deixa de exigir o Zotero aberto:
  o lookup passa a ser melhor-esforço (2 s), e um aviso por causa diz quantas citekeys saíram sem
  vínculo e o comando para refazer. Entram ainda a nota de primeiro uso nova e a mensagem
  específica do ingest quando o coautor usou os botões do Zotero (D6 do dono). Saem 2.195 linhas
  de Lua morto. A base URL do Zotero passa a ter uma fonte só em `core/deps.py`. O pandoc do
  Zettlr.app é usado quando falta pandoc no macOS, sob o piso único 3.8.2, e o doctor ganha a
  linha `pandoc`. O modo `reconcile` passa a pré-aprovar as tools com o prefixo que elas têm
  no plugin.
- **0.71.0 MINOR ⚠** (o evento breaking único, junto com a Spec A): saem `paper sync-annotations`,
  `sync-notes`, `sync-all` e a tool MCP `paper_sync_all` (D2 do dono). O doctor passa a usar uma
  única sonda ao BBT e deixa de exigir o toggle "Allow other applications". O `connect` ganha
  transporte próprio e mensagens que dizem a causa real. Pedidos do tipo "o que eu anotei" são
  roteados, só por texto, para o zotero-cli opcional do 54yyyu.

A recomendação de MCP de terceiro no onboarding troca de `cookjohn/zotero-mcp` para
`54yyyu/zotero-mcp`. É só documentação e pode sair já, sem bump.

Uma ADR nova, **ADR-0037 "Ponte Zotero mínima"**, entra aceita com a 0.70.3. Ela registra as
decisões do docx e a aposentadoria que a 0.71.0 implementa, emenda as ADR-0008, ADR-0020 e
ADR-0026 e substitui duas linhas da spec do Zettlr. A distribuição do CLI (launcher, hooks,
`.mcp.json`, `/par:start`, curingas das portas, Windows) é da Spec A,
[`2026-10-02-plugin-distribuicao-unica-design.md`](2026-10-02-plugin-distribuicao-unica-design.md),
com a ADR-0038, e não se repete aqui.

## Contexto e problema

### O que é usado e o que não é

A auditoria de 2026-08-23 ([`2026-08-23-ponte-zotero-auditoria-design.md`](2026-08-23-ponte-zotero-auditoria-design.md), A6)
contou os artefatos nos 14 `pj_*` do dono. Havia 340 symlinks de PDF, 61 `_meta.md` e 18
`_extract.md`, mas **0 `_annotations.md` e 0 `note__*.md`**. O dono confirmou que anota no Zotero
"muito raramente". Uma recontagem em 2026-10 achou 15 `pj_*` em `~/PycharmProjects`, todos ainda
com 0 nos dois. O pipeline de anotações e notas (`paper/zotero.py`, 668 linhas; `sync_all.py`, 47;
3 comandos; 1 tool MCP; cerca de 1.250 linhas de teste) nunca gerou um arquivo em projeto real. É
também o único consumidor da API local `/api/*` do Zotero, e é por causa dele que o doctor exige o
toggle "Allow other applications on this computer to communicate with Zotero"
(`core/deps.py:141-189`).

### Três defeitos do docx que atingem todo export padrão

1. **O lookup do vínculo morre no caminho padrão.** `fetch_bbt_zotero_metadata` manda
   `"params": [citekeys, True, library or ""]` (`write/export.py:193`). No BBT, `getLibraryID("")`
   não acha biblioteca e lança `could not find library`. O erro chega como JSON-RPC com HTTP 200,
   e `body.get("result") or {}` (`export.py:208`) o engole. Nenhum template nem skill define
   `zotero: {library: …}`, então o docx padrão sai sem `uris`, sem `prumoFingerprint` e sem
   `zoteroItemID`. O comportamento foi conferido em quatro revisões do fonte do BBT (master,
   649c37db97, 5d27ab7230 e 2e9a3f4651) e no bundle que o dono tem instalado (9.0.64,
   `content/better-bibtex.js:128265`). Com o parâmetro omitido, o BBT usa a "My Library" em todas
   elas.
2. **O Refresh do Zotero no Word quebra.** Em `integration.js` do Zotero (loadItemData, ~3299-3388;
   o mesmo código em 7.0, 9.0 e main), um `citationItem` sem `uris` cai em
   `Zotero.Items.get(<citekey>)`, que devolve `false`. Em seguida, o ramo de item embutido faz
   `citationItem.uris.length` e lança TypeError. O Refresh inteiro falha. Isso foi medido num
   harness QuickJS: o código real do Zotero 9.0 (URIMap, construtor de `Citation`,
   `loadItemData` e `toJSON`, extraídos de `integration.js`), com stubs só para `Zotero.Items`,
   `URI` e `Relations`. Sem `uris` → "THROWS TypeError"; `uris: []` → OK, item embutido; URI
   canônica do BBT (`users/local/<key>`) → religa. Por causa do defeito 1, isso atinge todo docx do CLI, e
   todo docx do perfil do Zettlr, que nunca tem lookup (`write/zettlr.py:63-68`). Para piorar, a
   nota pós-export manda a pessoa direto para o erro: "use Zotero → Refresh"
   (`write/cli.py:26-31`).
3. **O gate exige o Zotero aberto para um lookup descartado.** `_check_bbt_running`
   (`export.py:724-737`, chamado em 868 e 1013) recusa o export docx com o Zotero fechado, embora
   o resultado do lookup seja descartado pelo defeito 1 e o docx saia correto sem ele (o citeproc
   formata e o `itemData` vai embutido).

**Armadilha da correção.** `pandoc.List(...)` só vira array JSON a partir do pandoc 3.2.1 (entrada
3.2.1 de https://pandoc.org/releases.html, 2024-06-24: "pandoc.List tables are encoded as JSON
arrays"). Medido no pandoc 3.1.2: `pandoc.List({"u"})` sai `{"1":"u"}` e `pandoc.List({})` sai
`{}`. `json.decode('[]')` sai `[]`, e a tabela crua `{ uri }` sai `[uri]`, tanto no 3.1.2 quanto
no 3.10.1. A correção ingênua com `pandoc.List` regrediria em pandoc antigo.

### O Refresh também apaga as marcas do PAR

`Citation.toJSON` do Zotero guarda só uma lista fechada de chaves. `prumoOcc`, `prumoFingerprint`
e `zoteroItemID` somem, e o `id` troca de citekey para o itemID numérico (vinculado) ou para
`<sessão>/<rand>` (embutido). A sessão `prumo-export` não existe no Word do coautor, então
qualquer Refresh ou Add/Edit Citation marca todas as citações como novas e reescreve os campos
(`_updateDocument` chama `setCode` quando `serialize()` difere do código original). A perda das
chaves foi medida no mesmo harness QuickJS: a saída de `toJSON` não tem `prumoOcc`,
`prumoFingerprint` nem `zoteroItemID`, o `id` vira `42` (vinculado) ou `SESS/RND` (embutido), e o
`itemData.id` embutido continua sendo a citekey. Que o Refresh reescreve **todos** os campos é
inferido do fonte 9.0 (`refresh`, `addCitation`, `_updateDocument`). Hoje o ingest recusa esse
docx com uma mensagem enganosa ("occ_id duplicado … paste-clone", `write/review.py:443-450`).

### Pandoc: piso real, fallback que já está no disco e doctor cego

- O `crossref.lua` (ADR-0035) roda em todo formato e precisa de `: Legenda {#tbl:x}`, que o reader
  de Markdown só entende a partir do **pandoc 3.8.2** (extensão `table_attributes`; entrada 3.8.2
  de https://pandoc.org/releases.html). No 3.1.2, um
  documento com tabela rotulada falha com `crossref: @tbl:t1 não tem alvo` (exit 83). O cabeçalho
  do Lua diz "Pandoc 3.0+", e a spec do Zettlr diz "≥ 3.0". Nenhum dos dois está certo.
- O Zettlr 4.8.0 traz pandoc 3.10.1 arm64 em `/Applications/Zettlr.app/Contents/Resources/pandoc`.
  Quem usa Zettlr no Mac já tem um pandoc recente, mas `_check_pandoc` só olha o PATH
  (`export.py:132-138`).
- `check_external_deps` olha só qmd e zotero; o doctor não tem linha de pandoc. Quando falta
  pandoc, a pesquisadora só descobre no primeiro export.

### BBT, sonda e piso de versão

- `/better-bibtex/cayw?probe=true` responde `ready` ou `starting` antes de qualquer `await`
  (`content/cayw.ts:170`) e não passa pelo gate da API local. Os endpoints do BBT só são
  registrados depois da fase `translators`: até lá, o probe dá 404. O Zotero põe `X-Zotero-Version`
  em toda resposta, inclusive no 404 de endpoint desconhecido (`server.js:271-273, 362`). Uma única
  sonda diz "Zotero aberto", "BBT presente (ou iniciando)" e a versão do Zotero.
- O toggle da API local só bloqueia `LocalAPIEndpoint` (`server_localAPI.js:249-250`, o único 403
  "Local API is not enabled"). O JSON-RPC do BBT não passa por ele.
- Até o BBT 9.0.64, o serializer chamava `Zotero.getActiveZoteroPane()` sem checar null. Com o app
  aberto e a janela principal fechada (macOS), todo job de tradutor com item fora do cache quebra:
  o auto-export de itens novos e o `item.pandoc_filter`. O caso típico é um paper salvo pelo
  Connector com a janela fechada. Os commits 051d0843 ("solves no active zotero pane",
  2026-09-27; https://github.com/retorquere/zotero-better-bibtex/commit/051d0843) e 10022a3d
  (https://github.com/retorquere/zotero-better-bibtex/commit/10022a3d) corrigem isso, ambos no
  v9.0.65 (2026-09-30; a versão atual é a 9.0.68). O sintoma aparece em BBT #3617
  (https://github.com/retorquere/zotero-better-bibtex/issues/3617; Zotero 10.0.4 + BBT 9.0.64):
  `500 TypeError: can't access property "getSelectedLibraryIDs", azp is null`. **A máquina do dono
  roda Zotero 10.0.4 com BBT 9.0.64**, abaixo do piso.
- `autoexport.add` guarda um job por caminho de saída (`auto-export.ts:587`). Repetir com a mesma
  coleção e o mesmo tradutor só reagenda; com parâmetros diferentes e sem `replace`, o BBT recusa.
  A premissa da ADR-0020 ("reconectar às cegas duplicaria o export automático") é falsa. O risco
  que a Guarda 1 cobre de fato é sobrescrever um `.bib` feito à mão.

### Sandbox do Claude Code

Pela documentação de sandbox do Claude Code (https://code.claude.com/docs/en/sandboxing, § "A
command fails to reach a server on localhost"), um comando dentro do sandbox "can't connect
directly to a server that's running on your machine outside the sandbox". No Linux e no WSL2,
nunca; no macOS, só com `network.allowLocalBinding`. A mesma página documenta
`sandbox.excludedCommands` (§ "Run commands outside the sandbox with excludedCommands"), que tira
do sandbox só os comandos que casam com o padrão. Dentro do
sandbox, o `prumo` rodado pelo Bash não chega a `127.0.0.1:23119`: o doctor diz "Zotero fechado" e
o export, sem o gate, sairia sem vínculo com o conselho errado ("abra o Zotero"). O Claude Code
define `SANDBOX_RUNTIME=1` nos comandos que roda no sandbox. Isso foi observado no binário 2.1.286,
mas não está documentado. Servidores MCP rodam fora do sandbox.

### Base URL em três cópias

`core/deps.py:26`, `paper/zotero.py:29-38` e `write/export.py:64` têm a mesma URL. O export ignora
`PRUMO_ZOTERO_BASE`, o que a própria ADR-0007 registra como dívida.

### MCP de terceiro no onboarding

O onboarding (`docs/onboarding-pesquisador.md:174-180`) recomenda `cookjohn/zotero-mcp`. Pela
auditoria de 2026-08-23 (D4), ele é o único dos sete levantados cuja busca semântica manda texto
dos PDFs para `api.openai.com` por padrão. O substituto aprovado lá, `54yyyu/zotero-mcp` (MIT;
v0.13.1; 12 versões entre 2026-08-03 e 2026-09-24), teve as flags conferidas no fonte da 0.13.1 e
numa instalação com HOME falso: 38 tools, cerca de 13,4 mil tokens por request no modo MCP.

## Decisões

Numeração própria desta spec (B1–B13). "D2 do dono" e "D6 do dono" são as decisões finais do dono
compartilhadas com a Spec A.

### B1 · O export docx não exige mais o Zotero aberto

**Decisão.** Saem `_check_bbt_running`, as duas chamadas a ele, `ZoteroNotRunningError` e
`BBT_JSONRPC_URL`. `fetch_bbt_zotero_metadata` passa a ser melhor-esforço: timeout de 2 s, nunca
levanta, e devolve `BbtLookup`, com os itens achados e a causa da falha (`unreachable` ou
`rpc_error`). Depois de gravar o docx, `docx_link_warning` lê do próprio OOXML as citekeys que
saíram com `uris` vazio. Se houver alguma, devolve uma mensagem por causa, sempre com o comando de
refazer:
- Zotero inalcançável, com variante para o sandbox do Claude Code;
- erro JSON-RPC do BBT;
- chave não achada na biblioteca consultada.

O `{n}` das mensagens é o número de **citekeys distintas** com `uris` vazio no OOXML: uma chave
citada duas vezes conta uma vez.

O comando de refazer (`{redo}`) reproduz a chamada que gerou o docx. `export()` e `compose()` o
montam a partir dos argumentos que receberam, num helper privado `_redo_command`:
`prumo write export {page} --to docx --force` ou
`prumo write compose --index {index} --to docx --force`, acrescido de `--style {style}` (no
`export`, quando difere do default `apa`; no `compose`, quando veio), `--bib`, `--out-dir` e
`--reference-doc` quando vieram, com os caminhos passados por `shlex.quote`. `out` não entra: não
tem flag na CLI e nenhuma fachada o passa.

A variante do sandbox oferece dois remédios: repetir o comando fora do sandbox (o Claude pede
permissão) ou acrescentar `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`,
para que o `prumo` rode sempre fora do sandbox.

`export()` e `compose()` ganham `on_warning: Callable[[str], None] | None = None`; o padrão é
`logger.warning`. A CLI passa `avisos.append`, imprime cada aviso com `console.warn` e inclui
`warnings` no `--json`.

**Dono do ramo do sandbox.** `core/deps.in_claude_sandbox()` e as variantes de sandbox E2
(0.70.3), E11 e E15 (0.71.0) são desta spec, com o teste direto de `in_claude_sandbox()`. A A16
da Spec A só as referencia e chama a sonda pelo nome `_bbt_probe()`.

**Por quê.** O gate impõe um pré-requisito sem dar nada em troca: com o Zotero fechado, o docx
continua correto (o citeproc formata e o `itemData` vai embutido) e perde apenas o vínculo, que o
aviso ensina a recuperar. A lista de chaves vem do OOXML, não do texto, porque `scan_citekeys`
admite falso positivo (`core/citations.py:97-103`), e um falso positivo viraria uma citekey "não
achada" que não existe no docx. A causa vem do resultado do próprio lookup: não é preciso uma
segunda chamada, e dá para separar "BBT
recusou" (por exemplo, BBT < 9.0.65 com a janela fechada, ou `zotero.library` com nome errado) de
"chave fora da biblioteca". O callback segue o precedente de `connect_collection(confirm=…)`: a
saída é I/O de fachada e não mora no domínio. O `{redo}` carrega as opções da chamada porque um
redo com os defaults reescreveria, com `--force`, um docx em APA e sem o template de quem exportou
com `--style vancouver --reference-doc revista.docx`, ou gravaria em outro lugar quem usou
`--out-dir`, deixando o docx sem vínculo onde estava. O `excludedCommands` é o mecanismo que a
documentação de sandbox indica para uma ferramenta confiável que precisa do localhost do host; ele
tira do sandbox só o `prumo`, e o comando excluído continua passando pelo fluxo normal de
permissão.

**Alternativas rejeitadas.**
- Manter o gate: atrito sem valor (ver contexto).
- `{redo}` fixo com os defaults: o remédio refaria outro documento (ver acima).
- Só "repita fora do sandbox", sem o `excludedCommands`: a pesquisadora que trabalha sempre com o
  sandbox ligado passaria, a cada export, doctor e connect, por uma falha seguida de um pedido de
  repetir fora dele.
- Um GET de presença (`_bbt_up()`) antes de classificar: seria a segunda sonda de presença para o
  mesmo fato e ainda não distinguiria erro JSON-RPC de chave ausente.
- Mudar o retorno de `export()` para um objeto de resultado: quebraria `par.domains.write.api`
  numa PATCH.
- Timeout de 10 s (o valor atual): um Zotero travado prenderia o export por 10 s.

### B2 · `uris` sempre presente e sempre array, numa forma que vale em todo pandoc

**Decisão.** Em `zotero_live_docx.lua:99`, `item.uris = lookup.uri and { lookup.uri } or json.decode('[]')`
(`json` já é o `local json = pandoc.json` da linha 37).

**Por quê.** Sem `uris`, o Refresh lança TypeError. Com `[]`, o loop embutido roda 0 vezes. A forma
foi medida nos pandoc 3.1.2 e 3.10.1.

**Alternativas rejeitadas.**
- `pandoc.List(lookup.uri and { lookup.uri } or {})`: emitiria `{"1": uri}` para citações
  vinculadas nos pandoc 3.1.1–3.2.0, uma regressão em quem hoje funciona.
- Sentinela com `__tojson`: funciona, mas é mais obscura.
- URI sintética: o Zotero tentaria resolvê-la.

### B3 · Sem `zotero.library`, o terceiro parâmetro é omitido

**Decisão.** `params = [citekeys, True]` e, só quando o frontmatter tem `zotero.library`,
`params.append(library)`.

**Por quê.** Com o parâmetro omitido, o BBT usa `userLibraryID` em todas as revisões examinadas.
O `zotero.library` continua valendo como override para biblioteca de grupo.

**Alternativa rejeitada.** Mandar o id numérico da biblioteca pessoal: acoplaria o PAR a um
detalhe interno do BBT sem ganho nenhum.

### B4 · Contrato da rodada de revisão: sem botões do Zotero (D6 do dono)

**Decisão.**
- `FIRST_USE_DOCX_NOTE` é reescrita: o docx já sai formatado e com `ZOTERO_PREF`, então não
  precisa de Refresh; na revisão via ingest, o coautor não usa Refresh nem Add/Edit Citation. A
  nota sai **só depois de `write export`**. O `compose` não grava citemap, não pode ser ingerido,
  e a frase de revisão não se aplica a ele.
- `check_conservation` ganha uma **primeira** checagem, antes das outras checagens de
  conservação de citações: se **qualquer** citação observada tem `occ_id` vazio, levanta uma
  mensagem própria que cita Refresh e Add/Edit Citation e traz o comando com a página de
  `citemap.page`. As checagens que `ingest()` faz antes de `check_conservation` (preflight do
  `uvx`, estrutura do docx, `review.md` pendente, sidecars, fonte alterada, sha idêntico, Guarda A
  e os erros do próprio leitor stateful) continuam na frente.
- O comentário do `zotero_live_docx.lua` que justifica `prumoOcc` deixa de prometer degradação
  graciosa: o Zotero descarta `prumoOcc` no Refresh e no Add/Edit Citation, e o ingest recusa esse
  docx com mensagem própria.
- A tolerância no ingest fica adiada, com trigger.

**Por quê.** O PAR sempre grava `prumoOcc`, então `occ_id` vazio só acontece quando o Zotero
reescreveu aquele campo. A checagem vem antes das outras checagens de conservação porque, com
vários `occ_id` vazios, o ramo de duplicata (`review.py:430-450`) dispararia primeiro com
"paste-clone". Ela dispara com
**qualquer** vazio, e não só com todos, porque um único Add/Edit Citation cairia no
"ausente/hard delete". São cerca de 15 linhas, contra redesenhar o pareamento.

**Alternativas rejeitadas.**
- Tolerância agora: recuperar a citekey de `itemData.id`, que sobrevive nos itens embutidos, e
  parear pela ordem do documento. É um redesenho do pareamento sem nenhuma rodada real que tenha
  falhado.
- Manter a nota que manda dar Refresh: leva direto ao TypeError e, depois do B2, a um ingest
  recusado.

### B5 · Lua morto sai

**Decisão.** Apagar `src/par/_filters/zotero.lua` (2.155 linhas, que ainda fariam fetch em
`retorque.re` se rodassem) e `zotero_bibliography_docx.lua` (40), com os helpers
`_zotero_lua_filter` e `_zotero_bibliography_docx_filter` e os três testes que só conferem que eles
existem.

**Por quê.** `_build_pandoc_cmd` usa só `crossref.lua` e `zotero_live_docx.lua`
(`export.py:793, 806`), e um teste já afirma que os legados não entram no comando. O hatch empacota
`src/par` inteiro, então o pyproject não muda.

**Alternativa rejeitada.** Manter os arquivos "como utilitários": nada os chama (Princípio VI).

### B6 · Base URL do Zotero e URL do JSON-RPC com uma fonte só, em `core`

**Decisão.** `core/deps.py` ganha `zotero_base()` (lê `PRUMO_ZOTERO_BASE`, com default
`http://127.0.0.1:23119`) e `bbt_rpc_url()`. As duas leituras inline de `deps.py` passam a usá-las.
`paper/zotero.py::_zotero_base()` e `_bbt_rpc()` delegam a elas: os nomes ficam porque os testes
fazem monkeypatch neles, e o `connect` herda a unificação. O export troca a constante por
`bbt_rpc_url()`, calculada na hora da chamada.

**Por quê.** A ADR-0007 já decide o override por env para toda chamada. Isto é **conformidade**,
não emenda: o CHANGELOG diz "dívida da ADR-0007 quitada". `domains` importar `core` respeita o
layering.

**Alternativa rejeitada.** Um módulo novo `core/zotero_local.py` (cerca de 80 linhas mais testes),
da versão anterior do desenho: `deps.py` já é o dono das sondas e da env (Princípio VIII, "reusar
um seam existente").

### B7 · Pandoc: resolução compartilhada, Zettlr como alternativa, piso único 3.8.2

**Decisão.**
- `core/deps.pandoc_path()` procura `pandoc` no PATH e, se não achar, o binário de
  `/Applications/Zettlr.app/Contents/Resources/pandoc`, se for executável.
- `export._check_pandoc()` passa a usar `pandoc_path()`.
- O doctor ganha a linha `pandoc` (`required_by = ["write export", "write compose"]`). Ela roda
  `pandoc --version` pelo seam `_pandoc_version` e reprova versão abaixo de 3.8.2, com o comando
  de correção. Versão não detectada é tratada como presente, o mesmo fail-safe da linha do Zotero.
- O piso **3.8.2** aparece igual em todo lugar: cabeçalho do Lua, README, `project_guide.md` do
  `pj_base`, doctor, mensagem do export e dica de Linux.

**Por quê.** Quem usa Zettlr no Mac passa a ter zero passos de pandoc. O piso real vem das
tabelas rotuladas (ADR-0035), uma dependência que ninguém tinha documentado. A resolução fica em
`core` porque o doctor (`core/deps.py`) não pode importar `domains/write`. O export não checa
versão: recusar pandoc 3.1–3.8.1 quebraria quem não usa tabela rotulada. O doctor avisa.

**Alternativas rejeitadas.**
- Piso 3.1.1 ou 3.1.2: tabela rotulada falha com exit 83.
- Fallback só em `domains/write`: o doctor não o veria.
- Embutir pandoc via `pypandoc-binary`: decidido na Spec A. O wheel arm64 traz um binário x86_64.
- Checar a versão no export: seria uma regressão para quem não usa tabela rotulada.

### B8 · Prefixo das tools MCP no modo `reconcile` (0.70.3)

**Decisão.** Em `skills/review/modes/reconcile.md:5` e `:218`, `mcp__prumo__*` passa a
`mcp__plugin_par_prumo__*`, sem lista dupla. A porta `skills/review/SKILL.md` é regerada pelo
`gen_indexes.py`.

**Por quê.** O servidor do plugin aparece como `mcp__plugin_<plugin>_<servidor>__` (Claude Code,
https://code.claude.com/docs/en/mcp, § "Plugin MCP tool names"; binário 2.1.286). Hoje a
pré-aprovação nunca casa para
quem consome o plugin, e cada `review_status`, `review_events`, `review_worklist` e
`propose_prose_edit` pede permissão. O dono nunca viu isso porque, no repo, o `.mcp.json` de
projeto deduplica por endpoint. A pré-aprovação de `propose_prose_edit` é a da ADR-0017 e não
muda.

**Alternativa rejeitada.** Listar os dois prefixos: o antigo só casa no repo de desenvolvimento,
cujo `.mcp.json` de projeto a Spec A desliga.

### B9 · Anotações e notas saem do PAR (D2 do dono)

**Decisão.**
- Aposentar `prumo paper sync-annotations`, `sync-notes` e `sync-all`, a tool MCP `paper_sync_all`,
  os re-exports `sync_all`, `sync_annotations` e `sync_notes` da API, `ZoteroApiError`,
  `note_paths.child_note_path` e a regra de lint `duplicate_item_key` (lista exata em
  Componentes).
- `_annotations.md` e `note__*.md` existentes ficam intactos e legíveis (Princípio IV).
- **`migrate-layout` continua gravando `_annotations.md`.** Ao converter uma nota plana legada
  que tem o bloco `<!-- BEGIN ZOTERO ANNOTATIONS -->`, ele separa o bloco nesse arquivo, como
  hoje. Por isso `note_paths.annotations_path` e os testes dele ficam.
- "O que eu anotei" passa a ser roteado, só por texto, para o zotero-cli opcional (B12).

**Por quê.** Zero artefatos em 15 projetos. Saem cerca de 830 linhas de `src` e 1.250 de teste,
3 comandos, 1 tool e o único consumidor da API local (e, com ele, o toggle). Manter o
`migrate-layout` como está é a opção sem perda de dado e sem código: a alternativa mudaria um
conversor one-off, e os testes dele, para deixar o bloco legado dentro do `_meta.md`, sem valor
para a pesquisadora.

**Alternativas rejeitadas.**
- Migrar as leituras para a API local num módulo novo (desenho anterior): ver B13.
- Fazer o `migrate-layout` deixar o bloco no `_meta.md` e apagar `annotations_path`: mexe em
  conversor e em testes sem ganho.
- Manter `sync-all` como alias de `sync`: um nome a mais para o mesmo remédio (Princípio VIII).

### B10 · Doctor: uma sonda do BBT; o toggle sai

**Decisão.**
- Em `core/deps.py`, `_zotero_api_root`, `zotero_local_api_up`, `_zotero_host_port` e
  `_zotero_version_header` dão lugar a uma única sonda, `_bbt_probe()`:
  `GET {zotero_base()}/better-bibtex/cayw?probe=true`, que lê o status e o header
  `X-Zotero-Version` da mesma resposta, inclusive no 404.
- Estados, avaliados nesta ordem (o primeiro que casa decide):
  1. `status` `None` (nada escutando) → "Zotero fechado" (E10), com variante para o sandbox (E11);
  2. versão conhecida com `major < 9`, **mesmo no 404** → par não suportado (E14);
  3. 404 → "sem Better BibTeX (ou ainda iniciando — aguarde e rode `prumo doctor`)" (E12);
  4. outro código diferente de 200 → reiniciar o Zotero (E13);
  5. 200 → presente (com a versão `None`, presente pelo fail-safe que já existe).

  O item 2 vem antes do 404 porque o BBT acompanha o major do Zotero (o mesmo fato que o E14 já
  diz): mandar quem tem Zotero 7 ou 8 instalar o `.xpi` mais recente não resolve.
- `required_by = ["paper connect", "write export --to docx (vínculo com a biblioteca)"]`.
- Sem checagem da versão do BBT: o piso 9.0.65 fica no onboarding e nas mensagens do `connect` e
  do aviso do docx.

**Por quê.** Uma requisição dá os três fatos sem passar pelo gate da API local. Responde antes de
qualquer `await`, então não estoura os 2 s durante o startup do BBT. O nome e o formato do
`DepStatus` `zotero` não mudam, e o preflight `_PF_ZOTERO` e as skills ficam como estão.

**Alternativas rejeitadas.**
- `api.ready` por JSON-RPC (devolveria as versões do Zotero e do BBT): o handler JSON-RPC espera
  `Zotero.BetterBibTeX.ready` e pode estourar o timeout no startup, e uma checagem de versão no
  doctor não tem dor registrada. O BBT se atualiza sozinho.
- `/connector/ping` somado ao cayw: são duas requisições para o que uma já diz.
- Manter `/api/`: exige um toggle que nada no PAR usa depois do B9.

### B11 · `connect`: transporte próprio e mensagens pela causa real

**Decisão (0.71.0).**
- `paper/connect.py` ganha seu próprio `_http_post_json` (cerca de 10 linhas de `urllib`; mesmo
  nome de seam, então os monkeypatches de `test_connect.py` continuam valendo) e passa a postar
  em `core.deps.bbt_rpc_url()`. O `import zotero` sai.
- `_OFFLINE_MSG` vira uma função que monta o texto com `zotero_base()` e com a variante do
  sandbox.
- A mensagem da Guarda 1 (`AlreadyConnectedError`) passa a dizer o risco real (sobrescrever o
  `.bib`) e o remédio (`prumo paper sync`).
- A dica de `exported=False` na CLI cita o piso do BBT 9.0.65.
- Sem `--replace`.

**Por quê.** O `zotero.py` some com o B9, e o transporte de 10 linhas não justifica módulo
(Princípio VIII). As mensagens passam a dizer a causa que existe: hoje elas citam um risco que
não existe e escondem o que de fato falha (BBT antigo com a janela fechada). A coleção é escolhida
uma vez por projeto. Trocá-la seria um parâmetro (`replace`) a mais, sem `remove` nem `list`, mas
não há pedido real.

**Alternativas rejeitadas.**
- Mover o POST para `core`: `core` não deve conhecer o protocolo JSON-RPC de um domínio, e o
  export tem o seu próprio POST. Uma duplicação de cerca de 10 linhas é aceita.
- Construir `--replace` agora: YAGNI, com trigger.

### B12 · Zotero de terceiro: roteamento por texto e receita no onboarding

**Decisão.**
- As §1b–1d de `skills/paper/modes/library.md` dão lugar à seção de roteamento (texto abaixo, em
  Componentes). O agente detecta pela sessão (a skill `zotero-cli` ou tools `mcp__zotero__*`),
  sem sonda Bash nem código, e escreve no Zotero só a pedido explícito. Sem as ferramentas, uma
  linha de fallback, e não instala nada.
- A frase do modo vira "o que eu anotei no Zotero sobre este paper".
- O onboarding ganha a § "Perguntar ao seu Zotero" (texto abaixo) no lugar do cookjohn.
  - Rota A (Claude Code): skill + CLI, 3 comandos e o toggle.
  - Rota B (chat do app Claude): `setup` do MCP, num parágrafo.
  - Notas de privacidade incluídas.
- **Nada** do 54yyyu no `.mcp.json`, nos `allowed-tools` ou no `/par:start`. (O item 3 da trilha
  do `/par:start`, sobre o próprio Zotero e o BBT, tem o texto fixado por esta spec em
  Componentes 0.71.0.)

**Por quê.** Uso quase nulo (A6) não paga código. A receita fica fora do repo do PAR e sem
acoplamento: o 54yyyu solta uma ou duas versões por semana. Um curinga `Bash(zotero-cli *)`
cobriria `delete item` e `duplicates merge`. A description da skill do 54yyyu ("…references,
citations, papers they have saved, or their reading notes") disputa frases com `/par:paper`, e
por isso ela não é oferecida no start. A troca do cookjohn executa a D4 da auditoria de
2026-08-23 por privacidade. A nota de privacidade sobre `immutable=1` (leitura do `zotero.sqlite`
no lugar; cópia temporária só com WAL não vazio; leitura rasgada, sem erro, com o Zotero aberto)
vem do achado A8 da mesma auditoria.

**Divergência registrada.** Aquela D4 pedia grounding ao vivo antes de publicar. A receita sai
**antes**, marcada "não validada neste piloto", porque já reduz o risco de hoje (o cookjohn manda
texto para fora por padrão) e não acopla código. O grounding ao vivo vira o G4 e só retira a
marca.

**Alternativas rejeitadas.**
- Oferecer o zotero-cli no `/par:start`.
- Pré-aprovar comandos read-only do zotero-cli: acoplaria o PAR a uma sintaxe que muda toda
  semana.
- `ZOTERO_BACKEND=api` como default: dependeria de chave da Web API.

### B13 · A API local do Zotero fica fora do PAR

**Decisão.** Não criar `core/zotero_local.py` nem migrar o docx para a API local. O BBT continua
sendo a fonte da URI canônica (`custom.uri = Zotero.URI.getItemURI(item)`, inclusive
`users/local/<key>` para quem não sincroniza).

**Por quê.** A API local exige o toggle (403 sem ele) e um módulo novo: índice da biblioteca,
desambiguação 0/1/N que o BBT já faz e dependência do citationKey nativo, um risco nos grupos
só-leitura. O BBT segue obrigatório de qualquer jeito, pelas chaves e pelo auto-export. Esclarecendo
o motivo: `users/0` **religa**. O resolver do Zotero (`uri.js`, `_getURIObjectLibrary`) mapeia
qualquer `users/<x>` para a biblioteca do usuário, e no harness QuickJS com o código real do
Zotero 9.0 um `uris` com `users/0/items/<KEY>` religou, assim como a URI canônica
`users/local/<key>` do BBT. A API local é rejeitada pelo toggle e pelo código extra, não por falha
de vínculo.

**Alternativa rejeitada.** A migração da versão anterior do desenho, pelos motivos acima.

## Arquitetura

```
 máquina da pesquisadora (Claude Code local: terminal, aba Code ou IDE)

 Zotero 9+ ── BBT auto-export ──▶ docs/references/_references.bib ──▶ sync · sync-pdfs · find · lint
   │ 127.0.0.1:23119                                                    graph · verify-refs · Zettlr
   │                                                                     (tudo offline)
   ├─ JSON-RPC user.groups (leitura) + autoexport.add (única mutação) ◀── prumo paper connect (1x/projeto)
   ├─ JSON-RPC item.pandoc_filter (2 s, melhor-esforço)                ◀── prumo write export|compose --to docx
   └─ GET /better-bibtex/cayw?probe=true (+ header X-Zotero-Version)   ◀── prumo doctor

 opcional, instalado pela pesquisadora no escopo de usuário:
   zotero-cli / MCP do 54yyyu ──▶ anotações, notas, biblioteca inteira (nunca no .mcp.json do PAR)
```

O BBT tem três papéis, e em cada um ele é a única fonte:

1. citation keys nativas;
2. auto-export do `.bib`, registrado uma vez pelo `connect`, com `user.groups` como guarda e
   `autoexport.add` como escrita (ADR-0020 e ADR-0028 intactas nas guardas);
3. lookup `item.pandoc_filter` no export docx: URI canônica, sem toggle.

Nada no PAR usa mais `/api/*`.

**Layering.** Tudo o que é Zotero/pandoc e não é de domínio mora em `core/deps.py`:
`zotero_base()`, `bbt_rpc_url()`, `in_claude_sandbox()`, `_bbt_probe()`, `pandoc_path()` e
`_pandoc_version()`. `domains/write/export.py` (lookup e aviso) e `domains/paper/connect.py`
(transporte e guardas) importam de `core`; nenhum domínio importa outro. Todas essas funções, e
as mensagens de sandbox E2, E11 e E15, são desta spec; a Spec A (A16) só as referencia.

**Docx.** Com vínculo, `uris = [URI canônica]` e o campo religa no Word. Sem vínculo (Zotero
fechado, chave fora da biblioteca, perfil do Zettlr), `uris = []` com `itemData` embutido: o docx
abre formatado, o Refresh funciona e o aviso traz o comando de religar.

| Peça | Valor para a pesquisadora |
|---|---|
| BBT + `connect` | O `.bib` se atualiza sozinho, sem o "Keep updated" manual. |
| `item.pandoc_filter` melhor-esforço | Citações vivas e religáveis no Word quando o Zotero está aberto; o export não falha quando ele está fechado. |
| `uris` sempre array | O Refresh do coautor no Word não quebra. |
| `docx_link_warning` | Diz quantas citekeys ficaram sem vínculo, por quê e o comando para refazer. |
| Mensagem do ingest (B4) | Remédio certo em vez de "paste-clone". |
| `pandoc_path()` + linha `pandoc` no doctor | Zero passos de pandoc para quem tem Zettlr; a dica certa, com o piso, para quem não tem. |
| Sonda `cayw` no doctor | "Abra o Zotero" ou "instale o BBT", sem exigir o toggle. |
| Roteamento em `library.md` + receita 54yyyu | "O que eu anotei" tem resposta honesta, sem código no PAR. |

## Componentes

### 0.70.3 PATCH

| Caminho | Mudança exata |
|---|---|
| `src/par/_filters/zotero_live_docx.lua` | Linha 99: a linha do B2, com o comentário abaixo. Cabeçalho (l.22-23): "Pandoc 3.0+ (para `pandoc.json`)" vira "Pandoc ≥ 3.8.2: piso único do export (o `crossref.lua` precisa da extensão `table_attributes`)". Comentário do `prumoOcc` (l.116-119): o trecho "melhor-esforço (se o Refresh descartar chaves custom, a conservação degrada pro multiconjunto de citekeys, sem quebrar)" vira "o Zotero descarta `prumoOcc` no Refresh e no Add/Edit Citation; o ingest recusa esse docx com mensagem própria (ADR-0037)". |
| `src/par/_filters/zotero.lua`, `src/par/_filters/zotero_bibliography_docx.lua` | Apagados. |
| `src/par/_filters/__init__.py` | Docstring passa a listar `crossref.lua` (numeração de figuras e tabelas, ADR-0035) e `zotero_live_docx.lua` (campos vivos do Zotero no docx, ADR-0037); sai a instrução "Atualizar: curl …". |
| `src/par/core/deps.py` | Entram `zotero_base()`, `bbt_rpc_url()`, `in_claude_sandbox()` (dono: esta spec; a A16 da Spec A só a referencia), `pandoc_path()`, `_pandoc_version()` (seam), `_ZETTLR_PANDOC` e `_PANDOC_FLOOR = (3, 8, 2)`. `_zotero_api_root` e `_zotero_host_port` passam a ler `zotero_base()`. `check_external_deps` acrescenta o `DepStatus` `pandoc`. A linha `zotero` não muda nesta release. |
| `src/par/domains/write/export.py` | **Saem:** `BBT_JSONRPC_URL`, `ZoteroNotRunningError`, `_check_bbt_running` e as chamadas em `export()` e `compose()`, `_zotero_lua_filter` e `_zotero_bibliography_docx_filter`. **Docstrings:** a do módulo (l.13-16, "Exige Zotero + Better BibTeX rodando") passa a "usa o Better BibTeX, se estiver aberto, para vincular as citações à biblioteca"; a de `ZoteroCitekeyNotFoundError` troca "`zotero.lua` não encontrou" por "o citeproc não encontrou". **Mudam:** `fetch_bbt_zotero_metadata`, `_write_zotero_lookup` (devolve `tuple[Path \| None, BbtLookup]`), `_read_docx_citations` (cada ocorrência ganha `"unlinked"`, as citekeys com `uris` vazio), `_check_pandoc` (usa `pandoc_path()` e a mensagem E7). **Entram:** `BbtLookup`, `docx_link_warning` e `_redo_command`. `export()` e `compose()` ganham `on_warning` e montam o `{redo}` com `_redo_command` a partir dos próprios argumentos (regra do B1: `--style`, `--bib`, `--out-dir` e `--reference-doc` quando vieram). |
| `src/par/domains/write/cli.py` | `FIRST_USE_DOCX_NOTE` nova (texto em Erros), impressa só por `export_command`. `export_command` e `compose_command` passam `on_warning=avisos.append`, imprimem cada aviso com `console.warn` e emitem `"warnings": avisos` no payload. `zettlr_export_entry` passa `on_warning=console.warn` (o comando sai na 0.71.0, na Spec A). |
| `src/par/domains/write/review.py` | `check_conservation`: guarda nova antes do agrupamento por `occ_id` (código abaixo). Docstring: item 0 na ordem das checagens. |
| `src/par/domains/paper/zotero.py` | `_zotero_base()` devolve `zotero_base()`; `_bbt_rpc()` devolve `bbt_rpc_url()`; sai a constante própria. Docstring de `_zotero_base` (l.35-36): sai "unifica com os filtros Lua". |
| `skills/review/modes/reconcile.md` | l.5 e l.218: `mcp__prumo__` vira `mcp__plugin_par_prumo__`. Regerar com `uv run python .github/scripts/gen_indexes.py` (atualiza `skills/review/SKILL.md`). |
| `.github/workflows/ci.yml` | Passo novo antes do Pytest, `name: Pandoc 3.8.2 (piso do export)`, com `run: curl -fsSLo "$RUNNER_TEMP/pandoc.deb" https://github.com/jgm/pandoc/releases/download/3.8.2/pandoc-3.8.2-1-amd64.deb && sudo dpkg -i "$RUNNER_TEMP/pandoc.deb" && pandoc --version \| head -1`. O teste do Lua e os de pipeline real de `test_export_crossref.py` deixam de ser pulados no CI. `.github/` não bumpa. |
| `README.md` | §"Pré-requisitos externos", l.84: "O plugin orquestra duas ferramentas" vira "O plugin orquestra três ferramentas". Tabela de dependências: linha nova "**Pandoc ≥ 3.8.2** — `write export`, `write compose` — macOS: `brew install pandoc` (ou o Zettlr, cujo pandoc o PAR usa quando não há um no PATH); Linux: pacote oficial em https://github.com/jgm/pandoc/releases (o do apt costuma ser antigo); confira com `prumo doctor`". Na linha do Zotero, sai "`write export --to docx`" como pré-requisito e entra "(vínculo das citações, opcional)". |
| `templates/pj_base/docs/project_guide.md` | l.20: "(≥ 3.0 — o Pandoc embutido precisa ser 3.x)" vira "(recente: o 4.8 traz o pandoc 3.10.1; o export do PAR precisa de pandoc 3.8.2 ou mais novo, confira com `prumo doctor`)". Vale para projetos novos; o `update` não reflui este arquivo. |
| `docs/superpowers/specs/2026-07-22-zettlr-front-design.md` | Nota logo abaixo da tabela de degradações: "> As linhas 'Zotero/BBT fechado — caminho canônico' (l.107) e 'Pandoc embutido do Zettlr < 3.0' (l.112) foram substituídas pela ADR-0037: o export degrada com aviso, e o piso do pandoc é 3.8.2." |
| `docs/adr/adr-0037-ponte-zotero-minima.md` | Nova (texto em ADRs e emendas). `docs/adr/_index.md` regenerado pelo gerador. |
| `ROADMAP.md` | Três bullets em "Decisões deliberadas postergadas" (ver Quando reavaliar): tolerância do ingest a Refresh; checagem de versão do BBT no doctor; `connect --replace`. |
| `ARCHITECTURE.md` | l.85: `_filters/` lista `crossref.lua` e `zotero_live_docx.lua`. |

`src/par/_filters/zotero_live_docx.lua`, no lugar da l.99:

```lua
    -- `uris` SEMPRE presente e SEMPRE array JSON (ADR-0037). Sem ele, o
    -- Refresh do plugin do Zotero no Word lança TypeError em
    -- Citation.loadItemData (ramo de item embutido de integration.js).
    -- `json.decode('[]')` sai `[]` em todo pandoc suportado; `pandoc.List`
    -- vazio sai `{}` antes do pandoc 3.2.1, e uma tabela Lua vazia crua
    -- sai `{}` sempre.
    item.uris = lookup.uri and { lookup.uri } or json.decode('[]')
```

`src/par/core/deps.py` (esboço; nada importa `domains/`):

```python
_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"
_ZETTLR_PANDOC = Path("/Applications/Zettlr.app/Contents/Resources/pandoc")
_PANDOC_FLOOR = (3, 8, 2)


def zotero_base() -> str:
    """Base HTTP do Zotero local (connector + Better BibTeX). Override: ``PRUMO_ZOTERO_BASE`` (ADR-0007)."""
    return os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)


def bbt_rpc_url() -> str:
    """Endpoint JSON-RPC do Better BibTeX — único no pacote (ADR-0037)."""
    return f"{zotero_base()}/better-bibtex/json-rpc"


def in_claude_sandbox() -> bool:
    """``True`` dentro do sandbox do Bash do Claude Code, que não alcança o Zotero do host."""
    return os.environ.get("SANDBOX_RUNTIME") == "1"


def pandoc_path() -> str | None:
    """pandoc do PATH; senão o que vem dentro do Zettlr.app (macOS). Seam: ``_binary_on_path``/``_ZETTLR_PANDOC``."""
    found = _binary_on_path("pandoc")
    if found:
        return found
    if _ZETTLR_PANDOC.is_file() and os.access(_ZETTLR_PANDOC, os.X_OK):
        return str(_ZETTLR_PANDOC)
    return None


def _pandoc_version(path: str, timeout: float = 5.0) -> str | None:
    """``"3.10.1"`` a partir da 1ª linha de ``pandoc --version``; ``None`` se falhar. Seam testável."""
```

`src/par/domains/write/export.py` (esboço):

```python
@dataclass(frozen=True)
class BbtLookup:
    """Resultado do ``item.pandoc_filter`` — nunca levanta (ADR-0037)."""

    items: dict[str, dict[str, object]]  # citekey → {"itemID", "uri"}
    failure: Literal["", "unreachable", "rpc_error"] = ""
    detail: str = ""  # mensagem do BBT (rpc_error) ou repr da falha de rede
    library: str | None = None  # biblioteca consultada; None = My Library


def fetch_bbt_zotero_metadata(
    citekeys: list[str], library: str | None, *, timeout: float = 2.0
) -> BbtLookup:
    params: list[object] = [citekeys, True]
    if library:
        params.append(library)  # sem biblioteca o BBT usa a My Library; "" faz o BBT recusar
    # POST em bbt_rpc_url(). HTTPError 404 (Zotero sem BBT, ou BBT iniciando),
    # OSError, ValueError e HTTPException → failure="unreachable".
    # Outro HTTPError, ou "error" no corpo JSON-RPC → failure="rpc_error", detail=mensagem.


def docx_link_warning(docx_path: Path, lookup: BbtLookup, redo_command: str) -> str | None:
    """Uma mensagem pt-BR por causa, para as citekeys que saíram com ``uris`` vazio no OOXML;
    ``None`` quando todas têm vínculo."""


def export(..., on_warning: Callable[[str], None] | None = None) -> Path: ...
def compose(..., on_warning: Callable[[str], None] | None = None) -> Path: ...
```

`src/par/domains/write/review.py`, no início de `check_conservation`:

```python
    rewritten = [citation for citation in observed if not citation.occ_id]
    if rewritten:
        raise CitationConservationError(_ZOTERO_REWROTE_MSG.format(n=len(rewritten), page=citemap.page))
```

### 0.71.0 MINOR ⚠

| Caminho | Mudança exata |
|---|---|
| `src/par/domains/paper/zotero.py` | Apagado (668 linhas). |
| `src/par/domains/paper/sync_all.py` | Apagado (47 linhas). |
| `src/par/domains/paper/cli.py` | Saem `zotero,` do import (l.28), o import de `sync_all` (l.32) e os comandos `sync-annotations` (l.288-307), `sync-notes` (l.310-329) e `sync-all` (l.332-353). No `connect_command`, a dica de `exported=False` (l.270-274) passa ao texto de Erros. |
| `src/par/domains/paper/api.py` | Saem os imports das l.23 e 25 e as entradas `sync_all`, `sync_annotations` e `sync_notes` do `__all__`. |
| `src/par/domains/paper/errors.py` | Sai `ZoteroApiError` (l.18-24). |
| `src/par/domains/paper/__init__.py` | Sai a linha `annotations` da docstring (l.10). |
| `src/par/mcp_server.py` | Sai a tool `paper_sync_all` (l.229-234). O servidor fica com 10 tools; `MUTATING_TOOLS` não muda. Docstring do módulo: l.30 "(7 tools, uma delas mutante" vira "(6 tools, uma delas mutante"; l.33 "(`mcp__prumo__paper_find`)" vira "(`mcp__plugin_par_prumo__paper_find`)". |
| `src/par/core/note_paths.py` | Sai `child_note_path` (l.45-47). A docstring (l.7-8) passa a dizer: "`_annotations.md` — legado: só o `prumo paper migrate-layout` grava, ao separar o bloco de anotações de uma nota plana antiga; `note__*.md` — legado, só leitura". `annotations_path` fica. |
| `src/par/domains/paper/migrate.py` | Sem mudança (decisão do B9). |
| `src/par/domains/paper/lint.py` | Sai a regra 7, `duplicate_item_key` (docstring l.12; código l.159-176). |
| `src/par/core/deps.py` | Saem `_zotero_api_root`, `zotero_local_api_up`, `_zotero_host_port` e `_zotero_version_header`. Entra `_bbt_probe()` (abaixo). A linha `zotero` segue o B10, com o `required_by` novo e as mensagens de Erros. A docstring do módulo (l.7-8) passa a "Zotero + Better BibTeX — citation keys, auto-export do `.bib` (`paper connect`) e vínculo das citações do docx". |
| `src/par/domains/paper/connect.py` | `_http_post_json` próprio (POST JSON com `urllib`, timeout de 10 s, mesmo nome de seam). `_rpc` posta em `bbt_rpc_url()`. `_OFFLINE_MSG` vira `_offline_msg()` (Erros). Mensagem nova da Guarda 1 (Erros). Entra a constante `EXPORT_PENDING_HINT` (E17), que o `connect_command` imprime quando `exported=False`. Docstring do módulo (l.33-36): o seam deixa de ser "o mesmo de `zotero.py`". Docstring de `connect_collection` (l.525-526): "reconectar às cegas duplicaria o autoexport já configurado" vira "conectar poderia sobrescrever, com a coleção, um `.bib` que já tem entradas". Docstring de `_http_post_json`: sai a menção a `zotero._http_post_json`. |
| `skills/paper/modes/library.md` | `argument-hint` (l.4) e o enum de `operation` (l.12) sem `sync-annotations \| sync-notes \| sync-all`. Frase (l.17): "o que eu anotei no Zotero sobre este paper". Árvore (l.66-67): `_annotations.md` e `note__*` marcados "legado, não gerado". §1b–1d (l.124-152) dão lugar à seção de roteamento (abaixo). §8, passo 6: "Se `exported` vier `false`, repasse a dica do comando (o BBT pode levar alguns segundos; BBT ≥ 9.0.65)". Regra da Guarda 1 (l.256): "o comando recusa conectar quando o `.bib` já tem entradas, para não sobrescrevê-lo; se ele já vem do Better BibTeX, siga com `prumo paper sync`". |
| `skills/paper/SKILL.md` | Blocos gerados (l.7 e l.32) regerados por `gen_indexes.py`. Nunca à mão. |
| `README.md` | A linha do Zotero vira: "**Zotero 9+ e Better BibTeX ≥ 9.0.65** — `paper connect`; vínculo das citações no `write export --to docx` — abra o Zotero com o Better BibTeX instalado (`.xpi`). O PAR fala com ele em `127.0.0.1:23119` e não precisa da opção 'Allow other applications'. Sem o Zotero, o resto do PAR funciona, e o docx sai com as citações sem vínculo." |
| `ARCHITECTURE.md` | Diagrama (l.29-32): saem `sync-annotations`, `sync-notes` e `sync-all`. l.138: layout α = `_meta` e `_extract` (`_annotations` e `note__*` como legado legível; ADR-0037). |
| `docs/Research Project Structure.md` | l.61: sai `_annotations.md` da lista; nota "legado, se existir". |
| `docs/onboarding-pesquisador.md` | §4: "Zotero 9 ou mais novo, com o Better BibTeX 9.0.65 ou mais novo (versões anteriores não exportam itens novos com a janela do Zotero fechada)". |
| `templates/pj_base/docs/references/_references.bib` | Cabeçalho reescrito. A **1ª linha fica idêntica** (`% Bibliografia do projeto — formato Better BibTeX (BBT).`), porque `connect.bib_is_placeholder` (`connect.py:496-510`) exige que ela comece com `% Bibliografia do projeto`. As linhas "Zotero 7" e "Keep updated" saem; entra "Zotero 9+ com Better BibTeX ≥ 9.0.65; peça ao agente 'conecta minha coleção <nome>' (roda `prumo paper connect`)". O `update` não reflui esse arquivo em projetos existentes (`scaffold.py` só compara conteúdo em `.claude/rules/`). |
| `templates/pj_base/docs/project_guide.md` | l.24: "mantido pelo Better BibTeX com 'Keep updated'" vira "mantido pelo Better BibTeX (registrado por `prumo paper connect`)". A l.20 muda na 0.70.3 (piso do pandoc); as outras edições desse arquivo são da Spec A. |
| `skills/start/SKILL.md` | Item 3 da trilha guiada (texto abaixo), dentro da reescrita da trilha feita pela Spec A. A trilha é texto humano, fora dos blocos gerados. |
| `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md` | Frontmatter: `status: approved` vira `status: superseded`, com `superseded-by: "[[2026-10-02-ponte-zotero-minima-design]]"` (mesmo formato de `2026-04-29-prumo-scientific-writer-design.md`). Logo abaixo do título, a nota de uma linha "> Aposentado pela ADR-0037 (0.71.0): `sync-notes` e as notas-filhas saem do PAR." `docs/_index.md` regenerado com `uv run python .github/scripts/gen_indexes.py`. |

`docs/actions-by-context.md` (l.72-83 citam os comandos aposentados) é apagado inteiro pela Spec A
na mesma 0.71.0. `ROADMAP.md:14` (histórico da 0.61.0) fica.

`src/par/core/deps.py`, a sonda única:

```python
@dataclass(frozen=True)
class _BbtProbe:
    status: int | None  # None = nada escutando
    zotero_version: str | None  # header X-Zotero-Version, presente até no 404


def _bbt_probe(timeout: float = 2.0) -> _BbtProbe:
    """GET {zotero_base()}/better-bibtex/cayw?probe=true. 200 = BBT carregado
    ('ready' ou 'starting'); 404 = Zotero sem BBT ou BBT ainda iniciando. Não
    depende da API local. Seam testável."""
    url = f"{zotero_base()}/better-bibtex/cayw?probe=true"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return _BbtProbe(int(resp.status), resp.headers.get("X-Zotero-Version"))
    except urllib.error.HTTPError as exc:
        headers = exc.headers
        return _BbtProbe(int(exc.code), headers.get("X-Zotero-Version") if headers else None)
    except (OSError, http.client.HTTPException):
        return _BbtProbe(None, None)
```

**Item 3 da trilha do `/par:start`** (`skills/start/SKILL.md`; o resto da trilha é da Spec A). O
`prumo paper sync` roda offline, por isso o item não diz que o Zotero serve para sincronizar:

```markdown
3. **Zotero:** Zotero 9 ou mais novo com o Better BibTeX ≥ 9.0.65 (`.xpi`), app aberto. Serve para conectar a coleção (uma vez) e manter o `.bib` atualizado; no export docx, vincula as citações se estiver aberto. Não bloqueia escrita nem julgamento, e não é preciso ligar "Allow other applications".
```

**Seção de roteamento em `skills/paper/modes/library.md`** (substitui as §1b–1d):

```markdown
### Anotações, notas e a biblioteca inteira do Zotero (fora do PAR)

O PAR trabalha com o `.bib` do projeto e com os PDFs de `docs/references/pdfs/`. Ficam fora dele: destaques, comentários e notas-filhas do Zotero, busca na biblioteca inteira e cadastro de itens.

1. Se esta sessão tiver uma dessas ferramentas, use-a:
   - Com a skill `zotero-cli`: do citekey ao item, `zotero-cli --json search --mode citekey <citekey>`; depois `zotero-cli --json annotations list --item-key <KEY>` ou `zotero-cli --json notes list --item-key <KEY>`.
   - Com as tools `mcp__zotero__*`: use as equivalentes de busca por citekey, de anotações e de notas do item, só de leitura.
   - Cada comando ou tool pede permissão; não tente evitar essa confirmação.
2. Escrever no Zotero (adicionar por DOI, notas, tags, anotações) só quando o usuário pedir com as palavras dele.
   - Se aparecer "Cannot perform write operations", repasse: é preciso o Zotero 10 e `zotero-mcp authorize-local`.
   - Nunca sugira chave da Web API do Zotero.
3. Sem essas ferramentas, diga em 1 linha: "Isso fica fora do PAR: o PAR não lê destaques nem notas do Zotero." Depois ofereça ler o PDF do projeto e aponte a seção "Perguntar ao seu Zotero" de https://github.com/raphaelfh/prumo-assistant-for-researcher/blob/main/docs/onboarding-pesquisador.md. Não instale nada.
4. Para adicionar um paper: Zotero Connector no navegador, ou a varinha "Add Item by Identifier" no Zotero. O Better BibTeX atualiza o `.bib`; depois rode `prumo paper sync`.
5. Os `_annotations.md` e `note__*.md` antigos continuam onde estão e podem ser lidos. Nenhum comando os atualiza; só o `prumo paper migrate-layout` ainda grava `_annotations.md`, ao separar o bloco de anotações de uma nota plana antiga.
```

**Receita do onboarding**, a § nova de `docs/onboarding-pesquisador.md`, que substitui "Busca
semântica no seu acervo do Zotero, sem terminal" (l.174-180). É só documentação e pode sair já,
sem bump:

```markdown
### Perguntar ao seu Zotero (opcional, ferramenta de terceiros)

O PAR não lê destaques nem notas do Zotero, nem busca na biblioteca inteira. A ferramenta [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp) (licença MIT) faz isso. **Ela não foi validada neste piloto** e muda com frequência (12 versões entre agosto e setembro de 2026). Para a bibliografia do projeto, continue usando `/par:paper`.

**No Claude Code (terminal, aba Code do app ou IDE).** Rode no terminal, ou cole cada linha para o agente rodar com a sua permissão:

1. No Zotero 7 ou mais novo: Settings → Advanced → marque "Allow other applications on this computer to communicate with Zotero". Essa ferramenta exige essa opção.
2. `uv tool install zotero-mcp-server`
3. `zotero-mcp install-skill --target claude-user` (sem `--target`, o instalador grava também dentro do projeto).
4. Abra uma sessão nova e pergunte "o que eu anotei no paper X?". Cada comando pede permissão; aprove os de leitura.

Não é preciso rodar `zotero-mcp setup`: sem chave, a ferramenta usa o Zotero local.
Para escrever no Zotero (precisa do Zotero 10 ou mais novo): `zotero-mcp authorize-local` e clique em "Always Allow" no Zotero.
Para atualizar: `zotero-mcp update` e depois `zotero-mcp install-skill --target claude-user --force` (o update não atualiza a skill).

**No chat do app Claude (fora da aba Code).** No terminal: `zotero-mcp setup --skip-semantic-search`; depois reinicie o app. Isso registra 38 ferramentas, que custam cerca de 13 mil tokens em toda mensagem. No Cowork, não testado.

**Privacidade**
- O que o Claude lê (anotações, texto de PDF) entra na conversa. Não use em biblioteca com documento identificável de paciente.
- Nunca configure `ZOTERO_API_KEY`: o modo local basta, e a chave da Web API dá acesso à biblioteca inteira, PDFs incluídos.
- Não instale o extra `[semantic]`. Se um dia instalar, use só o modelo local padrão: as opções OpenAI e Gemini mandam texto para fora.
- Escritas vão para o Zotero e, com o sync ligado, para o zotero.org e seus outros dispositivos.
- A ferramenta lê o banco do Zotero (`zotero.sqlite`) direto, em modo `immutable=1`, e só faz uma cópia temporária privada (apagada ao sair) quando há escritas pendentes no WAL. Com o Zotero aberto, esse modo pode devolver dado inconsistente sem avisar: confira no Zotero o que for citar.
```

## Fluxo

1. **Setup (uma vez).** Zotero 9+ e BBT ≥ 9.0.65 (`.xpi`), com o Zotero aberto. "Conecta minha
   coleção X" roda `prumo paper connect`, o BBT escreve o `.bib`, e "sincroniza a bibliografia"
   roda `prumo paper sync`. Pandoc: zero passos com Zettlr no Mac; os demais recebem a dica do
   doctor uma vez.
2. **Dia a dia.** A pesquisadora adiciona pelo Connector ou pela varinha. O BBT atualiza o `.bib`,
   e `sync`, `find`, `lint` e o Zettlr rodam offline.
3. **Export docx.** `.bib`, citeproc, `crossref.lua` e `zotero_live_docx.lua`, com o lookup BBT de
   2 s.
   - Com vínculo, os campos ficam religáveis.
   - Sem vínculo, o export funciona igual, e sai um aviso por causa com o comando de refazer.
   - O docx já sai formatado, com `ZOTERO_PREF`; não precisa de Refresh.
   - No `export`, sai a nota de primeiro uso; no `compose`, só o aviso.
4. **Rodada de revisão (D6 do dono).** Export, revisão do coautor sem os botões do Zotero,
   `review ingest`, `reconcile`, `review apply`. Se houve Refresh ou Add/Edit Citation, o ingest
   recusa com a mensagem específica antes das outras checagens de conservação de citações
   (`check_conservation`). Os preflights anteriores do ingest (estrutura do docx, sidecars, fonte
   alterada, Guarda A) continuam na frente.
5. **"O que eu anotei".** O modo `library` roteia para o zotero-cli, se houver. Sem ele, uma linha
   de fallback e a oferta de ler o PDF do projeto.
6. **Doctor.** Linha `zotero`: uma sonda `cayw` (0.71.0). Linha `pandoc`: `pandoc_path()` e a
   versão (0.70.3).

## Erros

Todas as mensagens em pt-BR, com o comando de correção dentro (`.claude/rules/code.md`). `{redo}`
é `prumo write export {página} --to docx --force` ou
`prumo write compose --index {índice} --to docx --force`, acrescido das opções que a chamada
recebeu (`--style`, `--bib`, `--out-dir`, `--reference-doc`; regra no B1). `{n}` é o número de
citekeys distintas com `uris` vazio no OOXML. `{base}` é `zotero_base()`.

| # | Situação | Onde | Mensagem |
|---|---|---|---|
| E1 | Lookup sem resposta (Zotero fechado, sem BBT, iniciando, travado) | aviso do export/compose (0.70.3) | "Não consegui falar com o Better BibTeX (Zotero fechado, sem o Better BibTeX, ainda iniciando ou sem resposta em 2 s): {n} citekey(s) saíram sem vínculo com a sua biblioteca. O docx abre, e o Refresh do Word funciona com os dados embutidos. Para vincular, abra o Zotero e rode: {redo}" |
| E2 | E1 dentro do sandbox do Claude Code (`SANDBOX_RUNTIME=1`) | aviso do export/compose (0.70.3) | "O sandbox do Claude Code não deixou o export falar com o Zotero em {base}: {n} citekey(s) saíram sem vínculo com a sua biblioteca (o docx abre e o Refresh funciona). Para vincular, peça para repetir fora do sandbox (o Claude pede permissão): {redo}. Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`." |
| E3 | BBT respondeu erro JSON-RPC (ou HTTP ≠ 404) | aviso do export/compose (0.70.3) | "O Better BibTeX recusou a consulta ({detalhe}): {n} citekey(s) saíram sem vínculo com a sua biblioteca. Causas comuns: `zotero.library` no frontmatter com um nome que não existe no Zotero, ou Better BibTeX anterior a 9.0.65 com a janela principal do Zotero fechada. Corrija (Tools → Plugins atualiza o Better BibTeX; abra a janela do Zotero) e rode: {redo}" |
| E4 | BBT respondeu, mas sem algumas chaves | aviso do export/compose (0.70.3) | "{n} citekey(s) não foram achadas pelo Better BibTeX na biblioteca consultada ({biblioteca, ou 'My Library, a padrão'}): {até 5 chaves, depois '…'}. Saem sem vínculo. Se estão numa biblioteca de grupo, ponha `zotero: {library: "<nome do grupo>"}` no frontmatter e rode: {redo}" |
| E5 | Ingest de docx com campos reescritos pelo Zotero | `check_conservation` (0.70.3) | "{n} campo(s) de citação deste docx foram reescritos pelo plugin do Zotero no Word (Refresh ou Add/Edit Citation) e perderam as marcas do PAR: o ingest não consegue parear as citações. Peça ao coautor a versão de antes de usar esses botões e rode o ingest nela. Ou guarde a cópia do coautor fora de build/exports/, re-exporte com `prumo write export {page} --to docx --force` (acrescente as mesmas opções do export original, como `--style` ou `--reference-doc`) e peça uma revisão nova sem os botões do Zotero." O citemap não guarda as opções do export, por isso a mensagem pede para repeti-las. |
| E6 | Nota de 1º uso | `write export --to docx` (0.70.3) | "Primeiro uso no Word: o docx já sai com citações e bibliografia formatadas e com as preferências do Zotero embutidas, então não precisa de Refresh. Se ele for para revisão com `prumo write review ingest`, peça ao coautor para não usar os botões do Zotero (Refresh, Add/Edit Citation) nesse arquivo: o Zotero reescreve os campos de citação e o ingest recusa o arquivo." |
| E7 | Pandoc ausente no export | `ToolNotFoundError` (0.70.3) | "pandoc não encontrado (nem no PATH nem dentro do Zettlr.app). Instale o pandoc 3.8.2 ou mais novo (macOS: `brew install pandoc`; Linux: pacote oficial em https://github.com/jgm/pandoc/releases) e confira com: prumo doctor" |
| E8 | Doctor: pandoc ausente | linha `pandoc` (0.70.3) | detalhe "pandoc não encontrado (nem no PATH nem no Zettlr.app)"; dica "Instale o pandoc 3.8.2 ou mais novo. macOS: `brew install pandoc` (ou instale o Zettlr, que já traz um). Linux: pacote oficial em https://github.com/jgm/pandoc/releases (o do apt costuma ser antigo). Depois rode: prumo doctor" |
| E9 | Doctor: pandoc antigo | linha `pandoc` (0.70.3) | detalhe "pandoc {v} em {caminho}" (ou "pandoc {v} do Zettlr.app"); dica "O pandoc {v} é anterior a 3.8.2: tabelas numeradas (`{#tbl:…}`) falham no export. Atualize (macOS: `brew upgrade pandoc`; Linux: pacote oficial em https://github.com/jgm/pandoc/releases) e rode: prumo doctor" |
| E10 | Doctor: nada escutando | linha `zotero` (0.71.0) | detalhe "nada escutando em {base}"; dica "Abra o Zotero 9 ou mais novo, com o Better BibTeX, e rode: prumo doctor. Só o `prumo paper connect` e o vínculo das citações do docx precisam dele; o resto do PAR funciona sem ele." |
| E11 | E10 dentro do sandbox | linha `zotero` (0.71.0) | detalhe "o sandbox do Claude Code não deixa este comando falar com o Zotero em {base}"; dica "Peça para repetir fora do sandbox (o Claude pede permissão): prumo doctor. Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`." |
| E12 | Doctor: 404 | linha `zotero` (0.71.0) | detalhe "Zotero {v} aberto em {base}, mas o Better BibTeX não respondeu (HTTP 404)"; dica "Sem Better BibTeX (ou ainda iniciando — aguarde e rode prumo doctor). Para instalar: baixe o .xpi em https://github.com/retorquere/zotero-better-bibtex/releases e, no Zotero, Tools → Plugins → ⚙ → Install Plugin From File. Depois rode: prumo doctor" |
| E13 | Doctor: outro HTTP | linha `zotero` (0.71.0) | detalhe "o Zotero respondeu HTTP {code} em /better-bibtex/cayw"; dica "Reinicie o Zotero e rode: prumo doctor" |
| E14 | Doctor: Zotero < 9 | linha `zotero` (texto atual de `deps.py:166-175`, mantido) | "Atualize para o Zotero 9+: baixe em https://www.zotero.org/download, instale e reabra o app. Depois atualize o Better BibTeX em Tools → Plugins se ele avisar (o BBT acompanha o major do Zotero)." |
| E15 | `connect` sem resposta | `ZoteroOfflineError` (0.71.0) | "O Zotero não respondeu em {base}. Abra o Zotero (com o Better BibTeX), confira com `prumo doctor` e repita o comando." No sandbox: "O sandbox do Claude Code não deixa o `prumo paper connect` falar com o Zotero em {base}. Peça para repetir o comando fora do sandbox (o Claude pede permissão). Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em `sandbox.excludedCommands` no `~/.claude/settings.json`." |
| E16 | Guarda 1 | `AlreadyConnectedError` (0.71.0) | "docs/references/_references.bib já tem entradas: conectar agora poderia sobrescrevê-lo com a coleção. Se ele já vem do Better BibTeX (confira no Zotero: Settings → Better BibTeX → Automatic export), rode: prumo paper sync" |
| E17 | `connect` com `exported=False` | info da CLI, `EXPORT_PENDING_HINT` (0.71.0) | "O Better BibTeX ainda não gravou o .bib (pode levar alguns segundos). Se ele não aparecer, atualize o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins; as versões anteriores não exportam itens novos com a janela do Zotero fechada), confira em Settings → Better BibTeX → Automatic export e rode: prumo paper sync" |
| E18 | "O que eu anotei" sem zotero-cli | texto do modo `library` (0.71.0) | "Isso fica fora do PAR: o PAR não lê destaques nem notas do Zotero." Em seguida, a oferta de ler o PDF do projeto. |

Um comando aposentado (`prumo paper sync-all`) recebe o "No such command" do Typer. Não entra stub:
nenhuma skill o cita depois da 0.71.0, e a troca vai no CHANGELOG.

## Superfícies

A matriz completa de superfícies é da Spec A. Para a ponte Zotero:

| Superfície | `connect` e vínculo do docx | "O que eu anotei" (terceiro) |
|---|---|---|
| Claude Code local (terminal, aba Code, IDE), macOS ou Linux | sim | Rota A |
| Bash sob o sandbox do Claude Code | não alcança o Zotero; mensagens E2, E11 e E15. As tools MCP, que rodam fora do sandbox, alcançam | Rota A, fora do sandbox |
| Chat do app Claude | não (sem CLI; Spec A) | Rota B, não validada |
| Cowork | não suportado nem testado; use a aba Code (Spec A) | não testado |
| SSH, WSL, Windows | não suportado (Spec A) | — |

## Testes

### 0.70.3

- **`tests/unit/write/test_export_zotero_link.py` (novo).**
  - `fetch_bbt_zotero_metadata`, com `urlopen` mockado:
    - `URLError`, timeout e HTTP 404 dão `failure="unreachable"`;
    - `"error"` no corpo e HTTP 500 dão `failure="rpc_error"`, com o `detail` do BBT;
    - sucesso devolve os itens;
    - os params são `[keys, True]` sem `library` e `[keys, True, "Lab"]` com;
    - o `timeout` chega como 2.0;
    - a URL segue `PRUMO_ZOTERO_BASE`.
  - `docx_link_warning`, sobre docx mínimo montado com o helper de `test_export_docx_validation.py`:
    - `None` quando todas as citações têm `uris` preenchido;
    - E1; E2 com `SANDBOX_RUNTIME=1` (cita `sandbox.excludedCommands`); E3 citando 9.0.65 e
      `zotero.library`; E4 listando as chaves e a biblioteca;
    - o `{redo}` aparece em todas;
    - uma chave sem vínculo citada em duas ocorrências dá `n == 1` (citekeys distintas).
  - `export()` com `failure="unreachable"` termina sem exceção e chama `on_warning` uma vez.
  - `export(..., style="vancouver", reference_doc=p)` com `failure="unreachable"`: o `{redo}` do
    aviso contém `--style vancouver` e `--reference-doc`; com os defaults, o `{redo}` não tem
    `--style`.
  - `compose()` com `failure="unreachable"` termina sem exceção e chama `on_warning` uma vez, com
    `prumo write compose --index` no texto.
  - `_check_pandoc()`: com `par.core.deps._binary_on_path` devolvendo `None` e o
    `_ZETTLR_PANDOC` inexistente do `conftest`, levanta `ToolNotFoundError` com o E7 ("3.8.2" e
    "prumo doctor"); com `_ZETTLR_PANDOC` apontando para um executável em `tmp_path`, devolve esse
    caminho.
  - **Lua com pandoc real.** No nível do módulo, `_PANDOC = pandoc_path()` (resolvido uma vez, na
    coleta, antes das fixtures) e `skipif(_PANDOC is None)`. O teste chama
    `_build_pandoc_cmd(pandoc_bin=_PANDOC, …)` e usa o mesmo `_PANDOC` no
    `--print-default-data-file default.csl`: não copia o `"pandoc"` literal de
    `test_export_crossref.py`, para que a condição de skip e o binário executado sejam o mesmo.
    Casos: `[@linked2020]` com lookup de URI e `[@unlinked2021]` sem lookup. No
    `word/document.xml` decodificado, os dois `uris` são `list`:
    `["http://zotero.org/users/local/abcd/items/ABCD1234"]` e `[]`. No CI roda no pandoc 3.8.2 (o
    piso); na máquina do dono, no 3.10.1 do Zettlr.
- **`tests/unit/write/test_export_crossref.py`.** `requires_pandoc` passa a
  `skipif(_PANDOC is None)`, com `_PANDOC = pandoc_path()` no nível do módulo; `_cmd` passa
  `pandoc_bin=_PANDOC` e `_run_docx` roda `[_PANDOC, "--print-default-data-file", "default.csl"]`.
  Assim os testes de pipeline real também rodam na máquina do dono, onde o pandoc só existe dentro
  do Zettlr.app.
- **`tests/unit/conftest.py`.** Fixture `autouse` nova, `_no_real_pandoc`: faz monkeypatch de
  `par.core.deps._ZETTLR_PANDOC` para um caminho inexistente em `tmp_path` e de
  `par.core.deps._pandoc_version` para `lambda path, timeout=5.0: None`. Com isso nenhum teste que
  chame `check_external_deps()` sem mocks (doctor em `test_cli_doctor.py` l.146-203, em
  `test_cli_init.py` l.153 e l.181, e `test_doctor_flags_zotero_absent_when_local_api_is_disabled`
  em `test_deps.py`) executa um pandoc real: nem o do Zettlr.app na máquina do dono, nem o 3.8.2
  do CI (`.claude/rules/code.md`: dependência externa só nos seams). Os testes da linha `pandoc` e
  de `pandoc_path()` sobrescrevem os dois.
- **`tests/unit/write/test_review_reader.py`.** Três testes de `check_conservation`:
  - todos os `occ_id` vazios dão E5 (e não "occ_id duplicado");
  - um único vazio entre vários dá E5;
  - a mensagem cita "Refresh", "Add/Edit Citation" e `prumo write export {citemap.page} --to docx --force`.
- **`tests/unit/write/test_cli.py`.**
  - Saem:
    - o caso parametrizado `export-zotero-down`;
    - `test_write_compose_docx_prints_first_use_note` (l.368-378), que afirma o oposto do novo
      contrato e vira o teste "compose não imprime E6" abaixo.
  - Entram:
    - `write export --to docx` imprime E6 e não "use Zotero → Refresh";
    - `write compose --to docx` não imprime E6 (`"Primeiro uso no Word" not in result.output`);
    - aviso vindo de `on_warning` sai em `console.warn` e em `warnings` no `--json`. O teste usa
      um `export.export` falso que chama `kw["on_warning"]("…")`, o mesmo padrão de monkeypatch
      dos testes atuais do arquivo.
  - Docstring de `_stub_pandoc_seams` (l.283-286): sai "`--to html` evita a checagem de BBT (só
    exigida para docx)"; fica "`--to html` evita a validação estrutural do zip docx".
- **`tests/unit/write/test_errors.py`.** Sai `export.ZoteroNotRunningError` de `_WRITE_LEAVES`.
- **`tests/unit/write/test_export_docx_validation.py`.** `_patch_export_seams`: sai o monkeypatch de
  `_check_bbt_running`; o de `fetch_bbt_zotero_metadata` vira `lambda keys, lib, **kw: BbtLookup({})`;
  `_check_pandoc` continua mockado.
- **`tests/unit/write/test_export_pandoc_cmd.py`.** Saem os imports dos dois helpers (l.29 e 31) e os
  testes `test_zotero_lua_filter_resolves_to_real_file`,
  `test_zotero_bibliography_docx_filter_resolves_to_real_file` e
  `test_docx_does_not_chain_legacy_bbt_filters`.
- **`tests/unit/core/test_deps.py`.**
  - `zotero_base()`: default `http://127.0.0.1:23119` e override por env. `bbt_rpc_url()` segue a
    base.
  - `pandoc_path()`: o PATH vence; com o PATH vazio, um `_ZETTLR_PANDOC` executável em `tmp_path`;
    `None` sem nenhum.
  - Linha `pandoc`: presente com 3.10.1; reprovada com 3.1.2 (dica com 3.8.2); presente com versão
    `None` (fail-safe); ausente com dica de brew, de Linux e com 3.8.2.
  - `_pandoc_version` em si, com `subprocess.run` mockado: primeira linha `pandoc 3.10.1` dá
    `"3.10.1"`; `FileNotFoundError` e timeout dão `None`.
  - `in_claude_sandbox()`: `True` com `SANDBOX_RUNTIME=1`; `False` sem a variável e com outro
    valor (`monkeypatch.setenv`/`delenv`).
  - Os testes atuais do arquivo seguem sem pandoc real pela fixture `autouse` do `conftest.py`
    (acima). Os testes do doctor em `test_cli_doctor.py` que trocam `check_external_deps` inteiro
    não mudam; os que chamam o doctor sem mock ficam cobertos pela mesma fixture.
- **`tests/unit/core/test_skills.py`.** Nenhum `mcp__prumo__` em `skills/**`. A Spec A estende este
  mesmo teste a `mcp__qmd__`.
- **`tests/unit/paper/test_zotero_client.py`.** Sem mudança: os testes de base URL continuam
  verdes pela delegação.

### 0.71.0

- **Apagados:** `tests/unit/paper/test_zotero.py` (348 linhas), `test_zotero_notes.py` (192),
  `test_sync_all.py` (78) e `test_zotero_client.py` (562; a cobertura de base URL já está em
  `test_deps` desde a 0.70.3).
- **`tests/unit/paper/test_cli.py`.**
  - Saem `test_paper_sync_notes_cli_writes_files` (l.82-113) e
    `test_paper_sync_all_cli_runs_offline_sync` (l.184-219).
  - `test_paper_connect_export_pendente_avisa` (l.317-336) deixa de afirmar `"instantes"`, que o
    E17 não tem, e passa a afirmar `connect.EXPORT_PENDING_HINT in result.output` (o texto cita
    "9.0.65" e "prumo paper sync").
  - Entra um teste parametrizado: `prumo paper --help` não lista `sync-annotations`, `sync-notes`
    nem `sync-all`.
- **`tests/unit/test_mcp_server.py`.** Sai `"paper_sync_all"` do conjunto esperado (l.205); o
  servidor tem 10 tools.
- **`tests/unit/core/test_note_paths.py`.** Saem o import de `child_note_path` (l.9) e o teste das
  l.37-47; `test_annotations_path` fica.
- **`tests/unit/paper/test_lint.py`.** Saem `test_lint_flags_duplicate_item_key` (l.120-137) e
  `test_lint_no_duplicate_when_item_keys_distinct` (l.172-185).
- **`tests/unit/paper/test_migrate.py`.** Sem mudança (B9).
- **`tests/unit/core/test_deps.py`.**
  - Saem os testes de `_zotero_api_root` e de `zotero_local_api_up` (e o import de
    `zotero_local_api_up`, l.12).
  - Todo `patch("par.core.deps._zotero_api_root", …)` e `patch("par.core.deps._zotero_version_header", …)`
    que sobra, inclusive nos testes de qmd (l.17-18 e l.28-29), vira
    `patch("par.core.deps._bbt_probe", return_value=_BbtProbe(None, None))` (ou o estado que o
    teste precisa). Fazer patch de um atributo apagado levanta `AttributeError`, então apagar o
    teste não basta: os de qmd ficam e trocam o alvo.
  - Entram os estados de `_bbt_probe` (None, 404, 500, 200), com `X-Zotero-Version` lido do 200 e
    do 404.
  - Na linha `zotero`, na ordem do B10: E10, E11 (`SANDBOX_RUNTIME=1`), E12, E13, presente com 200
    e major ≥ 9, reprovada com major 8, **404 com `X-Zotero-Version: 8.0.1` dá E14** (e não E12),
    fail-safe com versão `None`; `required_by` novo.
- **`tests/unit/paper/test_connect.py`.**
  - Os testes atuais ficam (o seam é o mesmo), salvo `test_zotero_fechado` (l.176): o
    `match="abra o Zotero"` passa a `match="Abra o Zotero"`, porque o E15 abre a frase com
    maiúscula e o `match` diferencia caixa. O de `AlreadyConnectedError` continua casando
    "Automatic export".
  - Entram:
    - `_offline_msg()` com `PRUMO_ZOTERO_BASE` e a variante do sandbox (`SANDBOX_RUNTIME=1`,
      com "sandbox" e `sandbox.excludedCommands` no texto);
    - `_http_post_json` posta em `bbt_rpc_url()` (`urlopen` mockado);
    - a Guarda 1 cita `prumo paper sync`.
- **`tests/unit/test_cli_doctor.py`** (l.46) e **`tests/unit/core/test_cli_op.py`** (docstring da
  l.49): o exemplo `paper sync-annotations` vira `paper connect`.
- **`tests/unit/test_pj_base_integration.py`:** `connect.bib_is_placeholder` é verdadeiro num
  projeto recém-criado a partir do `_references.bib` novo do template.

## ADRs e emendas

**ADR-0037**, nova, aceita com a 0.70.3, em `docs/adr/adr-0037-ponte-zotero-minima.md`:

```markdown
# ADR-0037 — Ponte Zotero mínima: anotações e notas saem do PAR; Better BibTeX só no connect e no lookup do docx

- Status: aceito
- Data: 2026-10-02
- Origem: [[2026-10-02-ponte-zotero-minima-design]]; emenda a ADR-0008, a ADR-0020 e a ADR-0026; substitui as linhas "Zotero/BBT fechado — caminho canônico" e "Pandoc embutido do Zettlr < 3.0" da tabela de degradações de [[2026-07-22-zettlr-front-design]]

## Contexto

O PAR falava com o Zotero por quatro caminhos: auto-export do `.bib`, lookup do docx, anotações e notas pela API local, e a sonda do doctor. A auditoria de 2026-08-23 (A6) achou 0 `_annotations.md` e 0 `note__*.md` em 14 projetos, e a recontagem de 2026-10, 0 em 15. Esse pipeline era o único consumidor da API local, e por causa dele o doctor exigia o toggle "Allow other applications". O docx tinha três defeitos que atingiam todo export padrão: `library=""` fazia o Better BibTeX recusar o lookup em silêncio; sem `uris`, o Refresh do Zotero no Word lançava TypeError; e o gate exigia o Zotero aberto para um lookup descartado. O Refresh também reescreve os campos e apaga as marcas do PAR, e o ingest recusava esse docx com uma mensagem enganosa.

## Decisão

1. Saem `paper sync-annotations`, `sync-notes` e `sync-all`, a tool MCP `paper_sync_all` (o servidor fica com 10 tools, 6 de `paper`), os re-exports da API, `ZoteroApiError`, `note_paths.child_note_path` e a regra `duplicate_item_key`. Arquivos legados continuam legíveis. O `migrate-layout` continua separando o bloco de anotações de uma nota plana antiga em `_annotations.md`. A spec [[2026-05-03-zotero-notes-integration-design]], que desenhou o `sync-notes`, passa a `superseded` na 0.71.0.
2. O Better BibTeX fica só onde é a única fonte: citation keys, `autoexport.add` no `connect` (guardas da ADR-0020 e da ADR-0028 intactas) e `item.pandoc_filter` no export docx. A API local `/api/*` não é usada. O toggle não é exigido. Não existe `core/zotero_local.py`: a API local exige o toggle e um módulo novo; o vínculo não é o motivo (`users/0` também religa).
3. O lookup do docx é melhor-esforço (2 s), sem gate. O terceiro parâmetro só vai quando há `zotero.library`. Cada citação leva `uris`, sempre como array JSON (`lookup.uri and { lookup.uri } or json.decode('[]')`). As citações sem vínculo geram um aviso por causa (inalcançável, sandbox do Claude Code, erro JSON-RPC, chave ausente), com o comando de refazer, que repete as opções da chamada original.
4. Contrato da rodada de revisão: sem Refresh nem Add/Edit Citation do Zotero no docx em revisão. A nota de primeiro uso diz isso, e o ingest recusa com mensagem própria qualquer campo sem `prumoOcc`, antes das demais checagens de conservação. A tolerância fica adiada (ROADMAP).
5. Base URL e URL do JSON-RPC únicas em `core/deps.py`, o que quita a dívida da ADR-0007 sem emendá-la. O doctor usa uma única sonda (`GET /better-bibtex/cayw?probe=true`, com `X-Zotero-Version` lido da mesma resposta); o 404 vira "sem Better BibTeX (ou ainda iniciando)". O piso do Better BibTeX, 9.0.65 (commits 051d0843 e 10022a3d), fica em documentação e mensagens, sem checagem de versão.
6. Pandoc: `core/deps.pandoc_path()` (PATH e depois o pandoc do Zettlr.app), a linha `pandoc` no doctor e o piso único 3.8.2, exigido pelas tabelas rotuladas do `crossref.lua` (ADR-0035). Este piso estava implícito na ADR-0035 e fica registrado aqui; a linha `pandoc` do doctor é nova.
7. Emendas:
   - **ADR-0008:** o layout α canônico passa a `{_meta.md, _extract.md}`. `_annotations.md` e `note__*.md` são legado legível; só o `migrate-layout` ainda grava `_annotations.md`.
   - **ADR-0020:** a premissa "reconectar duplicaria o autoexport" é falsa. O BBT guarda um job por caminho, `add` com a mesma coleção só reagenda, e com parâmetros diferentes recusa, a menos que `replace=true`. A Guarda 1 fica, pelo motivo real: não sobrescrever um `.bib` que já tem entradas. `--replace` segue fora, agora com trigger. A versão do Zotero passa a vir do header da sonda do BBT, não da API local. A recomendação de MCP de terceiro passa de `cookjohn/zotero-mcp` a `54yyyu/zotero-mcp`, só em documentação e marcada "não validada". O `getCollection(collection, true)` do BBT continua criando o caminho antes de checar, por isso as guardas anti-fantasma continuam necessárias.
   - **ADR-0026:** sai `paper_sync_all`; 6 tools `paper`, 10 no total.

## Consequências

O export docx deixa de exigir o Zotero aberto, e o Refresh do coautor não quebra mais. A pesquisadora perde três comandos que nunca geraram arquivo e o passo do toggle. "O que eu anotei" passa a depender de uma ferramenta opcional de terceiros, roteada só por texto. O PAR não tem código nem permissão pré-aprovada para ela, e ela nunca entra no `.mcp.json`. A aposentadoria entra na 0.71.0, o evento breaking único junto com a ADR-0038. As correções do docx entram na 0.70.3. Uma rodada de revisão em que o coautor use os botões do Zotero precisa recomeçar do export.
```

- **ADR-0007:** não é emendada. A 0.70.3 cumpre o que ela já decide, e o CHANGELOG diz "dívida
  da ADR-0007 quitada".
- **Spec do Zettlr** (`2026-07-22-zettlr-front-design.md`): as linhas 107 ("Falha alta
  (`ZoteroNotRunningError`), como hoje") e 112 ("Pandoc ≥ 3.0") são substituídas explicitamente
  pela ADR-0037, com a nota de uma linha listada em Componentes.
- **Spec da integração de notas** (`2026-05-03-zotero-notes-integration-design.md`): passa a
  `status: superseded` na 0.71.0, quando a aposentadoria entra (Componentes 0.71.0), e o
  `docs/_index.md` é regenerado pelo gerador.
- **Constitution:** nenhuma emenda própria. A linha 139 já diz só "Zotero + Better BibTeX
  (bibliografia)". A emenda 1.2.3 da Spec A, na linha "Stack externa", deve dizer **Pandoc ≥ 3.8.2**,
  o piso fixado aqui.
- **ROADMAP:** três bullets em "Decisões deliberadas postergadas" (texto em Quando reavaliar),
  na 0.70.3, junto com a ADR.

## Release e migração

**Já, sem bump (só docs):** a receita do 54yyyu no lugar do cookjohn em
`docs/onboarding-pesquisador.md` (B12).

**0.70.3 PATCH**, num PR, sem depender de spike da Spec A. Entrada do CHANGELOG:

```markdown
### Corrigido

- **O Refresh do Zotero no Word não quebra mais no docx do PAR.** Todo docx exportado sem `zotero.library` no frontmatter (o caso padrão) e todo docx do perfil do Zettlr saíam com as citações sem `uris`, e o primeiro Refresh do plugin do Zotero no Word parava com TypeError. Agora cada citação leva `uris` (vazio quando não há vínculo), junto com os dados embutidos (ADR-0037).
- **As citações do docx voltam a se vincular à sua biblioteca.** O export mandava `library=""` ao Better BibTeX, que recusa a consulta; o erro era engolido e o vínculo nunca saía. Sem `zotero.library`, a consulta vai para a My Library.
- O export passa a respeitar `PRUMO_ZOTERO_BASE` (dívida da ADR-0007 quitada).
- `prumo write review ingest` diz o que aconteceu quando o coautor usou os botões do Zotero (Refresh, Add/Edit Citation) no docx, em vez de acusar "occ_id duplicado" (Princípio VIII).
- O modo `review reconcile` pré-aprova as ferramentas do PAR pelo nome que elas têm no plugin (`mcp__plugin_par_prumo__*`). Acabam os pedidos de permissão a cada chamada.

### Alterado

- **O export docx não exige mais o Zotero aberto.** Com o Zotero fechado, ou com uma citekey fora da biblioteca, o docx sai do mesmo jeito, formatado, e o PAR avisa quantas citekeys ficaram sem vínculo, por quê e o comando para refazer (Princípio VIII; ADR-0037).
- A nota de primeiro uso do docx deixa de mandar dar Refresh (o docx já sai formatado) e avisa que, na rodada de revisão, o coautor não deve usar os botões do Zotero.
- **Pandoc:** no macOS sem pandoc no PATH, o PAR usa o que vem dentro do Zettlr.app. O `prumo doctor` ganha a linha `pandoc` e acusa versão anterior a 3.8.2, o piso real do export (tabelas numeradas, ADR-0035).
- Dentro do sandbox do Claude Code, o aviso do docx diz que o sandbox bloqueou o acesso ao Zotero e como repetir fora dele. O `--json` de `write export` e `write compose` ganha a chave `warnings` (aditiva).

### Removido

- Os filtros Lua do pipeline antigo (`zotero.lua` e `zotero_bibliography_docx.lua`, 2.195 linhas), sem uso desde o filtro atual (Princípio VI).

Para atualizar: além do plugin, rode `uv tool upgrade prumo-assistant-for-researcher`. O filtro corrigido vem com o CLI, e o perfil do Zettlr pega a correção sem ser regerado.
```

`ZoteroNotRunningError` não é API pública (`write/api.py` re-exporta só `compose`, `export` e
`list_styles`), e `on_warning` é aditivo. Não há aviso de fingerprint: o ingest compara o docx com
o citemap do mesmo export e nunca recalcula (Princípio VIII). O release segue os 8 passos de
`RELEASING.md`.

**0.71.0 MINOR ⚠**, num corte único com a Spec A. A ordem de PRs e o corte são da Spec A. Bullets
desta spec para a entrada ⚠ do CHANGELOG:

```markdown
- **⚠ Breaking — anotações e notas do Zotero saem do PAR** (ADR-0037). Saem `prumo paper sync-annotations`, `sync-notes` e `sync-all`; a tool MCP `paper_sync_all` (o servidor passa de 11 para 10 tools); os re-exports `sync_all`, `sync_annotations` e `sync_notes` de `par.domains.paper.api`; a exceção `ZoteroApiError`; e a regra `duplicate_item_key` do `paper lint`. Em 15 projetos auditados, nenhum desses comandos tinha gerado arquivo. Os `_annotations.md` e `note__*.md` que existirem continuam onde estão e legíveis (Princípio IV). Para "o que eu anotei no paper X", o modo `paper library` aponta uma ferramenta opcional de terceiros. Quem usava `sync-all` passa a usar `prumo paper sync` (Princípios VI e VIII).
- `prumo doctor` não exige mais a opção "Allow other applications…" do Zotero. Uma única sonda ao Better BibTeX diz se o Zotero está aberto e se o Better BibTeX está instalado (ou ainda iniciando). A linha `zotero` passa a valer para `paper connect` e o vínculo do docx. Dentro do sandbox do Claude Code, o `doctor` e o `paper connect` dizem que o sandbox bloqueou o acesso ao Zotero, em vez de "Zotero fechado".
- `prumo paper connect`: a recusa de `.bib` já conectado e a dica de export pendente passam a dizer a causa real (o Better BibTeX anterior a 9.0.65 não exporta itens novos com a janela do Zotero fechada).
```

**Migração do consumidor.** A lista "Migração de quem já usa" da Spec A (itens 1-6) não tem os
passos do Zotero. Eles entram nela como item 7, e as notas do corte da 0.71.0 publicam a lista
única:

```markdown
7. **Zotero:**
   - nada a fazer nos arquivos: os `_annotations.md` e `note__*.md` ficam onde estão;
   - atualize o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins);
   - se você ligou "Allow other applications" só por causa do PAR, pode desligar (a ferramenta opcional do 54yyyu ainda precisa dela);
   - scripts com `prumo paper sync-all` passam a `prumo paper sync`.
```

O único usuário externo hoje é o colega do piloto (ROADMAP F2). A nota de migração vale para ele
e para o dono.

## Spikes e gates pré-merge

- **G1, na máquina do dono, antes do merge da 0.70.3** (só leitura, salvo o upgrade):
  0. Atualizar o Better BibTeX de 9.0.64 para ≥ 9.0.65 (Tools → Plugins; a versão atual é a
     9.0.68), reiniciar o Zotero e conferir `prumo doctor`. Sem isso, os resultados com a janela
     fechada ficam confundidos com o defeito do serializer.
  1. Checagem do `library` vazio, com a janela principal do Zotero aberta:
     ```sh
     # o que o PAR manda hoje — esperado: "error" com "could not find library"
     curl -s -X POST http://127.0.0.1:23119/better-bibtex/json-rpc \
       -H 'Content-Type: application/json' \
       -d '{"jsonrpc":"2.0","method":"item.pandoc_filter","params":[["<citekey>"],true,""],"id":1}'
     # o que o PAR passa a mandar — esperado: result.items.<citekey>.custom.uri
     curl -s -X POST http://127.0.0.1:23119/better-bibtex/json-rpc \
       -H 'Content-Type: application/json' \
       -d '{"jsonrpc":"2.0","method":"item.pandoc_filter","params":[["<citekey>"],true],"id":1}'
     ```
  2. Word real, com o branch da 0.70.3:
     - (a) exportar com o Zotero fechado e dar Refresh: sem erro, citações e bibliografia
       intactas, aviso E1 no terminal;
     - (b) exportar com o Zotero aberto **e a janela principal fechada** e dar Refresh: religa
       (Add/Edit Citation mostra o item da biblioteca, não um embutido). Se falhar só com a janela
       fechada, repetir com ela aberta para separar as causas;
     - (c) depois de um Refresh, `prumo write review ingest` falha com E5;
     - (d) exportar pelo perfil do Zettlr e dar Refresh: sem erro.
- **G2, CI da 0.70.3:** com o pandoc 3.8.2 instalado, o teste do Lua (vinculado e não vinculado) e
  os de pipeline real de `test_export_crossref.py` rodam, não são pulados, e passam.
- **G3, na máquina do dono, antes do merge da 0.71.0:**
  `curl -si 'http://127.0.0.1:23119/better-bibtex/cayw?probe=true'` dá 200, corpo `ready` e
  `X-Zotero-Version`. Com o BBT desativado em Tools → Plugins, dá 404 **com** `X-Zotero-Version`.
  `prumo doctor` mostra E10 (Zotero fechado), E12 (BBT desativado) e ✓. Num `pj` recém-criado
  (`prumo init pj_g3`, com o `.bib` ainda no placeholder, para a Guarda 1 não recusar antes do
  transporte), `prumo paper connect "<nome que não existe>"` exercita o transporte novo só em
  leitura (`user.groups`) e responde "NADA foi criado".
- **G4 (não bloqueia):** grounding ao vivo da Rota A contra o Zotero do dono, num item sem dado de
  paciente (`annotations list` em um item). Se passar, sai a marca "não validada neste piloto".

## Riscos e premissas restantes

| # | Premissa ou risco | Estado | Se for falsa (degradação) |
|---|---|---|---|
| P1 | `uris: []` se comporta no Word como no harness (código real de `integration.js` do Zotero 9.0 rodado em QuickJS) | medido fora do Word | G1 (a) pega antes do merge. |
| P2 | A URI canônica do BBT religa no Word real | medido no harness: `uris` com `users/local/<key>` (a URI do BBT) religa, e `users/0/items/<KEY>` também | G1 (b) pega. Sem religar, as citações seguem vivas com o `itemData` embutido. |
| P3 | O Refresh reescreve **todos** os campos | inferido do fonte 9.0 | O contrato vale do mesmo jeito: E5 dispara com **qualquer** `occ_id` vazio. |
| P4 | O BBT ≥ 9.0.65 conserta o lookup e o auto-export com a janela fechada | inferido do fonte (051d0843, 10022a3d) | G1 (b) separa a causa. Se não consertar, E3 e E17 continuam mandando abrir a janela. |
| P5 | O 404 do cayw traz `X-Zotero-Version` | verificado no fonte (`server.js`) | G3 confirma. Sem o header, a versão vira `None`, o caso fail-safe que já existe. |
| P6 | O BBT recusa `""` no `item.pandoc_filter` | verificado no bundle 9.0.64 instalado | G1 (1). Se aceitar, a correção é inofensiva: só omite um parâmetro. |
| P7 | O Claude Code define `SANDBOX_RUNTIME=1` no sandbox | observado no binário 2.1.286, não documentado | Se mudar, cai nas mensagens normais (E1, E10, E15): o conselho fica errado só no sandbox, como hoje. |
| P8 | Os 2 s bastam para o `item.pandoc_filter` de um manuscrito grande com itens fora do cache do BBT | desconhecido | E1 cita "sem resposta em 2 s"; repetir com o cache aquecido. Trigger para rever o timeout em Quando reavaliar. |
| P9 | Itens de grupos só-leitura têm chave resolvível pelo BBT | desconhecido (BBT, discussão #3404: https://github.com/retorquere/zotero-better-bibtex/discussions/3404) | Saem sem vínculo, e o E4 cita `zotero.library`. |
| P10 | O pandoc do Zettlr só é procurado em `/Applications` | decidido (YAGNI) | `~/Applications` e Linux recebem a dica E8. |
| P11 | A receita do 54yyyu funciona contra um Zotero real | só flags e HOME falso | A doc já sai "não validada"; G4 a valida. Não há acoplamento de código. |
| P12 | A skill do 54yyyu, instalada, disputa frases com `/par:paper` | inferido da description | A receita diz "para a bibliografia do projeto, use `/par:paper`". O start não a oferece. |
| P13 | `PRUMO_ZOTERO_BASE` exportado no perfil do shell não chega ao MCP aberto pelo app | verificado (docs do Desktop: no macOS o app lê só o PATH do perfil) | Afeta só quem mudou a porta do Zotero: a tool `paper_connect` fala com a porta padrão, e o `connect` pelo Bash usa a porta certa. |
| P14 | Instalar o pandoc no CI não revela falha nos testes hoje pulados | desconhecido | G2: corrigir antes do merge. |
| P15 | A forma `json.decode('[]')` continua emitindo `[]` em pandoc futuro | medido em 3.1.2 e 3.10.1 | O teste com pandoc real (G2 e máquina do dono) pega. |
| P16 | A frase nova "o que eu anotei no Zotero sobre este paper" cai em `paper/library`, e não em `wiki/query` ("o que já temos anotado…", na lista-ouro) | inferido ("no Zotero" desambigua) | Medir à mão no Desktop com a lista-ouro. Se cair no `wiki/query`, a pesquisadora recebe uma resposta do wiki em vez do roteamento; ajustar a frase. A frase não pode repetir nenhuma da lista-ouro (`test_routing_phrases.py`). |
| P17 | `sandbox.excludedCommands` continua existindo com a sintaxe de regra `Bash(...)` (`"prumo *"`) | verificado em https://code.claude.com/docs/en/sandboxing em 2026-10-02 | Se mudar, a última frase de E2, E11 e E15 fica errada; a primeira, repetir fora do sandbox, continua valendo. Trigger "Sandbox" em Quando reavaliar. |

## Fora de escopo

- Tolerância do ingest a Refresh e Add/Edit Citation: recuperar a citekey de `itemData.id` e
  parear pela ordem (trigger abaixo).
- `prumo paper connect --replace`.
- Checagem da versão do BBT no doctor (`api.ready`).
- `zoteroItemID` no campo, sem consumidor e inofensivo, e o ramo `bib:`/`none` de
  `_fingerprint_for`, inalcançável em produção.
- A mensagem da checagem I3-lite de fingerprint, que promete detectar re-chaveamento no Zotero e
  na prática só detecta adulteração do JSON do campo.
- Pull nativo do `.bib`.
- `prumo paper add <doi>` sobre a escrita local do Zotero 10.
- Ler o `zotero.sqlite` (descartado em definitivo pela auditoria, A8).
- MCP de terceiro no `.mcp.json`, nos `allowed-tools` ou no `/par:start`; busca semântica no
  acervo (o extra `[semantic]`).
- Tudo o que é distribuição: launcher, hooks, `.mcp.json`, os cortes da D3 do dono, o auto-update
  (D4 do dono), os curingas das portas (D5 do dono), Windows (D1 do dono), a cópia do Lua no pj, a
  constitution 1.2.3 e o ROADMAP F5 (Spec A).
- A frase opcional sobre Connector e varinha em `skills/wiki/modes/ingest.md`.

## Quando reavaliar

Bullets novos de "Decisões deliberadas postergadas" do `ROADMAP.md` (0.70.3):

- **Ingest tolerante aos botões do Zotero.** O ingest recusa docx cujos campos o Zotero reescreveu
  (ADR-0037). Trigger: a primeira rodada real de revisão que falhar por isso.
- **Versão do Better BibTeX no doctor.** O piso 9.0.65 vive só em documentação e mensagens. Trigger:
  a primeira falha real de export ou de `connect` atribuída a um BBT antigo.
- **`prumo paper connect --replace`.** O BBT aceita `replace=true` no `autoexport.add`. Trigger: o
  primeiro pedido real de trocar a coleção de um projeto.

Demais triggers, registrados aqui e na ADR-0037:

- **B1 (gate):** a primeira entrega real em que uma citação sem vínculo causou retrabalho → pensar
  num modo estrito (`--require-link`). E E1 frequente com o Zotero aberto → rever o timeout de 2 s
  (P8).
- **B7 (pandoc):** a primeira pesquisadora em Linux travada por um pandoc do apt abaixo de 3.8.2 →
  documentar passo a passo a instalação do pacote oficial. Uma versão nova do `pypandoc-binary` com
  binário arm64 de verdade → reabrir a decisão de não embutir (Spec A).
- **B9 (aposentadoria):** um pedido recorrente de "o que eu anotei" num projeto onde o zotero-cli
  não pode ser instalado (TI ou privacidade), ou um `_annotations.md` novo, criado à mão, em algum
  `pj_*`.
- **B10 (sonda):** o BBT mudando o contrato do `cayw?probe` ou o Zotero deixando de mandar
  `X-Zotero-Version` no 404 (G3 é a referência).
- **B12 (terceiro):** a cada release maior do 54yyyu; imediatamente se o embedder padrão dele virar
  hospedado, se a skill dele capturar frases de `/par:paper` numa sessão real, ou se surgir um MCP
  oficial do Zotero.
- **B13 (API local):** uma funcionalidade que precise de dado do Zotero que não está no `.bib` nem no
  BBT.
- **Sandbox:** o Claude Code documentar ou renomear `SANDBOX_RUNTIME` (P7), ou mudar o
  `sandbox.excludedCommands` (P17).
