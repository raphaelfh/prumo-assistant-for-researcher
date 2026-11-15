---
name: start
description: "Porta de entrada do par: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review)."
when_to_use: |
  Quando o usuário abre o PAR sem saber por onde começar, pergunta
  "o que dá pra fazer aqui?", "por onde eu começo?", "que skill eu uso pra X?",
  ou pede ajuda pra escolher entre bibliografia, wiki e escrita. É um roteador:
  orienta e inicia a skill certa, não executa a tarefa.
prumo:
  version: 1.0.0
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~1-2k tokens
  requires: []
---

# par: por onde começar

<!-- prumo:runtime:begin -->
**PAR 0.71.3** · raiz do plugin: `${CLAUDE_PLUGIN_ROOT}` (se ali aparecer a variável `CLAUDE_PLUGIN_ROOT` em vez de um caminho, você está no Antigravity ou no Codex: a raiz é a pasta que contém o `skills/` ou o `agents/` deste arquivo)
- CLI: `prumo`. Se `prumo` não existir nesta sessão (fora do Claude, ou hooks bloqueados pela organização), use `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` com a raiz acima: funciona igual, mas cada comando pode pedir permissão.
- Tools MCP do PAR (servidor `prumo`): `mcp__plugin_par_prumo__*` no Claude, `mcp__prumo__*` no Codex, servidor `<pasta do plugin>_prumo` no Antigravity.
- Invocação: o texto escreve `/par:<skill>` (Claude); no Codex e no app ChatGPT é `$par:<skill>`, no Antigravity `/<skill>`.
- Agents: `${CLAUDE_PLUGIN_ROOT}/agents/`. Sem tool de subagent no host, leia o agent e siga-o você mesmo.
<!-- prumo:runtime:end -->

<!-- prumo:preflight:begin -->
> **Preflight:** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer host, até num chat. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
<!-- prumo:preflight:end -->

Você é a porta de entrada E o instalador guiado. Primeiro descubra o estado:

1. **Superfície.** O PAR completo roda num agente com terminal no Mac ou no Linux: Claude Code
   (app Claude na aba **Code**, ou terminal), Antigravity, ou Codex (app ChatGPT ou terminal).
   Se esta conversa for uma tarefa do Cowork, um chat web (claude.ai ou chatgpt.com), uma sessão
   SSH, ou rodar no Windows ou no WSL, responda só isto e pare:
   "Aqui o PAR só julga texto que você colar — por exemplo, a revisão crítica de um trecho
   (`/par:review critique`). Bibliografia do Zotero, projeto no disco e exportação para Word
   precisam de um agente no seu computador: o app Claude na aba **Code**, o Antigravity ou o
   Codex no app ChatGPT (Mac), ou um deles no terminal (Mac ou Linux). Abra a pasta dos seus
   projetos lá e peça para começar com o PAR. No Windows (inclusive no WSL), o PAR ainda não
   funciona."
2. **CLI.** Rode `prumo --version`. O esperado é `prumo <versão do bloco PAR acima>`.
   - `prumo` não existe → rode a forma `sh … --version` do bloco PAR e aplique os casos abaixo
     à saída dela. No Antigravity e no Codex isso é o normal: use a forma `sh` sem avisar. No
     Claude, avise uma vez que os hooks do plugin não rodaram nesta sessão, então cada comando
     pedirá permissão. Só se a saída não trouxer nem a versão nem uma linha `PAR:`, diga
     "abra uma sessão nova" e pare.
   - A saída contém `PAR: falta o uv` → vá para **Instalar o uv**.
   - Outra versão → rode `command -v prumo`.
     - Caminho terminado em `/shims/prumo` (outra versão do plugin): diga "este `prumo` é de
       outra versão do plugin — abra uma sessão nova" e use a forma `sh` até lá.
     - Qualquer outro caminho (por exemplo `~/.local/bin/prumo`, o CLI antigo instalado à
       parte): ofereça UMA vez, com consentimento, `uv tool uninstall prumo-assistant-for-researcher`
       e use a forma `sh` nesta sessão. Se a pessoa usa o Zettlr, antes da remoção peça
       "regenera o perfil do Zettlr" dentro do projeto e a reimportação do perfil: o perfil
       antigo aponta para dentro desse CLI.
   - Linha `PAR:` do sandbox (saída 77) → ofereça repetir o mesmo comando fora do sandbox,
     pedindo permissão.
   - Qualquer outra linha `PAR:` → repasse-a (ela traz o comando de correção) e pare.
   - Versão certa, mas `type -a prumo` lista um `prumo` fora de `/shims/prumo` → ofereça UMA
     vez a mesma remoção, com o cuidado do Zettlr. Outros `…/shims/prumo` não pedem nada.
