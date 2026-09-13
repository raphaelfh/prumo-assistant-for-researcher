# Changelog

Todas as mudanças relevantes deste plugin.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/) — política de quando bumpar `MAJOR/MINOR/PATCH` em [`RELEASING.md`](RELEASING.md).

## [Não publicado]

## [0.70.2] - 2026-09-13

### Corrigido

- **Quem instalou antes do rename migra sozinho.** O `marketplace.json` ganha `renames` (`prumo-assist` → `par`), e o Claude Code (v2.1.193+) passa a carregar o plugin com o nome novo em vez de acusar `plugin-not-found`; como a fonte é remota, basta um `/plugin install par@prumo-assistant-for-researcher`. O schema de manifests passa a descrever o campo. Instalações registradas no marketplace antigo `prumo-assist` continuam precisando remover e readicionar `raphaelfh/prumo-assistant-for-researcher` (ADR-0034).

## [0.70.1] - 2026-09-13

### Adicionado

- **`review critique` confere o que as fontes citadas dizem.** Com o draft num `pj_*`, o `reviewer` escolhe até 8 citações que sustentam tese, causalidade ou números e sobe uma escada só enquanto houver dúvida: `_extract.md`, depois o abstract do `.bib`, depois o PDF (sem extract, começa pelo abstract). O extract libera, nunca acusa: `partial`, `contradicts` e `not_found` exigem abstract ou texto completo e trecho literal da fonte. O resultado sai no novo campo opcional `citation_checks` de `PeerReviewReport/v1` (forward-only, Princípio IV), e `prumo validate` confere o trecho e a presença de `[@citekey]` no draft (Princípio II). No A/B de 2026-09-12 com o ARS, três citações que não diziam o que o draft atribuía a elas tinham passado despercebidas.

### Alterado

- O plugin ganha o título "Prumo Assistant for Researcher" (`displayName` em `plugin.json` e
  `marketplace.json`), e o card do Desktop e o `/plugin` deixam de mostrar só "Par". O namespace
  das skills continua `par` (`/par:start`), conforme ADR-0034. A descrição passa a cobrir os cinco
  domínios, protocolo incluído, e o marketplace ganha descrição própria. O validador de manifests
  exige o mesmo `displayName` nos dois arquivos.

## [0.70.0] - 2026-09-12

### Alterado

- **Obsidian sai do produto.** O normalizador `core/obsidian` vira `core/markdown` (mesmo comportamento: wikilink, embed, callout e block ID continuam convertidos para Pandoc); documentação, modo `paper library` e keywords do plugin deixam de citar o Obsidian; a constitution passa a 1.2.2, com o Zettlr como front do wiki na stack do projeto-cliente (Princípio VIII). Pastas `.obsidian/` em projetos existentes não são tocadas.
- **Proveniência ligada.** Findings, sessão de `wiki study`, `write draft` e o `citemap.json` do export carimbam `_meta` via `build_meta` (Princípio V); `write disclosure` lê o `_meta` canônico, com fallback só para `extracted_model`. `TraceWriter`, sem uso, foi removido (Princípio VI; ADR-0036).
- Descrições de `protocol sap`, `protocol cep` e `write style` atenuadas para o que o modo de fato garante, alinhadas à nova página [`docs/positioning.md`](docs/positioning.md) (Princípio VIII).
- `prumo protocol diff` em modo texto não repete mais o payload bruto (Princípio VIII).
- **⚠ Breaking — o projeto vira `prumo-assistant-for-researcher` (PAR)**
  ([ADR-0034](docs/adr/adr-0034-renomeia-para-par.md)). Repo, marketplace e distribuição Python
  passam a `prumo-assistant-for-researcher`; o plugin passa a `par`, então as skills viram
  `/par:paper extract`, `/par:start` etc.; o pacote Python passa de `prumo_assist` a `par`.
  O CLI `prumo`, o MCP `prumo`, `.prumo/`, `prumo.*` e `PRUMO_*` não mudam. Sem migração:
  reinstale com `/plugin marketplace add raphaelfh/prumo-assistant-for-researcher`,
  `/plugin install par@prumo-assistant-for-researcher` e
  `uv tool install git+https://github.com/raphaelfh/prumo-assistant-for-researcher.git`.
- **`prumo paper extract` valida o payload por `PaperCallout/v1`** e recusa, sem gravar,
  seção fora do template ou valor que não é texto; antes a chave errada virava seção
  "pendente" em silêncio. Aceita a forma plana legada e `{"sections", "locators"}`.
- **⚠ Breaking — 16 skills viram `start` + cinco skills por domínio com modos**
  ([ADR-0032](docs/adr/adr-0032-superficie-por-dominio-e-modos.md)). A fricção mais vista era
  escolher a skill: descrições sobrepostas e 16 nomes no contexto de toda sessão. Agora são
  `paper`, `wiki`, `protocol`, `write` e `review`, e cada skill antiga virou um modo 1:1 em
  `skills/<skill>/modes/<modo>.md`:

  | Antes | Agora |
  |---|---|
  | `paper-manager` · `paper-extract` · `citation-support` | `paper library` · `paper extract` · `paper support` |
  | `wiki-ingest` · `wiki-query` · `wiki-lint` · `active-learning` | `wiki ingest` · `wiki query` · `wiki lint` · `wiki study` |
  | `formulate-picot` · `write-statistics` · `write-projeto-cep` | `protocol picot` · `protocol sap` · `protocol cep` |
  | `write-paper` · `write-scientific` · `scientific-writing` | `write manuscript` · `write section` · `write style` |
  | `peer-review` · `review-reconcile` | `review critique` · `review reconcile` |

  O frontmatter do modo é a fonte única de frases de roteamento, nomes antigos, requisitos,
  `write_kind` e `disclosure_task` (Princípio I). `when_to_use`, `allowed-tools`,
  `argument-hint`, a tabela frase → modo, a tabela do README e o catálogo do `start` são
  gerados (Princípio VII). Não há alias: **rode `prumo update`** no projeto.
- **Templates de escrita** moram em `skills/<skill>/templates/<modo>.md`, e o `compose` acha
  template e trava de idioma pelo modo que declara `prumo.write_kind`.
- **Disclosure canoniza a proveniência.** `generator: wiki-query` (legado) e `wiki/query`
  (novo) agregam na mesma ferramenta `par:wiki query`; nada já gravado é reescrito
  (Princípio IV). Findings novos gravam `generator: wiki/query`.

### Adicionado

- **Declaração de IA por periódico.** `prumo write disclosure --venue icmje|jama|bmj` segue a política do periódico conferida na fonte (`source_url` e `accessed`), lista o que falta preencher e diz onde inserir. Sem `--venue` a saída não muda; periódico sem perfil recebe o texto genérico com aviso. NEJM, The Lancet e einstein ficaram de fora porque a página oficial não pôde ser conferida (Princípios II, IV, VI, VIII).
- **`prumo protocol diff` aponta drift do manuscrito.** Compara os drafts de `writing/` com `protocol.md` e a PICOT: janela de coleta, `n`, testes estatísticos nomeados e pré-especificação de subgrupos, com arquivo:linha dos dois lados e dica de correção. Fato ausente no draft não conta como drift, e cada divergência aparece uma vez. Só lê (Princípios I, II, VIII).
- **`prumo wiki lint` recalcula estatísticas relatadas.** Porcentagens `x of n (p%)`, IC 95% de Wilson e valores q de Benjamini-Hochberg em tabelas Markdown; `stat_mismatch` mostra o valor relatado e o recalculado quando divergem (Princípios II, VI).
- **`review critique` com trecho literal e fontes lidas.** Cada fraqueza e claim sem evidência pode trazer um `quote` literal (até 25 palavras) que `prumo validate PeerReviewReport/v1` confere contra o `draft_path`, e o relatório lista `sources_read`. Campos opcionais, forward-only (Princípios II, IV; ADR-0033).
- **Passe adversarial no `review critique`, a pedido.** Com "seja o advogado do diabo", "seja duro" ou "revisa antes de submeter", um segundo `reviewer` ataca só o argumento central, com duplicatas removidas por sentido, sem schema novo. O padrão continua sendo uma chamada (Princípios VI, VIII; ADR-0033).
- **Figuras e tabelas numeradas no export.** `prumo write export` e `compose` numeram `{#fig:x}` e `{#tbl:x}` e resolvem `@fig:x`/`@tbl:x` com rótulo no idioma de `[writing].language`, por um filtro Lua vendorizado antes do citeproc, sem binário novo (Princípios II, VIII; ADR-0035).
- **Fronteira de confidencialidade no `pj_base`.** A rule `.claude/rules/safe_outputs.md` pede o mínimo necessário, célula mínima 5 para contagem de pacientes e dado fora do git; o `prumo doctor` ganha `[dado_versionavel]` para `content/` ou `.prumo/` fora do `.gitignore` ou rastreados. Projetos existentes recebem a rule com `prumo update` (Princípios II, VI).
- **Três subagents read-only** ([ADR-0033](docs/adr/adr-0033-subagents-nomeados.md)): `reader`
  extrai o PDF e grava via `prumo paper extract`, com locators por seção; `verifier` julga se
  a fonte sustenta a frase lendo o PDF, nunca o `_extract.md`; `reviewer` critica o draft sem
  ter visto a conversa de redação. Prompt canônico em `agents/<nome>.md`, copiado para
  `.claude/agents/` pelo `prumo init`. Os modos despacham pelo nome e, se o tipo não existir
  na sessão, `general-purpose` com o mesmo arquivo.
- **`prumo validate <schema>`** valida o JSON devolvido por um subagent contra
  `SupportReport/v1` ou `PeerReviewReport/v1` (agora contratos Pydantic) e aponta o campo a
  corrigir (Princípio II).
- **Proveniência ligada no extract** (Princípio V): o apply carimba `_meta` (skill, schema,
  modelo, `input_hash`) no `_meta.md` — primeiro produtor real de `core/provenance.py`.
- **`prumo status`** diz, só lendo o disco, em que ponto o estudo está e qual a próxima frase
  dizer ao agente: bibliografia vazia → papers com PDF sem extract → PICOT não fechada →
  escopo sem draft → eventos ambíguos de revisão. `--json` sai versionado
  (`ProjectStatus/v1`) e o `start` usa esse payload para sugerir o próximo passo. Não grava
  estado novo (mesma lógica da ADR-0029) e não consulta o Zotero, que é assunto do `doctor`.
- **`prumo update` reescreve invocações antigas** (`prumo-assist:<antigo>` ou `par:<antigo>` →
  `par:<skill> <modo>`) em `.md` e `.toml` do projeto, com `--dry-run` listando cada arquivo. O acervo
  gerado em `docs/references/papers/` fica de fora.
- **`doctor` aponta `[skill_obsoleta]`** quando sobra invocação antiga ou
  `.claude/skills/<antigo>/` de um `init` anterior (não apagado: pode ter customização).
- **Modo `write disclosure`** expõe `prumo write disclosure` pelo agente.
- **Lista-ouro de roteamento** (`tests/fixtures/routing_phrases.toml`): 30 frases inéditas
  cobrindo os 16 modos, para medir no Desktop (critério ≥ 27/30).

### Corrigido

- **Subcomando ausente conta como "sem CLI"** em `review critique`, `paper support` e `start`.
  Com o CLI global antigo (0.67.2), `prumo --version` respondia e `prumo validate` falhava
  com `No such command`, e os modos não diziam o que fazer. Agora eles checam os campos e
  enumerações do contrato à mão (critique e support) ou seguem sem `next` (start), e
  oferecem uma vez `uv tool upgrade prumo-assistant-for-researcher`, com consentimento. O
  preflight gerado da ADR-0019 não muda.
- **`prumo update` e `doctor [skill_obsoleta]` voltam a achar invocações de projetos antigos.**
  O rename para PAR trocou o padrão para `par:<antigo>`, prefixo que nenhum projeto gravou;
  `prumo-assist:<antigo>` passava sem migrar e sem aviso. Agora os dois prefixos casam
  (Princípio IV; ADR-0034).
- **Installer copiava só o `SKILL.md`.** `references/` e `examples/` do `peer-review` nunca
  chegavam ao `.claude/skills/` do projeto; agora a árvore da skill vai inteira.
- **Toda entrada de finding no `_log.md` caía em `broken_log_prefix`.** `archive_as_finding`
  gravava o gerador no lugar do verbo; o verbo passa a `note`, com o gerador entre parênteses.

## [0.69.1] - 2026-09-11

### Removido

- **`Makefile` sai do scaffold.** O `pj_base` deixa de criar `Makefile` e `.claude/make/`, e
  os módulos `ml` e `notebooks` deixam de depositar `ml.mk`/`notebooks.mk`. Todo alvo era
  atalho de um comando `prumo`, `qmd`, `uv run ruff` ou `uv run marimo` que continua
  existindo; skills e a rule de notebooks passam a citar o comando direto. Projetos
  existentes mantêm o `Makefile` que já têm — nada é apagado.

## [0.69.0] - 2026-09-07

### Corrigido

- **⚠ Breaking — as rules do `pj_base` nunca carregaram, e por isso saem do template.**
  `documentation.md` e `project_context.md` escopavam-se com `paths: ["**/pj_*/docs/**"]`
  e `["**/pj_*/**"]`. O Claude Code casa `paths:` contra o caminho **relativo à raiz da
  sessão**, e a raiz é o próprio `pj_*` — o segmento não existe no caminho, então o glob
  nunca casou e o agente jamais leu nenhuma das duas. Verificado empiricamente no Claude
  Code 2.1.263 com token sentinela e controle sem `paths:`: `docs/**` e `**/*.md` carregam,
  `**/pj_*/**` não, nem com a sessão aberta no diretório-pai. Mesmo defeito em
  `modules/clinical/clinical_context.md` e no arm `**/pj_*/**/*.py` de
  `modules/ml/data_governance.md`. Novo teste de regressão (`test_rules_scoping.py`)
  reprova qualquer glob distribuído que dependa do segmento `pj_*`.

### Removido

