---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-superficie-de-skills-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–6 implementadas em TDD: locators e validação por `PaperCallout/v1` no extract, `_meta` carimbado no `_meta.md`, `SupportReport/v1` e `PeerReviewReport/v1`, `prumo validate`, `agents/` no plugin, no wheel e em `.claude/agents/`, modos despachando `reader`/`verifier`/`reviewer` com fallback `general-purpose`, ADR-0033. Pendente: spike F0 (qual transporte roda no Desktop e no Cowork) e o corte do release. Verificação: suíte inteira verde exceto os 11 testes de `tests/unit/write/test_review_ingest.py` que dependem de `uvx` no PATH (falham igual no `main`); ruff, mypy, `gen_indexes --check`, `validate_manifests` e `sync_manifest_version --check` limpos.

# Superfície de skills — F2: três subagents com contratos verificáveis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `reader`, `verifier` e `reviewer` como subagents read-only com prompt canônico em `agents/<name>.md`, contratos Pydantic que o CLI valida, locators no extract, `verifier` lendo o PDF e proveniência carimbada no apply.

**Architecture:** Contratos novos em `domains/paper/schemas/v1.py` (`Locator`, `SupportVerdict`, `SupportReport`) e `domains/write/schemas/v1.py` (`PeerReviewReport`). `apply_extraction` valida o payload por `PaperCallout`, renderiza locators e grava `_meta` no `_meta.md`. `prumo validate <schema>` (registry em `src/prumo_assist/contracts.py`, topo do pacote, precedente ADR-0017) é o consumidor genérico dos contratos que não são persistidos. `agents/` vai no wheel e o installer copia para `.claude/agents/`. Os modos despacham o agent nomeado e, se o tipo não existir na sessão, `general-purpose` com o corpo do arquivo como prompt — o mesmo arquivo nos dois transportes, então F0 só mede qual deles roda no Cowork.

**Tech Stack:** Python 3.12, Pydantic v2, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-superficie-de-skills-design.md` (D3, D4 + Emendas).

## Global Constraints

- Nenhum agent tem `Write`, `Edit`, `MultiEdit` ou `NotebookEdit`; persistência só via `prumo`.
- Princípio IV: `locators` é campo novo opcional; extracts antigos seguem válidos; payload plano legado continua aceito.
- `_meta` carimbado não leva `human_reviewed` (não pode sombrear a flag humana do frontmatter).
- `core/` não importa `domains/`; `contracts.py` fica no topo do pacote.
- `skills/`, `templates/`, `agents/` force-included no wheel e resolvidos por `core/paths.py`.
- Release: PATCH (ADR-0015).

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/prumo_assist/domains/paper/schemas/v1.py` | `Locator`, `PaperCallout.locators`, `SupportVerdict`, `SupportReport` |
| `src/prumo_assist/domains/paper/callout.py` | `parse_extract_payload`, validação, render de locators, carimbo `_meta` |
| `src/prumo_assist/domains/paper/cli.py` | `extract` usa `parse_extract_payload` |
| `src/prumo_assist/domains/write/schemas/v1.py` | `PeerReviewReport/v1` e itens |
| `src/prumo_assist/contracts.py` + `cli.py` | registry de contratos e `prumo validate` |
| `agents/{reader,verifier,reviewer}.md` | prompts canônicos |
| `pyproject.toml`, `integrations/claude_code/installer.py` | wheel e instalação de `agents/` |
| `skills/paper/modes/{extract,support}.md`, `skills/review/modes/critique.md` | despacho e validação |
| `docs/adr/adr-0033-subagents-nomeados.md` | decisão estrutural |

### Task 1: Locators, validação e proveniência no extract
- [ ] Testes: `tests/unit/paper/test_schemas_v1.py` (novo), `tests/unit/paper/test_callout.py`, `tests/unit/paper/test_cli.py`, `tests/unit/write/test_disclosure.py` — seção fora do template e valor não-texto recusados sem gravar; locators renderizados (`p. N — "trecho"`); `_meta` com `skill: paper/extract`, `schema: PaperCallout/v1`, `model`, `input_hash`, sem `human_reviewed`; payload plano e `{"sections", "locators"}` aceitos; disclosure lê o `_meta` como `prumo-assist:paper extract` preservando `human_reviewed` do frontmatter; `SupportVerdict` exige `quote` quando `fully`/`partially`.
- [ ] Rodar → FAIL. Implementar. Rodar → PASS. Commit `feat(paper): locators, validação por PaperCallout e _meta no extract`.

### Task 2: `PeerReviewReport/v1`
- [ ] Teste em `tests/unit/write/test_schemas_v1.py`: `skills/review/examples/sample_report.json` valida; recomendação fora da lista é recusada.
- [ ] Implementar os modelos; commit `feat(write): PeerReviewReport/v1 como contrato Pydantic`.

### Task 3: `prumo validate <schema>`
- [ ] `tests/unit/test_contracts.py`: válido → exit 0 com `{"valid": true, "schema": ...}`; inválido → exit 1 com caminho do campo e instrução de correção; schema desconhecido → exit 1 listando os conhecidos; nome no registry == `schema_version` default do modelo.
- [ ] `contracts.py` com `CONTRACTS = {"PaperCallout/v1": PaperCallout, "SupportReport/v1": SupportReport, "PeerReviewReport/v1": PeerReviewReport}` e `validate_contract(name, payload) -> dict`; comando fino em `cli.py`. Commit.

### Task 4: `agents/` no plugin, no wheel e no projeto
- [ ] `tests/unit/test_agents.py`: cada `agents/*.md` tem `name` == arquivo, `description`, `tools` sem ferramenta de escrita; cada agent é citado por algum modo; `pyproject.toml` force-inclui `agents`. `tests/unit/integrations/test_claude_code_installer.py`: `install` copia `agents/*.md` para `.claude/agents/`.
- [ ] Criar os 3 agents, entrada no force-include, installer. Commit.

### Task 5: Modos despacham os agents
- [ ] `paper extract`: despacha `reader`, payload `{"sections", "locators"}`. `paper support`: `verifier` lê o PDF (locator só orienta), relatório validado com `prumo validate SupportReport/v1` (1 retry com o erro). `review critique`: `reviewer` recebe só caminho do draft e guideline; saída validada com `prumo validate PeerReviewReport/v1`.
- [ ] `gen_indexes`; testes de skills; commit.

### Task 6: ADR-0033, docs, verificação
- [ ] ADR-0033; ARCHITECTURE (`agents/`, `contracts.py`, `validate`); ROADMAP; CHANGELOG; emenda do spec (PeerReviewReport no lugar de CritiqueReport, `prumo validate`, installer de agents, transporte duplo sem esperar F0).
- [ ] `uv run pytest -q`, ruff, mypy, `gen_indexes --check`, `validate_manifests`; smoke `prumo init` → `.claude/agents/reader.md`; arquivar plano.
