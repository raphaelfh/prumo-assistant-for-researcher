# PAR — prumo-assistant-for-researcher

> **Knowledge, bibliography & academic writing assistant for clinical research.**
> Lives between Zotero, your wiki (Markdown; Zettlr front), and your agent-host.

Plugin para agentes como [Claude Code](https://code.claude.com) para pesquisa. 
Cobre cinco domínios: gerir conhecimento (wiki),
gerir bibliografia (Zotero ↔ notas), destrinchar fontes, formalizar 
protocolos e escrever/revisar documentos.

Arquitetura (what/where) em [`ARCHITECTURE.md`](ARCHITECTURE.md); princípios de design em [`docs/constitution.md`](docs/constitution.md); decisões registradas em [`docs/adr/`](docs/adr/); status atual e próximas fases em [`ROADMAP.md`](ROADMAP.md).

## Para pesquisadores (app Claude, aba Code)

Você não precisa de terminal para usar o PAR. Três passos:

1. Abra o app Claude (plano pago — Pro ou Max) → aba **Code**.
2. Cole `/plugin install par --marketplace raphaelfh/prumo-assistant-for-researcher`
   → **Instalar para você**. (Se o comando não for aceito, use o caminho pela
   interface: **+** → **Plugins** → **Add plugin**.)
3. Abra uma sessão nova e peça `/par:start`.

O `/par:start` confere o que falta e pede seu consentimento a cada comando. O
CLI `prumo` vem dentro do plugin: não há nada a instalar além do `uv`, que o
próprio `/par:start` oferece instalar.

**Onde funciona.** A aba Code do app Claude (Mac) e o Claude Code no terminal
(Mac ou Linux) são os canais suportados. No Cowork e no chat do claude.ai, só o
julgamento sobre texto colado (por exemplo, `/par:review critique`) é garantido:
para o resto, use a aba Code. Windows (inclusive WSL): sem suporte. Mac Intel:
suportado, validado pelo job `launcher-smoke` do CI.

Guia completo, passo a passo, em linguagem simples:
[`docs/onboarding-pesquisador.md`](docs/onboarding-pesquisador.md).

## Conteúdo

### Skills

<!-- prumo:skills-table:begin -->
| Você diz | Invocação | O que faz |
|---|---|---|
| "resuma o paper X" | `/par:paper extract` | Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /par:paper library sync executado + symlinks via prumo paper sync-pdfs. |
| "sincroniza minha bibliografia" | `/par:paper library` | Gerencia o acervo bibliográfico do pj_* (docs/references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas. |
| "as referências batem com o que eu afirmo?" | `/par:paper support` | Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated/No-source) com o subagent verifier lendo o PDF — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título). |
| "gera o projeto CEP" | `/par:protocol cep` | Rascunha projeto pra CEP/CONEP (não prevê o parecer) via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo. |
| "fecha a PICOT" | `/par:protocol picot` | Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/studies/<slug>/writing/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado. |
| "gera o plano de análise estatística" | `/par:protocol sap` | Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. Rascunho que referencia TRIPOD+AI/SPIRIT-AI, TRIPOD-LLM quando o pipeline usa LLM e CONSORT 2025/DECIDE-AI conforme o desenho; conformidade final é do estatístico. |
| "revisa este draft" | `/par:review critique` | Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE). |
| "reconcilia os eventos ambíguos da revisão" | `/par:review reconcile` | Reconcilia eventos ambíguos do round-trip de revisão (unanchored/ambiguous/non-identity) propondo marcas CriticMarkup pendentes no worklist via prumo — o humano decide com `prumo write review apply`. NUNCA propõe/move/cunha citação (I1/I3b: eventos de citação são decisão humana). |
| — | `/par:start` | Porta de entrada do par: instala o que falta e roteia para a skill e o modo certos (paper, wiki, protocol, write, review). |
| "adiciona esta fonte ao wiki" | `/par:wiki ingest` | Ingere fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria a nota da fonte (type: source) em docs/studies/<escopo>/notes/, atualiza docs/_index.md, anexa em docs/_log.md, reindexa qmd. Para papers DOI/arXiv delega a /par:paper library. |
| "audita o wiki" | `/par:wiki lint` | Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md. |
| "o que a literatura diz sobre X" | `/par:wiki query` | Responde pergunta ancorada no wiki do pj_* (docs/ + docs/references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [@citekeys]). Oferece arquivar a resposta como finding (type: finding) em docs/studies/<slug>/notes/ quando útil. NÃO é para perguntas de código. |
| "me ensina X" | `/par:wiki study` | Conduz sessão Socrática de estudo em 5 steps (Recall → Anchor → Connect → Apply → Reflect) ancorada nas fontes do projeto (wiki + acervo). Sessão curta (15-25 min) com citação strict. Log estruturado em docs/studies/<slug>/notes/. No Reflect, oferece arquivar insight como finding. |
| "gera a declaração de uso de IA" | `/par:write disclosure` | Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt ou en). |
| "escreve um draft do meu paper" | `/par:write manuscript` | Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente). |
| "escreve essa seção" | `/par:write section` | Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo. |
| "aplica as convenções de escrita científica" | `/par:write style` | Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc, em pt-BR ou inglês americano (idioma resolvido por cascata, default en-US) — citação sempre imediatamente antes do ponto final, múltiplas citações num único colchete ([@a; @b]), pontuação sem travessão/dois-pontos/ponto-e-vírgula em texto corrido, remoção de superlativo, economia lexical, coesão entre períodos. Mexe na forma, não na substância; o diff confere as citações, o sentido fica para o autor revisar. |
<!-- prumo:skills-table:end -->