- **⚠ Breaking — `.claude/rules/documentation.md` sai do `pj_base`.** Era 4.9 KB de
  duplicação: a tabela de campos YAML e as seções canônicas da nota já vivem em
  `docs/references/_note_template.md`, que ship no projeto; o formato de citekey, a árvore
  de `references/` e a tabela de busca no acervo já vivem na `paper-manager`. O único
  conteúdo exclusivo — *YAML é a única fonte de verdade, proibido metadata inline* — foi
  para a `paper-manager` e a `wiki-ingest`, ao lado de onde a nota é escrita.
- **⚠ Breaking — `.claude/rules/project_context.md` e
  `modules/clinical/.claude/rules/clinical_context.md` saem dos templates.** Contexto do
  estudo passa a ter uma casa só, `docs/project_guide.md` (ganhou a seção "Escopo do
  wiki"); o contexto clínico já estava inteiro no `protocol.md` do próprio módulo, que
  ganhou o único campo que faltava (`Contato / responsável`). `prumo update` migra o
  conteúdo preenchido para o `project_guide.md` **antes** de remover o arquivo — nada que
  o pesquisador digitou se perde por causa de um bug nosso.
- **O `doctor` para de cobrar campos em branco do `project_context.md`.** O aviso
  policiava um arquivo que o agente nunca leu. Saem junto `empty_context_fields`,
  `context_is_untouched`, `COMPARE_EXCLUDE` e o parser de campos — a exceção de
  comparação da 0.68.1 existia só porque o formulário morava em `.claude/rules/`.

### Modificado

- **`pj_base/CLAUDE.md` cai de 2.4 KB para 1.1 KB.** Saem a tabela "Início rápido"
  (redundante: as descriptions das 16 skills já carregam e roteiam melhor), a árvore de
  diretórios (duplicada) e a seção "Hierarquia de instruções" (que ainda por cima afirmava
  como funcional o carregamento quebrado). A tabela de invocação vai para o `README.md`,
  que é do humano e não custa contexto do agente. Fica o que o agente age em cima:
  persona, cascata de idioma, Zotero como fonte única, e o ponteiro para
  `docs/project_guide.md`, que agora é leitura obrigatória.


## [0.68.1] - 2026-09-07

### Corrigido

- **`project_context.md` preenchido deixa de ser tratado como rule desatualizada.** O
  arquivo mora em `.claude/rules/`, que o `[fora_do_padrao]` compara por conteúdo — então
  preenchê-lo, que é exatamente o que o `prumo init` manda fazer nos próximos passos,
  marcava o projeto como fora do padrão e fazia o `doctor` sair com código 1. Pior:
  `prumo update --yes` o listava como divergente e **sobrescrevia o contexto do
  pesquisador** com o template em branco. Ele é formulário, não regra: divergir do template
  é o estado correto, e agora é exceção explícita (`scaffold.COMPARE_EXCLUDE`).
- **O aviso de campos em branco via só duas das cinco entradas do template.** O
  `project_context.md` usa duas formas de campo — `- **Rótulo:**`, com os dois-pontos
  dentro do negrito, e `- **Rótulo** (dica):`, com eles fora depois de um parêntese — e o
  regex só reconhecia a primeira. O `doctor` acusava 2 campos vazios num `pj_*` novo que
  tem 5, sub-reportando em silêncio justamente o arquivo cujo esquecimento ele existe para
  pegar.

### Modificado

- **O `doctor` cala sobre `project_context.md` intocado, e avisa no preenchimento
  parcial.** Template todo em branco é o estado normal de um projeto recém-criado, e o
  `prumo init` já manda editá-lo — avisar de novo seria um comando cobrando o que o outro
  acabou de pedir. Preenchimento parcial é outra coisa: alguém mexeu no arquivo e deixou
  buraco, e aí o lembrete é sobre esquecimento real. Princípio VIII, toda saída diz cada
  coisa uma vez, aplicado entre comandos e não só dentro de um.

## [0.68.0] - 2026-09-07

### Adicionado

- **`prumo update` traz o `pj_base` de volta a um projeto que ficou para trás.** O `init`
  era overlay de uma vez só: o template nunca refluía para um `pj_*` vivo, e uma rule
  vendorizada podia ensinar layout obsoleto ao agente por meses sem que nada reclamasse —
  foi o que aconteceu com um `.claude/rules/documentation.md` preso no layout pré-[ADR-0008](docs/adr/adr-0008-layout-alfa-de-notas.md).
  Arquivo ausente é restaurado direto; arquivo que existe e difere só é tocado com
  confirmação, e sem TTY a resposta é não, para que um `update` em CI nunca apague
  customização. `--dry-run` mostra o plano sem escrever. A comparação é feita ao vivo
  contra o template instalado: nada de hash gravado no `pj_config.toml`, que seria uma
  terceira fonte de verdade livre para dessincronizar ([ADR-0029](docs/adr/adr-0029-update-reflui-o-template.md), Princípio VIII).
- **`prumo doctor` ganha a camada de prosa, com o check `[fora_do_padrao]`.** O `doctor`
  tinha quatro perguntas sobre empacotamento ([ADR-0027](docs/adr/adr-0027-pj-instalavel.md))
  e uma sobre prosa, que só olhava `references/` na raiz. Um projeto com `studies/` na raiz,
  sem `docs/project_guide.md` e com rule desatualizada passava limpo. Agora os três sintomas
  entram numa **mensagem só**, porque têm um remédio só (Princípio VIII): a detecção usa
  lista fechada de diretórios que um ADR aposentou — nunca "markdown fora de
  `docs/studies/`", que marcaria o `README.md` de todo projeto.
- **Aviso de `project_context.md` em branco.** É o arquivo que o agente lê a cada sessão, e
  falhar em silêncio custa a sessão inteira. Entra como *warning* e não como erro: projeto
  recém-criado tem o template legitimamente vazio, e falhar no minuto zero treinaria o
  pesquisador a ignorar o `doctor`.
- **`experiments/<run_id>/` como casa canônica das rodadas persistidas do módulo `ml`.** Na
  raiz, ao lado de `build/` e `reviews/`, fora de `docs/` — que é a raiz única de leitura
  indexada pelo `qmd`, onde bundle `.joblib` polui toda consulta ao wiki sem nunca ser
  conteúdo de leitura. `README.md` da rodada, métricas e figuras versionados; o bundle não
  ([ADR-0031](docs/adr/adr-0031-casa-das-rodadas-de-ml.md)). Chega por `prumo add ml`.
- **`decision` é o quinto tipo de página do wiki** ([ADR-0030](docs/adr/adr-0030-tipo-decision.md)).
  `decisions/` é um dos três `SCOPE_DIRS` e o lint cobra frontmatter nele, mas o
  [ADR-0025](docs/adr/adr-0025-tipo-de-pagina-no-frontmatter.md) só nomeava quatro tipos.

### Corrigido

- **Citação dentro de crase deixa de virar `broken_citekey` falso.** `scan_marked_citekeys`
  pulava bloco cercado, mas não código inline: qualquer nota que **documentasse** o formato
  de citação, escrevendo `` `[@chave]` `` como exemplo, gerava citekey quebrada — e o autor
  era empurrado a adaptar o texto à limitação do parser. A máscara mora só no scan: a Guarda
  I1 (`_citation_atom_spans`) continua rodando sobre o corpo cru, tratando `@key` em código
  como átomo protegido, com teste de regressão que cai se alguém "unificar" os dois caminhos.
- **A saída dos comandos deixa de dizer a mesma coisa duas vezes.** `prumo add study`
  imprimia o caminho absoluto duas vezes — `success` e depois `emit` renderizando o dict
  linha a linha —, e o segundo quebrava no wrap do Rich, com cara de erro num comando que
  funcionou. O padrão estava em outros seis subcomandos. Novo `Console.result(message,
  payload)`: frase em modo texto, payload em modo JSON, sem duplicar código (Princípio VIII).

### Modificado

- ⚠ **Breaking — o issue code `[legacy_layout]` do `prumo doctor` foi absorvido por
  `[fora_do_padrao]`.** Quem casava a string `legacy_layout` na saída `--json` precisa
  passar a casar `fora_do_padrao`. `[references_ressuscitado]` permanece separado, porque o
  remédio dele é outro (corrigir o autoexport na UI do Zotero, não adequar o repo).
- **Constitution 1.2.0 — Princípio VIII, "Simplicidade é o default".** O Princípio VI recusa
  código especulativo, mas mede custo em linhas escritas; nada media o que o **pesquisador**
  precisa aprender. O plano original desta auditoria somava quatro issue codes, um módulo
  simétrico e um campo de estado no `pj_config.toml` — cada peça passando no VI
  isoladamente. O VIII mede custo em conceitos: remédio igual gera mensagem única, saída diz
  cada coisa uma vez, menos estado persistido vence, e simetria de layout não justifica
  arquivo novo. Emenda MINOR; nenhum princípio existente alterado.
- A isenção de `orphan_page` para `README.md`, `protocol.md` e stems iniciados por `_` passa
  a estar **documentada** na skill `wiki-lint`. Ela existia no código desde sempre e não
  aparecia em prosa nenhuma: é a saída recomendada para o ruído de órfã em tabelas, figuras
  e drafts, que nunca terão link de entrada de outra nota.

## [0.67.2] - 2026-09-06

### Adicionado

- **O módulo `notebooks` aceita marimo (`.py`) além de Jupyter (`.ipynb`), e marimo
  passa a ser o formato padrão.** O notebook marimo é um `.py` comum: o diff é legível,
  o arquivo não carrega saída embutida e o grafo de dependência entre células elimina o
  estado oculto — o oposto do `.ipynb`, cujo JSON com outputs polui o histórico. O
  `.ipynb` continua aceito e nada precisa ser convertido (`marimo convert` está ali para
  quando valer a pena). `prumo add notebooks` agora entrega, além de
  `notebooks/<escopo>/`, um stub `00_exploracao.py`, a rule `.claude/rules/notebooks.md`
  e os alvos `nb-edit`/`nb-run`/`nb-convert` em `.claude/make/notebooks.mk`. O stub
  importa código próprio pelo nome do pacote, sem `sys.path` ([ADR-0027](docs/adr/adr-0027-pj-instalavel.md)).
- **Instruções do [marimo pair](https://marimo.io/blog/marimo-pair) na rule do módulo.**
  A agent skill coloca o agente dentro da sessão em execução do notebook — lê o valor das
  variáveis em memória e executa código num scratchpad com esse mesmo estado, em vez de
  pedir que o pesquisador descreva o schema do `DataFrame` na conversa. A rule traz a
  instalação (`npx skills add marimo-team/marimo-pair`, ou o marketplace de plugin do
  Claude Code), os requisitos (`bash`, `curl`, `jq`; `--no-token` para descoberta
  automática; `MARIMO_TOKEN` em servidor com auth) e a invocação
  (`/marimo-pair pair with me on <notebook>`).

### Modificado

- `marimo>=0.24` entra no grupo `dev` do `pyproject.toml` do módulo `code` (ao lado de
  `nbformat`, que segue servindo os `.ipynb` herdados), e `__marimo__/` entra no
  `.gitignore` do `pj_base` — cache e export de sessão são reconstruíveis, o `.py` do
  notebook é que se versiona.

## [0.67.1] - 2026-08-24

### Adicionado

- **`prumo paper connect "<coleção>" --create` cria a coleção no Zotero e liga o
  autoexport num passo só.** Quem ainda não tem a coleção não precisa mais sair do
  terminal, criá-la na UI do Zotero e voltar — o ida-e-volta que a Fase 4 do
  zero-friction existia para eliminar. A capacidade não é canal novo: `autoexport.add`
  do Better BibTeX sempre criou o caminho inexistente, e a
  [ADR-0020](docs/adr/adr-0020-connect-autoexport-bbt.md) tratou isso como risco a
  bloquear. A [ADR-0028](docs/adr/adr-0028-criacao-de-colecao-opt-in.md) emenda aquela
  decisão e promove o efeito colateral a **opt-in explícito**: sem `--create`, nada muda
  — `CollectionNotFoundError` com sugestões do `difflib` e a garantia "NADA foi criado"
  (a mensagem agora também aponta o `--create` como saída).
- **Eco do plano antes de mutar.** `connect.plan_connection` decide o `bbt_path` sem
  chamar nada mutante e devolve um `ConnectPlan` que marca **cada segmento** do caminho
  como já existente ou a criar; o CLI imprime isso antes de pedir confirmação. Como o
  BBT materializa a cadeia de pais inteira, o pesquisador precisa ver quantas coleções
  nascem antes de autorizar. Em sessão interativa há prompt; `--yes` segue direto; sem
  TTY e sem `--yes` (CI, pipe, `--json`) o comando **recusa** com exit 130 em vez de
  travar num prompt invisível ou assumir "sim".
- `connect.list_libraries()` e `LibraryRef` — biblioteca sem coleção nenhuma não produz
  `CollectionRef` algum e mesmo assim é alvo válido de criação. Sem `--library`, a
  criação vai para a biblioteca **pessoal** (`id == 1`), não para a primeira encontrada:
  criar no acervo próprio é menos invasivo que criar num grupo compartilhado com outras
  pessoas. `--library` informada precisa existir (`LibraryNotFoundError`).

### Modificado

- Guardas da ADR-0020 preservadas e **reforçadas** no caminho de criação, todas antes de
  qualquer mutação: `AlreadyConnectedError` continua sendo a primeira e é puramente
  local; `AmbiguousCollectionError` continua exigindo `--library`, porque `--create` não
  desempata nada; e `/` no nome com `--create` é recusado **antes de qualquer
  round-trip** — sem a flag o `/` aliasaria um export errado, com a flag viraria criação
  real de uma coleção por segmento. `--create` cria sempre **uma** coleção na raiz da
  biblioteca: `name` nunca é path.
- A fachada MCP `paper_connect` **não** recebe `create` e mantém `(pj_path, collection,
  library)`. Ela já está em `MUTATING_TOOLS` e é invocável por agente; uma flag de
  criação nesse caminho deixaria um agente materializar coleções no acervo real sem
  humano no meio. Um teste de desenho pina a assinatura
  ([ADR-0026](docs/adr/adr-0026-mcp-prumo-dominio-paper.md), Princípio II).
- **A skill `paper-manager` ganha regra dura contra `--create` de iniciativa própria.** Ela
  roda o CLI por `Bash(prumo paper *)`, então nenhuma assinatura a impede de acrescentar a
  flag — só a instrução. Diante de coleção inexistente o agente mostra as sugestões do CLI,
  **pergunta**, e só roda com `--create` quando o pesquisador pediu a criação em palavras
  dele; `--yes` nunca. A afirmação "typo nunca cria nada no Zotero" foi corrigida na skill e
  em `docs/onboarding-pesquisador.md` para valer explicitamente ao caminho **sem** `--create`.
- A mensagem de sucesso do `--create` declara, em uma linha, que **não há desfazer** pelo
  CLI: remover é manual na UI do Zotero. O regrounding ao vivo de 2026-08-24 mostrou que
  o BBT não expõe `autoexport.remove` nem `autoexport.list` (`-32601 Method not found`)
  e que a API local recusa `DELETE` de coleção (`501`) — a ausência é declarada, não
  contornada com um `--undo` inventado.

## [0.67.0] - 2026-08-24

### Adicionado

- **O `pj_*` com o módulo `code` é um pacote instalável.** O `pyproject.toml` gerado
  passa a declarar `[build-system]` com hatchling, e `prumo add code` entrega
  `src/<pkg>/__init__.py` — um pacote **nomeado** — em vez de um `src/` vazio. O nome sai
  do nome do projeto sem o prefixo `pj_` (`pj_prolapse_polymorphism` →
  `prolapse_polymorphism`): o prefixo marca diretório de projeto e em `import` é ruído.
  Com `uv sync` o projeto é instalado em editable no `.venv`, e o import de código próprio
  resolve **por instalação** em vez de `cwd` + `sys.path` — o que mata de uma vez o
  `sys.path.insert` nos notebooks, o `# noqa: E402` permanente e o unresolved import do
  PyCharm/VS Code. [ADR-0027](docs/adr/adr-0027-pj-instalavel.md) registra também por que
  a pergunta de configuração de IDE **se dissolve** em vez de ser respondida: com o pacote
  instalado, os dois editores resolvem pelo interpretador do `.venv`, sem source root, sem
  `python.analysis.extraPaths` e sem `.idea/` versionado.
- **Convenção de onde o código mora:** a raiz do pacote é o **compartilhado**
  (`src/<pkg>/cohort.py`, usado por vários estudos e notebooks) e um **subpacote por
  estudo** guarda o específico (`src/<pkg>/polymorphism/prep.py`). A assimetria é
  deliberada — o caminho curto pertence ao código reutilizável, que é o caso a incentivar.
  O nome do subpacote vem do slug de `docs/studies/` sem o prefixo numérico
  (`01_polymorphism` → `polymorphism`); o slug da escrita não muda. Isso elimina o motivo
  do tree paralelo `studies/<slug>/{notebooks,scripts}/` que projetos reais inventaram
  para preencher o vazio que o módulo `code` deixava.
- **Quatro checks de empacotamento no `prumo doctor`** (`core/packaging.py`), todos
  determinísticos e sem LLM (Princípio II), todos com o comando de correção embutido:
  `projeto_nao_instalavel` (há código em `src/` e falta `[build-system]`),
  `pacote_sem_nome` (módulo solto na raiz de `src/`, ou um `src/src/` — o caso do
  `from src.x import y`), `sys_path_hack` (`sys.path.insert`/`append` em notebook ou
  módulo) e `projeto_nao_sincronizado` (é instalável, há `.venv/`, e o pacote não está
  lá). A migração de projeto legado é **agêntica**, no molde exato do check
  `legacy_layout` da [ADR-0022](docs/adr/adr-0022-layout-por-escopo.md): o CLI detecta e
  convida, o agente adequa — não há comando de migração porque o estado de partida de cada
  projeto é arbitrário e um migrador determinístico erraria onde o agente acerta.
- `scaffold.PKG_MARKER` (`__pkg__`), resolvido em **caminho** por `overlay(pkg=...)` e em
  **conteúdo** por `apply_pkg_name` — o `pyproject.toml` precisa do nome real em
  `[tool.hatch.build.targets.wheel] packages`. Marcador não resolvido falha alto, em vez de
  virar diretório `__pkg__` órfão no projeto do pesquisador.
- Rule `.claude/rules/code_layout.md` no módulo `code`: onde o código mora, por que não se
  usa `sys.path`, como apontar o interpretador do editor, e por que bundle `joblib` guarda
  **dado + versão de schema** e nunca objeto cujo `__module__` importe.
- `tests/unit/core/test_packaging.py` (13 casos) e cobertura nova em
  `test_scaffold.py`, `test_modules.py` e `test_cli_doctor.py`.

### Alterado

- ⚠ **Breaking — `prumo add code` muda de forma.** Passa a criar `src/<pkg>/__init__.py` e
  a emitir `[build-system]`. Projetos que já rodaram `add code` não são tocados (o overlay
  nunca sobrescreve), mas passam a acusar `projeto_nao_instalavel` no `doctor` — que é o
  ponto: o defeito aparece antes do `ModuleNotFoundError` de daqui a três meses.
- ⚠ **Breaking — o módulo `notebooks` virou por-escopo.** `notebooks/<escopo>/` em vez de
  `notebooks/` plano, e o `anchor` mudou de `notebooks/.gitkeep` para
  `notebooks/__scope__/.gitkeep`. Consequência prática: projeto que já rodou
  `add notebooks` volta a aparecer como **não-aplicado** em `prumo add --list`, e um
  `prumo add notebooks` novo cria `notebooks/<escopo>/` ao lado do `notebooks/` existente.
  É ruído, não perda — nada é sobrescrito e o `doctor` não reclama.
- `apply_project_name` foi extraído para `_apply_placeholders`, agora compartilhado com
  `apply_pkg_name`.

### Notas

- **O que isto NÃO conserta:** o pickle. `joblib` continua gravando
  `<pkg>.<estudo>.prep` no bundle, e mover o módulo continua quebrando a desserialização.
  O que muda é que o caminho passa a ser **estável** (não depende mais de `cwd` nem da
  ordem do `sys.path`) e que sobra **um** movimento perigoso — promover de subpacote de
  estudo para a raiz do pacote — em vez de vários. A mitigação é orientação na rule, não
  código.
- **Corte deliberado:** o check "import top-level de módulo que não é dependência
  declarada" **não** entrou. Exigiria resolver o grafo de imports contra os
  `[dependency-groups]`, que são opt-in (`uv sync --group tabular`), tornando o
  falso-positivo o caso comum. Isso é trabalho de `deptry` ou do `ruff`.
- `uv sync` passa a ser pré-requisito para importar código próprio: invisível em projeto
  que já usa o `.venv` como kernel do notebook, e um passo novo em projeto que importava
  por `sys.path` — que é o que o check `projeto_nao_sincronizado` nomeia.

## [0.66.0] - 2026-08-24

### Adicionado

- Testes de regressão `test_add_nao_deixa_manifesto_do_modulo_no_projeto` e
  `test_lint_ignora_cabecalho_de_log_dentro_de_code_fence`.
- **O servidor MCP cobre o domínio `paper`:** sete tools novas (`paper_sync`, `paper_find`,
  `paper_lint`, `paper_graph`, `paper_verify_refs`, `paper_sync_all`, `paper_connect`),
  fachadas finas sobre `domains/paper/api.py` sem lógica nova (Princípio I), com o mesmo
  contrato de erro das tools de revisão — `ValueError` carregando a mensagem pt-BR do
  domínio, nunca traceback. O ganho que justifica: **tool MCP é descobrível sem carregar
  skill**, enquanto comando Bash só existe para o agente se a prosa de alguma skill o
  mencionar — e 14 das 16 skills declaram `Bash(prumo …)`.
  [ADR-0026](docs/adr/adr-0026-mcp-prumo-dominio-paper.md) registra também por que o
  argumento "funciona onde não há Bash" **não** sustenta esta decisão: o Cowork executa
  comandos, e a única superfície sem execução também não sobe o servidor.
  `paper_connect` é a segunda tool mutante e a primeira que muta estado fora do repo; as
  guardas anti-coleção-fantasma seguem no domínio
  ([ADR-0020](docs/adr/adr-0020-connect-autoexport-bbt.md)).
- `prumo paper sync-pdfs` distingue **"sem anexo PDF no Zotero"** de **"PDF não
  baixado"** (biblioteca em nuvem): campos `no_attachment` e `not_downloaded` no
  `--json`, contagens separadas na saída humana, e instrução de correção quando há
  arquivo não baixado. `missing` é preservado como a união dos dois, para não quebrar
  consumidores do `--json` ([ADR-0011](docs/adr/adr-0011-semver-por-visibilidade.md)).
- `tests/unit/paper/test_pdfs.py`: o módulo estava em 17% de cobertura, sem nenhuma
  asserção comportamental — o menos testado do domínio `paper` e o único cuja lógica é
  heurística. Agora em 100%, com caracterização do comportamento preservado
  (idempotência, auto-reparo de symlink desatualizado, recusa de sobrescrever arquivo
  real) e regressão dos dois defeitos abaixo. Achados e decisões em
  [`docs/superpowers/specs/2026-08-23-ponte-zotero-auditoria-design.md`](docs/superpowers/specs/2026-08-23-ponte-zotero-auditoria-design.md).

### Alterado

- **⚠ Breaking — o servidor MCP passa de `prumo-review` a `prumo`.** O nome é o prefixo
  das tools no agent-host (`mcp__prumo__paper_find`), e um servidor que cobre revisão e
  bibliografia sob um nome de revisão mente sobre o próprio escopo. Quem tiver
  `mcp__prumo-review__*` em configuração própria precisa trocar o prefixo; o `.mcp.json`
  distribuído e o `allowed-tools` de `review-reconcile` já vêm ajustados. Feito agora
  porque o custo de um breaking cresce com a adoção
  ([ADR-0011](docs/adr/adr-0011-semver-por-visibilidade.md)).
- **⚠ Breaking — `review_events` devolve o envelope `ReviewEventsFile/v1`**
  (`schema_version`, `page`, `events`) em vez da lista nua de eventos, alinhando a tool ao
  que o `--json` do CLI já emitia.

### Corrigido

- **`prumo add <módulo>` deixava um `_module.toml` órfão na raiz do `pj_*`.**
  `overlay()` varria `templates/modules/<nome>/` com `rglob("*")` sem excluir o
  manifesto do módulo — que é metadata pro próprio `add` (`description`,
  `when_to_use`, `anchor`), não payload de projeto. O arquivo copiado era o do
  módulo aplicado PRIMEIRO (os seguintes o viam existir e pulavam), então a raiz
  do projeto ficava com um descritor que não descreve o projeto e não é lido por
  nada. `MODULE_MANIFEST` passa a ser constante única, usada pelo skip do
  `overlay` e pelo `discover_modules`.
- **`prumo wiki lint` acusava `broken_log_prefix` em todo projeto recém-criado.**
  O `_log.md` do `pj_base` documenta o formato das entradas num code fence
  (`## [YYYY-MM-DD] <action> | <título curto>`); `_check_log_prefixes` lia o
  arquivo linha a linha, sem filtrar fence, e tratava o exemplo como entrada
  quebrada. Um warning que nasce com o projeto e não tem conserto ensina a
  ignorar o lint. Passa a usar `citations.body_lines` (o filtro de fence que já
  existia, agora público em vez de `_body_lines`).
- **`prumo paper sync-pdfs` perdia PDFs por dois defeitos no parser do campo `file`.**
  O Better BibTeX escapa três caracteres (`\\`, `\;`, `\:`) e o parser desfazia só o
  último: um anexo cujo nome de arquivo contém `;` — comum em export automático, do tipo
  `Smith; Jones - 2024.pdf` — tinha o caminho partido ao meio e caía em "sem PDF". E
  caminho relativo (pref "export file paths: relative" do BBT) nunca resolvia, zerando
  **todos** os PDFs de quem usa essa configuração; agora é resolvido contra o data dir
  do Zotero (`~/Zotero`, override por `PRUMO_ZOTERO_DATA_DIR`). Separação e
  desescape passam a ser a mesma passada, que é o que impede um `\:` do nome do arquivo
  de virar separador.
- **`prumo doctor` afirmava "API local respondendo" com a API local desligada.** A sonda
  era um TCP connect na 23119 (e, no seam usado pelos domínios, `GET /connector/ping`) —
  ambos sobem junto com o app, independentemente da preferência. Como a API local é
  opt-in, o `doctor` aprovava e os comandos de anotação tomavam HTTP 403 em série. A
  sonda passa a ser `GET /api/`, único endpoint que reprova nesse caso (`403 Local API
  is not enabled`), e o `doctor` ganha um terceiro estado com o remédio embutido
  (Settings → Advanced → "Allow other applications…").
- **Dívida de versionamento da [ADR-0017](docs/adr/adr-0017-prumo-mcp-reconciliador.md),
  declarada e adiada para a "Fase 4", quitada.** `serverInfo.version` reportava a versão do
  SDK — a ADR atribuía isso a uma limitação do FastMCP, o que vale para o construtor, mas o
  `Server` de baixo nível guarda `version` como atributo público e é justamente ele que o
  handshake lê; agora reporta a versão do prumo. `review_status` ganha o schema
  `ReviewStatus/v1`, definido no domínio e não na fachada.

## [0.65.2] - 2026-08-23

### Corrigido

- **`templates/pj_base/docs/_index.md` prometia cinco alvos que o núcleo não entrega.**
  A seção "Administrative templates" listava `templates/README.md`,
  `Template submissão Plataforma Brasil.docx`, `projeto-cep.md`,
  `data_dictionary_example.csv` e `statistical_analysis_plan_skeleton.md` — todos
  conteúdo do módulo `clinical`, nenhum criado por `prumo init`. Num projeto sem
  `prumo add clinical` os cinco links nasciam mortos; com o módulo aplicado, dois
  caminhos seguiam errados (`projeto-cep.md` e `statistical_analysis_plan_skeleton.md`
  vivem em `docs/studies/<slug>/writing/` desde o layout por escopo,
  [ADR-0022](docs/adr/adr-0022-layout-por-escopo.md)). Mesma classe de resíduo
  corrigida em 0.65.1 para os diretórios por tipo. O catálogo volta a ser só do wiki,
  como o próprio cabeçalho declara; o módulo `clinical` já documenta seus modelos, com
  os caminhos certos, em `docs/templates/README.md`.
- Documentação de topo desatualizada no front do wiki: tagline de `ARCHITECTURE.md` e
  stack de bibliografia do `README.md` ainda descreviam o Obsidian como front corrente,
  e `docs/actions-by-context.md` mandava abrir um grafo que o Zettlr não tem
  (`Ctrl/Cmd + G`).
- `skills/peer-review/examples/sample_report.json` era distribuído no wheel sem nenhum
  ponteiro — nem o `SKILL.md` o citava. Passa a ser linkado logo abaixo do shape do
  `PeerReviewReport/v1`, como os demais assets de skill já fazem.

### Removido

- **Dependências de runtime declaradas e nunca importadas:** `jinja2` (o único vestígio
  era a palavra "Jinja2" num comentário de `core/skills.py`) e `pydantic-settings`
  (nenhum `BaseSettings` no pacote — a config é lida à mão em `core/config.py` via
  `tomllib`; quem precisa dela é o `mcp`, que a traz transitivamente). Toda instalação
  do plugin fica mais leve, sem mudança de comportamento.

### Adicionado

- Teste de regressão `test_projeto_novo_nao_nasce_com_link_morto`: varre os `.md` de um
  projeto recém-criado e falha se algum link relativo apontar para arquivo inexistente.

## [0.65.1] - 2026-08-19

### Corrigido

- **Taxonomia plana sobreviveu à migração do layout por escopo.** `wiki-ingest`
  gravava a fonte em `docs/sources/<slug>.md` e as páginas relacionadas em
  `docs/{concepts,entities}/` — diretórios que o núcleo do `pj_base` não cria e que
  `prumo wiki lint` e `prumo wiki stats` não enxergam (ambos varrem escopos, ADR-0022).
  Toda página do wiki passa a ser nota de `docs/studies/<escopo>/notes/`, distinguida
  pelo `type:` do frontmatter — `concept`, `entity`, `finding`, `source`
  ([ADR-0025](docs/adr/adr-0025-tipo-de-pagina-no-frontmatter.md), generaliza
  [ADR-0023](docs/adr/adr-0023-finding-como-type.md)). A skill também pergunta em qual
  escopo ingerir quando o projeto tem mais de um.
- **`wiki-lint` auditava dois layouts ao mesmo tempo:** frontmatter e relatório já
  apontavam para o escopo, mas as seções 1 (órfãs), 6 (contradições) e 8 (conceitos
  candidatos) ainda globavam `docs/{concepts,entities,findings,sources}/`. As três
  passam a operar por escopo, alinhadas ao que a metade determinística
  (`prumo wiki lint`) já fazia.
- **`templates/pj_base/` prometia quatro pastas que o núcleo não cria** (`concepts/`,
  `entities/`, `findings/`, `sources/`) em `docs/README.md`, `docs/_index.md` e
  `CLAUDE.md` — contradizendo a própria suíte (`test_pj_base_integration` afirma que
  esses diretórios **não** devem existir). `docs/_index.md` segue agrupado por tipo:
  é catálogo por `type:`, não espelho de diretório.
- Mensagem de `prumo capture` para URL não-acadêmica citava `docs/sources/`; docstrings
  de `write/schemas/v1.py`, `write/export.py` e `wiki/__init__.py` descreviam o layout
  anterior.
- Ponteiro morto para `/docs/wiki-schema.md` (arquivo que não existe) na abertura de
  `wiki-ingest` e `wiki-lint` — o frontmatter canônico de cada tipo está nas próprias
  skills.

### Adicionado

- Guard test `test_nenhuma_skill_cita_a_taxonomia_plana` /
  `test_pj_base_nao_promete_pasta_de_taxonomia_plana`: rejeita `docs/concepts/`,
  `docs/{concepts,entities}/` e afins em qualquer `SKILL.md` e em qualquer markdown de
  `templates/pj_base/`. O guard anterior só cobria `references/notes/` e
  `docs/wiki/findings`, e por isso a taxonomia plana passou batida no 0.65.0.

## [0.65.0] - 2026-08-09

### Adicionado

- **`docs/studies/<slug>/` como escopo de escrita**, presente desde o `prumo init`
  (escopo default `principal`, mesmo em projeto de artigo único) — sem máquina de
  promoção nem estado intermediário "projeto sem escopo"
  ([ADR-0024](docs/adr/adr-0024-escopo-desde-o-init.md)). `prumo add study <slug>`
  cria a pasta irmã (`notes/`, `writing/`, `decisions/`); nada se move, nenhum link
  muda de profundidade.
- **`core/pj_layout.py`** como autoridade única de caminho: `find_pj_root`
  (sentinela `.claude/pj_config.toml`) separado de `find_scope_root` (resolve por
  posição — filho direto de `docs/studies/`) ([ADR-0022](docs/adr/adr-0022-layout-por-escopo.md)).
- **Três módulos novos com `_module.toml`** — `code` (`src/`, `tests/`,
  `pyproject.toml`), `data` (`content/01_raw` somente leitura + `02_processed`) e
  `notebooks` (`notebooks/` fora da raiz de leitura) — ativáveis com
  `prumo add <nome>`, somando aos já existentes `ml`/`clinical` (5 módulos reais).
- **`prumo doctor`** detecta layout legado (`references/` na raiz) e `references/`
  ressuscitado ao lado de `docs/references/` (sintoma do autoexport do Better
  BibTeX ainda apontando pro caminho antigo) — convite embutido à adequação
  agêntica; não existe `prumo migrate`.
- **`prumo wiki stats`** ganha `by_scope` (contagem de páginas por
  notes/writing/decisions em cada `docs/studies/<slug>/`).
- **`--force` em `prumo write export`/`prumo write compose`** e `--resource-path`
  passado ao Pandoc: figura referenciada que não resolvia mais vira erro
  (`MissingResourceError`) em vez de docx publicado sem a imagem, em silêncio.

### Mudado

- **⚠ Breaking — bibliografia do projeto muda de raiz.** `references/` sai da
  raiz do `pj_*` e vira `docs/references/`, com `papers/<citekey>/` no lugar de
  `notes/<citekey>/`; `docs/` passa a ser a raiz única de leitura
  ([ADR-0022](docs/adr/adr-0022-layout-por-escopo.md)). **Passo manual obrigatório
  no Zotero:** reaponte o autoexport do Better BibTeX (Preferences → Better
  BibTeX → Automatic export) pro `.bib` no caminho novo — o autoexport grava
  caminho absoluto, então sem esse passo o BBT recria `references/` na raiz
  antiga e desfaz o movimento assim que o Zotero reabrir. `prumo doctor` sinaliza
  os dois sintomas (`legacy_layout`, `references_ressuscitado`).
- **⚠ Breaking — escrita vira escopo.** Todo draft mora em
  `docs/studies/<slug>/writing/`; `docs/protocol.md` vira
  `docs/studies/<slug>/writing/protocol.md` e `docs/decisions/` vira
  `docs/studies/<slug>/decisions/`, numerado por escopo — sem máquina de
  promoção (YAGNI militante, Princípio VI da constitution;
  [ADR-0024](docs/adr/adr-0024-escopo-desde-o-init.md)). Com todo draft a três
  níveis de `docs/`, o campo `bibliography:` dos quatro `skills/write-<kind>/template.md`
  volta a ser um literal invariante: `../../../references/_references.bib`.
- **⚠ Breaking — finding vira `type: finding`, não diretório.**
  `docs/wiki/findings/` (e o fallback `docs/findings/`) somem; finding é uma nota
  comum de `docs/studies/<slug>/notes/` distinguida por `type: finding` no
  frontmatter ([ADR-0023](docs/adr/adr-0023-finding-como-type.md), substitui
  [ADR-0014](docs/adr/adr-0014-findings-canonico.md)).
- **⚠ Breaking — `pj_base` nasce sem estrutura de código.** `src/`, `tests/`,
  `pyproject.toml`, `content/` e `notebooks/` saem do núcleo mínimo e viram
  módulos opcionais com gatilho (`code`, `data`, `notebooks`) — a auditoria de
  estado da arte mostrou que quatro dos cinco arquétipos de pesquisador
  testados nunca abrem nenhum dos quatro (Princípio VI da constitution:
  adições especulativas são recusadas até a dor ser real).
- `wiki-lint` passa a operar por escopo: identidade de página é o caminho
  relativo ao escopo, não o `stem` (páginas homônimas em escopos diferentes
  não se fundem mais); `bib_missing` vira `warning` (só dispara quando há
  citação marcada em algum escopo); `multiple_primary` fica opt-in
  (`check_single_primary`, não roda mais por default).
- `formulate-picot`/`domains/protocol` resolvem por escopo: numeração de ADR
  passa a ser por `docs/studies/<slug>/decisions/`, não mais global ao projeto.
- Módulo `clinical`: o anchor deixa de assumir o escopo `principal` fixo e
  resolve o escopo real do projeto (via `--scope <slug>` quando há mais de um).

### Corrigido

- `prumo write export`/`compose` sobrescreviam `build/exports/*.docx` sem
  guarda; ganham `--force` e recusam com `PrumoError` (comando de correção
  embutido) quando o arquivo já existe.
- `zettlr_export_entry` sempre reexporta com `force=True` — o Zettlr invoca o
  entrypoint só com o caminho do arquivo, sem jeito de passar `--force`.
- `wiki-lint`: `dead_link`/`concept_candidate` resolviam alvo de wikilink
  contra a união global de stems entre escopos, mascarando link morto quando
  um escopo diferente tinha página homônima — resolução agora é só contra o
  próprio escopo que cita.
- `prumo wiki finding` e `prumo wiki study-start` repassavam o `--path` cru
  como escopo: apontados pra raiz do `pj_*` gravavam em `<pj>/notes/`, FORA de
  `docs/`, com exit 0 — invisíveis pra `write prep`, `wiki lint`/`stats` e o
  índice do `qmd`, enquanto o `_index.md` do projeto já ganhava o wikilink
  morto. Ambos resolvem o escopo por `pj_layout.find_scope_root` agora.
- `find_scope_root` exigia caminho dentro de `docs/studies/<slug>/` e falhava
  com exit 1 na raiz do `pj_*` — o cwd de onde as skills invocam `write
  prep`/`draft` e `protocol detect-mode`/`init`/`adr`/`propagate`/`diff` sem
  `--path`. Passa a aplicar a política que `prumo add <módulo>` já usava: um
  escopo resolve sozinho, zero ou vários exigem escolha explícita com os slugs
  disponíveis na mensagem. Caminho de escopo explícito mantém a precedência.
- Mensagens de erro e help do Typer citavam o layout antigo (`references/…`) —
  `prumo doctor` mandava conectar `references/_references.bib` em todo projeto
  novo, e seguir a mensagem acionava o próprio check `references_ressuscitado`.
- `prumo capture <url>` sugeria `/prumo:wiki-ingest <url>` pra URL
  não-acadêmica — namespace inexistente (o plugin inteiro usa
  `/prumo-assist:`). Corrigido pra `/prumo-assist:wiki-ingest <url>`.
- `prumo capture <citekey>` citava `prumo paper extract <citekey>` como
  comando pronto pra rodar, mas o comando exige `--model`/`--date` (sem
  default) e lê o conteúdo via stdin JSON — falha com `Missing option
  '--model'` se executado como escrito. Mensagem agora aponta a skill
  `/prumo-assist:paper-extract <citekey>`, o caminho que o usuário de fato usa.
- `PjRootNotFoundError` (`pj_layout.find_pj_root`) sugeria `--path <raiz>`
  como flag universal pra apontar a raiz do projeto, mas `prumo add study`
  usa `--target/-t`, `prumo protocol propagate/diff/detect-mode` recebem o
  caminho posicional e `prumo write export/compose` não têm flag de raiz
  nenhuma. Mensagem vira neutra: aponta a raiz pelo argumento que o comando
  aceita.

### Documentação

- [ADR-0022](docs/adr/adr-0022-layout-por-escopo.md),
  [ADR-0023](docs/adr/adr-0023-finding-como-type.md),
  [ADR-0024](docs/adr/adr-0024-escopo-desde-o-init.md) registram a governança
  do layout por escopo; [ADR-0014](docs/adr/adr-0014-findings-canonico.md)
  marcado substituído pelo ADR-0023.
- `docs/constitution.md` — emenda PATCH (1.1.1 → 1.1.2): caminho de exemplo do
  Princípio IV atualizado (`references/notes/` → `docs/references/papers/`);
  nenhuma norma alterada.
- Prosa das 15 skills universais e dos docs do repo (`ARCHITECTURE.md`,
  `README.md`, `docs/Research Project Structure.md`,
  `docs/actions-by-context.md`, `docs/onboarding-pesquisador.md`,
  `docs/canvas/*.canvas`) alinhada ao layout novo; módulo `obsidian-power`
  removido do catálogo (Obsidian é legado desde o front Zettlr, v0.62.1).

## [0.64.1] - 2026-07-28

### Corrigido

- **`/prumo-assist:peer-review` deixa de carregar o contrato de prosa.** A skill
  entrou no conjunto `prose: true` na 0.64.0 por erro de desenho: o bloco é
  escrito no imperativo de editor ("remova o intensificador", "reescreva", "use
  vírgula"), e a própria `peer-review` proíbe isso em três lugares — "Não comente
  vírgulas", "Não corrija ortografia ou estilo de linguagem" e "Não reescreva o
  draft. Sugira; o autor decide" —, além de o `when_to_use` já rotear correção de
  forma para `/prumo-assist:scientific-writing`. Eram 36 linhas de instrução
  inexecutável dentro do prompt. O conjunto passa de seis para cinco skills
  (`scientific-writing` e as quatro `write-*`); a remoção usa o caminho
  `strip_block` do gerador. Ver a emenda de 2026-07-28 em
  [ADR-0021](docs/adr/adr-0021-idioma-de-escrita-cascata-e-default.md).

### Documentação

- CHANGELOG da 0.64.0: linha em branco após os cabeçalhos `###` (a resolução de
  conflito do release colara cabeçalho e corpo em três das quatro seções) e
  descrição do audit da C1 corrigida para os dois greps que a versão de fato
  introduziu, não um.

## [0.64.0] - 2026-07-28

### Adicionado

- **Contrato de prosa `prumo:prose`** — bloco machine-owned estampado por
  `gen_indexes.py` nas 6 skills que produzem ou fiscalizam prosa
  (`scientific-writing`, `write-paper`, `write-scientific`, `write-statistics`,
  `write-projeto-cep`, `peer-review`), a partir da fonte única
  `.github/scripts/prose_conventions.md`. Mesmo mecanismo do preflight
  ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)), com `--check` no
  CI garantindo que as 6 nunca divirjam (Princípio VII;
  [ADR-0009](docs/adr/adr-0009-blocos-delimitados.md),
  [ADR-0021](docs/adr/adr-0021-idioma-de-escrita-cascata-e-default.md)).
- **`[writing].language` em `pj_config.toml`** — idioma das skills de prosa,
  validado em `core/config.py` contra `WRITING_LANGUAGES = {pt-BR, en-US}`,
  separado de `paper_extract.language` (contrato do callout de extração).
- **`prumo.prose` e `prumo.locale_lock` no frontmatter de skill** — opt-in pelo
  bloco e trava de idioma por gênero. `write-projeto-cep` declara
  `locale_lock: pt-BR`: CEP/CONEP e TCLE não admitem outro idioma.
- **Convenções C7 (padrão inglês americano) e C8 (economia lexical)** em
  `/prumo-assist:scientific-writing`, e `--lang pt-BR|en-US` nas skills de prosa.
- **`prumo write prep --lang` + `language`/`language_source` no JSON** — a cascata
  determinística (trava de gênero > flag > `[writing].language` > default) passou a
  ser resolvida por `compose.resolve_language`, e não recomposta em prosa pelas
  quatro skills `write-*`, que já dependem do CLI (Princípio II). Efeito colateral
  que é o ponto: `[writing].language` inválido passa a falhar no caminho de
  escrita, onde a chave importa — antes só quebrava `prumo paper` e era honrado em
  silêncio por quem escrevia. A trava de gênero é lida do próprio
  `skills/write-<kind>/SKILL.md`, mesma fonte do template. `scientific-writing` e
  `peer-review` seguem resolvendo em prosa por serem julgamento puro
  ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)).

