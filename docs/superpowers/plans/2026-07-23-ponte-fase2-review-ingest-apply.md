# Ponte docx↔CriticMarkup — Fase 2: MVP `review ingest`/`apply` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar o loop externo dos coautores: `prumo write review ingest <reviewed.docx> --page <page.md>` extrai marcas/comentários do docx revisado, aplica as guardas A/B/C e a conservação I2/I2b/I8, transplanta o que é determinístico como CriticMarkup para `reviews/<slug>/review.md`, e `prumo write review apply` aceita/rejeita por marca/autor com write-back na página-fonte.

**Architecture:** Novo módulo `domains/write/review.py` (toda a lógica; fachada fina no CLI). Citação NUNCA vem do adeu (decisão (b) da Fase 0): o leitor OOXML próprio (ET sobre `word/document.xml`) classifica cada campo `ADDIN ZOTERO_ITEM` como `live`/`deleted`/`touched` andando pelos ancestrais `w:del`/`w:ins`. Prosa vem do `uvx adeu==1.29.0 extract --json` (seam subprocess; SEM precisar do docx original — validado no spike: as tracked changes saem inline como `{++...++}{>>[Chg:N tipo] Autor<<}`). O transplante determinístico localiza cada marca no texto NORMALIZADO por âncora única de contexto e inverte para o SOURCE via span-map (`kind=identity` only); todo o resto vira evento em `events.yaml` (modo degradado do spec: checklist manual; reconciliador chega na Fase 3). Guardas hard-fail em pt-BR com comando embutido.

**Tech Stack:** Python 3.11 stdlib (ET/zipfile/subprocess/difflib), `core/criticmarkup` (parse/emit/apply), `core/obsidian` (span-map), schemas Pydantic v1, adeu pinado `uvx adeu==1.29.0` (seam mockado nos testes; golden fixture do formato de saída registrada do spike).

**Spec:** `docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md` (fluxo 3a–3h, guardas A/B/C, I1–I8, "Ingest e transplante", CLI). Release: PATCH (ADR-0015: pré-1.0 tudo PATCH releasável; comandos novos anotados no CHANGELOG).

## Global Constraints

- `mypy --strict`; `from __future__ import annotations`; mensagens pt-BR com comando de correção; identificadores em inglês; fachadas via `cli_run` + `Console`; sem `print()`.
- Citação/conservação SEMPRE do OOXML lido pelo prumo (I2); saída do adeu NUNCA é fonte de verdade de citação; adeu nunca recebe edit com alvo dentro de display de citação (não aplicamos edits via adeu nesta fase — só extração).
- adeu SEMPRE `uvx adeu==1.29.0` via seam `_run_adeu_extract(docx: Path) -> str` (retorna o campo `markdown` do JSON); testes mockam o seam; UMA golden fixture do JSON real (capturada do spike) trava o formato no CI (teste de parse contra a string literal — sem rodar adeu no CI).
- Hard-fails desta fase: cada um vira teste com fixture. Nenhum caminho prossegue parcial após guarda disparada.
- MVP: página única; um `reviewed.docx` por rodada; sem merge multi-coautor; sem add/replace de citação (I3b fica para Fase 3) — deleção de citação exige confirmação explícita no `apply`.
- Fonte inalterada desde o export é pré-condição (sha256 vs span-map); divergência → hard-fail com instrução (re-exportar) — offsets derivados nunca são "confiados" (spec).
- Sidecars desta fase em `reviews/<slug>/`: `review.md`, `review-comments.yaml`, `events.yaml` (schemas v1 novos: `ReviewCommentsFile`, `ReviewEventsFile`). Git add/commit é do humano (portão).
- Bateria completa antes de cada commit (`uv run pytest` — 509 hoje; ruff check+format; mypy; `gen_indexes --check` quando docs mudarem).

**Interfaces centrais (contrato entre tasks — nomes exatos):**