3. **Ferramentas do PAR.** Se as tools MCP do servidor `prumo` (nomes no bloco PAR) não
   estiverem no seu inventário, diga: "As ferramentas do PAR não subiram nesta sessão (a 1ª preparação pode ter
   demorado). Abra uma sessão nova." Siga pelo CLI enquanto isso.
4. **Diagnóstico.** Rode `prumo doctor --json`.
   - Dentro de um `pj_*` → rode `prumo status --json`. Com `next` preenchido, ofereça em 1 linha
     a frase `next.say` (invocação `next.invocation`) e o motivo `next.why`. Sem `next`, ou se a
     pessoa quiser outra coisa, pergunte o que ela quer fazer e roteie (bibliografia → `paper`;
     wiki e estudo → `wiki`; pergunta do estudo (PICOT, PECO, PCC…), plano de análise e CEP/CEUA → `protocol`; escrita → `write`;
     revisão → `review`), usando o catálogo abaixo. Não execute a tarefa você mesmo.
   - Fora de um `pj_*` → siga a **Trilha guiada**.
   - Dependência externa ausente → mostre o `hint` do doctor (ele traz o comando).
   - `issues` com `[skill_obsoleta]` → ofereça `prumo update` (move as cópias, nada é apagado).
   - `warnings` com `[referencia_obsoleta]` → ofereça editar as linhas listadas, só com um
     "sim"; a linha que já diz o certo (por exemplo, que algo saiu) fica como está.

## Instalar o uv (com consentimento — nunca rode sem um "sim")

Explique antes: o uv é o gerenciador de Python que o PAR usa para preparar o próprio ambiente
(instalação única).

`curl -LsSf https://astral.sh/uv/install.sh | sh`

Se falhar com `Operation not permitted`, `Read-only file system` ou erro de rede (sandbox do
agente), peça para repetir fora do sandbox. Depois rode `prumo --version` de novo: não precisa reiniciar
nada (o PAR acha o uv em `~/.local/bin`). A primeira vez baixa cerca de 60 MB, uma vez só.

## Trilha guiada (um comando por vez, com consentimento)

1. **Projeto:** `prumo init pj_<nome>` na pasta que a pessoa indicar. O projeto já sai com a
   atualização automática do PAR ligada.
2. **Sessão no projeto:** "Abra uma sessão nova com a pasta `pj_<nome>` (app Claude: aba Code →
   escolher a pasta; Antigravity: abrir a pasta; app ChatGPT: Codex → escolher a pasta; terminal:
   `cd pj_<nome>` e o seu agente) e peça para começar com o PAR de novo."
3. **Zotero:** Zotero 9 ou mais novo com o Better BibTeX ≥ 9.0.65 (`.xpi`), app aberto. Serve para conectar a coleção (uma vez) e manter o `.bib` atualizado; no export docx, vincula as citações se estiver aberto. Não bloqueia escrita nem julgamento, e não é preciso ligar "Allow other applications".
4. **Conectar a biblioteca:** com o Zotero aberto, `prumo paper connect "<coleção>"` liga o
   `.bib` do projeto à coleção. Se a coleção ainda não existir, `--create` cria e liga num
   passo — só quando a pessoa pedir a criação; nunca acrescente a flag por conta própria.
5. **Sincronizar:** `prumo paper sync`.
6. **qmd (opcional, busca semântica):** `npm install -g @tobilu/qmd` (ou
   `bun install -g @tobilu/qmd`) e depois `prumo wiki index`. Não precisa reiniciar a sessão. Sem
   qmd, `wiki query` funciona por leitura direta.
7. **Primeiro resultado em minutos:** peça um trecho de draft e rode `/par:review critique` —
   funciona sem nada do stack.