### Mudado

- **⚠ Breaking — idioma de escrita default passa a `en-US`.** As skills de prosa
  resolvem o idioma por cascata (trava de gênero > pedido explícito >
  `[writing].language` > idioma do texto alvo > `en-US`) e declaram qual usaram.
  Projetos `pj_*` existentes sem a chave caem no default; o passo de detecção
  cobre passe editorial sobre draft pt-BR, e **nenhuma skill de prosa traduz**
  texto existente. Geração do zero em projeto antigo sem a chave sai em inglês —
  acrescente `[writing] language = "pt-BR"` para manter o comportamento anterior.
- **Citação sempre imediatamente antes do terminador do período** (C1), nas duas
  formas Pandoc — marcada (`[@a]`) e narrativa (`@a`, mid-período por construção) —
  e sem a exceção de autor-sujeito: `Liang et al. [@a] propõem X.` vira `X foi proposto
  por Liang et al. [@a].`, e duas fontes com claims distintos viram dois períodos.
  O audit passou a dois greps de superconjunto conservador — `rg "\[@[^]]+\][^.]"`
  para a forma marcada e um `rg -nP` com `(*SKIP)(*F)` para a narrativa, que pula o
  miolo dos colchetes e descarta e-mail — no lugar da heurística acentuada, que
  perdia citação seguida de maiúscula, número ou vírgula.