```python
# domains/write/review.py
@dataclass(frozen=True)
class DocxCitation:
    occ_id: str
    citation_id: str
    citekeys: tuple[str, ...]
    fingerprints: dict[str, str]
    formatted: str
    state: Literal["live", "deleted", "touched"]

class SourceChangedError(RuntimeError): ...
class StructuralChangeError(RuntimeError): ...      # Guarda A
class MarkLostError(RuntimeError): ...              # Guarda B
class CitationConservationError(RuntimeError): ...  # I2/I2b/I8
class AdeuUnavailableError(RuntimeError): ...

def read_docx_citations_with_state(docx_path: Path) -> list[DocxCitation]
def check_conservation(observed: list[DocxCitation], citemap: CiteMapFile) -> list[DocxCitation]  # retorna deleted; hard-fail em qualquer outra divergência
def assert_no_structural_changes(docx_path: Path) -> None                    # Guarda A
def _run_adeu_extract(docx_path: Path) -> str                                # seam
def parse_adeu_markdown(markdown: str) -> list[ReviewMark]                   # marca + autor/tipo do {>>[Chg:...]<<}
def locate_marks_in_norm(marks, norm_text, citemap) -> tuple[list[LocatedMark], list[ReviewEvent]]
def transplant_to_source(located, source_text, span_frags) -> tuple[str, list[ReviewEvent]]
def ingest(reviewed_docx: Path, page: Path, project_root: Path | None = None) -> IngestResult
def apply_review(page: Path, *, accept_all=False, reject_all=False, by_author: str | None = None,
                 accept: bool | None = None, marks: list[int] | None = None,
                 confirm_citation_drops: list[str] | None = None, project_root: Path | None = None) -> ApplyResult
```

---

### Task 1: Leitor OOXML com estado (`read_docx_citations_with_state`, I2b)

**Files:** Create `src/prumo_assist/domains/write/review.py`; Create `tests/unit/write/test_review_reader.py`

Ler `word/document.xml` com ET (padrão de `comments.py`, `W_NS`); iterar na ordem do documento; um campo = sequência `fldChar begin` … `instrText` (com `ADDIN ZOTERO_ITEM CSL_CITATION`) … `fldChar end`; estado: `deleted` se TODOS os runs do campo têm ancestral `w:del`; `touched` se ALGUM run tem ancestral `w:ins`/`w:del` (mas não todos `w:del`); senão `live`. fldChar desbalanceado (begin sem end / end órfão) → `CitationConservationError` ("campo colapsado", I2b). JSON do payload: mesmo unescape do `_read_docx_citations` (importar/reusar helpers de `export.py` onde couber — sem duplicar lógica de decode; extrair helper compartilhado `_decode_field_payload` se necessário, movendo-o para `review.py` e reimportando no export? NÃO: export permanece dono; `review.py` importa de `export` as funções públicas/privadas necessárias — domains-internos, permitido).

Fixtures: estender o padrão `_write_minimal_docx_with_payloads` LOCALMENTE (novo helper no test file) com parâmetros por-payload `wrap_del: bool` / `touch_ins: bool`, gerando XML real de campo (fldChar begin/instrText/separate/display/end) dentro de `<w:del>` ou com run extra `<w:ins>` no display. Testes: live/deleted/touched; ordem preservada; occ_id/citekeys/fingerprints decodificados; fldChar desbalanceado → raise; JSON inválido → raise com índice.

Commit: `feat(write): leitor OOXML de citações com estado live/deleted/touched (I2b)`

---

### Task 2: Conservação (`check_conservation`, I2/I3-lite/I8)

**Files:** Modify `review.py`; Modify `tests/unit/write/test_review_reader.py` (append)

