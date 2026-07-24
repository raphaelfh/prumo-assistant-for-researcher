"""`ingest()` — orquestração do fluxo 3a-3h (Task 8 da ponte Fase 2).

Integração: sidecars (`citemap.json`/`span-map.json`) construídos à mão
simulando a saída real de `export._emit_review_sidecars` (nunca rodando o
export de verdade — sem Pandoc/BBT); docx revisado sintético via helpers
LOCAIS deste arquivo (mesmo padrão de `test_review_reader.py`/
`test_review_adeu.py`: cada arquivo de teste tem seu próprio builder, não
importa de outro). `_run_adeu_extract` (seam do adeu) é SEMPRE mockado via
`monkeypatch.setattr` no módulo `review` — nunca roda `uvx` de verdade
(regra deste repo, `.claude/rules/code.md`: dependência externa sempre
mockada no seam).

`_write_docx` inclui `[Content_Types].xml` (via `_CONTENT_TYPES_OK`, mesmo
formato de `test_export_docx_validation.py`) desde o achado do review final
da Fase 2 (Important #1): `ingest()` agora valida a ESTRUTURA do docx
revisado (`export._validate_docx_structure`) ANTES de tudo mais — sem essa
parte, todo teste que chama `ingest()` end-to-end falharia no preflight
novo, não só os dois que testam esse preflight de propósito.
"""

from __future__ import annotations

import hashlib
import html
import zipfile
from pathlib import Path

import pytest
import yaml

from prumo_assist.core.obsidian import normalize_markdown_with_map
from prumo_assist.domains.write import review
from prumo_assist.domains.write.export import _slugify
from prumo_assist.domains.write.review import (
    AdeuUnavailableError,
    CitationConservationError,
    IngestResult,
    SourceChangedError,
    ingest,
)
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ReviewCommentsFile,
    ReviewEventsFile,
    SpanMapFile,
)

_W_XMLNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# `[Content_Types].xml` mínimo válido — mesmo formato de
# `test_export_docx_validation.py::_CONTENT_TYPES_OK` — exigido desde que
# `ingest()` passou a validar a ESTRUTURA do docx revisado antes de tudo mais
# (achado do review final da Fase 2, Important #1).
_CONTENT_TYPES_OK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    "</Types>"
)

# sha256 estável usado como "docx exportado original" nos testes em que o I8
# (docx revisado idêntico ao exportado) NÃO deve disparar — qualquer valor
# que não seja o sha256 do docx revisado sintético serve.
_UNRELATED_DOCX_SHA256 = hashlib.sha256(b"docx-exportado-original-placeholder").hexdigest()


def _payload(*, occ_id: str, citekeys: list[str], formatted: str) -> str:
    """JSON cru do campo ``ADDIN ZOTERO_ITEM CSL_CITATION`` — mesmo formato
    de `test_review_reader.py`/`test_review_locate.py`."""
    items = ",".join(f'{{"id":"{key}","prumoFingerprint":"doi:10.1/{key}"}}' for key in citekeys)
    return (
        f'{{"citationID":"{occ_id}","prumoOcc":"{occ_id}",'
        f'"citationItems":[{items}],'
        f'"properties":{{"formattedCitation":"{formatted}"}}}}'
    )


def _citation_field_xml(payload: str, *, wrap_del: bool = False) -> str:
    """Um campo Zotero completo (fldChar begin/instrText/separate/display/end),
    opcionalmente embrulhado em `<w:del>` (estado `deleted`, I2b) — mesmo
    formato de `test_review_reader.py`, sem `touch_ins` (não usado aqui)."""
    instr_tag = "delInstrText" if wrap_del else "instrText"
    text_tag = "delText" if wrap_del else "t"
    begin = '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    instr = (
        f'<w:r><w:{instr_tag} xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
        + html.escape(payload)
        + f" </w:{instr_tag}></w:r>"
    )
    separate = '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    display = f"<w:r><w:{text_tag}>(Formatted, 2020)</w:{text_tag}></w:r>"
    end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    runs = begin + instr + separate + display + end
    if wrap_del:
        return f'<w:del w:id="1" w:author="Coautor">{runs}</w:del>'
    return runs


