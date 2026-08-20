---
title: Skill `/prumo-assist:active-learning` — tutor metacognitivo Socrático
date: 2026-05-03
status: approved
tags: [skill, active-learning, study, wiki]
---

# Skill `/prumo-assist:active-learning`

## Resumo executivo

Skill agêntica que conduz o pesquisador por uma **sessão de estudo Socrática estruturada em 5 steps** sobre um tópico específico, ancorada nas fontes do projeto (wiki + acervo bibliográfico). MVP foca em sessão **ad-hoc on-demand** (5–25 min, sem agendamento ou repetição espaçada). Cada sessão produz log estruturado em `docs/wiki/study-sessions/<topic>-<date>.md`. No último step (`Reflect`), skill oferece arquivar insight como finding canônico em `docs/wiki/findings/`. Citação **strict**: só citekeys do acervo; claim sem fonte vira `[REF FALTANTE: ...]`.

## Contexto e problema

Hoje quando o pesquisador quer aprender um conceito ancorado nas próprias fontes, ele:

- Abre `wiki-query` ou Claude direto, faz perguntas Q&A → recebe respostas one-shot
- Não há loop pedagógico (sem ativa recall, sem elaboração, sem reflexão)
- Não há trace persistente do que foi estudado
- ChatGPT genérico aluciona referências e não conhece as fontes do projeto

**Falhas observadas no canvas `journey.canvas`** (Fase 2 · EVIDÊNCIA Study and Develop, sub-precisa "Pergunta usando Claude para aprender com fontes internas + citação"):

> "Aprendizado otimizado:
> 1. Metodologia ativa
> 2. Repetição
> 3. Gamificação"

`wiki-query` é retrieval one-shot — não satisfaz nenhum dos três. Esta skill resolve **(1) metodologia ativa**; (2) e (3) ficam fora do MVP (triggers explícitos pra ativar).

## Decisões arquiteturais

### D1 — MVP: sessão ad-hoc, sem state cross-sessão

Cada `/active-learning <topic>` é uma sessão independente. Sem agendamento, sem repetição espaçada, sem multi-session-per-topic. Razão: complexidade de spaced repetition (algoritmo de intervalo, cron trigger, estado de "quando próxima revisão") explode o MVP. Sessão ad-hoc destrava o valor imediato (Claude como tutor agora) com complexidade contida.

Triggers concretos pra evoluir (em §10):
- Usuário pedir "revisar X que estudei semana passada" ≥3×/mês → adicionar spaced repetition
- Mesmo tópico re-estudado ≥3× em 3 meses → modo `--cumulative`
- Pedir "como estou progredindo em X?" → adicionar `prumo wiki study-stats`

### D2 — Método pedagógico: estrutura fixa em 5 steps

Toda sessão segue:

1. **Recall** — "De memória, defina `<topic>` em 2-3 frases."
2. **Anchor** — "Onde no acervo ancora cada parte? Qual paper/página sustenta?"
3. **Connect** — "Como `<topic>` se relaciona com `<conceito-vizinho>` (escolhido do graph)?"
4. **Apply** — "Cenário Z (derivado do PicotSpec do projeto, ou hipotético plausível) — como `<topic>` se comporta?"
5. **Reflect** — "O que ainda está confuso? Quer arquivar insight como finding?"

Razão: cobre **ativa recall** (1+4), **elaboração** (3), **ancoragem** (2 — alinha com strict citation), **metacognição** (5). Pedagogia testada (active learning meta-analysis literature). Estrutura previsível faz log auditável e re-leitura útil semanas depois.

Não-recomendados (descartados):
- Socrático puro adaptativo: log fica menos comparável; pedagogicamente menos robusto
- User-directed `--method=...`: força decisão a cada uso; usuário não sabe qual escolher
- Adaptativo via Claude judgment: ambicioso; risco de divergir

### D3 — Output: log + arquivamento opcional como finding (mesmo padrão wiki-query)

Sessão produz `docs/wiki/study-sessions/<topic-slug>-<YYYY-MM-DD>.md` (ou fallback `docs/study-sessions/...` se módulo `extended-wiki` não ativo). No step `Reflect`, skill oferece **uma vez** arquivar insight consolidado como `docs/wiki/findings/<slug>.md` (mesmo padrão do `wiki-query`).

Razão: composável com pattern existente; logs isolados ficam disponíveis pra auditoria; insights de valor explicito viram findings canônicos referenciados no `_index.md` e `_log.md`.

### D4 — Citação strict (mesmo padrão write-* family)