Regras (todas hard-fail `CitationConservationError` com mensagem pt-BR nomeando occ_ids/citekeys):
1. occ_id duplicado no observado (paste-clone, I2b). CASO ESPECIAL diagnosticado: se das duplicatas exatamente uma está `deleted` e outra `live`-dentro-de-`w:ins`, a mensagem vira "possível MOVE de citação (occ X) — mover citação não é suportado no MVP; rejeite a mudança no Word e mova via edição da fonte, ou aguarde a Fase 3 (I2c)". Continua hard-fail; só o diagnóstico melhora (teste próprio).
2. Multiconjunto: `{occ_id: citekeys}` de `live + touched + deleted` DEVE ser igual ao do citemap (nenhum campo sumiu sem rastro — deleção rastreada ainda mantém o campo no XML, validado no spike; campo AUSENTE = achatado/hard delete → fail). occ ausente OU occ extra → fail.
3. Fingerprints: para cada occ, fingerprints observados == do citemap (re-key/shadow → fail; I3-lite — revalidação BBT plena fica pra Fase 4).
4. `touched` no MVP → fail-informativo: "citação editada dentro do campo (occ X) — decisão humana necessária; MVP não transplanta CITATION-TOUCHED; rejeite a mudança no Word ou trate manualmente" (I2c vira evento na Fase 3; aqui é stop honesto).
Retorna a lista dos `deleted` (viram eventos de drop pendentes de confirmação no apply).

Testes: conservação ok com 2 live; deleted retorna na lista; occ faltante → raise; occ duplicado → raise; fingerprint divergente → raise; touched → raise com "decisão humana".

Commit: `feat(write): conservação de citações do docx revisado (I2/I2b/I3-lite)`

---

### Task 3: Guarda A — mudanças estruturais

**Files:** Modify `review.py`; Create `tests/unit/write/test_review_guards.py`

`assert_no_structural_changes(docx_path)`: hard-fail `StructuralChangeError` nomeando cada região quando: (a) `w:ins`/`w:del`/`w:commentRangeStart` com ancestral `w:tbl`; (b) `footnotes.xml`/`endnotes.xml` existentes contendo `w:ins`/`w:del`; (c) `w:ins`/`w:del` com ancestral `m:oMath` (namespace math `{http://schemas.openxmlformats.org/officeDocument/2006/math}`). Mensagem lista tipo+trecho (primeiros 60 chars do texto da região) e instrui: "peça ao coautor para mover a mudança para o corpo do texto ou aplique manualmente; re-exporte e re-ingira".

Fixtures: docx sintético com tabela contendo `w:ins`; footnotes.xml com `w:del`; oMath com `w:ins`; e docx limpo → passa.

Commit: `feat(write): guarda A — hard-fail em mudança estrutural (tabela/nota/equação)`

---

### Task 4: Seam do adeu + parser das marcas (`parse_adeu_markdown`)

**Files:** Modify `review.py`; Create `tests/unit/write/test_review_adeu.py`

`_run_adeu_extract`: `subprocess.run(["uvx", "adeu==1.29.0", "extract", "--json", str(docx), "-o", "-"], capture_output=True, text=True)`; exit≠0 ou `uvx` ausente → `AdeuUnavailableError` (pt-BR: instale uv / rode `uvx adeu==1.29.0 --version`; adeu é o backend de PROSA pinado). Parse do stdout: JSON com campo `markdown`.

`parse_adeu_markdown(markdown)`: usa `core.criticmarkup.parse`; anotações do adeu são marcas `comment` com corpo `[Chg:<id> <insert|delete>] <Autor>` IMEDIATAMENTE após a marca de conteúdo → parear (marca, anotação) em `ReviewMark(kind, a, b, author, chg_id, start, end)` (offsets no markdown do adeu); comment-annotation órfã ou marca sem anotação → manter com author="(desconhecido)". Remover do texto as anotações pareadas (elas não transplantam). O rodapé `\n---\n## Footnotes` do adeu é descartado. `{>>Diff: ...<<}` (formato do markup-path) tratado igual. Marcas de conteúdo sem par: ok.