- **Superlativo é removido, não atenuado** (C4). Intensificador sem número sai do
  texto ou é trocado pelo valor medido; claim descalibrado (causalidade em
  desenho associacional, hedging excessivo, antropomorfismo de modelo) passa a ser
  **sinalizado** com `<!-- REVER -->`, nunca reescrito — reescrever seria
  substância, e substância é peer-review.
- `stamp_block`/`strip_block` genéricos em `gen_indexes.py` absorvem
  `stamp_preflight`; skill que deixa de declarar `prose:` tem o bloco órfão
  removido em vez de mantido em silêncio.

### Removido

- **⚠ Breaking — a gramática legada `[[@citekey]]` deixou de ser reconhecida.**
  A citação Pandoc (`[@key]` bracketed e `@key` narrativa) é a única gramática
  do repo: `core/citations.py` é o único reconhecedor, e nenhum consumidor
  (export, compose, `wiki lint`, `paper graph`, `paper verify-refs`, `write
  review`, `capture route`) enxerga mais o colchete duplo. **Some junto a
  normalização `[[@key]]` → `[@key]` do export**, publicada desde a 0.5.0.
  Detecte o que ainda usa a forma antiga com `rg '\[\[@' docs/ references/`;
  migre trocando `[[@key]]` por `[@key]`, `[[@a]] [[@b]]` por `[@a; @b]` e
  `[[@key|alias]]` por `@key` (narrativa) ou por prosa + `[@key]`.
  Não migrar não corrompe mais nada, mas muda o resultado: um `[[@key]]`
  remanescente agora degrada para `@key` (citação narrativa VÁLIDA) —
  ver "Corrigido" abaixo.

