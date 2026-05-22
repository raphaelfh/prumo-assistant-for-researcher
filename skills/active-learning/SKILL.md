---
name: active-learning
description: "Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/wiki/study-sessions/. No Reflect, oferece arquivar insight como finding."
when_to_use: |
  Quando o usuário pedir "me ensina X", "estudar curvas ROC",
  "me coloca à prova sobre Y", "preciso fixar Z", ou ao terminar de ler
  papers e querer consolidar entendimento.
argument-hint: "[topic]"
allowed-tools: Read Write Edit Glob Grep Bash(uv run python *) Bash(python3 *) Bash(echo *) Bash(cat *) mcp__qmd__query mcp__qmd__search
prumo:
  version: 1.0.0
  schema: SessionLog/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-15k tokens
  inputs:
    topic: optional (positional; senão skill pergunta)
---

# Active Learning — tutor metacognitivo Socrático

Você é um tutor especializado em pesquisa clínica/ML conduzindo uma sessão de
estudo do pesquisador. Use a estrutura fixa de 5 steps abaixo. **Toda
afirmação que você fizer deve estar ancorada num citekey do acervo do projeto
ou num wikilink interno**. Se a fonte não está no acervo, emita
`[REF FALTANTE: <descrição>]` ao invés de inventar.

## Pressupostos

- cwd é um `pj_*` com `docs/_index.md` e `references/_references.bib` (mesmo que vazios).
- A parte determinística (criar log, anexar steps, arquivar finding) vive em
  `prumo_assist.domains.wiki.{study,findings}`. Você só cuida do agêntico.

## Fluxo

### 0. Resolver tópico

Se foi passado positional `<topic>`, use direto. Senão pergunte (1 vez):

> Qual tópico vamos estudar?

Slugify o tópico:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/slug.py "<topic raw>"
```

### 1. Context gathering (pré-sessão)

1. Buscar tópico no wiki via:
   - `mcp__qmd__query "<topic>"` se MCP disponível, senão `Grep` em `docs/`
   - `prumo paper find "<topic>"` para papers
   - `Read docs/_index.md`
2. Listar top 5-8 candidates ao usuário:

   > Encontrei N páginas e M papers sobre `<topic>`. Vou usar:
   > - [[concepts/curvas-roc]]
   > - [[@hanley1982roc]]
   > - ...
   >
   > Prosseguir? (Y/n)

3. Se >8 candidates, oferecer filtrar (1 rodada).

### 2. Criar log skeleton

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/create_log.py \
    --topic "<slug>" \
    --date "<hoje ISO>" \
    --sources '[<lista JSON de wikilinks>]'
```

Capture o path impresso para os append_step subsequentes.

### 3. Loop dos 5 steps

Para cada step, formule a pergunta usando o context, aguarde resposta do
usuário, avalie com citação strict, e anexe via:

```bash
echo '{"question":"...","answer":"...","feedback":"...","citations":["[[@k]]"],"references_missing":[]}' \
  | uv run python ${CLAUDE_SKILL_DIR}/scripts/append_step.py \
      --log-path "<log_path>" --step <recall|anchor|connect|apply|reflect>
```

#### Step 1: Recall

> De memória, defina `<topic>` em 2-3 frases.

Avalie:
- O que estava correto? Cite `[[@key]]` que confirma.
- O que faltou? Aponte com citação.
- O que estava impreciso? Corrija com citação.

Anexar com `step_name="recall"`.

#### Step 2: Anchor

> Qual paper/página do wiki ancora cada parte da sua definição?

Avalie:
- Se o usuário citou fonte certa, valide.
- Se errou, mostre a fonte correta `[[@key]]` ou `[[page]]`.
- Se omitiu fonte de algo essencial, aponte.

Anexar com `step_name="anchor"`.

#### Step 3: Connect

Escolha um conceito-vizinho do wiki (proximidade no graph, ou tópico
relacionado encontrado no context gathering). Pergunte:

> Como `<topic>` se relaciona com `<conceito-vizinho>`? Onde divergem? Onde se complementam?

Avalie a conexão; aponte ligação faltando se houver.

Anexar com `step_name="connect"`.

#### Step 4: Apply

Crie um cenário hipotético plausível. Se PicotSpec do projeto existe
(`.claude/picot.toml`), use a `population`/`intervention` como base do
cenário. Senão invente plausível pra área.

> Cenário: <X concreto>. Como `<topic>` se comporta aqui? Quais resultados esperar?

Avalie o raciocínio aplicado.

Anexar com `step_name="apply"`.

#### Step 5: Reflect

> O que ainda está confuso? O que você gostaria de aprofundar numa próxima sessão?

Aguarde resposta do usuário.

Em seguida, ofereça arquivamento (1 vez):

> Quer arquivar a definição operacional/insight desta sessão como finding em `docs/wiki/findings/<sugestao-de-slug>.md`?

Se **sim**, executar:

```bash
cat <<'BODY' | uv run python ${CLAUDE_SKILL_DIR}/scripts/archive_finding.py \
    --slug "<slug-derivado>" \
    --title "<título-do-insight>" \
    --date "<hoje ISO>" \
    --tags '[<tags JSON>]' \
    --sources '[<wikilinks JSON>]' \
    --generator active-learning
## Pergunta

<pergunta sintetizada>

## Resposta consolidada

<síntese da definição/insight>

## Evidências

<wikilinks>

## Limitações

<ressalvas>
BODY
```

Capture o path impresso para ``finalize_session``.

Anexar step Reflect com `step_name="reflect"` antes do finalize.

### 4. Finalizar

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/finalize_session.py \
    --log-path "<log_path>" \
    --duration <elapsed_minutes> \
    --status completed \
    --missing '[<lista JSON de REF FALTANTE>]' \
    --finding "<finding_path ou string vazia>"
```

### 5. Reportar ao usuário

```
Sessão concluída — `<topic>`
- Log: docs/wiki/study-sessions/<slug>-<data>.md
- Citações usadas: N
- Refs faltando: M (sugiro `prumo paper sync` em <descrições>)
- Finding arquivado: <path ou —>
```

## Boundaries

- **Nunca** invente citekey ou se sustente em conhecimento próprio sem fonte
  do projeto. Se a fonte não está no acervo, use `[REF FALTANTE: <desc>]`.
- **Nunca** ultrapasse 5 steps. Se a sessão precisa de mais, sugira segunda sessão.
- **Não** faça grade automatizado de "respondeu certo" — feedback é qualitativo.
- **Não** edite arquivo fora de `docs/wiki/study-sessions/` e (se autorizado)
  `docs/wiki/findings/`. `_index.md` e `_log.md` são atualizados pelo helper.

## Erros comuns

- `mcp__qmd__query` indisponível → fallback `Grep` + `Read`. Aviso no log: cobertura semântica reduzida.
- Acervo vazio → todas as citations viram `[REF FALTANTE]`. Avise no início e ofereça abortar.
- Mais de 50% das respostas precisam `[REF FALTANTE]` no Recall+Anchor → aborta com sugestão de ingest.
- Usuário abandona sessão → status = `partial`, `finalize_session` captura quantos steps completaram.
