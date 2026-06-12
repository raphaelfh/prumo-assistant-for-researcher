# prumo-assist

> **Knowledge, bibliography & academic writing assistant for clinical research.**
> Lives between Zotero, Obsidian, and your agent-host.

Plugin do [Claude Code](https://code.claude.com) **e** CLI Python (`prumo`)
para pesquisa clínica. Cobre cinco domínios: gerir conhecimento (wiki),
gerir bibliografia (Zotero ↔ notas), capturar fontes, formalizar o
protocolo (PICOT) e escrever (export Pandoc/Typst + revisão crítica).

Arquitetura (what/where) em [`ARCHITECTURE.md`](ARCHITECTURE.md); princípios de design em [`docs/constitution.md`](docs/constitution.md); decisões registradas em [`docs/adr/`](docs/adr/); status atual e próximas fases em [`ROADMAP.md`](ROADMAP.md).

## Conteúdo

### Skills

<!-- prumo:skills-table:begin -->
| Skill | Uso |
|---|---|
| `/prumo-assist:active-learning` | Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/wiki/study-sessions/. No Reflect, oferece arquivar insight como finding. |
| `/prumo-assist:formulate-picot` | Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado. |
| `/prumo-assist:paper-extract` | Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em references/notes/<citekey>/_extract.md. Pressupõe /paper-manager sync executado + symlinks via make sync-pdfs. |
| `/prumo-assist:paper-manager` | Gerencia o acervo bibliográfico do pj_* (references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas. |
| `/prumo-assist:peer-review` | Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE). |
| `/prumo-assist:scientific-writing` | Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc — pontuação (sem travessão / dois-pontos / ponto-e-vírgula em texto corrido), posição de citação (antes do ponto), agrupamento de múltiplas citações sem vírgula entre wikilinks, atenuação de superlativos, coesão entre períodos. Preserva conteúdo (forma, não substância). |
| `/prumo-assist:start` | Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*). |
| `/prumo-assist:wiki-ingest` | Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria docs/sources/<slug>.md, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /paper-manager. |
| `/prumo-assist:wiki-lint` | Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped em docs/findings/_lint_<data>.md. |
| `/prumo-assist:wiki-query` | Responde pergunta ancorada no wiki do pj_* (docs/ + references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [[@citekeys]]). Oferece arquivar a resposta como finding em docs/findings/ quando útil. NÃO é para perguntas de código. |
| `/prumo-assist:write-paper` | Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente). |
| `/prumo-assist:write-projeto-cep` | Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo. |
| `/prumo-assist:write-scientific` | Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo. |
| `/prumo-assist:write-statistics` | Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho. |
<!-- prumo:skills-table:end -->

### Agents

| Agent | Uso |
|---|---|
| `ml-theory-expert` | Fundamentação teórica (estatística/ML) com citações da base de conhecimento. |
| `stack-docs-researcher` | Consulta documentação atualizada da stack (scikit-learn, Lightning, albumentations, etc.). |

### MCP

- **`qmd`** — servidor MCP para busca BM25 + vector + rerank local no wiki dos projetos. **Requer instalação** — ver [Pré-requisitos externos](#pré-requisitos-externos).

## Instalação

```bash
# No Claude Code, dentro de qualquer projeto pj_*:
/plugin marketplace add raphaelfh/prumo-assist
/plugin install prumo-assist@prumo-assist
```

Após a instalação, as skills aparecem com o prefixo `/prumo-assist:...` e os agents ficam disponíveis via `Agent` tool.

## Pré-requisitos externos

O plugin orquestra duas ferramentas que vivem fora do pacote Python. Rode
`prumo doctor` a qualquer momento para checar o estado delas.

| Dependência | Necessária para | Como instalar / habilitar |
|---|---|---|
| **`qmd`** (MCP de busca) | `/prumo-assist:wiki-query`, `/prumo-assist:wiki-ingest`, `/prumo-assist:active-learning` | `bun install -g @tobilu/qmd` (repo: [github.com/tobi/qmd](https://github.com/tobi/qmd)). Precisa estar no `PATH`. Declarado em `.mcp.json` como servidor `qmd`. |
| **Zotero 9 + Better BibTeX** | `paper sync-annotations`, `paper sync-notes`, `write export --to docx` (citações vivas) | Abra o Zotero 9 com o [Better BibTeX](https://retorque.re/zotero-better-bibtex/) instalado. Ele expõe a API local em `127.0.0.1:23119`. Só é necessário para os comandos que leem anotações/notas — o resto do prumo funciona sem ele. |

> [!tip]
> `prumo doctor` lista o estado de cada dependência (`✓` presente / `○` ausente)
> com a dica de instalação. Dependência ausente é apenas um aviso — não impede
> o uso das partes do plugin que não dependem dela.

> [!note]
> Por padrão o prumo fala com o Zotero em `http://127.0.0.1:23119`. Para usar
> outra porta/host, exporte `PRUMO_ZOTERO_BASE` (ex.:
> `export PRUMO_ZOTERO_BASE=http://localhost:23200`).

## Pressupostos de projeto

Este plugin assume a estrutura de projeto `pj_*` do monorepo `monorepo-anterior`:

```
pj_<nome>/
├── content/01_raw|02_processed/
├── docs/{_index.md, _log.md, concepts/, entities/, findings/, sources/, decisions/}
├── references/{_index.md, _references.bib, notes/, pdfs/, views/}
├── 01_eda_clinical.ipynb … 05_combinado_fusion.ipynb
└── .claude/
    ├── rules/project_context.md
    └── skills/                   # extensões específicas do projeto
```

Para scaffolding de novos `pj_*` e orquestração de submodules, use o monorepo [`monorepo-anterior`](<monorepo-anterior>) (skill `/project-manager`).

## Stack implícita

- **Tabular:** Polars/pandas, Pandera, scikit-learn `Pipeline`; opcional XGBoost/LightGBM
- **Deep learning:** PyTorch Lightning + timm + TorchMetrics + albumentations
- **Visualização:** seaborn + matplotlib (padrão de publicação); Plotly apenas em dashboards
- **Bibliografia:** Zotero + Better BibTeX + Obsidian (Zotero Integration + Templater + Linter)

## Releases

- Histórico completo em [`CHANGELOG.md`](CHANGELOG.md).
- Política de versionamento e processo de release em [`RELEASING.md`](RELEASING.md).

Para atualizar o plugin num Claude Code já configurado:

```
/plugin marketplace update prumo-assist
/reload-plugins
```

## Licença

MIT — ver [LICENSE](LICENSE).
