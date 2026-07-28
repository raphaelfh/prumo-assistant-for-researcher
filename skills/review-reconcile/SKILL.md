---
name: review-reconcile
description: "Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana)."
when_to_use: |
  Depois de um `prumo write review ingest`, quando `prumo write review events`
  (ou o tool MCP `review_status`) mostrar eventos `unanchored-mark`,
  `ambiguous-anchor` ou `non-identity-span` pendentes e o usuário pedir para
  reconciliar, resolver ou revisar essas ambiguidades do round-trip de revisão
  docx↔CriticMarkup. NÃO é para decidir eventos de citação
  (`citation-touched-prose`/`citation-drop`) nem para aplicar decisões — isso é
  sempre `prumo write review apply`, rodado pelo humano.
argument-hint: "--page <page.md>"
allowed-tools: Read Glob Grep Bash(prumo write review events *) Bash(prumo doctor *) mcp__prumo-review__review_status mcp__prumo-review__review_events mcp__prumo-review__review_worklist mcp__prumo-review__propose_prose_edit
prumo:
  version: 1.0.0
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~3-10k tokens (depende do nº de eventos ambíguos)
  inputs:
    page: required
  requires: [cli]
---

# Review Reconcile — reconciliador de eventos ambíguos do round-trip

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

Opera sobre o ciclo de revisão docx↔CriticMarkup (`prumo write review ingest` →
`reviews/<slug>/{review.md,events.yaml,review-comments.yaml}`). Fecha os
eventos que o transplante determinístico não conseguiu localizar sozinho —
**propõe, nunca decide**: só insere marcas CriticMarkup pendentes no worklist
(`review.md`), com autoria `agente`, via o servidor MCP `prumo-review`
(`propose_prose_edit`). Quem aceita ou rejeita — inclusive as propostas desta
skill — é sempre o humano, com `prumo write review apply`.

## Pressupostos

- Um ciclo de revisão já existe para a página: `prumo write review ingest
  <reviewed.docx> --page <page>` já rodou e gerou `reviews/<slug>/events.yaml`
  + `review.md`. Sem isso, todo comando abaixo falha com o hint embutido
  (`prumo write review ingest ...`).
- O CLI `prumo` está no PATH (`prumo doctor`; senão `uv tool install
  git+https://github.com/raphaelfh/prumo-assist`).
- O servidor MCP `prumo-review` (tools `review_status`, `review_events`,
  `review_worklist`, `propose_prose_edit`) pode ou não estar conectado nesta
  sessão (registrado em `.mcp.json` como `"prumo-review"`, roda via `prumo mcp
  serve`). O fluxo abaixo usa MCP quando disponível e cai para `prumo write
  review events --page <page> --json/--checklist` quando não — **`propose_prose_edit`
  não tem equivalente CLI** (fora de escopo criar um); sem MCP, o Passo 2 vira
  só orientação ao humano, nunca edição manual do worklist por esta skill.

## Fluxo

### 1. Levantar os eventos

- Com MCP: opcionalmente `review_status(page)` primeiro (contagens por kind —
  visão rápida antes de entrar evento a evento), depois `review_events(page)`
  para a lista completa.
- Sem MCP: `prumo write review events --page <page> --json` (mesmos campos,
  dentro de `{schema_version, page, events}`) — `--checklist` também é útil
  aqui: mesma lista numerada em pt-BR com a AÇÃO por kind, boa referência para
  o resumo do Passo 4.
- Cada evento tem `kind`, `detail` (mensagem pt-BR já pronta explicando a
  causa). Os campos `author` (o **coautor do Word** que fez a mudança original
  — nunca "agente") e `mark_excerpt` (o texto afetado: `a` para `del`/`sub`/`highlight`, `b` para `ins`/`comment`) estão presentes nos 4 kinds de marca
  (`unanchored-mark`, `ambiguous-anchor`, `non-identity-span`,
  `citation-touched-prose`); `citation-drop` tem `author: null` (o leitor
  OOXML não captura o autor da deleção, mas `mark_excerpt` continua presente
  — a citação formatada, `formattedCitation`) e `applied` não carrega nenhum
  dos dois (é histórico). Só em eventos de citação, `occ_id`/`citekeys`.