def _comment_paragraph() -> str:
    """Parágrafo com âncora de comentário (`commentRangeStart/End` + id 0) —
    mesmo formato de `test_review_adeu.py::_docx_with_one_comment`."""
    return (
        "<w:p><w:r><w:t>Antes</w:t></w:r>"
        '<w:commentRangeStart w:id="0"/>'
        "<w:r><w:t> texto ancora</w:t></w:r>"
        '<w:commentRangeEnd w:id="0"/>'
        '<w:r><w:annotationRef w:id="0"/></w:r>'
        "<w:r><w:t> depois</w:t></w:r></w:p>"
    )


_COMMENTS_XML = """<?xml version="1.0"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:comment w:id="0" w:author="Revisor Alice" w:date="2026-07-23T10:30:00Z">
        <w:p><w:r><w:t>Sugestao de revisao aqui.</w:t></w:r></w:p>
    </w:comment>
</w:comments>"""


def _write_docx(path: Path, *, paragraphs: list[str], with_comment: bool = False) -> Path:
    document = (
        f'<?xml version="1.0"?><w:document {_W_XMLNS}><w:body>'
        + "".join(paragraphs)
        + "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", document)
        if with_comment:
            z.writestr("word/comments.xml", _COMMENTS_XML)
    return path


def _init_project(tmp_path: Path, *, body: str) -> tuple[Path, Path]:
    """Monta `project_root` mínimo (`references/_references.bib`, exigido por
    `export.detect_project_root` — não usado diretamente aqui pois os testes
    passam `project_root` explícito, mas mantido para realismo) + `pagina.md`
    com `body` (sem frontmatter)."""
    project_root = tmp_path
    (project_root / "references").mkdir(parents=True, exist_ok=True)
    (project_root / "references" / "_references.bib").write_text("")
    page = project_root / "pagina.md"
    page.write_text(body)
    return project_root, page


def _write_sidecars(
    project_root: Path,
    page: Path,
    *,
    source_text: str,
    docx_sha256: str,
    occurrences: list[CiteOccurrence] | None = None,
) -> Path:
    """Grava `reviews/<slug>/{citemap,span-map}.json` à mão — simula a saída
    de `export._emit_review_sidecars` sem rodar pandoc/BBT. `span_map.fragments`
    fica vazio de propósito: `ingest()` recalcula `norm_text`/`span_frags` na
    hora via `normalize_markdown_with_map(body, ...)` (mesma chamada do
    export — decisão documentada no brief da Task 8), então o sidecar só
    precisa do `source_sha256` para o preflight."""
    slug = _slugify(page, project_root)
    review_dir = project_root / "reviews" / slug
    review_dir.mkdir(parents=True, exist_ok=True)
    citemap = CiteMapFile(
        page=str(page.relative_to(project_root)),
        export_git_sha="deadbee",
        bib_sha256="ab" * 32,
        docx_sha256=docx_sha256,
        occurrences=occurrences or [],
    )
    span_map = SpanMapFile(
        page=str(page.relative_to(project_root)),
        source_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        fragments=[],
    )
    (review_dir / "citemap.json").write_text(citemap.model_dump_json())
    (review_dir / "span-map.json").write_text(span_map.model_dump_json())
    return review_dir


# --- 1. happy path: 1 ins de prosa + 1 comentário ---------------------------


def test_ingest_happy_path_prose_insertion_and_comment_writes_valid_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = "O paciente recebeu o tratamento"
    suffix = " conforme protocolo estabelecido pela equipe."
    body = prefix + suffix
    project_root, page = _init_project(tmp_path, body=body)

    docx = _write_docx(
        tmp_path / "revisado.docx", paragraphs=[_comment_paragraph()], with_comment=True
    )
    _write_sidecars(project_root, page, source_text=body, docx_sha256=_UNRELATED_DOCX_SHA256)

    adeu_markdown = prefix + "{++ novo++}{>>[Chg:1 insert] Coautor<<}" + suffix
    monkeypatch.setattr(review, "_run_adeu_extract", lambda _docx: adeu_markdown)

    result = ingest(reviewed_docx=docx, page=page, project_root=project_root)

    assert isinstance(result, IngestResult)
    assert result.marks_applied == 1
    assert result.deleted == []
    assert result.events.events == []
    assert len(result.comments.comments) == 1
    assert result.comments.comments[0].author == "Revisor Alice"

    # {++...++} no lugar certo (posição exata, não só substring), seguido da
    # âncora de autoria `{>>prumo-autor: X<<}` (Task 9 — `transplant_to_source`
    # agora roda com `author_anchors=True` dentro de `ingest()`; a âncora
    # nunca sobrevive ao `apply`, só existe em review.md. Prefixo `prumo-`
    # — Fix pós-review, achado Menor — evita colisão com um comentário
    # humano genuíno `{>>autor: ...<<}`).
    assert result.review_md.read_text() == prefix + "{++ novo++}{>>prumo-autor: Coautor<<}" + suffix

    # comments.yaml e events.yaml são YAML válido conforme os schemas.
    slug = _slugify(page, project_root)
    review_dir = project_root / "reviews" / slug
    comments_on_disk = ReviewCommentsFile.model_validate(
        yaml.safe_load((review_dir / "review-comments.yaml").read_text())
    )
    assert len(comments_on_disk.comments) == 1
    events_on_disk = ReviewEventsFile.model_validate(
        yaml.safe_load((review_dir / "events.yaml").read_text())
    )
    assert events_on_disk.events == []

    # Nada toca a página original no ingest.
    assert page.read_text() == body


