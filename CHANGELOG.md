# Changelog

Todas as mudanças relevantes deste plugin.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/) — política de quando bumpar `MAJOR/MINOR/PATCH` em [`RELEASING.md`](RELEASING.md).

## [Não publicado]

### Mudado

- **`peer-review` e `write-statistics` adotam os guidelines de 2025**:
  TRIPOD-LLM (Nat Med, jan/2025), DECIDE-AI e CONSORT 2025 entram nos mental
  models; CONSORT-AI deixa de ser citado isolado do CONSORT 2025. Card de
  referência load-on-demand em
  `skills/peer-review/references/reporting-guidelines.md`.
- **`prumo write export --to docx` agora gera citações vivas do Zotero**
  editáveis pelo plugin do Word (campos `ADDIN ZOTERO_ITEM CSL_CITATION` +
  `ADDIN ZOTERO_BIBL CSL_BIBLIOGRAPHY`), em vez de texto plano renderizado
  por `--citeproc`. O pipeline docx agora chama Pandoc com
  `--lua-filter=zotero.lua --lua-filter=zotero_bibliography_docx.lua
  --metadata=zotero_csl_style:<style>` e abandona `--bibliography`/`--csl`
  (o filtro busca metadata direto do Zotero via JSON-RPC do Better BibTeX).
  Formatos `html`/`typst`/`pdf` continuam com `--citeproc` + CSL local.
  Pré-requisitos: Zotero + Better BibTeX rodando em `127.0.0.1:23119` e
  a janela principal do Zotero aberta com uma biblioteca selecionada na
  sidebar (limitação do `Serializer.serialize()` do BBT, que chama
  `getActiveZoteroPane()`). Para itens em grupos do Zotero, adicionar
  `zotero: {library: "<Nome do Grupo>"}` no frontmatter do `.md`.
