---
title: Superfície de skills — start + 5 skills por domínio, 3 subagents e prumo status
date: 2026-09-12
status: approved
tags: [skills, modes, subagents, onboarding, status, migration, breaking, adr]
---

# Superfície de skills — start + 5 skills por domínio, 3 subagents e `prumo status`

## Resumo executivo

A fricção mais vista hoje é **escolher a skill certa**: são 16 nomes com descrições que se sobrepõem, e o pesquisador invoca a errada ou nenhuma. Este spec troca a superfície sem perder capacidade nenhuma:

1. **16 skills viram `start` + 5 skills por domínio** (`paper`, `wiki`, `protocol`, `write`, `review`), espelhando os domínios do CLI. Cada skill antiga vira um **modo** 1:1. O corpo de cada modo só é lido quando o modo é escolhido.
2. **Três subagents** com papel nomeado — `reader`, `verifier`, `reviewer` — justificados por isolamento de contexto, independência ou paralelismo. Nunca usam `Write`/`Edit`; persistência só pelo CLI, que carimba proveniência no ato (liga o Princípio V).
3. **`prumo status`** diz em que ponto o estudo está e qual a próxima frase a dizer. `start` renderiza.
4. **Migração sem alias**: `prumo update` reescreve as invocações antigas no `pj_*`; `doctor` aponta sobras; valores de proveniência antigos continuam legíveis.

Faseamento: **F0** spike (sem release) → **F1** consolidação, MINOR `⚠ Breaking` → **F2** subagents, PATCH → **F3** status, PATCH ([ADR-0015](../../adr/adr-0015-pre-1-0-patch-para-releasavel.md)).

## Contexto

### A dor

O piloto da F2 do programa zero-friction bateu ≤15 min até o primeiro output, mas o roteamento depende do `start` e da descrição de 16 skills. Três sintomas:

- **Sobreposição de gatilho.** `write-scientific`, `write-paper` e `scientific-writing` disputam "escreve essa seção"; `paper-manager` e `wiki-ingest` disputam "adiciona esse paper"; `peer-review` e `citation-support` disputam "minhas referências batem?".
- **Custo de contexto.** As 16 descrições + `when_to_use` entram no contexto de toda sessão, em qualquer projeto.
- **Nome ≠ intenção.** O pesquisador pensa em artefato ("meu projeto CEP", "minha bibliografia"), não em verbo técnico (`formulate-picot`, `review-reconcile`).

### O que o ARS mostra

O README do [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) resolve o mesmo problema com poucas skills e uma tabela **frase → modo** por skill ("Do a systematic review on X with PRISMA → systematic-review mode"). A intenção decide o modo; na ambiguidade vence o modo mais conservador. Adotamos esse padrão de superfície. **Não** adotamos o resto: orquestrador de pipeline, Material Passport, 39 papéis de prompt, 108 schemas — contrário aos Princípios VI e VIII.

### Restrições herdadas

- [ADR-0012](../../adr/adr-0012-remocao-agents-ml.md): agent futuro deve servir o fluxo clínico, funcionar standalone e allowlistar só tools universais.
- [ADR-0019](../../adr/adr-0019-preflight-uniforme-skills.md): preflight uniforme por skill.
- [ADR-0029](../../adr/adr-0029-update-reflui-o-template.md): `prumo update` só compara **conteúdo** em `.claude/rules/`; fora dela só presença. Renomear invocações exige migração própria.
- Princípio IV: `generator: wiki-query` e `skill="paper-extract"` já estão gravados em projetos reais e nunca são reescritos.
- Documentação oficial do Claude Code (consultada em 2026-09-11): plugin `agents/` existe; é **silenciosa** sobre Desktop (aba Code) e Cowork; plugin agents **não** configuram MCP servers nem hooks; `SKILL.md` só nomeia `Explore`/`Plan`/general-purpose no campo `agent:`. Daí o F0.
- Padrão vigente em `skills/paper-extract/SKILL.md`: subagents do batch já persistem via `Bash(prumo paper extract …)`, devolvendo só `{citekey, status, error?}` ao thread principal.

## Decisões