### Corrigido

- **`prumo write list-templates`** reportava `plugin_default: null` para os quatro
  kinds: apontava para `templates/writing/<kind>.md`, esvaziado quando os
  templates migraram para `skills/write-<kind>/template.md`. Agora consome
  `compose.template_candidates`, a mesma fonte de `resolve_template`, com teste
  travando as duas contra divergência futura.
- **⚠ Breaking — `[[@citekey]]` remanescente degrada para `@citekey` em vez de
  corromper o docx.** `normalize_markdown` excluía `@` do charset do wikilink
  (resíduo do reconhecedor legado), então `[[@smith2020]]` passava INTACTO
  pelo normalizador e o pandoc entregava `[(Smith 2020)]` no docx; com alias,
  `[[@jones2021|Jones et al.]]` virava `[(Jones 2021, |Jones et al.)]` — texto
  corrompido DENTRO da citação, sem erro nenhum (verificado contra pandoc
  3.9.0.2). O colchete duplo passa a cair na regra NORMAL de wikilink:
  `[[@key]]` → `@key` (citação narrativa Pandoc válida, renderizada corretamente)
  e `[[@key|alias]]` → `alias` (texto plano, como qualquer wikilink com alias —
  a citação some, então prefira migrar a forma com alias à mão). O pior caso
  deixa de ser docx corrompido.
- **⚠ Breaking — `prumo paper verify-refs --page` passa a verificar citação
  narrativa.** O escopo vinha de `scan_marked_citekeys`, que exclui `@key`
  solta por contrato: página cujas citações são narrativas saía com
  `checked=0`, exit 0 e "✓ 0 referência(s) verificada(s)" — indistinguível de
  página sem citação, mesmo com paper RETRATADO no acervo. O escopo passa a
  usar a captura ampla filtrada pelo bib (`@fulano` de prosa continua fora), e
  um achado `empty-page-scope` (`info`, não muda exit code) substitui o falso
  conforto. Páginas que hoje passam com exit 0 podem passar a sair com 1 —
  que é o gate correto do ADR-0018.
- **Guarda I1 (citação é átomo) cega para a sintaxe-padrão** — a guarda que
  recusa proposta de agente encostando em citação localizava o átomo só por
  regex própria de `review.py`, cega à forma narrativa `@key` da gramática
  Pandoc: um agente podia ancorar sobre a citação e alterá-la preservando a
  citekey (acrescentar locator, mover posição). Passa a usar a união de
  `core.citations.iter_marked_citation_spans`/`iter_narrative_citation_spans`
  (gramática única, Princípio I7) — cobre `[@key]` marcada e `@key` narrativa.
- Template clínico (`data_dictionary_skeleton.md`) prescrevia `[[citekey]]`
  (sem `@`) como âncora bibliográfica — forma que a gramática Pandoc não
  reconhece e que nenhum consumidor de citação enxerga, enquanto
  `PAGE_LINK_RE` a confundia com wikilink de página. Migrado para
  `[@citekey]` célula a célula (o `README.md` do mesmo diretório tinha a
  mesma menção em prosa, também corrigida). Projetos que já copiaram o
  skeleton NÃO mudam de comportamento — editar o template não reescreve
  cópia nenhuma, e `[[citekey]]` sem `@` continua invisível a
  `scan_marked_citekeys` e continua contada como wikilink de página
  (`concept_candidate`). Para colher `broken_citekey` nessas cópias é
  preciso migrar as células à mão para `[@citekey]`; ache-as com
  `rg '\[\[[a-z]' docs/`.
- Buscas embutidas em `paper-manager` (quem-cita) e `wiki-lint` (citekeys
  quebradas) divergiam da gramática única: a primeira casava zero em nota
  Pandoc (reportando "nenhum paper cita este"), a segunda tratava o colchete
  inteiro como citekey e acusava `[@a; @b]` de quebrada.
- `CITEKEY_RE` voltou a ignorar e-mail com local-part não-ASCII: o lookbehind
  bloqueava só letra/dígito ASCII, então `josé@usp.br` rendia o citekey
  fantasma `usp.br` enquanto `joao@usp.br` não rendia nada — mesmo e-mail,
  veredito diferente por causa do acento. A ênfase `_@lima2018 mostrou_`
  segue sendo citação.
- `prumo capture` não classifica mais caminho de arquivo como citekey: `.` e
  `/` são pontuação interna válida no citekey Pandoc, então `artigo.pdf` e
  `docs/notes.md` saíam como `citekey`. Como o ramo de PDF só dispara com o
  arquivo existente, um caminho digitado errado — o erro mais provável —
  perdia a mensagem que ensina o formato certo; agora responde `unknown` com
  a orientação.
- `prumo wiki lint` não acusa mais `dead_link` falso em `mailto:` dentro de
  `links_to`/`sources`/`related`: o caminho do frontmatter pulava só `"://"`,
  enquanto o do corpo já pulava `mailto:` — as duas pontas passam pela mesma
  checagem agora.
- **`prumo paper sync-annotations`/`sync-notes` voltam a funcionar** — o caminho
  que lê o Zotero ao vivo estava morto por três defeitos empilhados, cada um
  mascarando o seguinte, todos invisíveis à suíte porque os testes mockavam
  exatamente os três seams que falhavam (Princípio V — dependência externa
  mockada no seam só protege quando o fixture tem o shape real):
  - `check_zotero_running()` sondava a raiz `127.0.0.1:23119`, que responde
    **404** com o Zotero aberto; como `HTTPError` é subclasse de `URLError`, o
    resultado era `False` e os dois comandos recusavam com "Zotero não está
    rodando". A sonda passa a ser `/connector/ping` (200 + `X-Zotero-Version`),
    agora num seam único `core/deps.zotero_local_api_up()` reusado pelos dois
    lados — `prumo doctor` e `prumo paper` deixam de discordar sobre o mesmo fato.
  - `resolve_citekey()` estourava `AttributeError` contra o Better BibTeX real:
    `item.search` devolve `library` como **string** e não expõe `itemKey`. A
    identidade passa a vir da `custom.uri` de `item.pandoc_filter`
    (`http://zotero.org/users/<id>/items/<key>`), única fonte que carrega o
    caminho de biblioteca **e** o itemKey. O retorno vira o value object
    `ZoteroRef(library_path, item_key)`, e erro JSON-RPC no corpo com HTTP 200
    (`library.get ... not found`) deixa de passar batido.
  - `fetch_children()` montava `/api/users/<libraryID do BBT>/...` — o
    `libraryID` do BBT **não** é o id da API (`users/1` → HTTP 400; biblioteca de
    grupo exige `groups/<groupID>`), e o erro HTTP virava lista vazia, tornando
    "falhou" indistinguível de "sem anotações".
- **Annotations do Zotero passam a ser encontradas.** `/children` nunca devolve
  `itemType: annotation` — annotations são **netas** do item (top-level →
  attachment → annotation) e o filtro `?parentItem=` é ignorado pela API local.
  Novo `fetch_annotations_index()` varre `/items?itemType=annotation` **uma vez
  por biblioteca** e indexa por `parentItem`; `annotations_for_item()` casa o
  índice com os attachments do item. Child notes seguem vindo de `/children`.
- **HTTP 403 da API local vira erro acionável** (`ZoteroApiError`, sob
  `PaperError`) com o passo exato de correção — Zotero → Settings → Advanced →
  "Allow other applications on this computer to communicate with Zotero" — em vez
  de "0 anotações" silencioso.