- **Templates de escrita co-localizados nas skills `write-*`.** `templates/writing/{paper,projeto-cep,scientific,statistics}.md` agora vivem em `skills/write-<kind>/template.md`, alinhando com a recomendação atual de [Anthropic Agent Skills](https://code.claude.com/docs/en/skills) ("each skill is a directory with supporting files bundled inside"). O resolver `prumo_assist.domains.write.compose.resolve_template` foi atualizado e a wheel agora empacota também `skills/` em `prumo_assist/_skills/`. Override por projeto continua em `<pj>/.claude/writing_templates/<kind>.md`.
- **Frontmatter das 13 skills modernizado** para o spec atual:
  - `when_to_use` separado do `description` (gatilhos de invocação em campo próprio).
  - `allowed-tools` declarado por skill (pre-aprova ferramentas comuns sem prompt de permissão).
  - `argument-hint` para autocomplete do `/`.
  - Namespace `prumo:` padronizado em todas as skills (version, schema, determinism, agent_compat, cost_estimate, inputs).
- **`formulate-picot` enxugada** (247 → 159 linhas no SKILL.md). Operações 3 (`propagate`) e 4 (`diff`) migradas para `skills/formulate-picot/references/operations-advanced.md` — carregadas só quando o auto-detect aponta para esses modos.

### Adicionado

- **`prumo wiki lint` ganha 4 checks determinísticos** que antes custavam LLM na
  skill `wiki-lint`: prefixo de `_log.md` fora do padrão (`broken_log_prefix`),
  múltiplas notas `role: primary` (`multiple_primary`), links mortos em
  frontmatter `links_to`/`sources`/`related` (`dead_link`) e conceitos citados
  ≥3× sem página (`concept_candidate`, severity `info`). Contradições e stale
  claims permanecem agênticas (Princípio II). Nova severidade `info` não altera
  `ok`.
- **`prumo.guidelines_reviewed`** (frontmatter de skill) + aviso no
  `prumo doctor` quando os reporting guidelines de uma skill não são
  revisados há > 180 dias. Living guidelines (ex.: TRIPOD-LLM, revisado a cada
  ~3 meses) deixam de envelhecer em silêncio. `peer-review` e
  `write-statistics` já declaram o campo.
- **`prumo write disclosure`** — gera a declaração de uso de IA (PT/EN) a partir
  da proveniência dos artefatos (`extracted_model` em `_meta.md`, `generator` em
  findings, e blocos `_meta:` canônicos futuros), no formato exigido por
  periódicos (Elsevier, Springer Nature, Wiley, T&F, SAGE) e pelo EU AI Act.
  Schema `AIDisclosure/v1`.
- **`Meta.human_reviewed`** (provenance) — registra verificação humana; aditivo,
  Princípio IV. Findings agora gravam `generator` no frontmatter.
- **`prumo_assist/_filters/zotero.lua`** — filtro vendored do Better BibTeX
  ([upstream](https://retorque.re/zotero-better-bibtex/exporting/pandoc/),
  rev `199d652`, 54 KB). Atualizar com `curl -L https://raw.githubusercontent.com/retorquere/zotero-better-bibtex/master/site/content/exporting/zotero.lua -o src/prumo_assist/_filters/zotero.lua`.
- **`prumo_assist/_filters/zotero_bibliography_docx.lua`** — filtro
  companheiro que injeta o campo `ADDIN ZOTERO_BIBL` no docx onde houver
  `::: {#refs} :::`, fechando uma lacuna do upstream (que só emite o
  marcador de bibliografia para ODT). Sem isso, o usuário precisaria
  clicar manualmente "Add/Edit Bibliography" no Word a cada export.
- **`ZoteroNotRunningError` / `ZoteroCitekeyNotFoundError`** em
  `prumo_assist.domains.write.export` — promovem warnings silenciosos do
  filtro Lua a erros acionáveis com mensagens específicas para as três
  causas-raiz típicas (BBT offline, painel do Zotero inativo, citekey
  ausente da biblioteca ativa).
- **`tests/unit/write/test_export_pandoc_cmd.py`** — 17 testes cobrindo
  roteamento de formato em `_build_pandoc_cmd`, resolução dos filtros
  Lua vendored, e as três condições de erro detectadas por
  `_assert_no_missing_citekeys`.
- **`skills/formulate-picot/scripts/`** — 3 scripts Python testáveis substituem blocos `python3 -c '…'` inline:
  - `detect_mode.py` — auto-detect do modo (init/formalize/propagate/diff).
  - `init_picot.py` — lê PicotSpec JSON via stdin e grava `picot.toml` + propaga + cria ADR-0001.
  - `diff_and_adr.py` — gera ADR-N a partir de mudança estrutural já bumpada na TOML.
- **`skills/active-learning/scripts/`** — 5 scripts (`slug.py`, `create_log.py`, `append_step.py`, `archive_finding.py`, `finalize_session.py`) — substituem os blocos Python inline que rodavam helpers de `prumo_assist.domains.wiki.*`.
- **`skills/peer-review/examples/sample_report.json`** — exemplo concreto do schema `PeerReviewReport/v1` para guiar a saída.

## [0.6.0] - 2026-05-17

### Adicionado

- **`prumo init --merge`** — mescla o scaffold em diretório existente **sem sobrescrever** arquivos do usuário. Cria diretórios faltantes, copia apenas arquivos cujo destino não existe; preserva notebooks, dados, customizações de `CLAUDE.md`, etc. Mutuamente exclusivo com `--force`.
- **Wizard interativo Speckit-style em `prumo init`** — quando rodado sem argumento e em TTY, abre fluxo guiado:
  1. Banner Rich com versão e descrição
  2. Prompt do nome (validação de prefixo `srpj_`/`pj_` + `[a-z0-9_]` only)
  3. **Detecção automática** de diretório existente → oferece menu Merge / Force / Cancelar (com confirmação adicional para Force)
  4. Seleção numerada de integrações
  5. `git init` opcional (apenas em modo new)
  6. Próximos passos contextualizados ao modo (new/merge/force)
- **`prumo init --yes` / `-y`** — modo não-interativo para CI: aceita defaults e pula o wizard mesmo em TTY.
- **`prumo init --git` / `--no-git`** — controla `git init` no modo não-interativo (default `--git`).
- **`prumo init -f`** — alias curto de `--force`; **`prumo init -m`** — alias de `--merge`.
- **Validação de nome do projeto** — rejeita prefixos inválidos (deve começar com `srpj_` ou `pj_`) e caracteres fora de `[a-z0-9_]`; mensagens de erro acionáveis.
- **Output JSON enriquecido em `prumo init --json`**: agora inclui `mode` (`new`/`merge`/`force`), `files_copied`, `files_skipped`, `git_initialized` — útil para pipelines CI/CD que parseiam o resultado.

### Mudado

- **`prumo init <project>` (sem flags) agora aceita diretórios vazios** (ou só com `.DS_Store`/`Thumbs.db`) como destino válido, evitando o erro "já existe" em casos comuns como `mkdir srpj_x && cd srpj_x && prumo init .`.
- A mensagem de erro de "diretório já existe com conteúdo" agora **sugere as flags `--merge` e `--force`** com o trade-off de cada uma.
- Argumento `project` agora é **opcional** (default `None`) para habilitar o wizard interativo.

### Anteriormente em [Não publicado] — promovido a 0.6.0

- **`docs/templates/` no scaffold `pj_base/`** — diretório com 5 modelos administrativos prontos para uso em qualquer estudo observacional em saúde, copiados na criação do projeto via `prumo init`:
  - `Template submissão Plataforma Brasil.docx` — layout oficial do CEP/CONEP, usado como `--reference-doc` do `pandoc` para gerar o `.docx` final de submissão.
  - `projeto-cep.md` — esqueleto Markdown da submissão CEP (alinhado com Resolução CNS 466/2012 e CONEP 580/2018).
  - `data_dictionary_skeleton.md` — esqueleto Markdown do dicionário em **duas camadas** (extração fornecedor→nós + engineered features ancoradas em `[[citekey]]`).
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
