# Clinical Reporting-Guideline Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the 2025-era clinical reporting guidelines — **TRIPOD-LLM** (Nat Med, Jan 2025), **DECIDE-AI**, and **CONSORT 2025** — to the mental models of `peer-review` and `write-statistics`, so the project stops recommending superseded checklists.

**Architecture:** Content-only change to two `SKILL.md` files plus a co-located reference card. No runtime Python. Because skills are prose, the only automated safety net is a **regression guard test** that reads the `SKILL.md` files and asserts the new guideline names are present — this prevents a future edit from silently dropping them.

**Tech Stack:** Markdown (SKILL.md), pytest (guard test), `ruff`/`mypy` unaffected.

---

## Why (context for the engineer)

These guidelines are current as of 2026 and the project predates them:

- **TRIPOD-LLM** — Nature Medicine, Jan 2025. Extension of TRIPOD+AI for studies developing/evaluating LLMs in healthcare. 19 main items / 50 subitems, modular by task. A *living* guideline (expert panel revises every 3 months). Emphasizes hallucinations, transparency, human oversight, reproducibility. This is the single most relevant guideline for this project's own use case (it produces LLM-generated artifacts), and it is currently **absent** from every skill.
- **DECIDE-AI** — reporting guideline for *early-stage* clinical evaluation of AI decision-support systems (27 items). Fills the "first-in-human / small-scale live eval" stage that TRIPOD+AI (model development) and CONSORT-AI (full RCT) don't cover.
- **CONSORT 2025** — supersedes CONSORT 2010; 30-item checklist, new **open-science** section, several CONSORT-AI items integrated.

Verified current state (`grep -rn` across `skills/`): `peer-review/SKILL.md` lists `TRIPOD+AI / CLAIM / CONSORT-AI / PRISMA / STROBE` (lines 3, 54-60, 107). `write-statistics/SKILL.md` says `TRIPOD+AI / SPIRIT-AI compatível` (lines 3, 28). Neither names TRIPOD-LLM, DECIDE-AI, or CONSORT 2025.

## Files