### D1 — Superfície: `start` + 5 skills, modo = skill antiga

| Skill nova | Modo | Absorve | Determinismo |
|---|---|---|---|
| `start` | `route` · `install` · `status` | `start` | agentic (+ `prumo status`) |
| `paper` | `library` | `paper-manager` | deterministic |
| | `extract` | `paper-extract` | agentic |
| | `support` | `citation-support` | hybrid |
| `wiki` | `ingest` | `wiki-ingest` | agentic |
| | `query` | `wiki-query` | agentic |
| | `lint` | `wiki-lint` | hybrid |
| | `study` | `active-learning` | agentic |
| `protocol` | `picot` | `formulate-picot` | hybrid |
| | `sap` | `write-statistics` | agentic |
| | `cep` | `write-projeto-cep` | agentic |
| `write` | `manuscript` | `write-paper` | agentic |
| | `section` | `write-scientific` | agentic |
| | `style` | `scientific-writing` | agentic |
| | `disclosure` | — (expõe `prumo write disclosure`) | deterministic |
| `review` | `critique` | `peer-review` | agentic |
| | `reconcile` | `review-reconcile` | hybrid |

Nomes em inglês (regra do repo: identificadores em inglês). O modo de `write` chama `manuscript`, não `paper`, para não colidir com a skill `paper`.

O mapeamento 1:1 é deliberado: F1 é **movimentação**, não reescrita. O corpo de cada modo é o corpo da skill antiga com ajustes de referência cruzada. Fundir modos (ex.: `section` + `style`) só com novo trigger.

`protocol` ganha `sap` e `cep` porque ambos consomem `PicotSpec` e `protocol.md`; `write` fica com o que produz texto de manuscrito.

### D2 — Anatomia de uma skill

```
skills/<skill>/
├── SKILL.md              ← frontmatter + preflight geral + tabela frase→modo (gerada) + regra de escolha
├── modes/<mode>.md       ← corpo do modo (ex-SKILL.md da skill antiga), com preflight do modo no topo
└── references/           ← material compartilhado (ex.: reporting-guidelines.md)
```

Frontmatter — `prumo.modes` é a **fonte única** (Princípio I) de nome, frases, determinismo, requisitos e nome legado:

```yaml
---
name: paper
description: "Acervo bibliográfico do pj_*: sincronizar com o Zotero, extrair PDFs, checar se citações sustentam frases."
when_to_use: |            # GERADO de prumo.modes[].phrases — não editar à mão
  ...
argument-hint: "[library|extract|support] [args]"
allowed-tools: Read Glob Grep Bash(prumo paper *) Agent
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
  modes:
    - name: extract
      summary: "PDF → callout estruturado em _extract.md"
      phrases: ["resuma o paper X", "extraia os principais pontos", "processa todos os papers novos"]
      determinism: agentic
      requires: [cli]
      schema: PaperCallout/v1
      legacy: paper-extract
---
```

Regras de escolha de modo, escritas no `SKILL.md`:

1. **Argumento explícito vence**: `/prumo-assist:paper extract @smith2024`.
2. **Senão, intenção** contra a tabela frase → modo.
3. **Ambíguo → uma pergunta** com os modos candidatos (padrão do ARS: na dúvida entre gerar e orientar, orientar).
4. **Antes de agir, ler `modes/<mode>.md` inteiro.** O `SKILL.md` não contém instrução operacional de modo nenhum.

Gerador (`.github/scripts/gen_indexes.py`, Princípio VII) passa a produzir, a partir de `prumo.modes`:

- `when_to_use` de cada skill;
- a tabela frase → modo no `SKILL.md` (bloco `<!-- prumo:modes-table:begin/end -->`);
- a seção "Uso" do README no formato do ARS (frase → `skill modo`);
- o catálogo do `start`, agora com 5 skills × modos em vez de 16 linhas.

`allowed-tools` é a união dos modos, com `Bash` sempre escopado a `prumo <domínio> *` — a união nunca inclui `Write`/`Edit` sem que algum modo exija.

### D3 — Três subagents