- **O parser de `.bib` passa a falar os dois dialetos do Better BibTeX.** O
  `prumo paper connect` pina o translator **Better BibLaTeX**
  ([ADR-0020](docs/adr/adr-0020-connect-autoexport-bbt.md)), que usa um vocabulário
  diferente do Better BibTeX legado dos projetos mantidos à mão — e o parser do
  prumo só conhecia o legado. Consequência medida sobre a mesma coleção de 23
  entradas: todo projeto criado pelo caminho recomendado nascia com o acervo **sem
  ano e sem periódico**. Três correções, todas por extensão da cascata de fallback
  que o repo já praticava (`journal → booktitle → publisher` em `sync.py`,
  `eprinttype → archiveprefix` em `verify.py`) — Princípio I:
  - **ano** — novo `core/bib.py:extract_year()`, fonte única usada por
    `paper sync`, `paper find` e `write compose`. Prefere `year` (BibTeX) e cai
    para o ano do `date` (BibLaTeX). O `date` do BBT é **EDTF**, não ISO
    (`biblatexExtendedDateFormat` é default): tolera `1999-uu`, `1897/1913`,
    `2016-07-18T20:26:06`, `2020-21` (estação) e o `~` de aproximação que o BBT
    reescreve como NBSP; devolve `""` quando não há ano determinável (`19uu`) em
    vez de inventar. `_meta.md` deixa de sair com `issued: date-parts: [[null]]`.
  - **periódico** — a cascata do `container-title` em `domains/paper/sync.py`
    ganha `journaltitle`; `shortjournal` fica deliberadamente **fora** (é
    abreviação — "JAMA Oncol." — não o título do periódico).
  - **PMID** — `domains/paper/verify.py` reconhece `eprinttype = {pubmed}` +
    `eprint`, que é como o BibLaTeX carrega o mesmo PMID que o BibTeX põe em
    `pmid`. Sem isso, entrada BibLaTeX sem DOI perdia silenciosamente a checagem
    de existência/retração via PubMed.

  O dialeto legado fica **byte-idêntico** (verificado entrada a entrada nas 23
  reais: zero diferença no dict de metadata). `issued` e `container-title` estão em
  `METADATA_FIELDS`, então **`prumo paper sync` cura retroativamente** as notas já
  geradas com ano nulo e periódico vazio, preservando `tldr`/`role`/`added`.


## [0.63.0] - 2026-07-26

> **Marco:** fecha o programa zero-friction inteiro (F0–F5) — nenhuma fase
> tinha saído como versão própria até aqui. Ver
> [`ROADMAP.md`](ROADMAP.md) e a spec-guarda-chuva
> [`2026-07-22-zero-friction-onboarding-design.md`](docs/superpowers/specs/2026-07-22-zero-friction-onboarding-design.md).

### Adicionado

- **`core/criticmarkup.py`** — módulo de representação de revisão com as 5 marcas
  de CriticMarkup padrão (`{++...++}`, `{--...--}`, `{~~...~>...~~}`, `{==...==}`,
  `{>>...<<}`), parsing canônico, e operações determinísticas accept/reject/apply.
  Substrato da ponte docx ↔ CriticMarkup (spec 2026-07-05, [ADR-0016](docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md)).
- **`normalize_markdown_with_map`** em `core/obsidian.py` — o normalizador virou
  motor de edits de passada única e emite um mapa lossless de fragmentos
  source↔norm (base do transplante da ponte: inverte-se o mapa, nunca a função).
- **Sidecars `reviews/<slug>/{citemap,span-map}.json`** no export docx — versionáveis
  em Git; o citemap registra (occ_id, citekeys, fingerprint, formattedCitation,
  span no texto normalizado) com pareamento hard-fail contra os campos OOXML do
  docx gerado (`CiteMapMismatchError`; invariantes I2/I8).
- **Campos de citação travados** (`<w:lock w:val="sdtContentLocked"/>`, invariante I4) —
  cada campo Zotero sai como content control travado: o coautor não redigita a
  citação no Word; deleta o campo inteiro ou comenta. Guarda pós-build
  (`MissingFieldLockError`).
- **`prumoOcc`/`prumoFingerprint`** no payload OOXML — ocorrência estável por campo
  e impressão digital por chave (cadeia de prioridade: `doi:<valor>` quando o `.bib`
  tem DOI; senão `sha256:` de `itemID|uri` do BBT; senão `bib:` sha256 do entry cru).
- **`prumo write review ingest`/`apply`** — fecham o round-trip docx↔CriticMarkup do
  coautor: guardas A/B e conservação de citação (I2) na entrada, `review.md` como
  worklist viva (decisões por marca, autor ou lote) e confirmação humana explícita
  para cada drop de citação antes do write-back na página (spec 2026-07-05,
  [ADR-0016](docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md)).
- **Servidor MCP `prumo-review`** (`prumo mcp serve`, stdio, registrado em `.mcp.json`) —
  expõe o ciclo de revisão a agentes (Claude Code/Desktop) com 3 tools read-only
  (`review_status`/`review_events`/`review_worklist`) e `propose_prose_edit`, a única
  escrita permitida a um agente: insere marca CriticMarkup pendente no worklist
  `review.md` com âncora `{>>prumo-autor: <autor><<}`, decidida pelo `apply_review`
  humano; guardas hard-fail (âncora única, payload sem citação I3b, tangência de
  citação recusada I1, allowlist de autor, round-trip guard pós-composição) recusam
  qualquer proposta que fabrique ou aproxime citação. A skill `review-reconcile`
  consome essas tools para reconciliar eventos ambíguos do transplante sem nunca
  decidir; modo degradado sem MCP via `prumo write review events --checklist`
  (spec 2026-07-05, [ADR-0017](docs/adr/adr-0017-prumo-mcp-reconciliador.md)).
- **`prumo paper verify-refs`** — verificação determinística de referências do
  `.bib`: existência e título via Crossref, retração via Crossref/PubMed, com
  cache local (TTL 7 dias). `--page` restringe o escopo às citekeys marcadas na
  página (recomendado); `--deep` liga o backend opcional `uvx
  academic-refchecker==3.0.151` (pinado; achados viram `warning`, nunca gate);
  `--refresh` ignora o cache. Só achado `error` deriva exit 1 (spec 2026-07-05,
  [ADR-0018](docs/adr/adr-0018-verificacao-referencias-apis-publicas.md)).
- **Skill `citation-support`** — classifica se cada citação de uma página
  sustenta a frase que a cita (Fully/Partially/Unsubstantiated) a partir dos
  extracts do acervo; sinaliza no chat, nunca edita nem bloqueia — camada LLM
  da Fase 4 ([ADR-0018](docs/adr/adr-0018-verificacao-referencias-apis-publicas.md)).
- **Contrato de preflight uniforme (ADR-0019)** — bloco machine-owned
  (`<!-- prumo:preflight:begin/end -->`) gerado por `gen_indexes.py` e estampado
  nas 16 skills do plugin, a partir do campo novo `requires:`
  (`cli`/`qmd`/`zotero`, canônico em `core/skills.py`/`VALID_REQUIRES`) no
  frontmatter `prumo:` de cada `SKILL.md`. Recusa fail-closed com roteamento
  para `/prumo-assist:start` quando o CLI falta, checa drift de versão
  CLI×plugin via `$CLAUDE_PLUGIN_ROOT` (fallback silencioso sem a variável),
  avisa sobre MCP `qmd` ausente do inventário da sessão e sobre Zotero
  fechado/ausente; skills de julgamento puro (`start`, `peer-review`,
  `scientific-writing`) declaram `requires: []`. Enforcement:
  `gen_indexes.py --check` no CI
  ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)). Fecha os itens
  1–3 da Fase 2 do guarda-chuva zero-friction — item 4 (piloto com 1 colega
  real) segue pendente, a cargo do dono.
- **Skill `start` reescrita como instalador guiado** — além de rotear pelas
  capacidades do plugin, conduz a instalação do stack (uv, CLI `prumo`,
  Zotero, qmd opcional, `prumo init pj_<nome>`) dentro da própria conversa,
  com consentimento explícito por comando e sem simular saída de comando que
  falhou; é o destino único para onde as demais skills roteiam quando o CLI
  falta ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)).
- **`docs/onboarding-pesquisador.md`** — trilha sem terminal (Desktop/Cowork)
  para quem não programa, com o kit de medição do piloto da Fase 2 (cronômetro
  até o primeiro output, meta ≤15 min; o que observar no consentimento da UI);
  a trilha dev do README passa a documentar a instalação do CLI (`uv tool
  install git+https://github.com/raphaelfh/prumo-assistant-for-researcher.git`), que antes não
  aparecia em nenhum lugar do repo.
- **Finding `empty-bib`** (nível info) em `prumo paper verify-refs` — `.bib`
  sem entradas agora emite orientação explícita (adicionar referências no
  Zotero + `prumo paper sync`) em vez de reportar silenciosamente zero
  referências verificadas.
- **`prumo paper connect <coleção>`** — liga `references/_references.bib` a
  uma coleção do Zotero via `autoexport.add` do Better BibTeX, eliminando o
  fio manual do "Keep updated" dentro do próprio Zotero. Guardas anti-fantasma:
  recusa (`AlreadyConnectedError`) se o bib já tem entradas reais, antes de
  qualquer chamada ao Zotero; `find_collection` confirma a existência da
  coleção via `user.groups(true)` (só leitura) ANTES da única chamada MUTANTE
  do projeto no Zotero do usuário, então um nome digitado errado nunca cria
  coleção fantasma (`CollectionNotFoundError`/`AmbiguousCollectionError` com
  sugestões e `--library`); nome de coleção/biblioteca com `/` é recusado
  (`UnsupportedCollectionNameError`) para não aliasar uma cadeia inexistente
  no Better BibTeX. GUID do translator Better BibLaTeX pinado
  (`f895aa0d-f28e-47fe-b247-2ea77c6ed583`); poll de cortesia pós-`add` com
  `exported=False` honesto quando o export ainda não apareceu. `prumo doctor`
  ganha aviso não-bloqueante quando o bib ainda é o placeholder do scaffold,
  com o comando de correção embutido; a skill `paper-manager` ganha a
  operação `connect`; `docs/onboarding-pesquisador.md` ganha a seção "Busca e
  conectores" (marketplace `anthropics/life-sciences`/PubMed, `cookjohn/zotero-mcp`
  rotulado "não validado neste piloto", Zettlr como editor recomendado), e
  registra que o fallback lexical de busca é o caminho normal da persona sem
  terminal — `qmd` segue opcional-avançado ([ADR-0020](docs/adr/adr-0020-connect-autoexport-bbt.md)).
  Fecha o item 1 da emenda da Fase 4 do zero-friction (escopo A); **marco:
  Fase 4 (escopo A) implementada** — smoke real do `connect` contra um
  Zotero vivo segue pendente, a cargo do dono (nenhum teste automatizado
  muta o Zotero real).
- `prumo paper lint` detecta **citekey duplicada no `.bib`** (`duplicate_citekey`,
  severidade `error`) — mesmo blind spot corrigido no `verify-refs` (F4):
  duas entradas homônimas faziam uma esconder a outra em silêncio (inclusive
  uma retratada); uma issue por citekey, com o comando de correção embutido.

### Corrigido
- `prumo init`: os placeholders de nome do template (`pj-NOME` no
  `pyproject.toml`, `pj_<NOME>` nos títulos de README/docs) agora são
  substituídos pelo nome real do projeto nos arquivos copiados — o projeto
  novo não aparece mais como `pj-NOME` no PyCharm/uv. Em `--merge`,
  arquivos preservados do usuário seguem intocados.
- `prumo write export/compose --to docx`: o docx gerado passa por validação
  estrutural (zip, partes obrigatórias, `[Content_Types].xml`) com um retry
  automático do pandoc — absorve o defeito intermitente de "arquivo
  corrompido" documentado no pipeline BBT/pandoc; se persistir, falha alto
  (`CorruptDocxError`) em vez de entregar arquivo suspeito. Guarda de
  regressão das `ZOTERO_PREF` embutidas (`MissingZoteroPrefsError`).
  Fase 1 do spec zero-friction onboarding.
- Filtro `zotero_live_docx.lua`: `item.id` do campo `CSL_CITATION` agora carrega
  SEMPRE o citekey (o id numérico do Zotero migra para `zoteroItemID`) —
  pré-condição do átomo de citação da ponte docx↔CriticMarkup (spec 2026-07-05,
  invariantes I1/I2b).
- Seam do `adeu` (backend de prosa pinado, `uvx adeu==1.29.0`) no `review
  ingest` ganha timeout de 120s — evita travar indefinidamente numa rede lenta
  no primeiro download do `uvx`; erro acionável (`AdeuUnavailableError`) em vez
  de pendurar o comando (fila herdada F2+F3).
- Mensagens de RUNTIME do CLI não citam mais alvos `make` do monorepo do
  autor: o pré-requisito de PDF em `paper extract` aponta
  `prumo paper sync-pdfs` (era `make sync-pdfs`), e o erro de citekey ausente
  no export docx orienta o fluxo pós-connect — adicionar o paper à coleção
  conectada no Zotero (BBT regrava o `.bib`) — em vez de `make sync-paper`
  (follow-up conhecido da Fase 2 do zero-friction).
- Erro "Better BibTeX recusou o autoexport" do `paper connect` ganha o
  comando de correção embutido (conferir Automatic export no BBT e re-rodar) —
  item c3 do backlog do review final da F4.
- Efeitos visíveis do passe /simplify (verificação adversarial dos commits):
  `write export --to <inválido> --out-dir X` responde com o erro pt-BR de
  formato em vez de vazar `KeyError` cru; mensagens de achado `[deep]` do
  `verify-refs` são truncadas em 200 chars (m8 do backlog F4 — o refchecker
  embute referências cruas de milhares de chars); e o fingerprint de citação
  passa a resolver a entrada do `.bib` pela citekey exata do header (o match
  antigo por substring podia, em `.bib` patológico, hashear a entrada errada).
- Tools MCP do `prumo-review` (`review_status`/`review_worklist`) unificam o
  wording de artefato ausente com o domínio: "Sidecar de review ausente em
  `reviews/<slug>`: `<arquivo>`" (era "Artefato de review ausente: ...",
  variante própria da fachada — achado do agente de altitude do passe
  /simplify). A fachada não re-implementa mais leitura/validação de
  `review.md`/`review-comments.yaml`: leitores de domínio novos
  `review.read_worklist` e `review.read_comments_file`, siblings de
  `read_events_file` com o MESMO contrato de erro (fonte única de mensagem,
  Princípio de fachadas finas). A agregação de contagens da tool
  `review_status` também desceu pro domínio (`review.status(page)`), e a
  contagem de drops pendentes — antes duplicada entre a tool e o comando
  `write review ingest` — unificou em `review.count_pending_drops`.