Golden fixture (do spike, literal no teste):
```python
ADEU_GOLDEN = (
    "Primeiro paragrafo de prosa.\n\n"
    "Aqui vem a citacao (Smith, 2020){++ TEXTO INSERIDO PELO COAUTOR++}"
    "{>>[Chg:901 insert] Coautor<<} e mais prosa.\n\n"
    "{--Ultimo paragrafo.--}{>>[Chg:902 delete] Coautor<<}\n\n---\n## Footnotes"
)
```
Testes: golden → 2 ReviewMarks (ins autor Coautor chg 901; del autor Coautor chg 902) e texto limpo sem anotações/rodapé; marca sem anotação; seam com exit≠0 → AdeuUnavailableError (subprocess mockado).

Commit: `feat(write): seam do adeu pinado + parser de marcas com autoria (backend de prosa)`

---

### Task 5: Comentários reais → `review-comments.yaml` + schemas

**Files:** Modify `src/prumo_assist/domains/write/schemas/v1.py` (só adições); Modify `review.py`; Modify `tests/unit/write/test_schemas_v1.py` e `test_review_adeu.py` (append)

Schemas novos (forward-only):
```python
class ReviewComment(BaseModel):
    id: str
    author: str
    date: str | None = None
    text: str
    anchor_text: str | None = None
    reply_of: str | None = None

class ReviewCommentsFile(BaseModel):
    schema_version: Literal["ReviewCommentsFile/v1"] = "ReviewCommentsFile/v1"
    page: str
    comments: list[ReviewComment] = []

class ReviewEvent(BaseModel):
    kind: str            # "citation-drop" | "unanchored-mark" | "non-identity-span" | "ambiguous-anchor"
    detail: str
    occ_id: str | None = None
    citekeys: list[str] = []
    author: str | None = None
    mark_excerpt: str | None = None

class ReviewEventsFile(BaseModel):
    schema_version: Literal["ReviewEventsFile/v1"] = "ReviewEventsFile/v1"
    page: str
    events: list[ReviewEvent] = []
```
Coleta: reusar `comments.extract_from_docx` (import de `domains/write/comments.py`) → `ReviewCommentsFile` (reply_of=None no MVP; threads = interino ponto-ancorado do spec). Testes: roundtrip dos schemas; coleta de comments.xml da fixture com 1 comentário.

Commit: `feat(write): review-comments.yaml e events.yaml — schemas v1 + coleta de comentários`

---

### Task 6: Localizador de âncora única (`locate_marks_in_norm`)

**Files:** Modify `review.py`; Create `tests/unit/write/test_review_locate.py`

Para cada `ReviewMark` (offsets no texto do adeu): extrair contexto plano `before`/`after` (até 48 chars de texto SEM outras marcas, colapsando espaços múltiplos em 1) e o alvo (`a` para del/sub, âncora-ponto para ins). Procurar `before + alvo(a) + after` no `norm_text` — com a NUANCE de que displays de citação no adeu (`(Smith, 2020)`) não existem no norm (`[@smith2020]`): substituir no contexto do adeu toda ocorrência de `citemap.occurrences[*].formatted` por um TOKEN sentinela `\x00CIT<i>\x00` e no norm substituir o span correspondente da occurrence (via `norm_start/norm_end`) pelo MESMO token — aí a busca é textual pura. Resultados: exatamente 1 match → `LocatedMark(mark, norm_start, norm_end)`; 0 → evento `unanchored-mark`; >1 → `ambiguous-anchor`. Marca cujo alvo INTERSECTA um token de citação → evento `citation-touched-prose` (decisão humana; nunca auto-aplica — I1). Deleção rastreada de citação já vem via Task 2 (`deleted`) — o del correspondente no adeu (ex. `{--(Smith, 2020)--}`) é RECONHECIDO (alvo == token) e casado com o evento de drop, não duplicado.