Skill **só** cita `[[@citekey]]` que existe em `references/_references.bib`. Quando feedback precisa de fonte fora do acervo, emite `[REF FALTANTE: <descrição curta>]`. **Skill nunca** inventa citation ou se sustenta em conhecimento próprio sem fonte do projeto.

Se acervo está fraco (>50% das respostas exigem `[REF FALTANTE]`), skill avisa explicitamente:

> "Acervo insuficiente para sessão proveitosa sobre `<topic>`. Sugiro `prumo paper find` + `paper-extract` em N papers antes de re-tentar."

Razão: princípio constitution §V (Provenance em todo output) + risco de aluciar referências (problema crítico em ChatGPT genérico que essa skill resolve).

### D5 — Helper Python em `domains/wiki/`, com refator DRY

Adicionar:
- `src/prumo_assist/domains/wiki/schemas/v1.py` — `SessionLog/v1` Pydantic
- `src/prumo_assist/domains/wiki/study.py` — helpers de log (create / append_step / finalize)
- `src/prumo_assist/domains/wiki/findings.py` — `archive_as_finding` extraído de inline-no-SKILL do `wiki-query` e tornado reutilizável

A skill `wiki-query` SKILL.md atualiza pra chamar `archive_as_finding` Python helper (refactor sem mudança comportamental). Razão: princípio "lógica em um lugar só" — evita drift entre `wiki-query` e `active-learning` na geração de findings.

## Arquitetura

### Componentes

```
src/prumo_assist/
└── domains/
    └── wiki/                                    # já existe
        ├── api.py                               # MODIFY: re-export study + findings
        ├── findings.py                          # NEW: archive_as_finding (extraído do wiki-query)
        ├── study.py                             # NEW: SessionLog helpers
        └── schemas/
            ├── __init__.py                      # NEW
            └── v1.py                            # NEW: SessionLog/v1

skills/
├── active-learning/SKILL.md                     # NEW (~120 linhas)
└── wiki-query/SKILL.md                          # MODIFY: chamar findings.archive_as_finding
```

Não cria domínio novo; aproveita `domains/wiki/` (escopo natural).

### Fluxo de uma sessão

```
1. /prumo-assist:active-learning curvas-roc-prediction

2. Skill resolve topic:
   - Se passado, usa diretamente
   - Senão, pergunta "Qual tópico?" (1 prompt)

3. Context gathering:
   - mcp__qmd__query "<topic>"  ou wiki-query
   - prumo paper find "<topic>"
   - Read docs/_index.md
   - Top 5-8 fontes mais relevantes (lista mostrada ao usuário)
   - Se >8 candidates, oferece filtrar (1 rodada)

4. Confirmar contexto:
   "Vou usar: [fontes]. Pronto pra começar?"

5. Skill cria session log skeleton:
   docs/wiki/study-sessions/curvas-roc-prediction-2026-05-03.md
   (YAML frontmatter + sources_consulted; corpo vazio)

6. Loop dos 5 steps:
   Para cada step ∈ [Recall, Anchor, Connect, Apply, Reflect]:
     a. Skill formula pergunta usando context + previous answers
     b. Aguarda user response
     c. Skill avalia resposta com citation strict do acervo;
        emite [REF FALTANTE] se necessário
     d. Skill chama study.append_step(...) → log atualiza com
        (pergunta, resposta, feedback, citations)

7. Reflect step inclui oferta de arquivamento:
   "Quer arquivar insight como finding em docs/wiki/findings/<slug>.md?"
   Se sim: chama findings.archive_as_finding(...)
            (cria finding, atualiza _index.md e _log.md)

8. Skill chama study.finalize_session(...):
   - duration_minutes = elapsed
   - status = completed | abandoned | partial
   - references_missing = [REF FALTANTE] capturados
   - finding_archived = path | None

9. Reporta ao usuário:
   - log path
   - citations usadas
   - references_missing (sugerir ingest)
   - finding_archived (se aplicável)
```

### Schema `SessionLog/v1`

`src/prumo_assist/domains/wiki/schemas/v1.py`:

```python
from datetime import date as _date
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


class StepLog(BaseModel):
    """Log de 1 dos 5 steps da sessão."""

    step_name: Literal["recall", "anchor", "connect", "apply", "reflect"]
    question: str
    answer: str
    feedback: str
    citations: list[str] = []           # citekeys efetivamente usados
    references_missing: list[str] = []  # [REF FALTANTE] no feedback


class SessionLog(BaseModel):
    """Log canônico de uma sessão de active-learning."""

    schema_version: Literal["SessionLog/v1"] = "SessionLog/v1"
    topic: str                           # slug
    date: str                            # ISO YYYY-MM-DD
    duration_minutes: int = 0
    status: Literal["in-progress", "completed", "abandoned", "partial"] = "in-progress"
    sources_consulted: list[str] = []    # paths/wikilinks
    steps: list[StepLog] = []
    references_missing: list[str] = []   # agregado de todos os steps
    finding_archived: Path | None = None
```

### API Python (`domains/wiki/study.py`)

```python
from pathlib import Path
from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog


def session_log_path(pj_path: Path, topic: str, date: str) -> Path:
    """Resolve docs/wiki/study-sessions/<slug>-<date>.md ou fallback."""
    extended = pj_path / "docs" / "wiki" / "study-sessions"
    if extended.parent.exists():
        extended.mkdir(parents=True, exist_ok=True)
        return extended / f"{topic}-{date}.md"
    fallback = pj_path / "docs" / "study-sessions"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / f"{topic}-{date}.md"


def create_session_log(
    pj_path: Path,
    topic: str,
    date: str,
    sources_consulted: list[str],
) -> Path:
    """Cria arquivo com YAML frontmatter; corpo só com cabeçalho de seção."""
    log = SessionLog(
        topic=topic,
        date=date,
        sources_consulted=sources_consulted,
    )
    path = session_log_path(pj_path, topic, date)
    path.write_text(_render_log_skeleton(log), encoding="utf-8")
    return path


def append_step(log_path: Path, step: StepLog) -> None:
    """Anexa seção '## N. <step_name>' ao log com pergunta/resposta/feedback/citations."""
    ...


def finalize_session(
    log_path: Path,
    duration_minutes: int,
    status: Literal["completed", "abandoned", "partial"],
    references_missing: list[str],
    finding_archived: Path | None,
) -> None:
    """Atualiza YAML frontmatter com fechamento da sessão."""
    ...


def _render_log_skeleton(log: SessionLog) -> str:
    """YAML frontmatter + heading + bullet list de sources_consulted."""
    ...
```

### API Python (`domains/wiki/findings.py`)

Extraído da prose-only do `wiki-query` SKILL.md:

```python
from pathlib import Path


def archive_as_finding(
    pj_path: Path,
    slug: str,
    title: str,
    body: str,
    sources: list[str],
    tags: list[str] | None = None,
    date: str | None = None,
) -> Path:
    """Cria docs/wiki/findings/<slug>.md (ou fallback docs/findings/...) com YAML.

    YAML inclui: id, type=finding, title, added, status=active, tags, sources.
    Body recebe seções: ## Pergunta, ## Resposta consolidada, ## Evidências,
    ## Limitações.

    Após criar, anexa:
    - docs/_index.md § Findings (linha com wikilink)
    - docs/_log.md (entry com data + tipo do gerador)

    Retorna path do finding criado.
    """
    ...
```

`wiki-query` SKILL.md (modificada minimamente) chama esta função via `Bash + python3 -c` ao invés de inline file writes. Mudança backward-compatible (mesmo output).

### Slug do tópico

- `--topic <slug>` (ou positional arg `<topic>`) — preferido
- Se omitido, skill pergunta uma vez no início ("Qual tópico vamos estudar?")
- Slug normalizado via `core/note_paths.slugify` (já existe; ASCII kebab ≤30 chars)

## Casos de borda

| Caso | Comportamento |
|---|---|
| Tópico passado tem caracteres especiais | Slugify normaliza; skill confirma slug normalizado antes de criar log |
| Acervo vazio (sem `_references.bib` válido) | Skill avisa; segue sessão mas todas citations viram `[REF FALTANTE]` |
| `>50% [REF FALTANTE]` na sessão | Skill aborta o step atual com warning + sugestão de ingest; oferece continuar mesmo assim |
| Usuário abandona sessão no meio (não responde um step) | Status = `partial`; finalize_session captura quantos steps completados |
| Mesma session log path já existe (mesmo topic + mesmo dia) | Skill avisa; pergunta se sobrescreve ou cria com sufixo `-2` |
| `extended-wiki` module não ativo | Fallback automático pra `docs/study-sessions/` (sem `wiki/`) |
| `docs/_index.md` ausente | `archive_as_finding` cria seção `## Findings` no fim do `_index.md` se ausente; ou cria `_index.md` mínimo |
| Tópico ambíguo (matches múltiplos itens no wiki) | Skill mostra candidates + pede refinamento (1 rodada) |

