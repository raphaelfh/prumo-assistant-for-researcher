# ADR-0028 — Criação de coleção do Zotero como opt-in explícito de `prumo paper connect --create`

- Status: aceito
- Data: 2026-08-24
- Origem: emenda de [ADR-0020](adr-0020-connect-autoexport-bbt.md), que decidiu **impedir** a criação de coleção; este permite a criação **sob condição**. Regrounding ao vivo contra Zotero 9 + Better BibTeX em 2026-08-24. Precedentes: [ADR-0007](adr-0007-zotero-stdlib-urllib.md) (Zotero/BBT via `urllib` stdlib), [ADR-0026](adr-0026-mcp-prumo-dominio-paper.md) (fachada MCP do domínio `paper`).

## Contexto

A ADR-0020 registrou como "RISCO central" que `autoexport.add` **cria** a coleção no Zotero — e a cadeia de pais inteira junto — quando o `bbt_path` informado não existe, sem falhar e sem avisar. A resposta daquele ciclo foi puramente defensiva: `find_collection` confirma a existência por leitura (`user.groups(true)`) antes de qualquer chamada mutante, e nome que não casa vira `CollectionNotFoundError` com sugestões do `difflib` e a garantia "NADA foi criado".

O efeito prático é que o pesquisador que ainda não tem a coleção no Zotero — o caso normal de quem está começando um projeto — precisa sair do terminal, criar a coleção na UI do Zotero e voltar. Para a persona sem terminal do piloto da Fase 2, esse ida-e-volta é exatamente o tipo de fio manual que a Fase 4 existia para eliminar.

Um regrounding dedicado em 2026-08-24 confirmou ao vivo, contra o Zotero 9 + BBT do dono, que o comportamento da ADR-0020 não mudou: `autoexport.add` com `bbt_path` `/My Library/__prumo_probe__/__prumo_child__` devolveu sucesso (`{"libraryID":1,"key":…}`) e materializou **as duas** coleções — a filha e o pai. O mesmo regrounding acrescentou dois fatos que a ADR-0020 não tinha: o BBT desta versão **não expõe** `autoexport.remove` nem `autoexport.list` (`-32601 Method not found`, não "não groundado"), e a API local do Zotero recusa `DELETE /api/users/0/collections/<key>` com `501 Method not implemented`. Não existe, portanto, canal programático de desfazer — nem para a coleção, nem para o autoexport.

## Decisão

`prumo paper connect "<nome>" --create` cria a coleção no Zotero e liga o autoexport num passo só. Sem a flag, o comportamento da ADR-0020 é preservado integralmente, incluindo a mensagem "NADA foi criado" — que agora também aponta o `--create` como saída.

A criação é **opt-in explícito e nunca inferido**: não há fallback "não achei, então crio". `connect.py` separa o que era um caminho só em dois — `find_collection` continua resolvendo uma referência **existente** (leitura pura), e `plan_connection` decide, sem mutar nada, qual `bbt_path` o `autoexport.add` receberá, devolvendo um `ConnectPlan` que marca **cada segmento** do caminho como já existente ou a criar. O eco desse plano antes da mutação é requisito, não cortesia: como o BBT materializa a cadeia inteira, o pesquisador precisa ver quantas coleções nascem antes de autorizar.

A criação é sempre de **uma** coleção, na raiz da biblioteca alvo: `name` nunca é um path. `"Pesquisa/Nova"` com `--create` é recusado com `UnsupportedCollectionNameError` **antes de qualquer round-trip** — sem a flag, o `/` só aliasaria um export errado; com a flag, ele viraria criação real de um segmento por nível, que é precisamente o modo de falha que este comando existe para evitar. Pendurar a coleção sob um pai continua sendo trabalho da UI do Zotero, seguido de `connect` sem `--create`. As demais guardas da ADR-0020 seguem valendo e todas antecedem a mutação: `AlreadyConnectedError` (bib com entradas reais) continua sendo a primeira e é puramente local; `AmbiguousCollectionError` continua exigindo `--library`, porque `--create` não desempata nada — criar uma terceira "Pesquisa" ao lado de duas existentes seria o pior desfecho possível; e o `/` cru em qualquer segmento de uma cadeia resolvida continua recusado.