| Agent | Serve | Recebe | Devolve | Tools |
|---|---|---|---|---|
| `reader` | `paper extract` | citekey, caminho do PDF, template de extração | status `{citekey, status, error?}`; o extract (com `locator` por afirmação) é persistido via `prumo paper extract` | `Read`, `Bash(prumo paper extract *)` |
| `verifier` | `paper support` | frase, citekey, caminho do PDF, locator do extract quando houver | `{verdict: fully\|partially\|unsubstantiated, quote, page}` | `Read` |
| `reviewer` | `review critique` | caminho do draft, guideline de reporte escolhido — **nunca** a conversa de redação | crítica por seção em JSON | `Read`, `Grep` |

Critérios de existência — cada agent precisa de pelo menos um:

- **Isolamento**: bytes de PDF não entram no thread principal (`reader`, `verifier`).
- **Independência**: o crítico não viu o raciocínio de quem escreveu (`reviewer`).
- **Paralelismo**: batch de extract em ondas (`reader`).

Invariantes:

- **Nenhum agent usa `Write` ou `Edit`.** Persistência só por comando `prumo` allowlistado, que grava dentro do bloco delimitado (ADR-0009) e carimba o bloco `_meta` de proveniência no mesmo ato — primeiro produtor real de `core/provenance.py` (Princípio V).
- **`verifier` lê o PDF**, não o `_extract.md`. Resolve o achado "Groundedness" do ROADMAP: extract errado deixa de produzir confirmação ativa. O `locator` do extract só aponta onde procurar.
- **`locators` é campo opcional novo** em `PaperCallout/v1` (`domains/paper/schemas/v1.py`), mapeando seção → lista de `{page, quote}`. Princípio IV e a própria docstring do schema: nenhum campo removido, novos campos sempre opcionais; extracts antigos sem `locators` seguem válidos e o `verifier` busca no PDF inteiro.
- **Validação passa a ser ligada.** Hoje `PaperCallout` é exportado mas `apply_extraction` aceita qualquer dict vindo do stdin. F2 valida o conteúdo por `PaperCallout` antes de gravar; sem isso nenhum contrato de agent é verificável. O rótulo `schema: PaperExtract/v1` no frontmatter da skill atual está desatualizado e vira `PaperCallout/v1` em F1.
- **Contratos de retorno** em Pydantic: `PaperCallout` (reader), modelo novo `SupportVerdict` em `domains/paper/schemas/v1.py` (verifier), modelo novo `CritiqueReport` em `domains/write/schemas/v1.py` (reviewer); JSON inválido → 1 retry com o erro de validação, depois falha explícita (padrão atual do batch).
- **Os três seguem ADR-0012**: fluxo clínico, standalone (nenhum diretório externo), só tools universais.

Fonte canônica do prompt: `agents/<name>.md` na raiz do plugin (frontmatter `name`, `description`, `tools`, `model`). O transporte é decidido no F0 (D4).

### D4 — Transporte decidido por spike (F0)

A doc não garante que plugin agents funcionem nas superfícies-alvo (memória do projeto: superfície-alvo é Desktop/Cowork). F0 responde, na aba Code do Desktop e no Cowork:

| # | Pergunta | Como observar |
|---|---|---|
| Q1 | Um `agents/<name>.md` do plugin aparece como `subagent_type` disponível? | Invocar skill de teste que lista/dispara o agent por nome |
| Q2 | Prosa de `SKILL.md` consegue despachar o agent **pelo nome**? | Skill de teste com instrução "despache `reader`" |
| Q3 | O agent tem `Bash` e enxerga o `prumo` no PATH? | Agent roda `prumo --version` |
| Q4 | O agent tem `Read` de PDF nativo? | Agent lê 1 PDF real de `docs/references/pdfs/` |
| Q5 | O `tools:` do agent restringe de fato (sem `Write`)? | Pedir ao agent que escreva um arquivo; esperar recusa |

Resultado → transporte:

- **Q1–Q5 sim nas duas superfícies** → plugin agent nomeado.
- **Qualquer não** → *fallback*: a skill lê `agents/<name>.md` e despacha `general-purpose` com o corpo como prompt e as mesmas restrições em prosa. Mesmo arquivo, dois transportes; nenhuma prosa de modo muda.