## Fora do escopo (deliberado)

- **Spaced repetition / scheduling** — sem state cross-sessão; cada `/active-learning <topic>` é isolada. Trigger pra adicionar: usuário pedir "revisar o que estudei semana passada" ≥3×/mês.
- **Gamificação** (pontos, streaks, badges) — sem repetição não há fluxo natural. Trigger: usuário pedir explicitamente.
- **Multi-sessão por tópico** (cumulative log) — cada sessão é independente. Trigger: re-estudar mesmo tópico ≥3× em 3 meses.
- **Avaliação automática rigorosa** (skill testar correctness via cálculo) — feedback é qualitativo + ancorado em citation, não auto-grading.
- **Sessão multi-topic** (estudar A e B juntos) — força foco em 1 topic; multi = múltiplas sessões.
- **Modo offline / sem qmd** — skill ainda funciona via `Grep` + `Read` (mesmo fallback do `wiki-query`), mas cobertura semântica reduz.
- **Adaptação de método pedagógico** (Socrático puro vs Feynman vs adaptativo) — fixed 5-step structure no MVP. Trigger pra adicionar: usuário pedir flag `--method=...` explicitamente.
- **Integração com calendar/cron** — sessão é manual on-demand.
- **Modo guided pra leitura colaborativa de paper específico** (`/active-learning --paper @key`) — interessante mas extensão; trigger separado.

## Quando re-avaliar (triggers concretos)

| Trigger | Resposta |
|---|---|
| "revisar X que estudei semana passada" ≥3×/mês | Adicionar `study-sessions` index + spaced repetition (intervalo configurável) |
| Mesmo tópico re-estudado ≥3× em 3 meses | Adicionar `--cumulative` mode; agrega sessões em note crescente |
| "como estou progredindo em X?" | Adicionar `prumo wiki study-stats` (lista sessões por tópico, status, gaps) |
| Acervo fraco (>50% `[REF FALTANTE]` em sessões frequentes) | Skill já avisa; revisitar workflow de ingest; talvez sugerir RSL automatizada |
| Sessões de >30 min frequentes | Adicionar suporte a sessão multi-step assincrona (pause + resume) |
| Multiple users colaborando no mesmo `pj_*` | State per-user; nome no log + acl |

## Plano de implementação (alto nível, 4 PRs)

1. **PR-A1 — Refator DRY**: extrair `archive_as_finding` de `wiki-query` SKILL.md (prose inline) pra `domains/wiki/findings.py` (Python helper). Atualizar `wiki-query` SKILL.md pra chamar via Bash. Tests com fixtures de wiki vazio + populado. Sem mudança comportamental observável pelo usuário.

2. **PR-A2 — Schemas + study helpers**: `domains/wiki/schemas/v1.py` (`SessionLog/v1`, `StepLog`) + `domains/wiki/study.py` (`session_log_path`, `create_session_log`, `append_step`, `finalize_session`). Tests round-trip do log markdown.

3. **PR-A3 — `skills/active-learning/SKILL.md`** (~120 linhas). Prompt do agente Socrático com 5 steps detalhados + context gathering + reflect+archive offer. Manual smoke test em projeto real.

4. **PR-A4 — Docs**: README skills table (adiciona linha `active-learning`), `docs/actions-by-context.md` (atualiza gatilho "Quero estudar conceito X usando minhas próprias fontes" — já existe placeholder, materializar), `docs/Research Project Structure.md` (mention).

Cada PR independente; PR-A1 destrava DRY pro PR-A2/A3.

## Referências

- `docs/canvas/journey.canvas` (removido do repo; conteúdo na tag `v0.65.0`) — Fase 2 EVIDÊNCIA (Study and Develop), sub-precisa "Pergunta usando Claude para aprender com fontes internas + citação"
- [`docs/actions-by-context.md`](../../actions-by-context.md) — gatilho "Quero estudar conceito X usando minhas próprias fontes"
- [`skills/wiki-query/SKILL.md`](../../../skills/wiki-query/SKILL.md) — Q&A one-shot; pattern de finding archival reutilizado aqui
- [`docs/superpowers/specs/2026-05-03-write-family-design.md`](2026-05-03-write-family-design.md) — pattern de citação strict + `[REF FALTANTE]` reutilizado
- [`docs/constitution.md`](../../constitution.md) — princípios I (Lógica em um lugar só), II (Determinístico antes de agêntico — helpers Python para state), V (Provenance em todo output)