Testes: ins com âncora única localiza; del com alvo único localiza; contexto ambíguo (frase repetida) → ambiguous; marca encostando no token de citação → citation-touched-prose; del de citação casa com deleted (sem evento duplicado); texto do adeu com citação no meio da âncora → localiza via sentinela.

Commit: `feat(write): localizador determinístico de marcas no texto normalizado (âncora única + sentinela de citação)`

---

### Task 7: Transplante para o source + Guarda B (`transplant_to_source`)

**Files:** Modify `review.py`; Modify `tests/unit/write/test_review_locate.py` (append)

Para cada `LocatedMark`: mapear `norm_start`/`norm_end` pelos `span_frags`: só aplica se o intervalo INTEIRO cai em UM fragment `kind="identity"` (spec: prosa-pura-âncora-única-zero-overlap); demais kinds/fronteiras → evento `non-identity-span`. Offset source = `frag.source_start + (norm_off - frag.norm_start)`. Aplicar as marcas de trás pra frente (offsets estáveis) inserindo `criticmarkup.emit(kind, a, b)` no texto SOURCE (body sem frontmatter; frontmatter preservado na escrita). **Guarda B (ingest-side):** nº de ReviewMarks == nº de (marcas escritas no review.md) + nº de eventos gerados — QUALQUER marca não contabilizada → `MarkLostError` listando o excerpt. Retorna `(source_with_marks, events)`.

Testes: ins/del/sub transplantados no lugar certo do source (com wikilink/citação AO REDOR intactos); marca em fragment `citation` → evento; contabilidade B: forçar (monkeypatch em helper interno) uma marca a "sumir" → MarkLostError; aplicação de múltiplas marcas preserva offsets (ordem reversa).

Commit: `feat(write): transplante determinístico para o source via span-map + guarda B (mark-count)`

---

### Task 8: `ingest()` — orquestração + preflight + escrita dos sidecars

**Files:** Modify `review.py`; Create `tests/unit/write/test_review_ingest.py`

Sequência (espelha o fluxo 3a–3h do spec): resolver `project_root` (via `export.detect_project_root(page)`); slug (via `export._slugify`); carregar `reviews/<slug>/{citemap,span-map}.json` (ausentes → FileNotFoundError pt-BR: "rode `prumo write export --to docx` antes"); **preflight fonte**: sha256(body atual sem frontmatter) == `span_map.source_sha256` senão `SourceChangedError` ("página mudou desde o export — re-exporte e peça nova revisão sobre o docx novo"); **I8**: docx revisado idêntico ao exportado (`sha256 == citemap.docx_sha256`) → erro "docx não contém revisão (é o exportado)"; Guarda A; leitor com estado; conservação (→ deleted list); adeu extract + parse; localizar; transplantar; montar eventos (+ `citation-drop` por deleted, com occ_id/citekeys/autor se disponível via `w:del` author do campo); escrever `reviews/<slug>/review.md` (frontmatter da página + source_with_marks), `review-comments.yaml`, `events.yaml`. Retorna `IngestResult(review_md, marks_applied, events, comments, deleted)` (dataclass). Nada toca a página original no ingest.

Testes (integração com seams mockados — adeu seam, fixtures docx): happy path 1 ins de prosa + 1 comentário → review.md com `{++...++}` no lugar certo, comments.yaml e events.yaml válidos; fonte alterada → SourceChangedError; docx == exportado → erro I8; deleted citation → evento citation-drop e review.md SEM marca dupla.

Commit: `feat(write): review ingest — orquestração com preflight, guardas e sidecars`

---

### Task 9: `apply_review()` + write-back com confirmação de drops

**Files:** Modify `review.py`; Create `tests/unit/write/test_review_apply.py`