O spike é descartável (nada do código fica), registra achados num finding de `docs/superpowers/specs/` e **precede** o ADR de agents — ADR é imutável após aceito, e o transporte é parte da decisão.

### D5 — `prumo status`

`prumo status [path] [--scope <slug>] [--json]` — **deterministic**, só lê arquivos, **não grava estado novo** (mesma lógica da ADR-0029: comparação ao vivo não pode mentir).

| Sinal | Fonte | Quando é "pendente" |
|---|---|---|
| `library.entries` / `library.synced_at` | `_references.bib` (contagem, mtime) | 0 entradas |
| `extracts.pending` / `extracts.stale` | papers sem `_extract.md`; `extracted_template_hash` ≠ hash atual | > 0 |
| `picot.closed` | `.claude/picot.toml` válido por `PicotSpec` | ausente/inválido |
| `drafts` | arquivos em `docs/studies/<slug>/writing/` | — (informativo) |
| `review.pending_events` | worklist do round-trip (`write review events`) | > 0 |

`next` = primeiro pendente numa ordem fixa, com a **frase** a dizer, não o comando:

```
entries → extracts → picot → manuscript → review
```

Ex.: `{"next": {"skill": "paper", "mode": "extract", "say": "processa todos os papers novos", "why": "12 papers sem extract"}}`.

Localização: `src/prumo_assist/status.py` no **topo do pacote**, compondo `domains/*/api.py` — mesmo precedente do `mcp_server.py` ([ADR-0017](../../adr/adr-0017-prumo-mcp-reconciliador.md)); `core/` continua sem importar `domains/`. Cada domínio expõe só leitura já existente ou uma função `progress()` pura em `api.py`. Multi-escopo: sem `--scope` e com mais de um escopo, lista um bloco por escopo ([ADR-0022](../../adr/adr-0022-layout-por-escopo.md)).

Ligação com o Zotero (autoexport do BBT) **não** é sinal de `status`: vive dentro do Zotero, só é observável por RPC, e já é assunto do `doctor`. `status` fica restrito ao que o disco mostra.

`doctor` e `status` ficam separados: `doctor` responde "o que está quebrado no meu ambiente"; `status` responde "onde está meu estudo e o que vem agora". `start` chama `doctor --json` primeiro (instalação) e `status --json` depois (roteamento).

### D6 — Migração: `prumo update` reescreve invocações

Nova migração `migrate_skill_names(pj_root)`, chamada por `prumo update` ao lado de `migrate_project_context`:

- **Reescreve só o token de invocação** `prumo-assist:<antigo>` → `prumo-assist:<skill> <modo>` (ex.: `/prumo-assist:paper-extract` → `/prumo-assist:paper extract`), em `.md` e `.toml` do `pj_*`.
- **Nunca toca valores sem o prefixo** (`generator: wiki-query`, `skill = "paper-extract"`): são dados de proveniência (Princípio IV).
- **Não entra em `docs/references/papers/**`** (conteúdo gerado de acervo) nem em blocos machine-owned.
- Mapa derivado de `prumo.modes[].legacy` via `core/skills.py` (fonte única; skills vão no wheel, ADR-0002).
- Respeita `--dry-run` (mostra cada troca) e é idempotente.
- `doctor` ganha check `[skill_obsoleta]` que aponta `prumo update` quando sobra token antigo.
- Templates do repo (`templates/pj_base/**`, `templates/modules/**`) são atualizados em F1; `pj_config.toml` corrige a referência morta a `paper-extract-all`.

### D7 — Proveniência legada continua legível

- `core/skills.py` expõe `resolve_skill_ref(value) -> SkillRef(skill, mode)`, aceitando o formato novo `paper/extract` e qualquer `legacy`.
- `domains/write/disclosure.py` agrega por `SkillRef`, então um projeto com `generator: wiki-query` antigo e `generator: wiki/query` novo produz **uma** linha na declaração.
- Escritas novas usam `skill/mode` (`findings.generator` default passa a `wiki/query`; `--generator` aceita os dois).
- `core/deps.py::required_by` passa a citar `skill modo`.