### 2. Para cada evento `unanchored-mark` / `ambiguous-anchor` / `non-identity-span`

Os três kinds compartilham a mesma causa raiz — o transplante determinístico
não achou (ou achou ambíguo, ou achou sobre um átomo) onde a mudança do
coautor pousa na página fonte — e a mesma saída: alguém tem que ler o
contexto real e decidir o ponto certo.

1. Leia `detail` + `mark_excerpt` + `author` do evento para entender a
   intenção do coautor.
2. Leia o worklist vivo — `review_worklist(page)` (MCP) ou, sem MCP, `Read
   reviews/<slug>/review.md` (mesmo slug do `ingest`: caminho da página
   relativo à raiz do projeto, sem prefixo `docs/`, cada `/` vira `__`; `Glob
   reviews/*/review.md` se estiver em dúvida).
3. Localize no corpo o ponto exato onde a mudança pertence, **lendo o
   contexto ao redor** — nunca adivinhe por posição relativa ao evento
   anterior.
4. Chame `propose_prose_edit` (MCP) com:
   - `anchor_excerpt`: o **menor trecho literal** do worklist que identifica
     o ponto de forma única (0 ocorrências → âncora errada; 2+ → âncora
     ambígua — ver guardas abaixo).
   - `position`: `"before"`/`"after"` para inserir texto novo junto de um
     ponto de referência (`kind="ins"`, só `b` importa — o excerto-âncora em
     si nunca muda); `"replace"` para substituir o próprio `anchor_excerpt`
     (`kind="del"`/`"sub"`, exige `a == anchor_excerpt`).
   - `a`/`b`: o **menor payload fiel** à intenção do coautor — nunca
     reescreva mais do que `mark_excerpt` indica.
   - `author="agente"` (default) — nunca o nome do coautor original; a
     proposta é sua, não dele.
5. Sem MCP conectado: não existe comando CLI para propor — descreva ao
   humano, em prosa, a proposta que você faria (âncora + kind + a/b) para ele
   aplicar manualmente ou reconectar o MCP. Nunca edite `review.md` você
   mesmo para compensar.

### 3. Eventos de citação: nunca propor

`citation-touched-prose` e `citation-drop` **nunca** recebem proposta —
citação é átomo, decisão sempre humana (I1/I3b). Liste-os com a AÇÃO exata
(mesma do `events --checklist`):

- `citation-drop` → confirme com `--confirm-citation-drops <occ_id>` (aceita
  lista separada por vírgula) no `apply`.
- `citation-touched-prose` → decisão humana: rejeite a mudança no Word ou
  edite a fonte diretamente.
- `applied` → histórico; ignore ao contar pendências.

### 4. Fechar com resumo

Reporte ao usuário — nunca aplique nada sozinho:

- **N propostas** feitas no worklist (todas `author="agente"`, filtráveis
  com `--by-author agente`).
- **M itens humanos** (eventos de citação do Passo 3 + qualquer evento do
  Passo 2 que você teve que escalar).
- **Antes do apply, um passo manual do humano**: `propose_prose_edit` só
  grava a marca pendente em `review.md` — o evento correspondente CONTINUA
  em `reviews/<slug>/events.yaml` até alguém remover a entrada (o bloco YAML
  inteiro do evento, não só um campo). `prumo write review apply` bloqueia
  enquanto sobrar qualquer evento fora de `citation-drop`/`applied`, mesmo
  já proposto. Avise o humano: ele precisa abrir `events.yaml` e apagar a
  entrada de cada evento já resolvido (por proposta sua ou por edição manual
  dele) antes de rodar o `apply` abaixo.
- O comando sugerido para o humano decidir:

  ```bash
  prumo write review apply --page <page> --by-author agente --accept   # aceita as propostas do agente
  prumo write review apply --page <page> --by-author agente --reject  # ou rejeita, se preferir descartar
  ```

Esta skill nunca roda `apply` — só sugere o comando.

> **AVISO:** nunca sugira re-rodar `prumo write review ingest` para "limpar"
> eventos pendentes que já têm proposta no worklist — o ingest reescreve
> `review.md` do zero e destrói as propostas ainda não decididas. Um
> mecanismo de 1ª classe pra isso (`--resolve-events`, ou equivalente) está
> na fila; até lá, remover a entrada de `events.yaml` é sempre manual.

