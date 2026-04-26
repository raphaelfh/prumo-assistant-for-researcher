# prumo-assist

Plugin do [Claude Code](https://code.claude.com) com skills e agents para pesquisa em **machine learning aplicado à saúde**. Projetado para projetos `pj_*` do monorepo `monorepo-anterior` (e derivados standalone).

## Conteúdo

### Skills

| Skill | Uso |
|---|---|
| `/prumo-assist:tabular-eda` | Gera notebook Jupyter pré-populado para EDA tabular clínica com data profiling e quality assessment. |
| `/prumo-assist:data-cleaning` | Workflow padronizado de limpeza/pré-processamento clínico com relatório automático em `data/reports/`. |
| `/prumo-assist:clinical-metrics` | Métricas para classificadores clínicos (AUROC, PR-AUC, sens/esp, Brier, calibração) + figuras seaborn publicáveis + bootstrap CI. |
| `/prumo-assist:paper-manager` | Gestão do acervo bibliográfico (Zotero + Better BibTeX + `references/`): sincroniza `.bib`, grafo de citação, paper principal. |
| `/prumo-assist:paper-extract` | Lê PDF e preenche callout estruturado (TL;DR + PICOT + Método + Resultados + Limitações) na nota do paper. Single ou batch. |
| `/prumo-assist:wiki-ingest` | Ingere fonte (URL, DOI, arXiv, PDF, decisão) no wiki do projeto. Delega papers a `paper-manager`. |
| `/prumo-assist:wiki-query` | Responde perguntas ancoradas no wiki do projeto com citações. Oferece arquivar em `docs/findings/`. |
| `/prumo-assist:wiki-lint` | Health-check do wiki: páginas órfãs, citekeys quebradas, contradições, stale claims. |

### Agents

| Agent | Uso |
|---|---|
| `ml-theory-expert` | Fundamentação teórica (estatística/ML) com citações da base de conhecimento. |
| `stack-docs-researcher` | Consulta documentação atualizada da stack (scikit-learn, Lightning, albumentations, etc.). |

### MCP

- **`qmd`** — servidor MCP para busca BM25 + vector + rerank local no wiki dos projetos.

## Instalação

```bash
# No Claude Code, dentro de qualquer projeto pj_*:
/plugin marketplace add raphaelfh/prumo-assist
/plugin install prumo-assist@prumo-assist
```

Após a instalação, as skills aparecem com o prefixo `/prumo-assist:...` e os agents ficam disponíveis via `Agent` tool.

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

## Licença

MIT — ver [LICENSE](LICENSE).
