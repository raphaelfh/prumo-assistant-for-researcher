# Changelog

Todas as mudanças relevantes deste plugin.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/) — política de quando bumpar `MAJOR/MINOR/PATCH` em [`RELEASING.md`](RELEASING.md).

## [Não publicado]

### Adicionado

- **`docs/templates/` no scaffold `pj_base/`** — diretório com 4 modelos administrativos prontos para uso em qualquer estudo observacional em saúde, copiados na criação do projeto via `prumo init`:
  - `Template submissão Plataforma Brasil.docx` — layout oficial do CEP/CONEP, usado como `--reference-doc` do `pandoc` para gerar o `.docx` final de submissão.
  - `projeto-cep.md` — esqueleto Markdown da submissão CEP (alinhado com Resolução CNS 466/2012 e CONEP 580/2018).
  - `data_dictionary_example.csv` — gabarito pipe-delimited (NAME · DEFINITION · MIN_OR_VALUES · MAX · UNIT · TYPE · WINDOW · SELECTION_RULE · AVAILABLE · NOTES) com convenções (UPPERCASE ≤10 chars, datas `YYYY-MM-DD`, decimal `.`, missing `NA`).
  - `statistical_analysis_plan_skeleton.md` — esqueleto de SAP com seções pré-especificadas: princípios, populações de análise, descritiva, sobrevida (KM + Fine-Gray), longitudinais (spaghetti/Sankey), exploratórias, 6 análises de sensibilidade tipo, subgrupos, reporting (STROBE/RECORD/CONSORT/SPIRIT/TRIPOD-AI).
  - `README.md` no diretório explica o fluxo: `cp templates/<X> docs/<Y>`, edição da cópia, geração do `.docx` final via `pandoc --reference-doc`.
- `docs/_index.md` do scaffold lista o diretório `templates/` em seção dedicada "Administrative templates".

## [0.5.0] - 2026-05-04

### Adicionado

- **`/prumo-assist:formulate-picot`** — skill agêntica que formaliza/propaga/versiona o PICOT do projeto. Mantém spec canônica em `.claude/picot.toml`, renderiza blocos delimitados em `protocol.md` e `project.md`, e gera ADR `adr-NNNN-picot-v<N>` quando hipótese ou campo estrutural muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff). Domínio `domains/protocol/` com `PicotSpec/v1` (Pydantic), `picot_io`, `render`, `diff`, `adr`, `ops`. CLI: `prumo protocol propagate|diff`.
- **`/prumo-assist:active-learning`** — skill agêntica que conduz sessão de estudo Socrática estruturada em 5 steps (Recall → Anchor → Connect → Apply → Reflect) sobre um tópico, ancorada nas fontes do projeto (wiki + acervo). Sessão ad-hoc 15-25 min com citação strict (só citekeys do acervo + `[REF FALTANTE]`). Log estruturado em `docs/wiki/study-sessions/<topic>-<data>.md` (`SessionLog/v1`). No step Reflect, oferece arquivar insight como finding via helper `archive_as_finding` (extraído de `wiki-query` para reuso).
- **Família `/prumo-assist:write-*`** (4 skills agênticas + backend compartilhado):
  - `write-paper` — draft IMRaD venue-aware a partir do PICOT + papers do acervo.
  - `write-projeto-cep` — projeto pra CEP brasileiro (TCLE, Cronograma, Conformidade ética CNS 466/2012 + 510/2016, LGPD).
  - `write-statistics` — Plano de Análise Estatística (PAE): outcome operacional, sample size, métricas, sensibilidade, splits anti-leakage.
  - `write-scientific` — prose acadêmica genérica flexível (1 seção, parágrafo, expansão de seed).
  - Backend: `domains/write/compose.py` (`read_inputs`, `resolve_template`, `compose_path`, `write_output`, `extract_missing_refs`); schemas `ComposeInputs/v1`, `WriteOutput/v1`, `PaperSummary`, `FindingSummary`. 3 modos de output: `drafts/` (default), `--into <path>` (bloco delimitado), `--out <path>` (livre).
  - 4 templates default em `templates/writing/{paper,projeto-cep,statistics,scientific}.md`. Override por projeto em `.claude/writing_templates/<kind>.md` ou `--template <path>`.
  - CLI: `prumo write list-templates [--json]` lista templates resolvíveis.
