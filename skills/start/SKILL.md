---
name: start
description: "Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*)."
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
   - **Tudo OK** → pergunte em 1 linha o que a pessoa quer fazer e roteie
     (bibliografia → paper-manager/paper-extract; wiki → wiki-ingest/query/lint;
     escrita → scientific-writing/peer-review/write-*). Não execute a tarefa
     você mesmo.
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
   diga que é opcional e PULE (wiki-query funciona em modo degradado por leitura
   direta). Quem quiser: `bun install -g @tobilu/qmd`.
5. **Projeto**: `prumo init pj_<nome>` na pasta que a pessoa designar.
6. **Conectar a biblioteca**: com o Zotero aberto, `prumo paper connect "<coleção>"`
   liga o `.bib` do projeto à coleção do Zotero (substitui a configuração manual
   de "Keep updated"). Não é bloqueante — pode ser feito depois.
7. **Primeiro output em minutos**: peça um trecho de draft e rode
   `/prumo-assist:peer-review` — funciona sem NADA do stack (julgamento puro).

Regras duras: nunca simule saída de comando que falhou; nunca crie scaffold
manualmente (`prumo init` é o único caminho); nunca cite tooling do monorepo do
autor (`make ...`) — a pessoa instalou um plugin, não clonou um repositório.

## Catálogo completo (gerado — não editar à mão)

<!-- prumo:skills-catalog:begin -->
- `/prumo-assist:active-learning` — Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/wiki/study-sessions/. No Reflect, oferece arquivar insight como finding.
- `/prumo-assist:citation-support` — Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated) usando os extracts do acervo — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título).
- `/prumo-assist:formulate-picot` — Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado.
- `/prumo-assist:paper-extract` — Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em references/notes/<citekey>/_extract.md. Pressupõe /prumo-assist:paper-manager sync executado + symlinks via prumo paper sync-pdfs.
- `/prumo-assist:paper-manager` — Gerencia o acervo bibliográfico do pj_* (references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas.
- `/prumo-assist:peer-review` — Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE).
- `/prumo-assist:review-reconcile` — Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana).
- `/prumo-assist:scientific-writing` — Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc — pontuação (sem travessão / dois-pontos / ponto-e-vírgula em texto corrido), posição de citação (antes do ponto), agrupamento de múltiplas citações num único colchete separadas por ponto-e-vírgula ([@a; @b]), atenuação de superlativos, coesão entre períodos. Preserva conteúdo (forma, não substância).
- `/prumo-assist:start` — Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*).
- `/prumo-assist:wiki-ingest` — Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria docs/sources/<slug>.md, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /prumo-assist:paper-manager.
- `/prumo-assist:wiki-lint` — Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped em docs/wiki/findings/_lint_<data>.md (fallback: docs/findings/).
- `/prumo-assist:wiki-query` — Responde pergunta ancorada no wiki do pj_* (docs/ + references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [@citekeys]). Oferece arquivar a resposta como finding em docs/wiki/findings/ (ou docs/findings/ em projetos sem docs/wiki/) quando útil. NÃO é para perguntas de código.
- `/prumo-assist:write-paper` — Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente).
- `/prumo-assist:write-projeto-cep` — Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo.
- `/prumo-assist:write-scientific` — Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo.
- `/prumo-assist:write-statistics` — Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho.
<!-- prumo:skills-catalog:end -->