### Mudado
- `prumo doctor` detecta a versão do Zotero pela API local e sinaliza par
  fora do suportado (Zotero 9+) com o comando de correção na mensagem;
  o payload JSON de `external_deps` ganha o campo `version`.
- Export docx imprime nota de primeiro uso no Word (Zotero → Refresh;
  prefs já embutidas).
- Fachadas de `write export`/`write compose` (e o `prumo-zettlr-export`) capturam
  a família enumerada `_EXPORT_CATCHES` — incluindo a nova `PandocFailedError`
  (pandoc exit ≠ 0 com stderr embutido) — em vez do `RuntimeError` amplo
  introduzido em 0.62.1: erro acionável continua saindo limpo no CLI, e erro
  inesperado volta a vazar traceback (filosofia do `cli_run`: bug é bug).
- `prumo write review ingest` agora exige `--force` para re-ingerir uma página
  que já tem `review.md` com marca(s) pendente(s) — protege propostas do
  agente (`propose_prose_edit`) de sobrescrita silenciosa; sem `--force`, falha
  com o comando de correção embutido (fila herdada F2+F3).
- Remediação de estrutura ausente por CONTEXTO em `wiki-ingest` e
  `paper-manager`: as duas skills agora orientam `prumo init pj_<nome>` (via
  `/prumo-assist:start` se o CLI não existir) — nunca tooling do monorepo do
  autor (`make new-project`) nem scaffold manual. `paper-extract` troca, na
  própria descrição da skill, a referência a `make sync-pdfs` (monorepo do
  dono) por `prumo paper sync-pdfs`. Achado R4 do spike da Fase 0
  ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)).
- **⚠ Breaking — Erros de domínio sob `PrumoError`** — as 19 exceções de negócio de `write`
  e `paper` (antes `RuntimeError` cru) herdam de `WriteError`/`PaperError`
  (`domains/<X>/errors.py`), auto-capturadas por `cli_run`; as tuplas de catch
  enumeradas das fachadas (`_EXPORT_CATCHES`, `_REVIEW_CATCHES`,
  `_CONNECT_CATCHES`, `_VERIFY_CATCHES`) viraram builtins inlinados e `cli_run`
  ganhou `exit_codes` declarativo (`ZoteroOfflineError` → exit 2). Comportamento
  do CLI (mensagens e exit codes) inalterado; consumidor da API Python que
  capturava `RuntimeError` deve capturar `PrumoError` (spec 2026-07-26;
  follow-up do passe /simplify).

## [0.62.1] - 2026-07-22

### Adicionado
- `prumo write zettlr-profile` — gera o defaults file de export docx do Zettlr (`docs/templates/prumo-docx.yaml`) com a cadeia `citeproc → zotero_live_docx.lua` (spec 2026-07-22; primeiro release sob ADR-0015).
- Console-script `prumo-zettlr-export` — entrypoint para o custom command do Zettlr disparar o export docx canônico (guardas intactas).
- `core/citations.py` — gramática única de citekey (Pandoc + legado), consumida por export, compose, wiki lint e paper graph (invariante I7 do spec 2026-07-05).
- Export docx canônico falha alto em citekey ausente do `.bib` (warning do citeproc promovido a erro).
- `prumo doctor` acusa perfil Zettlr quebrado (filtro/reference-doc inexistentes) com o fix embutido.

### Mudado
- `templates/pj_base` v2 (Zettlr-ready): sai o vault Obsidian (`.obsidian/`, `references/views/`, `docs/canvas/`); templates nascem Pandoc-puros (`[@key]`, sem callouts); entra `docs/templates/reference.docx` e frontmatter `bibliography:` nos drafts. Projetos existentes não são tocados (Princípio: legado intocado — `normalize_markdown` permanece).
- Skills de escrita/consulta instruem citação Pandoc `[@key]`; leitura/lint aceitam as duas gramáticas.
- `wiki lint` e `paper graph` flavor-agnósticos; links markdown contam como link de entrada no cálculo de órfãs.

### Corrigido
- `prumo write zettlr-profile` valida a raiz do pj_* (exige `references/_references.bib`) em vez de criar o perfil em diretório arbitrário.
- Pitch do pacote (`pyproject.toml`, `prumo --help`, `CITATION.cff`) atualizado: Zettlr no lugar de Obsidian.

### Removido
- Helper morto `_assert_no_missing_citekeys` (parser do pipeline legado `zotero.lua`, sem call-site desde o pipeline live-docx).

### Documentação
- [ADR-0015](docs/adr/adr-0015-pre-1-0-patch-para-releasavel.md) — política de release pré-1.0 (PATCH para tudo releasável; MINOR reservado a breaking/marco). Este é o primeiro release sob a política.
- Guia one-time de setup do Zettlr em `docs/project_guide.md` do pj_base; ROADMAP marca `prumo write preview` como superado pelo Zettlr para projetos novos.

## [0.62.0] - 2026-06-12

### Removido
- **⚠ Breaking** — agents `ml-theory-expert` e `stack-docs-researcher` (pré-pivot, quebrados como distribuídos; [ADR-0012](docs/adr/adr-0012-remocao-agents-ml.md)). Conteúdo preservado no histórico git.

### Mudado
- Skills `paper-extract` e `wiki-ingest` leem PDF com a tool `Read` nativa — removida a dependência fantasma do MCP `pdf-reader` ([ADR-0013](docs/adr/adr-0013-pdf-via-read-nativo.md)).
- Caminho de findings unificado na prosa das skills: `docs/wiki/findings/` com fallback `docs/findings/`, espelhando o resolver real ([ADR-0014](docs/adr/adr-0014-findings-canonico.md)).
- `paper-extract` invoca os backends reais do pacote (`core/config.py`, `domains/paper/callout.py`) — o import legado de `.claude/scripts/` estava quebrado desde a migração pro pacote.

### Documentação
- Slash-commands citados na prosa das skills padronizados na forma qualificada `/prumo-assist:<skill>`.
- Router `start` ganhou catálogo completo gerado (14 skills) — Princípio VII.

## [0.61.0] - 2026-05-31

### Mudado

- **`peer-review` e `write-statistics` adotam os guidelines de 2025**:
  TRIPOD-LLM (Nat Med, jan/2025), DECIDE-AI e CONSORT 2025 entram nos mental
  models; CONSORT-AI deixa de ser citado isolado do CONSORT 2025. Card de
  referência load-on-demand em
  `skills/peer-review/references/reporting-guidelines.md`.
- **`prumo write export --to docx` agora gera citações vivas do Zotero**
  editáveis pelo plugin do Word (campos `ADDIN ZOTERO_ITEM CSL_CITATION` +
  `ADDIN ZOTERO_BIBL CSL_BIBLIOGRAPHY`), em vez de texto plano renderizado
  por `--citeproc`. O pipeline docx agora chama Pandoc com
  `--lua-filter=zotero.lua --lua-filter=zotero_bibliography_docx.lua
  --metadata=zotero_csl_style:<style>` e abandona `--bibliography`/`--csl`
  (o filtro busca metadata direto do Zotero via JSON-RPC do Better BibTeX).
  Formatos `html`/`typst`/`pdf` continuam com `--citeproc` + CSL local.
  Pré-requisitos: Zotero + Better BibTeX rodando em `127.0.0.1:23119` e
  a janela principal do Zotero aberta com uma biblioteca selecionada na
  sidebar (limitação do `Serializer.serialize()` do BBT, que chama
  `getActiveZoteroPane()`). Para itens em grupos do Zotero, adicionar
  `zotero: {library: "<Nome do Grupo>"}` no frontmatter do `.md`.