- Citação strict transversal (formulate-picot, active-learning, write-*): só `[[@citekey]]` que existe em `references/_references.bib`. Falta vira `[REF FALTANTE: <descrição>]` — nunca invenção.

## [0.4.0] - 2026-05-03

### Adicionado

- **Layout α de notas**: cada paper agora vive em `references/notes/<citekey>/` com `_meta.md`, `_extract.md`, `_annotations.md` separados. Permite múltiplas child notes por paper (PR-N2 traz `note__*.md`) e melhora retrieval por chunk pequeno + metadata estável.
- **`prumo paper migrate-layout`**: comando one-shot que desmembra `<key>.md` legado em pasta α, preservando histórico via `git mv`. Idempotente.
- **`core/note_paths.py`**: helpers de path centralizados (`note_dir`, `meta_path`, `extract_path`, `annotations_path`, `child_note_path`, `slugify`, `iter_note_meta_files`, `citekey_from_meta_path`). Domínios `paper.{graph,find,lint,sync,zotero,callout,migrate}` usam essas funções como single source of truth.
- **Nova regra de lint**: `subdir_without_meta` — sinaliza pasta `notes/<key>/` sem `_meta.md` (migração interrompida ou pasta órfã).

### Modificado

- `prumo paper sync` escreve em `<key>/_meta.md` (era `<key>.md`).
- `prumo paper sync-annotations` escreve em `<key>/_annotations.md` dedicado (era bloco delimitado dentro do `<key>.md`).
- `/prumo-assist:paper-extract` escreve em `<key>/_extract.md` dedicado (era callout dentro do `<key>.md`).
- `paper graph`, `paper find`, `paper lint`, `set_primary` aceitam ambos layouts durante transição (graceful degradation; preferência por α quando ambos existem).
- `templates/pj_base/references/templates/literature_note.md` reflete o novo layout (campo `pdf:` ajustado pra `../../pdfs/<key>.pdf`).

## [0.3.0] - 2026-05-03

### Removido — ⚠ Breaking

- **Skills de código spin-off**: `tabular-eda`, `data-cleaning`, `clinical-metrics` removidas deste repo. Escopo do plugin volta a "knowledge, bibliography & academic writing for clinical research" (a tagline real). Quem dependia delas deve migrar pro `prumo-code-assist` (repo separado) quando publicado. O conteúdo continua acessível via histórico git (`git log -- skills/tabular-eda`).
- **`agents/` revistos**: `ml-theory-expert` e `stack-docs-researcher` permanecem por enquanto (cobrem fundamentação teórica e consulta de docs, úteis também na escrita); serão reavaliados na próxima minor.
- Tarball gerado por `prumo init` deixa de conter as skills removidas (consequência direta).

### Simplificado — refator interno

- **Fachadas CLI ↔ API**: introduzido `core/cli_op.cli_run` (context manager) que encapsula `Console + try/except PrumoError + typer.Exit(1)`. Subcomandos Typer ficam ~30% menores. Os `domains/<X>/api.py` viraram re-exports puros (sem wrappers passthrough).
- **Resolução de paths**: `core/paths.py::resolve_resource/find_resource` consolida a busca de `templates/` e `skills/` (instalado vs worktree dev) que estava duplicada no CLI e na API pública.
- **Documentação dividida**: `ROADMAP.md` (305 linhas) virou `ARCHITECTURE.md` (estável: princípios, layout, fluxo) + `ROADMAP.md` (dinâmico: status PR + próximas fases).
- **Manifests bumpáveis sem garfo**: novo `.github/scripts/sync_manifest_version.py` propaga `_version.py` pra `plugin.json`/`marketplace.json` (`--check` em CI futuro).
- **Tests por domínio**: `tests/unit/<core|paper|wiki|write|capture>/` espelha `src/prumo_assist/`. 97 testes preservados.

## [0.2.0] - 2026-04-28

### Adicionado — fundação do CLI Python (PR0–PR3)

- **Pacote Python instalável** `prumo-assist` (entry point `prumo`).
  Build via hatchling, distribuível por `uv tool install` ou `pipx`.
