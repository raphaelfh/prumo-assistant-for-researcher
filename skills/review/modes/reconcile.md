---
name: reconcile
description: "Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (citação é decisão humana)."
argument-hint: "--page <page.md>"
allowed-tools: Read Glob Grep Bash(prumo write review events *) Bash(prumo doctor *) mcp__plugin_par_prumo__review_status mcp__plugin_par_prumo__review_events mcp__plugin_par_prumo__review_worklist mcp__plugin_par_prumo__propose_prose_edit
prumo:
  version: 1.0.0
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~3-10k tokens (depende do nº de eventos ambíguos)
  inputs:
    page: required
  requires: [cli]
  phrases:
    - "reconcilia os eventos ambíguos da revisão"
    - "resolve as marcas sem âncora do docx"
  legacy: [review-reconcile]
---

# Review Reconcile — reconciliador de eventos ambíguos do round-trip

<!-- prumo:preflight:begin -->
> **Preflight — antes de qualquer operação deste modo:**
>
> 1. **Superfície e CLI:** fora do app Claude na aba Code (Mac) ou do Claude Code no terminal
>    (Mac ou Linux), isto é, numa tarefa do Cowork, num chat, numa sessão SSH, no Windows ou no
>    WSL, diga em uma frase que este modo não roda aqui e pare. Senão, rode `prumo --version`
>    (sem `prumo`, a forma `sh … --version` do bloco PAR; cada comando pedirá permissão). O
>    esperado é `prumo <versão do bloco PAR da porta>`.
>    - Linha `PAR:` do sandbox (saída 77): ofereça repetir o comando fora do sandbox, pedindo
>      permissão.
>    - Qualquer outra saída (outra versão, `PAR: falta o uv`, outra linha `PAR:`, nada): roteie
>      para `/par:start`, que resolve, e pare.
>    Nunca simule a operação.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>`; nunca crie o scaffold à mão.
<!-- prumo:preflight:end -->

Opera sobre o ciclo de revisão docx↔CriticMarkup (`prumo write review ingest` →
`reviews/<slug>/{review.md,events.yaml,review-comments.yaml}`). Fecha os
eventos que o transplante determinístico não conseguiu localizar sozinho —
**propõe, nunca decide**: só insere marcas CriticMarkup pendentes no worklist
(`review.md`), com autoria `agente`, via o servidor MCP `prumo`
(`propose_prose_edit`). Quem aceita ou rejeita — inclusive as propostas desta
skill — é sempre o humano, com `prumo write review apply`.

## Pressupostos

- Um ciclo de revisão já existe para a página: `prumo write review ingest
  <reviewed.docx> --page <page>` já rodou e gerou `reviews/<slug>/events.yaml`
  + `review.md`. Sem isso, todo comando abaixo falha com o hint embutido
  (`prumo write review ingest ...`).
- O fluxo usa as tools MCP `review_status`, `review_events`,
  `review_worklist` e `propose_prose_edit`. Sem as tools
  `mcp__plugin_par_prumo__*` na sessão: peça para abrir uma sessão nova; até
  lá, use o fallback CLI (`prumo write review events --page <page>
  --json/--checklist`). **`propose_prose_edit` não tem equivalente CLI**: sem
  MCP, o Passo 2 vira só orientação ao humano, nunca edição manual do
  worklist por esta skill.

## Fluxo

### 1. Levantar os eventos

- Com MCP: opcionalmente `review_status(page)` primeiro (contagens por kind —
  visão rápida antes de entrar evento a evento), depois `review_events(page)`
  para a lista completa.
- Sem MCP: `prumo write review events --page <page> --json` (mesmos campos,
  dentro de `{schema_version, page, events}`) — `--checklist` também é útil
  aqui: mesma lista numerada em pt-BR com a AÇÃO por kind, boa referência para
  o resumo do Passo 4.
- Cada evento tem `kind` e `detail` (causa em pt-BR); os de marca trazem `author` (o coautor do
  Word, nunca "agente") e `mark_excerpt`; os de citação, `occ_id`/`citekeys` (`citation-drop` tem `author: null`).

### 2. Para cada evento `unanchored-mark` / `ambiguous-anchor` / `non-identity-span`

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
citação é átomo, decisão sempre humana. Liste-os com a AÇÃO exata
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
  dele) antes de rodar o `apply` abaixo. NUNCA sugira re-rodar `prumo write
  review ingest` para "limpar" eventos: ele reescreve `review.md` do zero e
  destrói as propostas ainda não decididas.
- O comando sugerido para o humano decidir:

  ```bash
  prumo write review apply --page <page> --by-author agente --accept   # aceita as propostas do agente
  prumo write review apply --page <page> --by-author agente --reject  # ou rejeita, se preferir descartar
  ```

Esta skill nunca roda `apply` — só sugere o comando.

## Guardas e recusas — antecipe, não force

`propose_prose_edit` recusa (`ValueError` pt-BR) **antes** de escrever
qualquer coisa. Trate cada recusa como esperada, não como bug a contornar:

- **Âncora não encontrada** (0 ocorrências do `anchor_excerpt` no worklist) →
  releia o corpo real (não confie em memória/paráfrase) e copie o trecho
  exato.
- **Âncora ambígua** (2+ ocorrências) → amplie o excerto com mais contexto
  (frase inteira, não 3 palavras) até virar único.
- **Payload contém citekey/sintaxe de citação** → PARE; não tente
  mascarar. Reduza o payload para não incluir citekey/colchete, ou deixe o
  evento inteiro para o humano se a intenção do coautor era mexer na
  citação.
- **Âncora encosta em ou intersecta citação (`[@key]` ou `@key`)** → PARE; escolha
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
  só bloqueia citação; o mesmo cuidado se aplica por julgamento: se a
  única âncora fiel toca esse átomo, escale em vez de forçar.

> **Regra de ouro:** Se a âncora for ambígua ou o evento tocar citação, PARE
> e escale — nunca chute.

## Boundaries

- Nunca edita `review.md`, `events.yaml` ou a página original diretamente —
  toda escrita passa por `propose_prose_edit`, que valida antes de gravar.
  Sem MCP, a skill não escreve nada, só orienta.

## Erros comuns

- **`events.yaml`/`review.md` ausentes** → o ciclo de revisão ainda não foi
  iniciado para essa página; rode `prumo write review ingest <reviewed.docx>
  --page <page>` primeiro.
- **Sem as tools `mcp__plugin_par_prumo__*` na sessão** → peça para abrir uma
  sessão nova; até lá, use o fallback CLI do Passo 1 e a orientação em prosa
  do Passo 2 (item 5).
- **Todos os eventos são `citation-*`/`applied`** → nada para propor; liste
  o checklist humano (Passo 3) e feche o resumo (Passo 4) sem chamar
  `propose_prose_edit`.
- **`propose_prose_edit` recusa repetidamente o mesmo payload** → não
  insista; é sinal de que o evento pertence ao Passo 3 (escale), não ao
  Passo 2.
