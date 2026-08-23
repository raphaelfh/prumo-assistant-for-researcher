# prumo-assist

> **Knowledge, bibliography & academic writing assistant for clinical research.**
> Lives between Zotero, your wiki (Markdown; Zettlr front — Obsidian legacy), and your agent-host.

Plugin para agentes como [Claude Code](https://code.claude.com) para pesquisa. 
Cobre cinco domínios: gerir conhecimento (wiki),
gerir bibliografia (Zotero ↔ notas), destrinchar fontes, formalizar 
protocolos e escrever/revisar documentos.

Arquitetura (what/where) em [`ARCHITECTURE.md`](ARCHITECTURE.md); princípios de design em [`docs/constitution.md`](docs/constitution.md); decisões registradas em [`docs/adr/`](docs/adr/); status atual e próximas fases em [`ROADMAP.md`](ROADMAP.md).

## Para pesquisadores (Desktop/Cowork, sem terminal)

Você não precisa de terminal para usar o prumo-assist. Direto no Claude
Desktop ou no Cowork: menu de plugins → **"Add from a repository"** →
`raphaelfh/prumo-assist` (exige plano Claude pago — Pro ou Max).

Depois de instalado, cole um trecho de draft e peça `/prumo-assist:peer-review`
— funciona sem instalar mais nada (julgamento puro; testado no spike da Fase 0
sem CLI/Zotero/qmd). Quando quiser ir além (bibliografia, projeto no disco), a
própria conversa guia a instalação do resto — `/prumo-assist:start` pede seu
consentimento a cada comando.

Guia completo, passo a passo, em linguagem simples:
[`docs/onboarding-pesquisador.md`](docs/onboarding-pesquisador.md).

## Conteúdo

### Skills

<!-- prumo:skills-table:begin -->
| Skill | Uso |
|---|---|
| `/prumo-assist:active-learning` | Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/studies/<slug>/notes/. No Reflect, oferece arquivar insight como finding. |
| `/prumo-assist:citation-support` | Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated) usando os extracts do acervo — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título). |
| `/prumo-assist:formulate-picot` | Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/studies/<slug>/writing/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado. |
| `/prumo-assist:paper-extract` | Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /prumo-assist:paper-manager sync executado + symlinks via prumo paper sync-pdfs. |
| `/prumo-assist:paper-manager` | Gerencia o acervo bibliográfico do pj_* (docs/references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas. |
| `/prumo-assist:peer-review` | Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE). |
| `/prumo-assist:review-reconcile` | Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana). |
| `/prumo-assist:scientific-writing` | Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc, em pt-BR ou inglês americano (idioma resolvido por cascata, default en-US) — citação sempre imediatamente antes do ponto final, múltiplas citações num único colchete ([@a; @b]), pontuação sem travessão/dois-pontos/ponto-e-vírgula em texto corrido, remoção de superlativo, economia lexical, coesão entre períodos. Preserva conteúdo (forma, não substância). |
| `/prumo-assist:start` | Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*). |
| `/prumo-assist:wiki-ingest` | Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria a nota da fonte (type: source) em docs/studies/<escopo>/notes/, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /prumo-assist:paper-manager. |
| `/prumo-assist:wiki-lint` | Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md. |
| `/prumo-assist:wiki-query` | Responde pergunta ancorada no wiki do pj_* (docs/ + docs/references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [@citekeys]). Oferece arquivar a resposta como finding (type: finding) em docs/studies/<slug>/notes/ quando útil. NÃO é para perguntas de código. |
| `/prumo-assist:write-paper` | Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente). |
| `/prumo-assist:write-projeto-cep` | Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo. |
| `/prumo-assist:write-scientific` | Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo. |
| `/prumo-assist:write-statistics` | Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho. |
<!-- prumo:skills-table:end -->

### MCP

- **`qmd`** — servidor MCP para busca BM25 + vector + rerank local no wiki dos projetos. **Requer instalação** — ver [Pré-requisitos externos](#pré-requisitos-externos).

## Instalação

```bash
# No Claude Code, dentro de qualquer projeto pj_*:
/plugin marketplace add raphaelfh/prumo-assist
/plugin install prumo-assist@prumo-assist
```

Após a instalação, as skills aparecem com o prefixo `/prumo-assist:...`.

Para usar as skills que dependem do CLI Python (bibliografia, escrita, wiki),
instale também o `prumo`:

```bash
uv tool install git+https://github.com/raphaelfh/prumo-assist.git
```

Atualizar depois: `uv tool upgrade prumo-assist`.

Guia sem terminal para quem prefere não usar o CLI/Claude Code: [Para
pesquisadores](#para-pesquisadores-desktopcowork-sem-terminal) acima, ou o
passo a passo completo em
[`docs/onboarding-pesquisador.md`](docs/onboarding-pesquisador.md).

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

Este plugin assume a estrutura de projeto `pj_*`, com `docs/` como raiz única de leitura:

```
pj_<nome>/
├── .claude/                pj_config.toml = sentinela do projeto
├── build/exports/          reviews/<slug>/ — saída de máquina, gitignored
└── docs/                   raiz única de leitura
    ├── _index.md, _log.md, project_guide.md, templates/
    ├── references/          DO PROJETO — _references.bib, _index.md, .gitignore,
    │                        papers/<citekey>/, pdfs/<citekey>.pdf
    └── studies/<slug>/      O ESCOPO — notes/, writing/, decisions/
```

Camadas opcionais com gatilho (`prumo add <módulo>`): `code`, `data`, `notebooks`, `ml`, `clinical`. Detalhes em [`docs/Research Project Structure.md`](docs/Research%20Project%20Structure.md).

## Stack implícita

- **Tabular:** Polars/pandas, Pandera, scikit-learn `Pipeline`; opcional XGBoost/LightGBM
- **Deep learning:** PyTorch Lightning + timm + TorchMetrics + albumentations
- **Visualização:** seaborn + matplotlib (padrão de publicação); Plotly apenas em dashboards
- **Bibliografia:** Zotero + Better BibTeX (auto-export do `.bib`); notas e PDFs sincronizados pelo `prumo paper`

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