- **`core/`** (transversal, 7 módulos): `config`, `bib`, `csl`, `obsidian`,
  `skills` (parser SKILL.md frontmatter rico + registry), `provenance`
  (bloco `_meta` + JSONL trace local-only), `output` (Rich + JSON dual).
- **Domínio `paper`**: 7 subcomandos `prumo paper {sync, graph, find, lint,
  set-primary, sync-pdfs, sync-annotations}`. 6 vendor scripts migrados
  (paper_sync, cite_graph, cite_lookup, paper_extract, sync_zotero_pdfs,
  sync_zotero_annotations) sem mudança comportamental + `lint.py` novo.
- **Domínio `wiki`**: `prumo wiki {lint, index, stats}` — auditoria
  determinística (broken citekeys, orphan pages, missing frontmatter),
  reindex via subprocess `qmd`, contagem por tipo.
- **Domínio `capture`**: `prumo capture <input>` — router que classifica
  DOI/arXiv/PDF/URL/citekey e sugere próxima ação.
- **Domínio `write`**: `prumo write {export, compose, list-styles,
  extract-comments}` — TRANSFORM de `export_page.py` (single + multi-page
  Pandoc/Typst) e `extract_comments.py` (.docx → checklist Markdown).
- **`integrations/claude_code/`**: instala skills em `<pj>/.claude/skills/`
  com base na `SkillRegistry`. `BaseIntegration` abre caminho pra
  Cursor/Codex/Gemini sem mexer em `core/` ou `domains/`.
- **`templates/pj_base/`**: scaffold de novo `pj_*` sem vendor scripts
  (acabou o copy-pasta × N submodules).
- **Skill nova `peer-review`**: simula revisão crítica de drafts acadêmicos
  com mental models clínicos (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE).
- **API Python pública** (`from prumo_assist import api`): paridade com CLI
  pra notebooks Jupyter.
- **Schemas Pydantic versionados forward-only** (`PaperCallout/v1`).
- **Testes**: 97 unit + integration; ruff + mypy strict zerados.
- **CI** (GitHub Actions): matrix Python 3.11/3.12, ruff + mypy + pytest.
- **`ROADMAP.md`**: documento didático com princípios, layout, fluxo de dados,
  faseamento (PR0–3 MVP) e roadmap pós-MVP por trigger.
- **`CITATION.cff`**: prumo-assist citável academicamente.

### Em curso

- Plugin marketplace continua em v0.1.1 (skills + agents existentes
  preservados intactos). Bump pra v0.2.0 do plugin acontece quando o spin-off
  das skills de código (`tabular-eda`, `data-cleaning`, `clinical-metrics`)
  for confirmado pra `prumo-code-assist` (repo separado).

## [0.1.1] - 2026-04-26

### Adicionado
- `.claude-plugin/marketplace.json` — o repo agora é simultaneamente plugin e marketplace de 1 entry, permitindo `/plugin marketplace add raphaelfh/prumo-assist` direto.
- CI (`.github/workflows/validate-manifests.yml`) que valida `plugin.json` e `marketplace.json` contra JSON Schema em cada PR/push.
- Schemas explícitos em `.github/schemas/` (referência viva do que o Claude Code aceita).
- Este `CHANGELOG.md`.

### Corrigido
- `plugin.json#repository` passou de objeto `{type, url}` para string — formato que o validador do Claude Code aceita (rejeitava o anterior em `/plugin install`).
- README: link de instalação corrigido (`raphaelfh/prumo-assist`, não `claude-prumo-assist`) e comando atualizado para o formato qualificado `prumo-assist@prumo-assist`.

## [0.1.0] - 2026-04-22

### Adicionado
- Estrutura inicial do plugin extraída do monorepo `monorepo-anterior`.
- 8 skills: `tabular-eda`, `data-cleaning`, `clinical-metrics`, `paper-manager`, `paper-extract`, `wiki-ingest`, `wiki-query`, `wiki-lint`.
- 2 agents: `ml-theory-expert`, `stack-docs-researcher`.
- MCP `qmd` (busca BM25 + vector + rerank local no wiki).

[Não publicado]: https://github.com/raphaelfh/prumo-assist/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/raphaelfh/prumo-assist/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raphaelfh/prumo-assist/releases/tag/v0.1.0