- Modify `skills/peer-review/SKILL.md` — add the three guidelines to the genre→model map, the `mental_model_applied` enum, and the `--venue` note.
- Modify `skills/write-statistics/SKILL.md` — note TRIPOD-LLM applicability + CONSORT 2025 / DECIDE-AI in the reporting line.
- Create `skills/peer-review/references/reporting-guidelines.md` — load-on-demand reference card (one block per guideline; keeps `SKILL.md` lean per the project's load-on-demand convention).
- Create `tests/unit/test_guidelines_present.py` — regression guard.

---

### Task 1: Regression guard test (write first — it must fail)

**Files:** Create `tests/unit/test_guidelines_present.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_guidelines_present.py`:

```python
"""Guard: as skills clínicas devem nomear os guidelines de reporting atuais.

Conteúdo de skill é prose; este teste impede que uma edição futura derrube
silenciosamente TRIPOD-LLM / DECIDE-AI / CONSORT 2025.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[2] / "skills"


def _read(rel: str) -> str:
    return (_SKILLS / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("guideline", ["TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025"])
def test_peer_review_names_current_guidelines(guideline: str) -> None:
    assert guideline in _read("peer-review/SKILL.md")


def test_peer_review_reference_card_exists_and_covers_all() -> None:
    card = _read("peer-review/references/reporting-guidelines.md")
    for g in ("TRIPOD-LLM", "DECIDE-AI", "CONSORT 2025", "TRIPOD+AI", "CLAIM", "STROBE"):
        assert g in card


def test_write_statistics_mentions_tripod_llm_and_consort2025() -> None:
    text = _read("write-statistics/SKILL.md")
    assert "TRIPOD-LLM" in text
    assert "CONSORT 2025" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_guidelines_present.py -v`
Expected: FAIL — guideline strings absent; reference card file missing (`FileNotFoundError`).

- [ ] **Step 3: (no code yet — guard precedes content)**

This task only adds the failing guard. Content tasks below make it pass.

- [ ] **Step 4: Commit the guard**

```bash
git add tests/unit/test_guidelines_present.py
git commit -m "test: guard presence of current clinical reporting guidelines"
```

---

### Task 2: Reference card (load-on-demand)

**Files:** Create `skills/peer-review/references/reporting-guidelines.md`

- [ ] **Step 1: Create the file**

Create `skills/peer-review/references/reporting-guidelines.md`:

```markdown
# Reporting guidelines — mental-model reference

Carregado sob demanda pela skill `peer-review`. Use como _mental model_ para
identificar lacunas; não cite a checklist no review final salvo se útil.
Mapear o gênero do draft → guideline(s):

| Gênero do draft | Guideline(s) |
|---|---|
| Modelo de predição (regressão ou ML) | **TRIPOD+AI** (2024) |
| Estudo que desenvolve/avalia um **LLM** em saúde | **TRIPOD-LLM** (Nat Med, jan/2025) |
| Avaliação clínica **precoce** de sistema de apoio à decisão por IA | **DECIDE-AI** |
| RCT (geral) | **CONSORT 2025** |
| RCT com IA no pipeline | **CONSORT 2025** + **CONSORT-AI** |
| Protocolo de ensaio com IA | **SPIRIT-AI** |
| Imaging AI | **CLAIM / MI-CLAIM** |
| Revisão sistemática | **PRISMA 2020** |
| Estudo observacional | **STROBE** |

## TRIPOD-LLM (Nature Medicine, jan/2025)

Extensão do TRIPOD+AI para estudos que desenvolvem ou avaliam LLMs em saúde.
19 itens principais / 50 subitens; formato modular por tarefa de LLM.
Guideline **viva** (painel revisa a cada ~3 meses). Foco: alucinações,
omissões, confiabilidade, explicabilidade, **reprodutibilidade**, privacy,
viés downstream, e **supervisão humana**. Checklist interativa:
https://tripod-llm.vercel.app/ . Ao revisar um paper que usa LLM, cobrar:
modelo + versão + data de acesso, prompts/temperatura, estratégia de
avaliação task-specific, e a etapa de verificação humana.

## DECIDE-AI

Reporting da avaliação clínica **precoce** (small-scale, live) de sistemas de
apoio à decisão baseados em IA — o estágio entre desenvolvimento do modelo
(TRIPOD+AI) e o RCT completo (CONSORT-AI). 27 itens; ênfase em fatores
humanos, segurança, e desempenho em uso real.

## CONSORT 2025

Atualiza o CONSORT 2010 (não usar mais o 2010). 30 itens + diagrama de fluxo;
adiciona uma seção de **open science** e integra itens de extensões. Para
RCTs com componente de IA, combinar com CONSORT-AI.

## Demais (inalterados)

- **TRIPOD+AI** (2024) — modelos de predição (regressão/ML), 27 itens.
- **SPIRIT-AI** — protocolo de ensaio clínico com IA.
- **CLAIM / MI-CLAIM** — imaging AI.
- **PRISMA 2020** — revisões sistemáticas.
- **STROBE** — estudos observacionais.
```

- [ ] **Step 2: Run the guard (reference-card test should pass now)**

Run: `uv run pytest tests/unit/test_guidelines_present.py -k reference_card -v`
Expected: PASS for `test_peer_review_reference_card_exists_and_covers_all`.

- [ ] **Step 3: Commit**

```bash
git add skills/peer-review/references/reporting-guidelines.md
git commit -m "docs(peer-review): add reporting-guidelines reference card"
```

---

### Task 3: Update `peer-review/SKILL.md`

**Files:** Modify `skills/peer-review/SKILL.md`

- [ ] **Step 1: Update the description (line 3)**

Replace the `description:` value so its parenthetical reads:

```
(TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE)
```

i.e. change the existing `(TRIPOD+AI / CLAIM / CONSORT-AI / PRISMA / STROBE).` to
`(TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE).`

- [ ] **Step 2: Update the genre→model map (the bullet list at lines 54-60)**

Replace that bullet block with:

```markdown
- **Paper de modelo de predição** → aplicar mental model TRIPOD+AI.
- **Paper que desenvolve/avalia um LLM em saúde** → aplicar TRIPOD-LLM
  (Nat Med 2025; living guideline).
- **Avaliação clínica precoce de IA de apoio à decisão** → aplicar DECIDE-AI.
- **Paper de imaging AI** → aplicar mental model CLAIM/MI-CLAIM.
- **RCT** → CONSORT 2025 (e CONSORT-AI se houver IA no pipeline).
- **Revisão sistemática** → PRISMA.
- **Estudo observacional** → STROBE.
- **Capítulo de tese** → estrutura de argumento + clareza pra banca.
- **Grant/proposta** → alinhamento problema-método-impacto.

> Detalhamento de cada guideline (quando carregar): ver
> [`references/reporting-guidelines.md`](references/reporting-guidelines.md).
```

- [ ] **Step 3: Update the `mental_model_applied` enum in the JSON shape (line 107)**

Replace that line with:

```
  "mental_model_applied": "TRIPOD+AI | TRIPOD-LLM | DECIDE-AI | CLAIM | CONSORT 2025 | CONSORT-AI | PRISMA | STROBE | thesis-defense | grant-impact | none"
```

- [ ] **Step 4: Run the guard**

Run: `uv run pytest tests/unit/test_guidelines_present.py -v`
Expected: PASS for all `test_peer_review_*`.

- [ ] **Step 5: Commit**

```bash
git add skills/peer-review/SKILL.md
git commit -m "feat(peer-review): adopt TRIPOD-LLM, DECIDE-AI, CONSORT 2025"
```

---

### Task 4: Update `write-statistics/SKILL.md`

**Files:** Modify `skills/write-statistics/SKILL.md`

- [ ] **Step 1: Update the description (line 3)**

Change the trailing `TRIPOD+AI/SPIRIT-AI compatível.` to:

```
TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho.
```

- [ ] **Step 2: Update the body line (line 28)**

Change `Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível).` to:

```markdown
Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível). Se o estudo desenvolve ou
avalia um LLM, reporte também conforme **TRIPOD-LLM** (Nat Med 2025). Para o
desenho de ensaio, alinhe o reporting a **CONSORT 2025** (RCT) ou **DECIDE-AI**
(avaliação clínica precoce de IA).
```

- [ ] **Step 3: Run the guard + skill-parse sanity**

Run: `uv run pytest tests/unit/test_guidelines_present.py tests/unit/core/test_skills.py -v`
Expected: PASS (guard green; the skills parser still reads both frontmatters fine — content edits don't touch frontmatter).

- [ ] **Step 4: Commit**

```bash
git add skills/write-statistics/SKILL.md
git commit -m "feat(write-statistics): reference TRIPOD-LLM/CONSORT 2025/DECIDE-AI"
```

---

### Task 5: Bump skill versions + changelog

**Files:** Modify `skills/peer-review/SKILL.md`, `skills/write-statistics/SKILL.md`, `CHANGELOG.md`

- [ ] **Step 1: Bump `prumo.version`**

In each of the two `SKILL.md` frontmatters, change `version: 1.0.0` to `version: 1.1.0` (content of the mental models changed — a minor bump is honest).

- [ ] **Step 2: Changelog** — under `## [Não publicado]` → `### Mudado` add:

```markdown
- **`peer-review` e `write-statistics` adotam os guidelines de 2025**:
  TRIPOD-LLM (Nat Med, jan/2025), DECIDE-AI e CONSORT 2025 entram nos mental
  models; CONSORT-AI deixa de ser citado isolado do CONSORT 2025. Card de
  referência load-on-demand em
  `skills/peer-review/references/reporting-guidelines.md`.
```

- [ ] **Step 3: Run full gate**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: green (mypy unaffected — no Python changed beyond the guard test, which is annotated).

- [ ] **Step 4: Commit**

```bash
git add skills/peer-review/SKILL.md skills/write-statistics/SKILL.md CHANGELOG.md
git commit -m "chore(skills): bump versions + changelog for guideline refresh"
```

---

## Self-Review

- **Spec coverage:** "TRIPOD-LLM + DECIDE-AI + CONSORT 2025 no peer-review/write-statistics" — peer-review (Tasks 2-3), write-statistics (Task 4), guarded (Task 1). ✅
- **Placeholders:** none — full file content and exact string replacements given. ✅
- **Consistency:** the three guideline strings asserted by the guard (`"TRIPOD-LLM"`, `"DECIDE-AI"`, `"CONSORT 2025"`) appear verbatim in Tasks 2-4. The guard reads `skills/` via `parents[2]` from `tests/unit/test_guidelines_present.py` → repo root; verified `skills/` is at repo root. ✅
- **Note:** `CONSORT-AI` (older string) intentionally remains *alongside* `CONSORT 2025` for the AI-pipeline RCT case; the guard only requires the new strings to be present, not the old ones removed.