Ler `reviews/<slug>/review.md` e `events.yaml`; `criticmarkup.parse` nas marcas; seleção de decisões: `--accept-all` / `--reject-all` / `--by-author X --accept|--reject` (autor vem de `review-comments`? NÃO — autor da marca não sobrevive no CriticMarkup puro: gravar em `events.yaml`… melhor: sidecar `review-marks.yaml`? SIMPLIFICAÇÃO DO MVP, decidida aqui: autoria por marca é registrada como sufixo do comentário-âncora `{>>autor: X<<}` imediatamente após cada marca no review.md — o parser de apply pareia igual à Task 4 e o filtro `--by-author` opera nisso; anotações-âncora nunca vão para a fonte final); `--mark N --accept/--reject` por índice. **Pré-condições:** eventos `citation-drop` pendentes exigem `--confirm-citation-drops occ1,occ2` cobrindo TODOS os drops, senão hard-fail listando-os (decisão humana explícita em Git — I6); eventos de outros kinds pendentes → hard-fail "resolva manualmente os eventos em events.yaml e re-rode ingest, ou edite review.md" (modo degradado do spec). **Aplicação:** `criticmarkup.apply` com as decisões; Guarda B apply-side: após aplicar TODAS as decisões pedidas com `--accept-all`/`--reject-all`, nenhum residual de marca pode sobrar (parse == []) senão `MarkLostError`; conservação pós-apply: `scan_citekeys(texto_final)` como multiconjunto == citekeys do citemap − drops confirmados (posições não — só multiconjunto; I5: bibliografia é função da fonte, nada a transplantar). **Write-back:** reescreve a PÁGINA original (frontmatter preservado + corpo aplicado); events.yaml ganha registro `applied` (drops confirmados com timestamp via parâmetro `today: str` — sem Date.now no teste); review.md permanece para o histórico Git (o humano commita).

Testes: accept-all limpa e escreve na página; reject-all restaura o original byte a byte; by-author aplica só as do autor; drop sem confirmação → hard-fail; com confirmação → página sem a citação e conservação ok; marca residual forjada → MarkLostError.

Commit: `feat(write): review apply — decisões por marca/autor, confirmação de drops e write-back`

---

### Task 10: CLI `prumo write review ingest|apply` + CHANGELOG + bateria

**Files:** Modify `src/prumo_assist/domains/write/cli.py`; Modify `src/prumo_assist/domains/write/api.py` (re-export `ingest`/`apply_review`); Modify `tests/unit/write/test_cli.py` (append); Modify `CHANGELOG.md`

Sub-app `review_app = typer.Typer()` montado em `write_app.add_typer(review_app, name="review")`. `ingest <reviewed_docx> --page <page.md> [--json]`: fachada fina chamando `review.ingest`; saída: contagens (marcas aplicadas, eventos, comentários, drops pendentes) + próximo passo ("revise reviews/<slug>/review.md e rode `prumo write review apply ...`"). `apply --page <page.md> [--accept-all|--reject-all|--by-author X --accept/--reject|--mark N --accept/--reject] [--confirm-citation-drops occs] [--json]`. `catches=` novo `_REVIEW_CATCHES` = (`FileNotFoundError`, `ValueError`, `SourceChangedError`, `StructuralChangeError`, `MarkLostError`, `CitationConservationError`, `AdeuUnavailableError`). Testes CLI: ingest happy (review mockado), erro limpo p/ SourceChangedError (sem traceback), apply happy, drops sem confirmação → exit 1 mensagem. CHANGELOG "Não publicado" ### Adicionado: os dois comandos + guardas (1 bullet denso citando spec/ADR-0016). Bateria completa + `gen_indexes --check`.

Commit: `feat(write): comandos prumo write review ingest/apply (fachadas finas)`

---

### Task 11 (controller): review final da fase + arquivar

Review final (modelo mais capaz) sobre o range da fase; fixes se houver; frontmatter implemented/verified; archive/; gen_indexes; push.

## Verificação final

- [ ] Fluxo end-to-end nos testes de integração: export (fixture) → ingest (reviewed sintético) → review.md → apply → página final; cada hard-fail com fixture própria.
- [ ] Smoke manual futuro (dono, não-bloqueante): rodada real com um docx revisado no Word.