- **Templates de escrita co-localizados nas skills `write-*`.** `templates/writing/{paper,projeto-cep,scientific,statistics}.md` agora vivem em `skills/write-<kind>/template.md`, alinhando com a recomendação atual de [Anthropic Agent Skills](https://code.claude.com/docs/en/skills) ("each skill is a directory with supporting files bundled inside"). O resolver `prumo_assist.domains.write.compose.resolve_template` foi atualizado e a wheel agora empacota também `skills/` em `prumo_assist/_skills/`. Override por projeto continua em `<pj>/.claude/writing_templates/<kind>.md`.
- **Frontmatter das 13 skills modernizado** para o spec atual:
  - `when_to_use` separado do `description` (gatilhos de invocação em campo próprio).
  - `allowed-tools` declarado por skill (pre-aprova ferramentas comuns sem prompt de permissão).
  - `argument-hint` para autocomplete do `/`.
  - Namespace `prumo:` padronizado em todas as skills (version, schema, determinism, agent_compat, cost_estimate, inputs).
- **`formulate-picot` enxugada** (247 → 159 linhas no SKILL.md). Operações 3 (`propagate`) e 4 (`diff`) migradas para `skills/formulate-picot/references/operations-advanced.md` — carregadas só quando o auto-detect aponta para esses modos.

### Adicionado

- **`prumo wiki lint` ganha 4 checks determinísticos** que antes custavam LLM na
  skill `wiki-lint`: prefixo de `_log.md` fora do padrão (`broken_log_prefix`),
  múltiplas notas `role: primary` (`multiple_primary`), links mortos em
  frontmatter `links_to`/`sources`/`related` (`dead_link`) e conceitos citados
  ≥3× sem página (`concept_candidate`, severity `info`). Contradições e stale
  claims permanecem agênticas (Princípio II). Nova severidade `info` não altera
  `ok`.
- **`prumo.guidelines_reviewed`** (frontmatter de skill) + aviso no
  `prumo doctor` quando os reporting guidelines de uma skill não são
  revisados há > 180 dias. Living guidelines (ex.: TRIPOD-LLM, revisado a cada
  ~3 meses) deixam de envelhecer em silêncio. `peer-review` e
  `write-statistics` já declaram o campo.
- **`prumo write disclosure`** — gera a declaração de uso de IA (PT/EN) a partir
  da proveniência dos artefatos (`extracted_model` em `_meta.md`, `generator` em
  findings, e blocos `_meta:` canônicos futuros), no formato exigido por
  periódicos (Elsevier, Springer Nature, Wiley, T&F, SAGE) e pelo EU AI Act.
  Schema `AIDisclosure/v1`.
- **`Meta.human_reviewed`** (provenance) — registra verificação humana; aditivo,
  Princípio IV. Findings agora gravam `generator` no frontmatter.
- **`prumo_assist/_filters/zotero.lua`** — filtro vendored do Better BibTeX
  ([upstream](https://retorque.re/zotero-better-bibtex/exporting/pandoc/),
  rev `199d652`, 54 KB). Atualizar com `curl -L https://raw.githubusercontent.com/retorquere/zotero-better-bibtex/master/site/content/exporting/zotero.lua -o src/prumo_assist/_filters/zotero.lua`.
- **`prumo_assist/_filters/zotero_bibliography_docx.lua`** — filtro
  companheiro que injeta o campo `ADDIN ZOTERO_BIBL` no docx onde houver
  `::: {#refs} :::`, fechando uma lacuna do upstream (que só emite o
  marcador de bibliografia para ODT). Sem isso, o usuário precisaria
  clicar manualmente "Add/Edit Bibliography" no Word a cada export.
- **`ZoteroNotRunningError` / `ZoteroCitekeyNotFoundError`** em
  `prumo_assist.domains.write.export` — promovem warnings silenciosos do
  filtro Lua a erros acionáveis com mensagens específicas para as três
  causas-raiz típicas (BBT offline, painel do Zotero inativo, citekey
  ausente da biblioteca ativa).
- **`tests/unit/write/test_export_pandoc_cmd.py`** — 17 testes cobrindo
  roteamento de formato em `_build_pandoc_cmd`, resolução dos filtros
  Lua vendored, e as três condições de erro detectadas por
  `_assert_no_missing_citekeys`.
- **`skills/formulate-picot/scripts/`** — 3 scripts Python testáveis substituem blocos `python3 -c '…'` inline:
  - `detect_mode.py` — auto-detect do modo (init/formalize/propagate/diff).
  - `init_picot.py` — lê PicotSpec JSON via stdin e grava `picot.toml` + propaga + cria ADR-0001.
  - `diff_and_adr.py` — gera ADR-N a partir de mudança estrutural já bumpada na TOML.
- **`skills/active-learning/scripts/`** — 5 scripts (`slug.py`, `create_log.py`, `append_step.py`, `archive_finding.py`, `finalize_session.py`) — substituem os blocos Python inline que rodavam helpers de `prumo_assist.domains.wiki.*`.
- **`skills/peer-review/examples/sample_report.json`** — exemplo concreto do schema `PeerReviewReport/v1` para guiar a saída.

## [0.6.0] - 2026-05-17

### Adicionado

- **`prumo init --merge`** — mescla o scaffold em diretório existente **sem sobrescrever** arquivos do usuário. Cria diretórios faltantes, copia apenas arquivos cujo destino não existe; preserva notebooks, dados, customizações de `CLAUDE.md`, etc. Mutuamente exclusivo com `--force`.
- **Wizard interativo Speckit-style em `prumo init`** — quando rodado sem argumento e em TTY, abre fluxo guiado:
  1. Banner Rich com versão e descrição
  2. Prompt do nome (validação de prefixo `srpj_`/`pj_` + `[a-z0-9_]` only)
  3. **Detecção automática** de diretório existente → oferece menu Merge / Force / Cancelar (com confirmação adicional para Force)
  4. Seleção numerada de integrações
  5. `git init` opcional (apenas em modo new)
  6. Próximos passos contextualizados ao modo (new/merge/force)
- **`prumo init --yes` / `-y`** — modo não-interativo para CI: aceita defaults e pula o wizard mesmo em TTY.
- **`prumo init --git` / `--no-git`** — controla `git init` no modo não-interativo (default `--git`).
- **`prumo init -f`** — alias curto de `--force`; **`prumo init -m`** — alias de `--merge`.
- **Validação de nome do projeto** — rejeita prefixos inválidos (deve começar com `srpj_` ou `pj_`) e caracteres fora de `[a-z0-9_]`; mensagens de erro acionáveis.
- **Output JSON enriquecido em `prumo init --json`**: agora inclui `mode` (`new`/`merge`/`force`), `files_copied`, `files_skipped`, `git_initialized` — útil para pipelines CI/CD que parseiam o resultado.

### Mudado

- **`prumo init <project>` (sem flags) agora aceita diretórios vazios** (ou só com `.DS_Store`/`Thumbs.db`) como destino válido, evitando o erro "já existe" em casos comuns como `mkdir srpj_x && cd srpj_x && prumo init .`.
- A mensagem de erro de "diretório já existe com conteúdo" agora **sugere as flags `--merge` e `--force`** com o trade-off de cada uma.
- Argumento `project` agora é **opcional** (default `None`) para habilitar o wizard interativo.

### Anteriormente em [Não publicado] — promovido a 0.6.0

- **`docs/templates/` no scaffold `pj_base/`** — diretório com 5 modelos administrativos prontos para uso em qualquer estudo observacional em saúde, copiados na criação do projeto via `prumo init`:
  - `Template submissão Plataforma Brasil.docx` — layout oficial do CEP/CONEP, usado como `--reference-doc` do `pandoc` para gerar o `.docx` final de submissão.
  - `projeto-cep.md` — esqueleto Markdown da submissão CEP (alinhado com Resolução CNS 466/2012 e CONEP 580/2018).
  - `data_dictionary_skeleton.md` — esqueleto Markdown do dicionário em **duas camadas** (extração fornecedor→nós + engineered features ancoradas em `[[citekey]]`).
  - `data_dictionary_example.csv` — gabarito pipe-delimited (NAME · DEFINITION · MIN_OR_VALUES · MAX · UNIT · TYPE · WINDOW · SELECTION_RULE · AVAILABLE · NOTES) com convenções (UPPERCASE ≤10 chars, datas `YYYY-MM-DD`, decimal `.`, missing `NA`).
  - `statistical_analysis_plan_skeleton.md` — esqueleto de SAP com seções pré-especificadas: princípios, populações de análise, descritiva, sobrevida (KM + Fine-Gray), longitudinais (spaghetti/Sankey), exploratórias, 6 análises de sensibilidade tipo, subgrupos, reporting (STROBE/RECORD/CONSORT/SPIRIT/TRIPOD-AI).
  - `README.md` no diretório explica o fluxo: `cp templates/<X> docs/<Y>`, edição da cópia, geração do `.docx` final via `pandoc --reference-doc`.
- `docs/_index.md` do scaffold lista o diretório `templates/` em seção dedicada "Administrative templates".

## [0.5.0] - 2026-05-04

### Adicionado

- **`/prumo-assist:formulate-picot`** — skill agêntica que formaliza/propaga/versiona o PICOT do projeto. Mantém spec canônica em `.claude/picot.toml`, renderiza blocos delimitados em `protocol.md` e `project.md`, e gera ADR `adr-NNNN-picot-v<N>` quando hipótese ou campo estrutural muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff). Domínio `domains/protocol/` com `PicotSpec/v1` (Pydantic), `picot_io`, `render`, `diff`, `adr`, `ops`. CLI: `prumo protocol propagate|diff`.
- **`/prumo-assist:active-learning`** — skill agêntica que conduz sessão de estudo Socrática estruturada em 5 steps (Recall → Anchor → Connect → Apply → Reflect) sobre um tópico, ancorada nas fontes do projeto (wiki + acervo). Sessão ad-hoc 15-25 min com citação strict (só citekeys do acervo + `[REF FALTANTE]`). Log estruturado em `docs/wiki/study-sessions/<topic>-<data>.md` (`SessionLog/v1`). No step Reflect, oferece arquivar insight como finding via helper `archive_as_finding` (extraído de `wiki-query` para reuso).
- **Família `/prumo-assist:write-*`** (4 skills agênticas + backend compartilhado):
  - `write-paper` — draft IMRaD venue-aware a partir do PICOT + papers do acervo.
  - `write-projeto-cep` — projeto pra CEP brasileiro (TCLE, Cronograma, Conformidade ética CNS 466/2012 + 510/2016, LGPD).
  - `write-statistics` — Plano de Análise Estatística (PAE): outcome operacional, sample size, métricas, sensibilidade, splits anti-leakage.
  - `write-scientific` — prose acadêmica genérica flexível (1 seção, parágrafo, expansão de seed).
  - Backend: `domains/write/compose.py` (`read_inputs`, `resolve_template`, `compose_path`, `write_output`, `extract_missing_refs`); schemas `ComposeInputs/v1`, `WriteOutput/v1`, `PaperSummary`, `FindingSummary`. 3 modos de output: `drafts/` (default), `--into <path>` (bloco delimitado), `--out <path>` (livre).
  - 4 templates default em `templates/writing/{paper,projeto-cep,statistics,scientific}.md`. Override por projeto em `.claude/writing_templates/<kind>.md` ou `--template <path>`.
  - CLI: `prumo write list-templates [--json]` lista templates resolvíveis.
- Citação strict transversal (formulate-picot, active-learning, write-*): só `[[@citekey]]` que existe em `references/_references.bib`. Falta vira `[REF FALTANTE: <descrição>]` — nunca invenção.

## [0.4.0] - 2026-05-03

### Adicionado

- **Layout α de notas**: cada paper agora vive em `references/notes/<citekey>/` com `_meta.md`, `_extract.md`, `_annotations.md` separados. Permite múltiplas child notes por paper (PR-N2 traz `note__*.md`) e melhora retrieval por chunk pequeno + metadata estável.
- **`prumo paper migrate-layout`**: comando one-shot que desmembra `<key>.md` legado em pasta α, preservando histórico via `git mv`. Idempotente.
- **`core/note_paths.py`**: helpers de path centralizados (`note_dir`, `meta_path`, `extract_path`, `annotations_path`, `child_note_path`, `slugify`, `iter_note_meta_files`, `citekey_from_meta_path`). Domínios `paper.{graph,find,lint,sync,zotero,callout,migrate}` usam essas funções como single source of truth.
- **Nova regra de lint**: `subdir_without_meta` — sinaliza pasta `notes/<key>/` sem `_meta.md` (migração interrompida ou pasta órfã).

### Modificado

- `prumo paper sync` escreve em `<key>/_meta.md` (era `<key>.md`).
- `prumo paper sync-annotations` escreve em `<key>/_annotations.md` dedicado (era bloco delimitado dentro do `<key>.md`).
- `/prumo-assist:paper-extract` escreve em `<key>/_extract.md` dedicado (era callout dentro do `<key>.md`).
- `paper graph`, `paper find`, `paper lint`, `set_primary` aceitam ambos layouts durante transição (graceful degradation; preferência por α quando ambos existem).
- `templates/pj_base/references/templates/literature_note.md` reflete o novo layout (campo `pdf:` ajustado pra `../../pdfs/<key>.pdf`).

## [0.3.0] - 2026-05-03

### Removido — ⚠ Breaking

- **Skills de código spin-off**: `tabular-eda`, `data-cleaning`, `clinical-metrics` removidas deste repo. Escopo do plugin volta a "knowledge, bibliography & academic writing for clinical research" (a tagline real). Quem dependia delas deve migrar pro `prumo-code-assist` (repo separado) quando publicado. O conteúdo continua acessível via histórico git (`git log -- skills/tabular-eda`).
- **`agents/` revistos**: `ml-theory-expert` e `stack-docs-researcher` permanecem por enquanto (cobrem fundamentação teórica e consulta de docs, úteis também na escrita); serão reavaliados na próxima minor.
- Tarball gerado por `prumo init` deixa de conter as skills removidas (consequência direta).

### Simplificado — refator interno

- **Fachadas CLI ↔ API**: introduzido `core/cli_op.cli_run` (context manager) que encapsula `Console + try/except PrumoError + typer.Exit(1)`. Subcomandos Typer ficam ~30% menores. Os `domains/<X>/api.py` viraram re-exports puros (sem wrappers passthrough).
- **Resolução de paths**: `core/paths.py::resolve_resource/find_resource` consolida a busca de `templates/` e `skills/` (instalado vs worktree dev) que estava duplicada no CLI e na API pública.
- **Documentação dividida**: `ROADMAP.md` (305 linhas) virou `ARCHITECTURE.md` (estável: princípios, layout, fluxo) + `ROADMAP.md` (dinâmico: status PR + próximas fases).
- **Manifests bumpáveis sem garfo**: novo `.github/scripts/sync_manifest_version.py` propaga `_version.py` pra `plugin.json`/`marketplace.json` (`--check` em CI futuro).
- **Tests por domínio**: `tests/unit/<core|paper|wiki|write|capture>/` espelha `src/prumo_assist/`. 97 testes preservados.

## [0.2.0] - 2026-04-28

### Adicionado — fundação do CLI Python (PR0–PR3)

- **Pacote Python instalável** `prumo-assist` (entry point `prumo`).
  Build via hatchling, distribuível por `uv tool install` ou `pipx`.
- **`core/`** (transversal, 7 módulos): `config`, `bib`, `csl`, `obsidian`,
  `skills` (parser SKILL.md frontmatter rico + registry), `provenance`
  (bloco `_meta` + JSONL trace local-only), `output` (Rich + JSON dual).
- **Domínio `paper`**: 7 subcomandos `prumo paper {sync, graph, find, lint,
  set-primary, sync-pdfs, sync-annotations}`. 6 vendor scripts migrados
  (paper_sync, cite_graph, cite_lookup, paper_extract, sync_zotero_pdfs,
  sync_zotero_annotations) sem mudança comportamental + `lint.py` novo.
- **Domínio `wiki`**: `prumo wiki {lint, index, stats}` — auditoria
  determinística (broken citekeys, orphan pages, missing frontmatter),
  reindex via subprocess `qmd`, contagem por tipo.
- **Domínio `capture`**: `prumo capture <input>` — router que classifica
  DOI/arXiv/PDF/URL/citekey e sugere próxima ação.
- **Domínio `write`**: `prumo write {export, compose, list-styles,
  extract-comments}` — TRANSFORM de `export_page.py` (single + multi-page
  Pandoc/Typst) e `extract_comments.py` (.docx → checklist Markdown).
- **`integrations/claude_code/`**: instala skills em `<pj>/.claude/skills/`
  com base na `SkillRegistry`. `BaseIntegration` abre caminho pra
  Cursor/Codex/Gemini sem mexer em `core/` ou `domains/`.
- **`templates/pj_base/`**: scaffold de novo `pj_*` sem vendor scripts
  (acabou o copy-pasta × N submodules).
- **Skill nova `peer-review`**: simula revisão crítica de drafts acadêmicos
  com mental models clínicos (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE).
- **API Python pública** (`from prumo_assist import api`): paridade com CLI
  pra notebooks Jupyter.
- **Schemas Pydantic versionados forward-only** (`PaperCallout/v1`).
- **Testes**: 97 unit + integration; ruff + mypy strict zerados.
- **CI** (GitHub Actions): matrix Python 3.11/3.12, ruff + mypy + pytest.
- **`ROADMAP.md`**: documento didático com princípios, layout, fluxo de dados,
  faseamento (PR0–3 MVP) e roadmap pós-MVP por trigger.
- **`CITATION.cff`**: prumo-assist citável academicamente.

### Em curso

- Plugin marketplace continua em v0.1.1 (skills + agents existentes
  preservados intactos). Bump pra v0.2.0 do plugin acontece quando o spin-off
  das skills de código (`tabular-eda`, `data-cleaning`, `clinical-metrics`)
  for confirmado pra `prumo-code-assist` (repo separado).

## [0.1.1] - 2026-04-26

### Adicionado
- `.claude-plugin/marketplace.json` — o repo agora é simultaneamente plugin e marketplace de 1 entry, permitindo `/plugin marketplace add raphaelfh/prumo-assist` direto.
- CI (`.github/workflows/validate-manifests.yml`) que valida `plugin.json` e `marketplace.json` contra JSON Schema em cada PR/push.
- Schemas explícitos em `.github/schemas/` (referência viva do que o Claude Code aceita).
- Este `CHANGELOG.md`.

### Corrigido
- `plugin.json#repository` passou de objeto `{type, url}` para string — formato que o validador do Claude Code aceita (rejeitava o anterior em `/plugin install`).
- README: link de instalação corrigido (`raphaelfh/prumo-assist`, não `claude-prumo-assist`) e comando atualizado para o formato qualificado `prumo-assist@prumo-assist`.

## [0.1.0] - 2026-04-22

### Adicionado
- Estrutura inicial do plugin extraída do monorepo `multimodal_projects`.
- 8 skills: `tabular-eda`, `data-cleaning`, `clinical-metrics`, `paper-manager`, `paper-extract`, `wiki-ingest`, `wiki-query`, `wiki-lint`.
- 2 agents: `ml-theory-expert`, `stack-docs-researcher`.
- MCP `qmd` (busca BM25 + vector + rerank local no wiki).

[Não publicado]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.70.2...HEAD
[0.70.2]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.70.1...v0.70.2
[0.70.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.70.0...v0.70.1
[0.70.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.69.1...v0.70.0
[0.69.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.69.0...v0.69.1
[0.69.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.68.1...v0.69.0
[0.68.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.68.0...v0.68.1
[0.68.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.67.2...v0.68.0
[0.67.2]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.67.1...v0.67.2
[0.67.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.67.0...v0.67.1
[0.67.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.66.0...v0.67.0
[0.66.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.65.2...v0.66.0
[0.65.2]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.65.1...v0.65.2
[0.65.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.65.0...v0.65.1
[0.65.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.64.1...v0.65.0
[0.64.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.64.0...v0.64.1
[0.64.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.63.0...v0.64.0
[0.63.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.62.1...v0.63.0
[0.62.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.62.0...v0.62.1
[0.62.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.61.0...v0.62.0
[0.61.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.6.0...v0.61.0
[0.6.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/raphaelfh/prumo-assistant-for-researcher/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raphaelfh/prumo-assistant-for-researcher/releases/tag/v0.1.0