A biblioteca alvo da criação, quando `--library` não é informada, é a **pessoal** (`id == 1`), não a primeira encontrada: criar no acervo próprio é sempre menos invasivo que criar num grupo compartilhado com outras pessoas. `--library` informada precisa existir — criar numa biblioteca que o Zotero não conhece seria um modo de falha novo, não um default. As bibliotecas saem de um caminho próprio (`_libraries_from`) sobre a mesma resposta de `user.groups`, porque biblioteca sem coleção nenhuma não produz `CollectionRef` algum e mesmo assim é alvo válido.

A confirmação interativa mora no CLI, não no domínio: `connect_collection` recebe um callback `confirm` e só o consulta quando o plano cria algo. Sem TTY e sem `--yes` — CI, pipe, `--json` — a resposta é **não** (`CreationDeclinedError`, exit 130): travar num prompt que ninguém vê seria pior, e assumir "sim" contrariaria o opt-in.

A tool MCP `paper_connect` **não** recebe `create` e mantém a assinatura `(pj_path, collection, library)`. Ela já está em `MUTATING_TOOLS` e é invocável por agente; um parâmetro de criação nesse caminho deixaria um agente materializar coleções no acervo real do pesquisador sem humano no meio. A criação é decisão de humano com o plano na frente dos olhos, e o único lugar onde isso é verdade é o CLI. Um teste de desenho pina a assinatura da fachada.

A mesma restrição vale, por regra escrita, no caminho que de fato é mais permissivo: a skill `paper-manager` roda `prumo paper connect` direto por `Bash(prumo paper *)`, então nenhum tipo de assinatura a impede de acrescentar a flag — só a instrução. A skill passa a mandar, como regra dura, que o agente **nunca** acrescente `--create` nem `--yes` por iniciativa própria: diante de uma coleção inexistente ele mostra as sugestões do CLI, pergunta, e só roda com `--create` quando o pesquisador pediu a criação em palavras dele; o eco do plano é repassado como veio. `docs/onboarding-pesquisador.md` documenta a flag pelo mesmo enquadramento, e corrige de passagem a afirmação que este ADR tornou parcialmente falsa ("um typo nunca cria nada no Zotero" passa a valer explicitamente para o caminho sem `--create`).

Não há desfazer, e a ausência é declarada em vez de contornada: a mensagem de sucesso do `--create` diz, em uma linha, que remover é manual na UI do Zotero (a coleção e o autoexport em Preferences → Better BibTeX → Automatic export). Não se inventa `--undo`, porque o canal não existe.

## Consequências

O ganho é o passo único para quem está começando: `prumo paper connect "Meu Projeto" --create` sai de zero a bibliografia conectada sem abrir a UI do Zotero. O custo é que o comando passa a ter um caminho que **cria** estrutura no acervo real, e a única barreira entre um typo e uma coleção fantasma é o eco do plano — por isso ele é obrigatório e lista segmento a segmento, e por isso o não-interativo sem `--yes` recusa em vez de seguir.

A recusa por ausência de undo tem preço assumido: quem criar a coleção errada com `--create --yes` terá de limpar na UI do Zotero, e o CLI não tem como ajudar. Se uma versão futura do BBT expuser `autoexport.remove`/`autoexport.list`, um `--replace` (deferral já registrado pela ADR-0020) e uma limpeza assistida passam a ser possíveis — e exigirão grounding próprio e ADR novo, não a reinterpretação deste.

Nenhum teste toca o Zotero real: o seam `connect._http_post_json` segue sempre mockado, e os testes do `--create` asseguram nas **chamadas do mock** — não só na exceção — que os caminhos de recusa (sem `--create`, `/` no nome, ambiguidade, biblioteca inexistente, confirmação negada) não emitem `autoexport.add` nenhum. `prumo doctor` não muda: o aviso de bib placeholder não conhece uma "coleção pedida", então mencionar `--create` ali seria conselho sem contexto; o ponteiro para a flag vive onde ele tem contexto, na mensagem de `CollectionNotFoundError`.