# --- 1a. preflight 3a: uvx não disponível → fail-fast antes de sidecars ------


def test_ingest_fails_fast_without_uvx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Preflight 3a: `ingest()` checa uvx no PATH ANTES de carregar sidecars.
    Sem uvx, levanta `AdeuUnavailableError` mencionando o comando de
    instalação, e NÃO faz nenhuma leitura de sidecar (fail-fast: economia de
    trabalho inútil se o backend não estiver disponível)."""
    body = "Pagina de teste para preflight uvx."
    project_root, page = _init_project(tmp_path, body=body)
    _write_sidecars(project_root, page, source_text=body, docx_sha256=_UNRELATED_DOCX_SHA256)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])

    # Monkeypatch shutil.which no módulo review para simular uvx ausente
    monkeypatch.setattr("prumo_assist.domains.write.review.shutil.which", lambda _: None)

    with pytest.raises(AdeuUnavailableError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    message = str(exc.value)
    assert "uvx" in message
    assert "uvx adeu==1.29.0 --version" in message


# --- 1b. preflight de estrutura: docx não-zip → ValueError pt-BR ------------
#
# Achado do review final da Fase 2 (Important #1): `reviewed_docx` é o input
# mais hostil do sistema (chega por e-mail) — um arquivo texto renomeado para
# `.docx` (ou um `.doc` binário antigo) não é um zip, e sem esta validação
# `zipfile.BadZipFile` vazava cru pelo CLI (fora de `_REVIEW_CATCHES`).


def test_ingest_non_zip_docx_raises_value_error_with_actionable_hint(tmp_path: Path) -> None:
    body = "Pagina de teste para docx nao-zip."
    project_root, page = _init_project(tmp_path, body=body)
    docx = tmp_path / "revisado.docx"
    docx.write_text("isto claramente nao e um arquivo zip/docx")

    # Preflight de estrutura roda ANTES de `_read_sidecars` (mesmo estilo
    # fail-fast do preflight de uvx acima) — nenhum sidecar precisa existir
    # para este teste.
    with pytest.raises(ValueError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    message = str(exc.value)
    assert "não é um .docx válido" in message
    assert "prumo write review ingest" in message


def test_ingest_happy_path_preserves_frontmatter_in_review_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Frontmatter da página sobrevive em `review.md` BYTE A BYTE (Fix
    pós-review, achado Crítico 1 — `_compose_page` nunca faz
    `yaml.safe_dump`; write-back usa `core.obsidian.split_frontmatter_raw`),
    inclusive comentário YAML e espaçamento incomum que um reserialize
    destruiria."""
    prefix = "Frase inicial da pagina de teste completo"
    suffix = " e nada mais."
    prose = prefix + suffix
    raw_frontmatter = (
        "---\n"
        "title: Pagina com frontmatter\n"
        "# comentario do humano que nao pode sumir\n"
        "tags:   [a, b]\n"
        "---\n\n"
    )
    page_text = raw_frontmatter + prose
    project_root = tmp_path
    (project_root / "references").mkdir(parents=True, exist_ok=True)
    (project_root / "references" / "_references.bib").write_text("")
    page = project_root / "pagina.md"
    page.write_text(page_text)

    _write_sidecars(project_root, page, source_text=prose, docx_sha256=_UNRELATED_DOCX_SHA256)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])

    adeu_markdown = prefix + "{++ ADICIONADO++}" + suffix
    monkeypatch.setattr(review, "_run_adeu_extract", lambda _docx: adeu_markdown)

    result = ingest(reviewed_docx=docx, page=page, project_root=project_root)

    review_md_text = result.review_md.read_text()
    # frontmatter VERBATIM — comentário e espaçamento sobrevivem byte a byte
    # (um `yaml.safe_dump` de round-trip, como a versão antiga fazia,
    # deletaria o comentário e reformataria `tags:   [a, b]`).
    assert review_md_text.startswith(raw_frontmatter)
    assert "# comentario do humano que nao pode sumir" in review_md_text
    assert "tags:   [a, b]" in review_md_text
    rest = review_md_text[len(raw_frontmatter) :]
    # Sem anotação `[Chg:...]` pareada, o autor cai no default
    # `_UNKNOWN_AUTHOR` (Task 4) — a âncora ainda é emitida (Task 9:
    # `author_anchors=True` sempre anota, mesmo autor desconhecido); formato
    # `prumo-autor:` (Fix pós-review, achado Menor — evita colisão com
    # comentário humano `{>>autor: ...<<}`).
    assert rest == prefix + "{++ ADICIONADO++}{>>prumo-autor: (desconhecido)<<}" + suffix


