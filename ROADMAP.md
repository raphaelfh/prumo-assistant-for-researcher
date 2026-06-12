# Roadmap

> Status atual + próximas fases. Layout em [`ARCHITECTURE.md`](ARCHITECTURE.md); princípios em [`docs/constitution.md`](docs/constitution.md); histórico narrativo em [`CHANGELOG.md`](CHANGELOG.md).

## Status (atualizado 2026-06-11)

| Release | Data | Conteúdo |
|---------|------|----------|
| 0.2.0 | 2026-04-28 | Fundação do CLI Python (core/ + Typer + domains paper/wiki/capture/write + peer-review + 97 testes) |
| 0.3.0 | 2026-05-03 | Spin-off das skills de código + simplificação interna + split ARCHITECTURE/ROADMAP |
| 0.4.0 | 2026-05-03 | Layout α de notas (`references/notes/<citekey>/`) + `paper migrate-layout` |
| 0.5.0 | 2026-05-04 | Domínio `protocol` (PICOT + ADRs) + família `write-*` + `formulate-picot` + `active-learning` |
| 0.6.0 | 2026-05-17 | Wizard interativo do `prumo init` |
| 0.61.0 | 2026-05-31 | Disclosure de IA, citações Word vivas (zotero_live_docx.lua), sync-notes/sync-all, doctor de deps externas, pj_base simplificado (módulos clinical/ml), wiki-lint determinístico, refresh de guidelines |
| — | 2026-06-11 | Reorganização do repo (CLAUDE.md, `docs/adr/`, lifecycle, índices gerados — não-releasável) |
| 0.62.0 | 2026-06-12 | Remoção agents ML (ADR-0012) + pdf-reader → Read (ADR-0013) + contratos de skill reconciliados (ADR-0014) |

## Em curso

- `prumo-code-assist` ainda **não existe**. As skills `tabular-eda`, `data-cleaning`, `clinical-metrics` (removidas na v0.3.0) seguem acessíveis via histórico git. Mover quando o repo for criado.
- Agents `ml-theory-expert` e `stack-docs-researcher`: decisão tomada em [ADR-0012](docs/adr/adr-0012-remocao-agents-ml.md) — remoção no v0.62.0.

## Fases pós-MVP (cada uma justificada por dor real, **nunca antes**)

| Fase | Adição | Trigger |
|------|--------|---------|
| 2.1  | Pack `clinical-checklists` (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE, SPIRIT) | Reportar resultados de modelo de predição |
| 2.2  | Pack `schematics` (CONSORT/PRISMA flow via Mermaid+TikZ) | Submissão de paper |
| 2.3  | Pack `venue-clinical` (NEJM, JAMA, Lancet, Nature Medicine, Radiology) | Submeter pra venue específico |
| 2.4  | Pack `thesis` (chapter-from-findings, snapshot, defense-summary) | Aproximação da defesa |
| 2.5  | `kg/` module (grafo de papers, paths de citação) | Wiki passar de 50+ papers |
| 3.0  | `integrations/{cursor,codex,gemini,jupyter}/` | Colega adotar host diferente |
| 3.1  | Hooks system (PII redaction, cost gates) | Houver ≥3 cross-cutting concerns |
| 3.2  | Eval gate em CI | Drift de prompt observado em prod |

## Decisões deliberadas postergadas

> Espelhadas em [ADR-0011](docs/adr/adr-0011-semver-por-visibilidade.md); promover qualquer item exige citar o trigger atingido.

- **Sem hooks system.** Trace e provenance são chamadas explícitas em `domains/`, não decoradores plugáveis. Quando ≥3 cross-cutting forem competir, refatora.
- **Sem cache de LLM.** Idempotência por hash do input fica para quando algum caller real precisar.
- **Sem lockfile.** Faz sentido quando packs externos virarem realidade.
- **Sem multi-host.** Um adapter (`claude_code`) prova a interface; expandir é trivial depois (não é refactor, é adição).
- **Sem packs externos.** Único pack hoje é o implícito da raiz (`skills/` na raiz). Estrutura `packs/<name>/` está prevista mas vazia.
- **Sem MkDocs publicado.** Documentação vive no repo em Markdown. Site só quando `prumo --version` justificar (volume de usuários externos).
- **Produto continua gerando `docs/decisions/`** nos `pj_*` enquanto o repo usa `docs/adr/` — alinhar na próxima mudança em `domains/protocol/adr.py` ([ADR-0001](docs/adr/adr-0001-adr-log-em-docs-adr.md)).