## Fases e releases

| Fase | Entrega | Release | ADR |
|---|---|---|---|
| **F0** | Spike D4 — finding com Q1–Q5 por superfície e transporte escolhido | nenhum (docs) | — |
| **F1** | D1 + D2 + D6 + D7 — 16 → start + 5, gerador de modos, migração, proveniência legada, README "Uso" | MINOR `⚠ Breaking` | **ADR-0032** superfície por domínio e modos |
| **F2** | D3 no transporte do F0 — `agents/`, `locator` no extract, `verifier` lendo PDF, carimbo de proveniência no apply | PATCH | **ADR-0033** subagents nomeados (transporte + invariantes) |
| **F3** | D5 — `prumo status`, `start` em modo `status` | PATCH | — (precedente ADR-0017) |

F1 não depende de F0 e pode correr em paralelo; F2 depende de F0. Cada fase tem plano próprio em `docs/superpowers/plans/`.

## Critérios de aceite

- **F1 — roteamento.** Lista-ouro de 30 frases reais de pesquisador (em `tests/fixtures/routing_phrases.toml`, `frase → skill modo`). Baseline medido **antes** de F1 contra as 16 skills; após F1, no Desktop, **≥ 27/30** caem no modo certo na primeira invocação, e nenhuma pior que o baseline. Manual, registrado no plano arquivado — não é eval em CI (ROADMAP 3.2, trigger não atingido).
- **F1 — paridade.** Todo comportamento documentado nas 16 `SKILL.md` antigas tem destino num `modes/<mode>.md` (checklist no plano).
- **F1 — migração.** `prumo update` num clone do `pj_piloto_genetica` zera `[skill_obsoleta]` e `disclosure` gera o mesmo parágrafo de antes.
- **F2.** Batch de 20 extracts no Desktop: thread principal recebe só status; 100% dos `_extract.md` novos com `_meta` de proveniência; `verifier` num extract deliberadamente errado devolve `unsubstantiated`.
- **F3.** `prumo status` num projeto real devolve `next` coerente com inspeção manual em 3 estados (recém-criado, com bib sem extract, com draft e eventos pendentes).

## Erros e degradação

- Modo inexistente no argumento → lista os modos da skill com uma frase de exemplo cada.
- `modes/<mode>.md` ausente → hard-fail com mensagem pt-BR e o comando de correção (`uv tool upgrade prumo-assist`), nunca improviso.
- Agent indisponível na superfície → fallback D4, silencioso para o pesquisador.
- `prumo` ausente → `start` segue o fluxo de instalação guiada atual; modos `requires: []` (`critique`, `style`, `study`, `section`) continuam funcionando sem CLI.
- `status` num diretório que não é `pj_*` → `PrumoError` com `prumo init`.

## Testes

Espelham o layout (`tests/unit/...`); externos mockados nos seams de sempre.

- `test_gen_indexes.py`: todo `prumo.modes[].name` tem `modes/<name>.md`; todo `legacy` é único; `when_to_use` e tabela gerados batem (`--check`); nenhuma skill sem modo.
- `tests/unit/core/test_skills.py`: `resolve_skill_ref` para formato novo, legado e desconhecido.
- `tests/unit/test_cli_update.py` (existente): `migrate_skill_names` troca token prefixado, preserva `generator:` sem prefixo, ignora `docs/references/papers/**`, é idempotente, respeita `--dry-run`.
- `tests/unit/write/test_disclosure.py` (existente): projeto misto (legado + novo) agrega numa linha.
- `tests/unit/paper/test_schemas_v1.py` (novo): `PaperCallout` aceita extract sem `locators` e com `locators`; `SupportVerdict` rejeita veredito fora das 3 vias.
- `tests/unit/paper/test_callout.py` (existente): `apply_extraction` recusa dict que não valida por `PaperCallout`, sem gravar.
- `tests/unit/test_status.py` (novo, espelha `status.py` no topo do pacote, como `test_mcp_server.py`): fixtures dos 3 estados do critério de F3; multi-escopo; ordem de `next`.
- `test_pj_base_integration.py`: `init` → nenhum token antigo no scaffold.

