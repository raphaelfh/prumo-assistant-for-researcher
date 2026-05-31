# prumo-assist

> **Knowledge, bibliography & academic writing assistant for clinical research.**
> Lives between Zotero, Obsidian, and your agent-host.

Plugin do [Claude Code](https://code.claude.com) **e** CLI Python (`prumo`)
para pesquisa clínica. Cobre quatro pilares: gerir conhecimento (wiki),
gerir bibliografia (Zotero ↔ notas), capturar fontes, e escrever (export
Pandoc/Typst + revisão crítica).

Arquitetura e princípios de design em [`ARCHITECTURE.md`](ARCHITECTURE.md); status atual e próximas fases em [`ROADMAP.md`](ROADMAP.md).

## Conteúdo

### Skills

| Skill | Uso |
|---|---|
| `/prumo-assist:paper-manager` | Gestão do acervo bibliográfico (Zotero + Better BibTeX + `references/`): sincroniza `.bib`, grafo de citação, paper principal. |
| `/prumo-assist:paper-extract` | Lê PDF e preenche callout estruturado (TL;DR + PICOT + Método + Resultados + Limitações) na nota do paper. Single ou batch. |
| `/prumo-assist:wiki-ingest` | Ingere fonte (URL, DOI, arXiv, PDF, decisão) no wiki do projeto. Delega papers a `paper-manager`. |
| `/prumo-assist:wiki-query` | Responde perguntas ancoradas no wiki do projeto com citações. Oferece arquivar em `docs/findings/`. |
| `/prumo-assist:wiki-lint` | Health-check do wiki: páginas órfãs, citekeys quebradas, contradições, stale claims. |
| `/prumo-assist:scientific-writing` | Passe editorial de escrita científica formal em draft Markdown/Quarto. Padroniza pontuação (sem travessão, dois-pontos ou ponto-e-vírgula no texto corrido), posiciona citação ao final do período, agrupa múltiplas citações sem vírgula entre wikilinks (`[[@a]] [[@b]] [[@c]]`) para fusão em campo único pelo normalizador de export, e atenua superlativos. |
| `/prumo-assist:peer-review` | Revisão crítica substantiva (forças, fraquezas, claims sem evidência) em draft acadêmico. |
| `/prumo-assist:formulate-picot` | Formaliza/propaga/versiona PICOT do projeto. Mantém canônico em `.claude/picot.toml` e renderiza blocos delimitados em `protocol.md`, `project.md`. Gera ADR `adr-NNNN-picot-v<N>` quando hipótese ou campo estrutural muda. Auto-detecta modo Socrático/Formalize/Propagate/Diff. |
| `/prumo-assist:active-learning` | Tutor Socrático em 5 steps (recall → anchor → connect → apply → reflect) ancorado nas fontes do projeto. Sessão ad-hoc 15-25 min. Log estruturado em `docs/wiki/study-sessions/`. Pode arquivar insight como finding. |
| `/prumo-assist:write-paper` | Gera draft de paper IMRaD venue-aware a partir do PICOT + papers do acervo. Citação strict; `[REF FALTANTE]` se acervo faltante. Default: `docs/drafts/paper-<data>-<slug>.md`. |
| `/prumo-assist:write-projeto-cep` | Gera projeto pra CEP brasileiro (Resumo, Justificativa, Coorte, Riscos+benefícios, TCLE, Cronograma, Conformidade ética CNS 466/2012 + 510/2016). |
| `/prumo-assist:write-statistics` | Gera Plano de Análise Estatística (PAE): outcome operacional, sample size, métricas, análises de sensibilidade, splits anti-leakage. |
| `/prumo-assist:write-scientific` | Gera prose acadêmica genérica (1 seção, parágrafo isolado, expansão de seed text). Mais flexível das 4 skills `write-*`. |

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