### MCP

- **`prumo`** — servidor MCP do PAR. Sobe pelo lançador do plugin (`/bin/sh ${CLAUDE_PLUGIN_ROOT}/shims/prumo mcp serve`); as tools aparecem como `mcp__plugin_par_prumo__*`. Não há nada a instalar além do `uv`.

qmd é CLI opcional (ver [Pré-requisitos externos](#pré-requisitos-externos)); não há servidor MCP do qmd no plugin.

## Instalação

```bash
# No Claude Code, dentro de qualquer projeto pj_*:
/plugin marketplace add raphaelfh/prumo-assistant-for-researcher
/plugin install par@prumo-assistant-for-researcher
```

Após a instalação, as skills aparecem com o prefixo `/par:...`.

O CLI `prumo` vem no plugin: o lançador `shims/prumo` roda o código da raiz do
plugin num ambiente montado pelo `uv` a partir do `uv.lock` (na 1ª vez, cerca
de 60 MB em `~/.cache/prumo`), sem instalar nada no sistema.

O PAR se atualiza sozinho nos projetos criados ou atualizados a partir da
0.71.0; senão, aceite a atualização em + → Plugins. Depois, abra uma sessão
nova.

Guia pelo app Claude, sem terminal: [Para
pesquisadores](#para-pesquisadores-app-claude-aba-code) acima, ou o
passo a passo completo em
[`docs/onboarding-pesquisador.md`](docs/onboarding-pesquisador.md).

## Pré-requisitos externos

O plugin orquestra ferramentas que vivem fora do pacote Python. Rode
`prumo doctor` a qualquer momento para checar o estado delas.

| Dependência | Necessária para | Como instalar / habilitar |
|---|---|---|
| **`uv`** | o CLI `prumo` e o servidor MCP do PAR (o lançador monta o ambiente com ele) | Instalador oficial em [docs.astral.sh/uv](https://docs.astral.sh/uv/); o `/par:start` oferece instalar. Sem versão mínima a decorar: o PAR avisa se o seu for antigo e diz como atualizar. |
| **`qmd`** (CLI de busca, opcional) | busca semântica em `/par:wiki query`, `/par:wiki ingest`, `/par:wiki study` | `npm install -g @tobilu/qmd` (repo: [github.com/tobi/qmd](https://github.com/tobi/qmd)). Precisa estar no `PATH`. É CLI: não há servidor MCP do qmd no plugin. |
| **Zotero 9+ e Better BibTeX ≥ 9.0.65** | `paper connect`; vínculo das citações no `write export --to docx` | Abra o Zotero com o [Better BibTeX](https://retorque.re/zotero-better-bibtex/) instalado (`.xpi`). O PAR fala com ele em `127.0.0.1:23119` e não precisa da opção 'Allow other applications'. Sem o Zotero, o resto do PAR funciona, e o docx sai com as citações sem vínculo. |
| **Pandoc ≥ 3.8.2** | `write export`, `write compose` | macOS: `brew install pandoc` (ou o Zettlr, cujo pandoc o PAR usa quando não há um no PATH); Linux: pacote oficial em https://github.com/jgm/pandoc/releases (o do apt costuma ser antigo); confira com `prumo doctor`. |

> [!tip]
> `prumo doctor` lista o estado de cada dependência (`✓` presente / `○` ausente)
> com a dica de instalação. Dependência ausente é apenas um aviso — não impede
> o uso das partes do plugin que não dependem dela.

> [!note]
> Por padrão o prumo fala com o Zotero em `http://127.0.0.1:23119`.
> `PRUMO_ZOTERO_BASE` (ex.: `export PRUMO_ZOTERO_BASE=http://localhost:23200`)
> é variável de dev: o servidor MCP aberto pelo app não herda variáveis do
> perfil do shell.

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

Camadas opcionais com gatilho (`prumo add <módulo>`): `code`, `data`, `notebooks` (marimo `.py` ou Jupyter `.ipynb`), `ml`, `clinical`. Detalhes em [`docs/Research Project Structure.md`](docs/Research%20Project%20Structure.md).

## Stack implícita

- **Tabular:** Polars/pandas, Pandera, scikit-learn `Pipeline`; opcional XGBoost/LightGBM
- **Deep learning:** PyTorch Lightning + timm + TorchMetrics + albumentations
- **Visualização:** seaborn + matplotlib (padrão de publicação); Plotly apenas em dashboards
- **Bibliografia:** Zotero + Better BibTeX (auto-export do `.bib`); notas e PDFs sincronizados pelo `prumo paper`

## Releases

- Histórico completo em [`CHANGELOG.md`](CHANGELOG.md).
- Política de versionamento e processo de release em [`RELEASING.md`](RELEASING.md).

Para atualizar o plugin num Claude Code já configurado: o PAR se atualiza
sozinho nos projetos criados ou atualizados a partir da 0.71.0; senão, aceite a
atualização em + → Plugins (ou `/plugin marketplace update
prumo-assistant-for-researcher` no terminal). Depois, abra uma sessão nova.

## Desinstalar

```
/plugin uninstall par
rm -rf ~/.cache/prumo
```

Só se nada mais os usa: `uv cache clean` e `uv python uninstall 3.12` (cerca
de 70 MB).

## Licença

MIT — ver [LICENSE](LICENSE).
