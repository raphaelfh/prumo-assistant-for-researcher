---
status: implemented
date: 2026-09-12
---

# Proveniência ligada — `_meta` canônico em todos os produtores

## Problema

O Princípio V exige `_meta` em todo artefato gerado, mas só `paper extract` carimbava (`build_meta` em `domains/paper/callout.py`). Findings gravavam `generator` solto no frontmatter; drafts do `write draft`, a sessão do `wiki study` e o export não carimbavam nada. `domains/write/disclosure.py` compensava lendo três sinais heterogêneos. `TraceWriter` existia sem nenhuma chamada.

## Inventário de produtores

| Produtor | Artefato | Gerado por agent/CLI? | Decisão |
|---|---|---|---|
| `paper/callout.apply_extraction` | `_meta.md` (frontmatter) | agent | já carimbava |
| `wiki/findings.archive_as_finding` | `notes/<slug>.md` | agent (`wiki query`/`study`) | **carimba** `_meta` (substitui `generator`) |
| `wiki/study.create_session_log` | `notes/session-*.md` | agent (`wiki study`) | **carimba** `_meta` |
| `write/compose.write_output` | draft em `writing/` ou `--into`/`--out` | agent (`write manuscript`/`section`) | **carimba** `_meta` no frontmatter |
| `write/export._emit_review_sidecars` | `reviews/<slug>/citemap.json` | CLI (export docx) | **carimba** `_meta` no sidecar |
| `paper/sync`, `paper/zotero`, `paper/migrate` | espelho do Zotero | determinístico, fonte externa | não carimba — a fonte é o Zotero |
| `paper/verify` (cache), `write/zettlr` (perfil) | cache/config | determinístico | não é artefato de pesquisa |
| `protocol/ops`, `protocol/picot_io` | `picot.toml`, blocos, ADRs | render do PICOT humano | já carrega hash do spec no bloco |
| `write/comments`, `write/review` | checklist, `events.yaml` | extração determinística do docx | já carrega `extracted_at`/eventos |

## Decisão

1. Cada produtor marcado chama `build_meta(...).to_dict()` e grava a chave `_meta` no frontmatter YAML (Markdown) ou no JSON (sidecar). A chave de frontmatter é machine-owned, o mesmo arranjo do `_meta.md` do extract; o corpo humano e as demais chaves são preservados. No `--into`, o bloco `<!-- write:begin -->` continua sendo a região do corpo que a máquina reescreve (ADR-0009), e o `_meta` vai no frontmatter.
2. `skill` usa o id `<skill>/<modo>` do registry: `wiki/query`/`wiki/study` (o `--generator` de sempre), `write/manuscript` (drafts/out), `write/section` (into). Sem flag nova; `model` fica ausente onde o CLI não o recebe.
3. `disclosure.collect_records` lê o `_meta` canônico primeiro. Fallback legado só para `extracted_model`/`extracted_at`. `human_reviewed` é o OU entre o frontmatter (flag humana) e o `_meta`.
4. `TraceWriter`, `is_trace_disabled` e seus testes saem (Princípio VI; ADR-0035).

## Contagem legada nos `pj_*` (leitura, 2026-09-12)

- `extracted_model:` no frontmatter: **126** arquivos em 7 projetos (67 `pj_piloto_revisao`, 30 `pj_piloto_questionario`, 25 `pj_piloto_imagem`, 1 em cada um de outros 4) → fallback mantido.
- `generator:` no frontmatter: **0** → leitura removida.
- `_meta:` canônico com `prumo_version`: **0**.

## Alternativas rejeitadas

- Helper genérico `stamp_frontmatter` em `core/` — só `write_output` recebe texto arbitrário; findings e study já montam o dict.
- Carimbar `_meta` como atributo do comentário `write:begin` — disclosure teria de ler corpo, e a regex de substituição de bloco quebraria.
- Carimbar metadados no docx/pdf via metadata do Pandoc — o writer docx achata mapas; o sidecar já é o par legível por máquina do export.
- Ligar `TraceWriter` agora — nenhum consumidor lê trace; seria código especulativo com payload de LLM em disco (ver "Safe outputs" no ROADMAP).

## Aceitação

- Teste por produtor afirmando `_meta` (findings, study, write_output nos 3 modos, citemap).
- Teste de disclosure sobre fixture mista canônica + legada.
- `TraceWriter` sem referências em `src/` e `tests/`.
