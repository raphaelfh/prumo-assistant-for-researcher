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
---

# prumo-assist: por onde começar

Você é o guia de entrada. Pergunte ao usuário, em 1 linha, o que ele quer fazer e
roteie para a skill adequada (não execute a tarefa você mesmo — apenas oriente/inicie):

- **Bibliografia / Zotero** → `/prumo-assist:paper-manager` (sincronizar acervo),
  `/prumo-assist:paper-extract` (PDF → resumo estruturado).
- **Conhecimento / wiki** → `/prumo-assist:wiki-ingest <fonte>` (guardar),
  `/prumo-assist:wiki-query "..."` (perguntar com citações),
  `/prumo-assist:wiki-lint` (auditar).
- **Escrita** → `/prumo-assist:scientific-writing` (passe editorial),
  `/prumo-assist:peer-review` (revisão crítica), `/prumo-assist:write-paper` (draft).

Se o projeto precisar de mais estrutura (protocolo clínico, stack de ML), informe que
isso vem de módulos: `prumo add clinical` ou `prumo add ml` no terminal.

Comece perguntando: **"O que você quer fazer agora — bibliografia, wiki ou escrita?"**

## Catálogo completo (gerado — não editar à mão)

<!-- prumo:skills-catalog:begin -->
- `/prumo-assist:active-learning` — Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/wiki/study-sessions/. No Reflect, oferece arquivar insight como finding.
- `/prumo-assist:formulate-picot` — Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado.
- `/prumo-assist:paper-extract` — Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em references/notes/<citekey>/_extract.md. Pressupõe /prumo-assist:paper-manager sync executado + symlinks via make sync-pdfs.
- `/prumo-assist:paper-manager` — Gerencia o acervo bibliográfico do pj_* (references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas.
- `/prumo-assist:peer-review` — Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE).
- `/prumo-assist:scientific-writing` — Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc — pontuação (sem travessão / dois-pontos / ponto-e-vírgula em texto corrido), posição de citação (antes do ponto), agrupamento de múltiplas citações sem vírgula entre wikilinks, atenuação de superlativos, coesão entre períodos. Preserva conteúdo (forma, não substância).
- `/prumo-assist:start` — Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*).
- `/prumo-assist:wiki-ingest` — Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria docs/sources/<slug>.md, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /prumo-assist:paper-manager.
- `/prumo-assist:wiki-lint` — Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped em docs/wiki/findings/_lint_<data>.md (fallback: docs/findings/).
- `/prumo-assist:wiki-query` — Responde pergunta ancorada no wiki do pj_* (docs/ + references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [[@citekeys]]). Oferece arquivar a resposta como finding em docs/wiki/findings/ (ou docs/findings/ em projetos sem docs/wiki/) quando útil. NÃO é para perguntas de código.
- `/prumo-assist:write-paper` — Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente).
- `/prumo-assist:write-projeto-cep` — Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo.
- `/prumo-assist:write-scientific` — Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo.
- `/prumo-assist:write-statistics` — Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho.
<!-- prumo:skills-catalog:end -->