## Fora de escopo (cada um com trigger próprio)

| Item | Trigger |
|---|---|
| `verify-refs` automático dentro do `write export` | primeira submissão com referência inválida chegando ao docx |
| OpenAlex como segundo resolver + veredito de 3 vias | falso positivo de `verify-refs` reportado por colega |
| Perfis de disclosure por periódico | ROADMAP 2.3 (submeter pra venue específico) |
| Orquestrador de pipeline / estado entre estágios | nenhum previsto — o layout do `pj_*` já é o estado |
| Fundir modos (`section`+`style`, etc.) | lista-ouro de F1 mostrar confusão persistente entre eles |
| Mais agents | agent novo precisa cumprir um dos 3 critérios de D3 e ADR-0012 |

## Riscos

| Risco | Mitigação |
|---|---|
| Modelo pula a leitura de `modes/<mode>.md` e age só pelo `SKILL.md` | `SKILL.md` sem instrução operacional; regra 4 de D2 explícita; lista-ouro de F1 inclui 5 frases cujo modo exige passo que só existe no arquivo do modo |
| Descrições de 5 skills largas demais roteiam mal entre si | `when_to_use` gerado de frases concretas; critério ≥27/30 bloqueia release de F1 |
| `allowed-tools` por união amplia pré-aprovação | `Bash` sempre escopado por domínio; `Write`/`Edit` só onde modo exige |
| Plugin agents não funcionam no Cowork | F0 antes de F2; fallback com o mesmo arquivo |
| Pesquisador com hábito do nome antigo | `start` e `doctor` apontam o novo; CHANGELOG com tabela antigo → novo |

## Sync impact report (constitution)

Nenhuma emenda. Princípios exercidos:

- **I** — `prumo.modes` é fonte única de frases, nomes legados e requisitos.
- **II** — `status` e a migração são determinísticos; agents só julgam, CLI persiste.
- **III** — prompt canônico em `agents/<name>.md` roda também como `general-purpose` (fallback), sem acoplar ao host.
- **IV** — `locator` aditivo; proveniência antiga nunca reescrita.
- **V** — primeiro produtor real de `core/provenance.py` (F2).
- **VI / VIII** — sem orquestrador nem estado novo; 3 agents com critério de existência; modos 1:1 sem reescrita.
- **VII** — `when_to_use`, tabela de modos, README e catálogo do `start` gerados.

## Emenda de implementação (F1, 2026-09-12)

Decisões tomadas ao implementar F1, registradas aqui para o spec não contradizer o código:

1. **Metadados do modo moram no frontmatter de `modes/<mode>.md`**, não numa lista `prumo.modes` do `SKILL.md`. O arquivo do modo reusa `parse_skill_file` inteiro, e o `SKILL.md` fica pequeno no momento da invocação.
2. **`start` continua sem `modes/`.** É um roteador curto; `status` entra como seção dele em F3.
3. **Dois campos novos no frontmatter do modo**, ambos fonte única: `prumo.write_kind` (compose acha template e trava de idioma pelo modo) e `prumo.disclosure_task` (disclosure descreve a tarefa pelo modo).
4. **Templates de escrita** em `skills/<skill>/templates/<modo>.md`.
5. **Critério de disclosure em F1**: mesma contagem e mesmas tarefas de antes; o rótulo da ferramenta passa ao nome novo (`prumo-assist:wiki query`), porque legado e novo precisam agregar numa linha.
6. **A exclusão de "blocos machine-owned" na migração cai.** No `pj_*`, blocos gerados vivem em `docs/references/papers/`, que já é excluído inteiro.
7. **`.claude/skills/<antigo>/` não é apagado** pelo `update` (pode ter customização); o `doctor` aponta.
8. **Bug pré-existente corrigido no caminho**: `archive_as_finding` gravava o `generator` no lugar do verbo do `_log.md`, e o `wiki lint` marcava toda entrada de finding como `broken_log_prefix`. O verbo passa a `note`, com o gerador entre parênteses.
9. **Installer copia a árvore inteira da skill.** Antes copiava só o `SKILL.md`, então `references/` já não chegava aos projetos.
