# ADR-0026 — Servidor MCP cobre o domínio `paper` e passa a se chamar `prumo`

- Status: aceito
- Data: 2026-08-23
- Origem: [[2026-08-23-ponte-zotero-auditoria-design]] (D3); emenda a [ADR-0017](adr-0017-prumo-mcp-reconciliador.md)

## Contexto

A ADR-0017 criou `mcp_server.py` com quatro tools do ciclo de revisão e justificou a existência do servidor por uma premissa que a auditoria de 2026-08-23 **verificou e achou fraca**: "nessa superfície não há terminal". O [`onboarding-pesquisador.md`](../onboarding-pesquisador.md) se intitula "sem terminal", mas a trilha que ele descreve roda `curl | sh`, `uv tool install`, `prumo doctor` e `prumo init` dentro do Cowork — "sem terminal" significa que o pesquisador não digita, não que não haja execução. A única superfície sem execução é "chat simples sem pasta conectada", onde o servidor também não sobe, porque é `command: "prumo"` e o CLI não está instalado. **Quem reabrir esta decisão não deve reciclar o argumento de alcance.**

O que sustenta estender é outra coisa, e ela não estava enunciada na 0017: **tool MCP é descobrível sem carregar skill**. Comando Bash só existe para o agente se a prosa de alguma skill o mencionar; 14 das 16 skills declaram `Bash(prumo …)`, o que torna o domínio `paper` inacessível em conversa solta. Somam-se dois ganhos menores: permissão granulável por operação — hoje `Bash(prumo paper *)` é wildcard sobre 14 subcomandos, incluindo o único que muta o Zotero do usuário — e contrato de erro tipado em vez de o agente parsear stdout e exit code.

O custo de contexto foi medido, não estimado: uma tool read-only tem ~8 linhas, e sete tools custam ~600–800 tokens de definição por sessão — duas ordens de grandeza abaixo dos ~23k de um MCP de terceiro com 52 tools, que é o motivo separado pelo qual nenhum deles entra no `.mcp.json` do plugin.

A 0017 também declarou três lacunas de versionamento e as adiou. Uma delas está registrada com premissa incorreta: "`serverInfo.version` reporta a versão do SDK (limitação do FastMCP 1.28.1, que não expõe parâmetro de versão de aplicação)". O `FastMCP.__init__` de fato não aceita `version`, mas o `Server` de baixo nível guarda `version` como atributo **público** e é exatamente ele que `create_initialization_options()` lê (`server_version=self.version if self.version else pkg_version("mcp")`).

## Decisão

O servidor expõe o núcleo do domínio `paper` como sete tools — `paper_sync`, `paper_find`, `paper_lint`, `paper_graph`, `paper_verify_refs`, `paper_sync_all` e `paper_connect` — fachadas finas sobre `domains/paper/api.py`, com **zero lógica nova**, na mesma disciplina das tools de revisão: dado plano na saída (nunca objeto de domínio) e contrato de erro unificado, com `FileNotFoundError` e `PrumoError` re-levantados como `ValueError` carregando a mensagem pt-BR do domínio, que já embute o comando de correção. Ficam de fora `migrate-layout` (one-off), `extract-prep` (preflight interno de skill), `extract`, e a flag `--deep` de `verify-refs` (dispara `uvx`: subprocess externo não é fachada fina).

`paper_connect` é a segunda tool mutante do servidor e a primeira que muta estado **fora** do repositório. A constante `MUTATING_TOOLS` nomeia as duas e é coberta por teste, de modo que tool nova que mute algo entre nessa lista conscientemente e não por descuido. As guardas anti-coleção-fantasma continuam no domínio ([ADR-0020](adr-0020-connect-autoexport-bbt.md)), inclusive a mensagem que afirma "NADA foi criado" — a fachada não as reimplementa nem as afrouxa.

O servidor passa a se chamar `prumo`, não `prumo-review`: o nome é o prefixo das tools no agent-host (`mcp__prumo__paper_find`), e um servidor que cobre revisão e bibliografia sob um nome de revisão mente sobre o próprio escopo. É **breaking** em `.mcp.json` e no `allowed-tools` de `review-reconcile`.

As três lacunas de versionamento da 0017 ficam quitadas nesta ADR, como pré-requisito das tools novas e não como trabalho paralelo: `serverInfo.version` reporta `_version.__version__` (via `Server.version`, com o acoplamento ao nome `_mcp_server` coberto por teste que falha alto se o SDK mudar); `review_events` devolve o envelope `ReviewEventsFile/v1` completo em vez da lista nua, alinhando a tool ao que o `--json` do CLI já emitia; e `review_status` ganha o schema `ReviewStatus/v1`, definido no domínio e não na fachada.

## Consequências

O domínio `paper` fica utilizável sem carregar skill, e a operação que muta o Zotero deixa de estar escondida num wildcard de Bash. O `.mcp.json` do plugin continua sem qualquer MCP de terceiro.

O rename quebra consumidores. Foi feito **agora** exatamente por isso: com 0 usuários externos o custo é nulo, e cresce monotonicamente com a adoção — adiar é escolher pagar mais. Quem tiver `mcp__prumo-review__*` em configuração própria precisa trocar o prefixo.

A superfície de protocolo passa de 4 para 11 tools, e com ela a disciplina de compatibilidade. Diferente da 0017, a dívida de versionamento não é herdada: os três retornos que atravessam a fronteira carregam versão explícita desde este commit. O que permanece em aberto é `paper_verify_refs` fazendo I/O de rede (Crossref/PubMed) dentro de uma tool — aceitável porque é leitura e tem cache em disco, mas é a única tool do servidor cuja latência não é local.

`MUTATING_TOOLS` é convenção interna, não mecanismo: ela não impede nada em runtime, só documenta e testa a intenção. Se um dia a distinção precisar valer de verdade (por exemplo, um modo read-only do servidor), vira ADR nova.
