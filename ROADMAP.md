# Roadmap

> Status atual + próximas fases. Princípios e layout estão em [`ARCHITECTURE.md`](ARCHITECTURE.md). Histórico narrativo em [`CHANGELOG.md`](CHANGELOG.md).

## Status (atualizado 2026-05-03)

| PR  | Status      | Conteúdo |
|-----|-------------|----------|
| PR0 | ✅ entregue | Fundação `core/` + Typer + `prumo init/doctor/skills` + integration `claude_code` + templates |
| PR1 | ✅ entregue | Domínio `paper` completo (7 subcomandos, 6 scripts migrados + `lint.py` + schemas v1) |
| PR2 | ✅ entregue | Domínios `wiki`, `capture`, `write` (subcomandos por pilar) |
| PR3 | ✅ entregue | Skill `peer-review` + `CITATION.cff` + CHANGELOG + 97 testes |
| PR4 | ✅ entregue | Spin-off de skills de código + simplificação interna (CLI helper, paths, docs split) — v0.3.0 |
| PR5 | 📌 backlog | Pack `clinical-checklists` (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE) |
| PR6 | 📌 backlog | Multi-host (Cursor, Codex, Gemini, Jupyter integrations) |

## Em curso

- `prumo-code-assist` ainda **não existe**. As skills `tabular-eda`, `data-cleaning`, `clinical-metrics` foram removidas deste repo na v0.3.0; o conteúdo continua acessível via histórico git. Mover para `prumo-code-assist` quando o repo for criado.
- Agents `ml-theory-expert` e `stack-docs-researcher` mantidos provisoriamente. Reavaliar na próxima minor.

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

- **Sem hooks system.** Trace e provenance são chamadas explícitas em `domains/`, não decoradores plugáveis. Quando ≥3 cross-cutting forem competir, refatora.
- **Sem cache de LLM.** Idempotência por hash do input fica para quando algum caller real precisar.
- **Sem lockfile.** Faz sentido quando packs externos virarem realidade.
- **Sem multi-host.** Um adapter (`claude_code`) prova a interface; expandir é trivial depois (não é refactor, é adição).
- **Sem packs externos.** Único pack hoje é o implícito da raiz (`skills/` na raiz). Estrutura `packs/<name>/` está prevista mas vazia.
- **Sem MkDocs publicado.** Documentação vive no repo em Markdown. Site só quando `prumo --version` justificar (volume de usuários externos).