Regras duras: nunca simule saída de comando que falhou; nunca crie scaffold à mão
(`prumo init` é o único caminho); nunca ofereça
instalar o CLI à parte — ele vem no plugin.

## Catálogo completo (gerado — não editar à mão)

<!-- prumo:skills-catalog:begin -->
- `/par:paper extract` — "resuma o paper X" — Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /par:paper library sync executado + symlinks via prumo paper sync-pdfs.
- `/par:paper library` — "sincroniza minha bibliografia" — Gerencia o acervo bibliográfico do pj_* (docs/references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas.
- `/par:paper support` — "as referências batem com o que eu afirmo?" — Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated/No-source) com o subagent verifier lendo o PDF — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título).
- `/par:protocol cep` — "gera o projeto CEP" — Rascunha projeto pra CEP/CONEP via Plataforma Brasil, ou pra CEUA em pesquisa com animais (não prevê o parecer), a partir da pergunta do estudo, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese ou Objetivo, Participantes, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Diz quando o CEP é dispensável. Citação strict. Linguagem acessível no Resumo.
- `/par:protocol picot` — "fecha a PICOT" — Apelido de `question` (ADR-0041): a PICOT agora é um dos frameworks opcionais da pergunta do estudo. Leia modes/question.md e siga-o.
- `/par:protocol question` — "fecha a pergunta do estudo" — Fecha, propaga e versiona a pergunta do estudo em qualquer desenho de pesquisa em saúde (clínico, experimental, observacional, predição, revisão, qualitativo, métodos mistos, econômico, computacional, teórico, metodológico, relato de caso). PICOT, PECO, PCC, PICo, SPIDER e outros entram como estrutura opcional. Grava .claude/question.toml (QuestionSpec/v1), blocos em protocol.md e project_guide.md e ADR append-only quando muda.
- `/par:protocol sap` — "gera o plano de análise estatística" — Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa o desfecho e as métricas da pergunta do estudo e protocol.md. Rascunho que referencia TRIPOD+AI/SPIRIT-AI, TRIPOD-LLM quando o pipeline usa LLM e CONSORT 2025/DECIDE-AI conforme o desenho; conformidade final é do estatístico.
- `/par:review critique` — "revisa este draft" — Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE).
- `/par:review reconcile` — "reconcilia os eventos ambíguos da revisão" — Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (citação é decisão humana).
- `/par:start` — Porta de entrada do par: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review).
- `/par:wiki ingest` — "adiciona esta fonte ao wiki" — Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria a nota da fonte (type: source) em docs/studies/<escopo>/notes/, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /par:paper library.
- `/par:wiki lint` — "audita o wiki" — Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md.
- `/par:wiki query` — "o que a literatura diz sobre X" — Responde pergunta ancorada no wiki do pj_* (docs/ + docs/references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [@citekeys]). Oferece arquivar a resposta como finding (type: finding) em docs/studies/<slug>/notes/ quando útil. NÃO é para perguntas de código.
- `/par:wiki study` — "me ensina X" — Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/studies/<slug>/notes/. No Reflect, oferece arquivar insight como finding.
- `/par:write disclosure` — "gera a declaração de uso de IA" — Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt ou en).
- `/par:write export` — "exporta o docx para o coautor revisar" — Gera o docx do manuscrito com citações vivas do Zotero: travado para a rodada de revisão do coautor, ou final para editar no Word com o Zotero.
- `/par:write manuscript` — "escreve um draft do meu paper" — Gera draft de paper IMRaD venue-aware a partir da pergunta do estudo, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente).
- `/par:write section` — "escreve essa seção" — Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo.
- `/par:write style` — "aplica as convenções de escrita científica" — Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc, em pt-BR ou inglês americano (idioma resolvido por cascata, default en-US) — citação sempre imediatamente antes do ponto final, múltiplas citações num único colchete ([@a; @b]), pontuação sem travessão/dois-pontos/ponto-e-vírgula em texto corrido, remoção de superlativo, economia lexical, coesão entre períodos. Mexe na forma, não na substância; o diff confere as citações, o sentido fica para o autor revisar.
<!-- prumo:skills-catalog:end -->
