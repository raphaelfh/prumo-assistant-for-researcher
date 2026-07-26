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

## Status do programa zero-friction (atualizado 2026-07-25)

> Este programa (guarda-chuva com 6 fases, F0–F5) fica fora da tabela de
> releases acima porque nenhuma fase saiu como versão própria ainda — tudo
> segue acumulado em `[Não publicado]` no CHANGELOG. Spec-guarda-chuva:
> [`docs/superpowers/specs/2026-07-22-zero-friction-onboarding-design.md`](docs/superpowers/specs/2026-07-22-zero-friction-onboarding-design.md).
> A Fase 3 executa um sub-programa próprio (fases 0–4 dele) especificado em
> [`docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md`](docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md).
> Planos arquivados em `docs/superpowers/plans/archive/`; ADR-0016 a ADR-0020
> (ADR-0015 é a política de release pré-1.0 que rege o bump de todas elas).

| Fase | Entrega | Status |
|------|---------|--------|
| F0 | Spike de validação empírica no Desktop/Cowork (sem código) | implementada, arquivada (verified 2026-07-24) |
| F1 | Export docx confiável (validação + retry + hard-fail) + `doctor` de versões Zotero/BBT | implementada, arquivada (verified 2026-07-23); release PATCH ainda pendente |
| F2 | Golden path Desktop/Cowork: preflight uniforme ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)), instalação guiada via skill `start`, docs em duas trilhas (`docs/onboarding-pesquisador.md`) | implementada, arquivada (verified 2026-07-25); piloto com 1 colega real **bateu o critério ≤15 min até o primeiro output**; release MINOR ainda pendente |
| F3 | Ponte docx↔CriticMarkup — sub-programa próprio de 5 fases (spike/adeu, substrato, review ingest/apply, MCP reconciliador, verificação de referências) | implementada, arquivada ([ADR-0016](docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md), [ADR-0017](docs/adr/adr-0017-prumo-mcp-reconciliador.md), [ADR-0018](docs/adr/adr-0018-verificacao-referencias-apis-publicas.md)) |
| F4 | Colapso de dependências, escopo A: `prumo paper connect <coleção>` liga o bib do projeto a uma coleção do Zotero via `autoexport.add` do BBT, com guardas anti-fantasma; qmd→MCPB avaliado e refutado (fallback lexical vira caminho normal documentado) | implementada e arquivada ([ADR-0020](docs/adr/adr-0020-connect-autoexport-bbt.md); plano em `docs/superpowers/plans/archive/2026-07-25-zero-friction-fase4-colapso-deps.md`) |
| F5 | Empacotamento do CLI Python pro Desktop (que não embute Python) | **encerrada fechada** — o trigger (colega travado apesar da instalação guiada) não disparou: o piloto da F2 passou sem travar (YAGNI aplicado, sem trabalho feito) |

## Em curso

- `prumo-code-assist` ainda **não existe**. As skills `tabular-eda`, `data-cleaning`, `clinical-metrics` (removidas na v0.3.0) seguem acessíveis via histórico git. Mover quando o repo for criado.
- Agents `ml-theory-expert` e `stack-docs-researcher`: decisão tomada em [ADR-0012](docs/adr/adr-0012-remocao-agents-ml.md) — remoção no v0.62.0.
- Zettlr como front humano (spec 2026-07-22): implementado na v0.62.1. `prumo write preview` fica **superado pelo Zettlr** para projetos novos — não construir sem novo trigger.

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