# --- 2. sidecars ausentes → FileNotFoundError pt-BR -------------------------


def test_ingest_missing_sidecars_raises_file_not_found_with_export_hint(tmp_path: Path) -> None:
    body = "Pagina sem nenhum sidecar gravado ainda."
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])

    with pytest.raises(FileNotFoundError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    assert "prumo write export --to docx" in str(exc.value)


# --- 2a. citemap.json corrompido → ValueError pt-BR -------------------------
#
# Achado do review final da Fase 2 (Important #1): `reviews/<slug>/citemap.json`
# pode ser corrompido por edição manual, merge malsucedido, ou truncamento em
# disco — sem esta tradução, `pydantic.ValidationError` vazava cru pelo CLI
# (fora de `_REVIEW_CATCHES`).


def test_ingest_corrupted_citemap_json_raises_value_error_with_sidecar_hint(
    tmp_path: Path,
) -> None:
    body = "Pagina com citemap.json corrompido."
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])
    review_dir = _write_sidecars(
        project_root, page, source_text=body, docx_sha256=_UNRELATED_DOCX_SHA256
    )
    (review_dir / "citemap.json").write_text("{invalid")

    with pytest.raises(ValueError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    message = str(exc.value)
    assert "sidecar corrompido" in message
    assert "citemap.json" in message
    assert "prumo write export --to docx" in message


# --- 3. fonte alterada desde o export → SourceChangedError ------------------


def test_ingest_source_changed_since_export_raises(tmp_path: Path) -> None:
    body = "Texto ATUAL da pagina, editado depois do export original."
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])
    _write_sidecars(
        project_root,
        page,
        source_text="Texto ANTIGO, exportado antes da edicao na fonte.",
        docx_sha256=_UNRELATED_DOCX_SHA256,
    )

    with pytest.raises(SourceChangedError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    assert "re-exporte" in str(exc.value)


# --- 4. docx revisado idêntico ao exportado → erro I8 -----------------------


def test_ingest_docx_identical_to_exported_raises_i8(tmp_path: Path) -> None:
    body = "Texto da pagina, inalterado desde o export."
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(tmp_path / "revisado.docx", paragraphs=[])
    docx_sha256 = hashlib.sha256(docx.read_bytes()).hexdigest()
    _write_sidecars(project_root, page, source_text=body, docx_sha256=docx_sha256)

    with pytest.raises(CitationConservationError) as exc:
        ingest(reviewed_docx=docx, page=page, project_root=project_root)

    assert "exportado" in str(exc.value)


# --- 5. citação deletada → evento citation-drop, review.md sem marca dupla -


def test_ingest_deleted_citation_emits_drop_event_without_duplicate_mark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    formatted = "(Jones, 2021)"
    prose_before = "Outro estudo "
    prose_after = " confirmou o achado principal."
    body = prose_before + "[[@jones2021]]" + prose_after
    project_root, page = _init_project(tmp_path, body=body)

    payload = _payload(occ_id="00000002", citekeys=["jones2021"], formatted=formatted)
    docx = _write_docx(
        tmp_path / "revisado.docx",
        paragraphs=[f"<w:p>{_citation_field_xml(payload, wrap_del=True)}</w:p>"],
    )

    norm_text, _frags = normalize_markdown_with_map(body)
    cit_start = norm_text.index("[@jones2021]")
    cit_end = cit_start + len("[@jones2021]")
    occ = CiteOccurrence(
        occ_id="00000002",
        citation_id="00000002",
        citekeys=["jones2021"],
        fingerprints={"jones2021": "doi:10.1/jones2021"},
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )
    _write_sidecars(
        project_root,
        page,
        source_text=body,
        docx_sha256=_UNRELATED_DOCX_SHA256,
        occurrences=[occ],
    )

    adeu_markdown = (
        prose_before + "{--" + formatted + "--}{>>[Chg:4 delete] Coautor<<}" + prose_after
    )
    monkeypatch.setattr(review, "_run_adeu_extract", lambda _docx: adeu_markdown)

    result = ingest(reviewed_docx=docx, page=page, project_root=project_root)

    assert result.marks_applied == 0
    assert [c.occ_id for c in result.deleted] == ["00000002"]
    assert result.deleted[0].state == "deleted"

    assert len(result.events.events) == 1
    drop_event = result.events.events[0]
    assert drop_event.kind == "citation-drop"
    assert drop_event.occ_id == "00000002"
    assert drop_event.citekeys == ["jones2021"]
    assert "deletada no Word" in drop_event.detail
    assert "confirme no apply" in drop_event.detail

    # review.md SEM marca dupla: a citação nunca foi transplantada (o drop é
    # só o evento) — o texto sai idêntico ao source, wikilink intacto.
    review_md_text = result.review_md.read_text()
    assert review_md_text == body
    assert "{--" not in review_md_text
    assert "[[@jones2021]]" in review_md_text


# --- 6. guarda de re-ingest: worklist pendente exige --force ----------------
#
# Fila herdada do archive da F3 (commit 711c0c0): re-ingest SOBRESCREVE
# `reviews/<slug>/review.md` silenciosamente — se há marcas pendentes
# (inclusive propostas do agente via `propose_prose_edit`), elas são
# destruídas. Prioridade subiu: hard-fail por padrão, `--force` para optar
# pelo descarte.


def _ingest_ok_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Receita mínima de ingest válido (mesma do happy path, linha ~185):
    devolve (project_root, page, docx) com adeu mockado no seam."""
    prefix = "O paciente recebeu o tratamento"
    suffix = " conforme protocolo estabelecido pela equipe."
    body = prefix + suffix
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(
        tmp_path / "revisado.docx", paragraphs=[_comment_paragraph()], with_comment=True
    )
    _write_sidecars(project_root, page, source_text=body, docx_sha256=_UNRELATED_DOCX_SHA256)
    adeu_markdown = prefix + "{++ novo++}{>>[Chg:1 insert] Coautor<<}" + suffix
    monkeypatch.setattr(review, "_run_adeu_extract", lambda _docx: adeu_markdown)
    return project_root, page, docx


def test_reingest_com_worklist_pendente_hard_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    assert first.marks_applied == 1  # worklist ficou com marca pendente

    with pytest.raises(ValueError, match=r"marca\(s\) pendente"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)
    # a mensagem embute os DOIS caminhos de saída (decidir ou --force):
    with pytest.raises(ValueError, match="prumo write review apply"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)
    with pytest.raises(ValueError, match="--force"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)


def test_reingest_com_force_sobrescreve_propostas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    first.review_md.write_text(
        first.review_md.read_text() + "{++proposta do agente++}{>>prumo-autor: agente<<}"
    )
    result = ingest(reviewed_docx=docx, page=page, project_root=project_root, force=True)
    assert "proposta do agente" not in result.review_md.read_text()
    assert "{++ novo++}" in result.review_md.read_text()  # worklist regenerado


def test_reingest_com_worklist_consumido_nao_exige_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    # simula worklist 100% consumido pelo apply: corpo sem nenhuma marca
    first.review_md.write_text("corpo decidido, sem marcas")
    result = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    assert "{++ novo++}" in result.review_md.read_text()