## Guardas e recusas — antecipe, não force

`propose_prose_edit` recusa (`ValueError` pt-BR) **antes** de escrever
qualquer coisa. Trate cada recusa como esperada, não como bug a contornar:

- **Âncora não encontrada** (0 ocorrências do `anchor_excerpt` no worklist) →
  releia o corpo real (não confie em memória/paráfrase) e copie o trecho
  exato.
- **Âncora ambígua** (2+ ocorrências) → amplie o excerto com mais contexto
  (frase inteira, não 3 palavras) até virar único.
- **Payload contém citekey/sintaxe de citação** (I3b) → PARE; não tente
  mascarar. Reduza o payload para não incluir citekey/colchete, ou deixe o
  evento inteiro para o humano se a intenção do coautor era mexer na
  citação.
- **Âncora encosta em ou intersecta citação (`[@key]` ou `@key`)** (I1) → PARE; escolha
  uma âncora que não toque a citação, ou escale.
- **`author` inválido** → sempre `author="agente"` (default); nunca copie o
  nome do coautor nem invente string com `{`, `}`, `[`, `]`.
- **`kind="comment"` não é proponível** → nunca proponha comentário;
  observações viram prosa no seu resumo do Passo 4, nunca marca.
- **Round-trip guard reprovou a composição** (contagem de marcas, identidade
  da marca inserida, ou conservação de citações diverge após a inserção
  simulada) → falha interna genuína; não repita a mesma chamada — reporte ao
  humano com o payload tentado.
- **`non-identity-span` cuja causa é o alvo cair sobre um átomo que NÃO é
  citação** (wikilink, callout, bloco de código, embed) → o guard técnico
  (I1) só bloqueia citação; o mesmo cuidado se aplica por julgamento: se a
  única âncora fiel toca esse átomo, escale em vez de forçar.

> **Regra de ouro:** Se a âncora for ambígua ou o evento tocar citação, PARE
> e escale — nunca chute.

## Boundaries

- Nunca decide — só propõe marcas pendentes com `author="agente"`;
  aceitar/rejeitar (inclusive as próprias propostas) é sempre `prumo write
  review apply`, rodado pelo humano.
- Nunca propõe, move ou cunha citação — todo evento de citação vai para o
  humano, sem exceção (I1/I3b).
- Nunca edita `review.md`, `events.yaml` ou a página original diretamente —
  toda escrita passa por `propose_prose_edit`, que valida antes de gravar.
  Sem MCP, a skill não escreve nada, só orienta.
- Nunca roda `prumo write review apply` — mesmo sugerindo o comando.

## Erros comuns

- **Evento com proposta ainda bloqueia o `apply`** → `propose_prose_edit` só
  grava a marca em `review.md`; o evento continua "pendente" em
  `events.yaml` até o humano remover a entrada inteira dele — sem isso,
  `prumo write review apply` recusa com `ValueError` mesmo já tendo a marca
  resolvida no worklist. NUNCA sugira `ingest` de novo pra resolver isso:
  reescreve `review.md` do zero e destrói o worklist com as propostas ainda
  pendentes.
- **`events.yaml`/`review.md` ausentes** → o ciclo de revisão ainda não foi
  iniciado para essa página; rode `prumo write review ingest <reviewed.docx>
  --page <page>` primeiro.
- **Ferramentas `mcp__prumo-review__*` não aparecem disponíveis** → o
  servidor precisa estar registrado em `.mcp.json` (roda via `prumo mcp
  serve`) e conectado nesta sessão; sem ele, use o fallback CLI do Passo 1 e
  a orientação em prosa do Passo 2 (item 5).
- **Todos os eventos são `citation-*`/`applied`** → nada para propor; liste
  o checklist humano (Passo 3) e feche o resumo (Passo 4) sem chamar
  `propose_prose_edit`.
- **`propose_prose_edit` recusa repetidamente o mesmo payload** → não
  insista; é sinal de que o evento pertence ao Passo 3 (escale), não ao
  Passo 2.
