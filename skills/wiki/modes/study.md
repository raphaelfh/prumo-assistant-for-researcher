---
name: study
description: "Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/studies/<slug>/notes/. No Reflect, oferece arquivar insight como finding."
argument-hint: "[topic]"
allowed-tools: Read Write Edit Glob Grep Bash(qmd *) Bash(prumo wiki *) Bash(prumo paper find *) Bash(echo *) Bash(cat *)
prumo:
  version: 1.0.0
  schema: SessionLog/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-15k tokens
  inputs:
    topic: optional (positional; senão skill pergunta)
  requires: [cli, qmd]
  phrases:
    - "me ensina X"
    - "me coloca à prova sobre Y"
    - "preciso fixar Z"
  legacy: [active-learning]
  disclosure_task: "synthesis of study-session findings"
---

# Active Learning — tutor metacognitivo Socrático

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **Superfície e CLI:** este modo precisa do app Claude na aba Code (Mac) ou do Claude Code
>    no terminal (Mac ou Linux). Se esta conversa for uma tarefa do Cowork, um chat, uma sessão
>    SSH ou rodar no Windows ou no WSL, diga em uma frase que este modo não é suportado aqui e
>    que a pessoa deve abrir o app Claude na aba Code (Mac) ou o Claude Code no terminal (Mac ou
>    Linux), e pare. Senão, rode `prumo --version`; o esperado é
>    `prumo <versão do bloco PAR da porta>`.
>    (a) `prumo` não existe: rode a forma `sh … --version` do bloco PAR e aplique (b)–(d) à
>    saída dela; avise uma vez que cada comando vai pedir permissão. Só se a saída não trouxer
>    nem a versão nem uma linha `PAR:`, diga "abra uma sessão nova" e pare.
>    (b) Outra versão: rode `command -v prumo`. Caminho terminado em `/shims/prumo`: é outra
>    versão do plugin; diga "este `prumo` é de outra versão do plugin — abra uma sessão nova".
>    Qualquer outro caminho (por exemplo `~/.local/bin/prumo`): é o CLI antigo, instalado à
>    parte; ofereça UMA vez, com consentimento, `uv tool uninstall prumo-assistant-for-researcher`
>    (se a pessoa usa o Zettlr, antes peça "regenera o perfil do Zettlr" e a reimportação do
>    perfil, que ainda aponta para dentro desse CLI). Nos dois casos, use a forma `sh …` nesta
>    sessão.
>    (c) A saída contém `PAR: falta o uv`: roteie para `/par:start` (que instala o uv com
>    consentimento) e pare.
>    (d) Qualquer outra linha que comece com `PAR:`: repasse-a (ela traz o comando de correção).
>    Se for a do sandbox (saída 77), ofereça repetir o mesmo comando fora do sandbox, pedindo
>    permissão; nos outros casos, pare.
>    Nunca simule a operação.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
> 3. **Busca semântica (qmd):** rode `qmd --version`; só
>    `command not found` significa ausente. Se ausente, diga isso explicitamente ("busca semântica
>    indisponível — resultados via leitura direta, mais lentos/parciais") e
>    prossiga só no fallback documentado por esta skill; sem fallback, recuse a
>    operação com o hint do `prumo doctor`.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

Você é um tutor especializado em pesquisa clínica/ML conduzindo uma sessão de
estudo do pesquisador. Use a estrutura fixa de 5 steps abaixo. **Toda
afirmação que você fizer deve estar ancorada num citekey do acervo do projeto
ou num wikilink interno**. Se a fonte não está no acervo, emita
`[REF FALTANTE: <descrição>]` ao invés de inventar.

## Pressupostos

- cwd é um `pj_*` com `docs/_index.md` e `docs/references/_references.bib` (mesmo que vazios).
- A parte determinística (criar log, anexar steps, arquivar finding) é exposta
  via `prumo wiki *` (study-start/step/finish, finding). Você só cuida do agêntico.

## Fluxo

### 0. Resolver tópico

Se foi passado positional `<topic>`, use direto. Senão pergunte (1 vez):

> Qual tópico vamos estudar?

O slug é derivado automaticamente do tópico ao criar o log (passo 2).

### 1. Context gathering (pré-sessão)

1. Buscar tópico no wiki via:
   - `qmd query "<topic>"` pelo Bash se o qmd existir, senão `Grep` em `docs/`
   - `prumo paper find "<topic>"` para papers
   - `Read docs/_index.md`
2. Listar top 5-8 candidates ao usuário:

   > Encontrei N páginas e M papers sobre `<topic>`. Vou usar:
   > - [[conformal-prediction]]
   > - [@vovk2005algorithmic]
   > - ...
   >
   > Prosseguir? (Y/n)

3. Se >8 candidates, oferecer filtrar (1 rodada).

### 2. Criar log skeleton

```bash
prumo wiki study-start "<topic raw>" \
    --date "<hoje ISO>" \
    --sources '[<lista JSON de wikilinks>]' --json
```

Capture `slug` e `log_path` do JSON impresso para os passos seguintes.

### 3. Loop dos 5 steps

Para cada step, formule a pergunta usando o context, aguarde resposta do
usuário, avalie com citação strict, e anexe via:

```bash
echo '{"question":"...","answer":"...","feedback":"...","citations":["[@k]"],"references_missing":[]}' \
  | prumo wiki study-step --log-path "<log_path>" --step <recall|anchor|connect|apply|reflect> --json
```

#### Step 1: Recall

> De memória, defina `<topic>` em 2-3 frases.

Avalie:
- O que estava correto? Cite `[@key]` que confirma.
- O que faltou? Aponte com citação.
- O que estava impreciso? Corrija com citação.

Anexar com `step_name="recall"`.

#### Step 2: Anchor

> Qual paper/página do wiki ancora cada parte da sua definição?

Avalie:
- Se o usuário citou fonte certa, valide.
- Se errou, mostre a fonte correta `[@key]` ou `[[page]]`.
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

> Quer arquivar a definição operacional/insight desta sessão como finding
> (`type: finding`) em `docs/studies/<slug>/notes/<sugestao-de-slug>.md`?

Se **sim**, executar:

```bash
cat <<'BODY' | prumo wiki finding \
    --slug "<slug-derivado>" \
    --title "<título-do-insight>" \
    --date "<hoje ISO>" \
    --tags '[<tags JSON>]' \
    --sources '[<wikilinks JSON>]' \
    --generator wiki/study --json
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

Capture o path impresso e guarde como `finding_path` para o passo 4.

Anexar step Reflect com `step_name="reflect"` antes do finalize.

### 4. Finalizar

```bash
prumo wiki study-finish \
    --log-path "<log_path>" \
    --duration <elapsed_minutes> \
    --status completed \
    --missing '[<lista JSON de REF FALTANTE>]' \
    --finding "<finding_path ou string vazia>" --json
```

### 5. Reportar ao usuário

```
Sessão concluída — `<topic>`
- Log: docs/studies/<escopo>/notes/session-<slug>-<data>.md
- Citações usadas: N
- Refs faltando: M (sugiro `prumo paper sync` em <descrições>)
- Finding arquivado: <path ou —>
```

## Boundaries

- **Nunca** invente citekey ou se sustente em conhecimento próprio sem fonte
  do projeto. Se a fonte não está no acervo, use `[REF FALTANTE: <desc>]`.
- **Nunca** ultrapasse 5 steps. Se a sessão precisa de mais, sugira segunda sessão.
- **Não** faça grade automatizado de "respondeu certo" — feedback é qualitativo.
- **Não** edite arquivo fora de `docs/studies/<slug>/notes/` (log da sessão e, se
  autorizado, o finding). `_index.md` e `_log.md` são atualizados pelo helper.

## Erros comuns

- `qmd` indisponível → fallback `Grep` + `Read`. Aviso no log: cobertura semântica reduzida.
- Acervo vazio → todas as citations viram `[REF FALTANTE]`. Avise no início e ofereça abortar.
- Mais de 50% das respostas precisam `[REF FALTANTE]` no Recall+Anchor → aborta com sugestão de ingest.
- Usuário abandona sessão → status = `partial`, `prumo wiki study-finish` captura quantos steps completaram.
