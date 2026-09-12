---
name: start
description: "Porta de entrada do prumo-assist: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review)."
when_to_use: |
  Quando o usuário abre o prumo-assist sem saber por onde começar, pergunta
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

# prumo-assist: por onde começar

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
<!-- prumo:preflight:end -->

Você é a porta de entrada E o instalador guiado. Primeiro descubra o estado:

1. Rode `prumo doctor --json` (se `prumo` existir). Três cenários:
   - **Tudo OK** → rode `prumo status --json`. Com `next` preenchido, ofereça
     em 1 linha a frase `next.say` (invocação `next.invocation`) e o motivo
     `next.why`. Sem `next`, ou se a pessoa quiser outra coisa, pergunte o que
     ela quer fazer e roteie para a skill e o modo (bibliografia → `paper`; wiki
     e estudo → `wiki`; PICOT, plano estatístico e CEP → `protocol`; escrita →
     `write`; revisão → `review`). Use o catálogo abaixo para achar o modo pela
     frase. Não execute a tarefa você mesmo. Se `status` não existir
     (`No such command 'status'`, exit 2 — CLI instalado mais antigo que o
     plugin), siga como sem `next` e ofereça UMA vez
     `uv tool upgrade prumo-assist` (rode SÓ com consentimento).
   - **`prumo` NÃO existe** → ofereça a instalação guiada abaixo.
   - **Superfície sem execução de comandos** (chat puro) → aponte a trilha do
     pesquisador: `docs/onboarding-pesquisador.md` no repositório do plugin.

## Instalação guiada (com consentimento POR COMANDO — nunca rode sem um "sim")

Explique o que cada passo faz ANTES de rodar; peça consentimento explícito;
mostre a saída; siga só se funcionou:

1. **uv** (gerenciador Python): `command -v uv` — ausente? →
   `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **CLI prumo**: `uv tool install git+https://github.com/raphaelfh/prumo-assist.git`
   (atualização depois: `uv tool upgrade prumo-assist`)
3. **Diagnóstico**: `prumo doctor` — Zotero fechado/ausente? Oriente: instalar o
   Zotero (zotero.org) + plugin Better BibTeX, abrir o app. NÃO é bloqueante para
   escrita/julgamento; é necessário para sincronizar bibliografia.
4. **qmd (OPCIONAL — busca semântica)**: exige `bun`. Se a pessoa não tem bun,
   diga que é opcional e PULE (`wiki query` funciona em modo degradado por leitura
   direta). Quem quiser: `bun install -g @tobilu/qmd`.
5. **Projeto**: `prumo init pj_<nome>` na pasta que a pessoa designar.
6. **Conectar a biblioteca**: com o Zotero aberto, `prumo paper connect "<coleção>"`
   liga o `.bib` do projeto à coleção do Zotero (substitui a configuração manual
   de "Keep updated"). Não é bloqueante — pode ser feito depois. Se a coleção ainda
   não existir, `--create` cria e liga num passo — mas só quando a pessoa pedir a
   criação: nunca acrescente a flag por conta própria (ADR-0028).
7. **Primeiro output em minutos**: peça um trecho de draft e rode
   `/prumo-assist:review critique` — funciona sem NADA do stack (julgamento puro).

Regras duras: nunca simule saída de comando que falhou; nunca crie scaffold
manualmente (`prumo init` é o único caminho); nunca cite tooling do monorepo do
autor (`make ...`) — a pessoa instalou um plugin, não clonou um repositório.

## Catálogo completo (gerado — não editar à mão)

<!-- prumo:skills-catalog:begin -->
- `/prumo-assist:paper extract` — "resuma o paper X" — Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /prumo-assist:paper library sync executado + symlinks via prumo paper sync-pdfs.
- `/prumo-assist:paper library` — "sincroniza minha bibliografia" — Gerencia o acervo bibliográfico do pj_* (docs/references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas.
- `/prumo-assist:paper support` — "as referências batem com o que eu afirmo?" — Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated/No-source) com o subagent verifier lendo o PDF — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título).
- `/prumo-assist:protocol cep` — "gera o projeto CEP" — Rascunha projeto pra CEP/CONEP (não prevê o parecer) via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo.
- `/prumo-assist:protocol picot` — "fecha a PICOT" — Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/studies/<slug>/writing/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado.
- `/prumo-assist:protocol sap` — "gera o plano de análise estatística" — Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. Rascunho que referencia TRIPOD+AI/SPIRIT-AI, TRIPOD-LLM quando o pipeline usa LLM e CONSORT 2025/DECIDE-AI conforme o desenho; conformidade final é do estatístico.
- `/prumo-assist:review critique` — "revisa este draft" — Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE).
- `/prumo-assist:review reconcile` — "reconcilia os eventos ambíguos da revisão" — Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana).
- `/prumo-assist:start` — Porta de entrada do prumo-assist: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review).
- `/prumo-assist:wiki ingest` — "adiciona esta fonte ao wiki" — Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria a nota da fonte (type: source) em docs/studies/<escopo>/notes/, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /prumo-assist:paper library.
- `/prumo-assist:wiki lint` — "audita o wiki" — Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md.
- `/prumo-assist:wiki query` — "o que a literatura diz sobre X" — Responde pergunta ancorada no wiki do pj_* (docs/ + docs/references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [@citekeys]). Oferece arquivar a resposta como finding (type: finding) em docs/studies/<slug>/notes/ quando útil. NÃO é para perguntas de código.
- `/prumo-assist:wiki study` — "me ensina X" — Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/studies/<slug>/notes/. No Reflect, oferece arquivar insight como finding.
- `/prumo-assist:write disclosure` — "gera a declaração de uso de IA" — Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt ou en).
- `/prumo-assist:write manuscript` — "escreve um draft do meu paper" — Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente).
- `/prumo-assist:write section` — "escreve essa seção" — Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo.
- `/prumo-assist:write style` — "aplica as convenções de escrita científica" — Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc, em pt-BR ou inglês americano (idioma resolvido por cascata, default en-US) — citação sempre imediatamente antes do ponto final, múltiplas citações num único colchete ([@a; @b]), pontuação sem travessão/dois-pontos/ponto-e-vírgula em texto corrido, remoção de superlativo, economia lexical, coesão entre períodos. Mexe na forma, não na substância; o diff confere as citações, o sentido fica para o autor revisar.
<!-- prumo:skills-catalog:end -->
