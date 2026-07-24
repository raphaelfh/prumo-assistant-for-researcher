"""`apply_review()` — decisões por marca/autor, drops e write-back (Task 9).

Fixtures LOCAIS (`_init_project`/`_write_review_dir`), não reusadas de
`test_review_ingest.py` (mesma convenção documentada em
`test_review_locate.py`: cada arquivo de teste tem seu próprio builder).
`review.md`/`events.yaml`/`citemap.json`/`span-map.json` são escritos À MÃO
simulando a saída de `ingest()` (Task 8) — sem rodar o pipeline adeu/docx de
verdade: o que importa aqui é o CONTRATO de `apply_review` (decisões,
guardas, conservação, write-back), já coberto em `test_review_ingest.py` na
outra ponta. `review.md` é escrito com a âncora `{>>autor: X<<}` já colada
depois de cada marca (per Task 9 — decisão do controller: âncora-autor é
como a autoria sobrevive no CriticMarkup puro; nunca vai para a página
final)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from prumo_assist.core import criticmarkup
from prumo_assist.domains.write.export import _slugify
from prumo_assist.domains.write.review import (
    ApplyResult,
    CitationConservationError,
    MarkLostError,
    apply_review,
)
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ReviewEvent,
    ReviewEventsFile,
    SpanMapFile,
)


def _init_project(tmp_path: Path, *, page_body: str) -> tuple[Path, Path]:
    """Monta `project_root` mínimo (`references/_references.bib`) + `pagina.md`
    com `page_body` (sem frontmatter) — mesmo padrão de `test_review_ingest.py`."""
    project_root = tmp_path
    (project_root / "references").mkdir(parents=True, exist_ok=True)
    (project_root / "references" / "_references.bib").write_text("")
    page = project_root / "pagina.md"
    page.write_text(page_body)
    return project_root, page


def _write_review_dir(
    project_root: Path,
    page: Path,
    *,
    review_body: str,
    events: list[ReviewEvent] | None = None,
    occurrences: list[CiteOccurrence] | None = None,
) -> Path:
    """Grava `reviews/<slug>/{review.md,events.yaml,citemap.json,span-map.json}`
    à mão — simula a saída de `ingest()` (Task 8) sem rodar o pipeline
    adeu/docx. `span-map.json` fica com `fragments=[]`: `apply_review` nunca
    reinverte offsets (I5 — bibliografia é função da fonte, nada a
    transplantar), então o sidecar só precisa existir para `_read_sidecars`
    (reusado de Task 8) não falhar."""
    slug = _slugify(page, project_root)
    review_dir = project_root / "reviews" / slug
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "review.md").write_text(review_body, encoding="utf-8")

    events_file = ReviewEventsFile(page=str(page.relative_to(project_root)), events=events or [])
    (review_dir / "events.yaml").write_text(
        yaml.safe_dump(events_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    citemap = CiteMapFile(
        page=str(page.relative_to(project_root)),
        export_git_sha="deadbee",
        bib_sha256="ab" * 32,
        docx_sha256="cd" * 32,
        occurrences=occurrences or [],
    )
    (review_dir / "citemap.json").write_text(citemap.model_dump_json())

    span_map = SpanMapFile(
        page=str(page.relative_to(project_root)),
        source_sha256=hashlib.sha256(b"irrelevante para apply_review").hexdigest(),
        fragments=[],
    )
    (review_dir / "span-map.json").write_text(span_map.model_dump_json())
    return review_dir


def _events_on_disk(review_dir: Path) -> ReviewEventsFile:
    return ReviewEventsFile.model_validate(yaml.safe_load((review_dir / "events.yaml").read_text()))


# --- 1. accept-all limpa e escreve na página --------------------------------


def test_apply_accept_all_resolves_marks_and_writes_page(tmp_path: Path) -> None:
    prefix = "O paciente recebeu o tratamento"
    suffix = " conforme protocolo estabelecido pela equipe."
    page_body = prefix + suffix
    project_root, page = _init_project(tmp_path, page_body=page_body)
    review_body = prefix + "{++ novo++}{>>autor: Coautor<<}" + suffix
    review_dir = _write_review_dir(project_root, page, review_body=review_body)

    result = apply_review(page=page, accept_all=True, today="2026-07-24", project_root=project_root)

    assert isinstance(result, ApplyResult)
    assert result.applied == 1
    assert result.rejected == 0
    assert result.drops_confirmed == []
    assert result.page == page

    assert page.read_text() == prefix + " novo" + suffix

    events = _events_on_disk(review_dir)
    assert events.events[-1].kind == "applied"
    assert "2026-07-24" in events.events[-1].detail

    # review.md nunca é reescrito pelo apply — permanece para o histórico Git.
    assert (review_dir / "review.md").read_text() == review_body


# --- 2. reject-all restaura o original byte a byte --------------------------


def test_apply_reject_all_restores_original_bytes(tmp_path: Path) -> None:
    page_body = "O paciente recebeu tratamento adequado e cirurgia foi bem sucedida."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    review_body = page_body.replace("adequado ", "{--adequado --}{>>autor: Coautor<<}")
    assert review_body != page_body  # garante que a substituição de fato ocorreu
    _write_review_dir(project_root, page, review_body=review_body)

    result = apply_review(page=page, reject_all=True, today="2026-07-24", project_root=project_root)

    assert result.applied == 0
    assert result.rejected == 1
    assert page.read_text() == page_body


# --- 3. by-author aplica só as do autor -------------------------------------


def test_apply_by_author_applies_only_that_authors_marks(tmp_path: Path) -> None:
    prefix = "Primeira frase da secao"
    mid = " e segunda frase completando o paragrafo"
    suffix = " e concluindo o texto."
    page_body = prefix + mid + suffix
    project_root, page = _init_project(tmp_path, page_body=page_body)
    review_body = (
        prefix + "{++ ALICE++}{>>autor: Alice<<}" + mid + "{++ BOB++}{>>autor: Bob<<}" + suffix
    )
    _write_review_dir(project_root, page, review_body=review_body)

    result = apply_review(
        page=page,
        by_author="Alice",
        author_decision=True,
        today="2026-07-24",
        project_root=project_root,
    )

    assert result.applied == 1
    assert result.rejected == 0
    page_text = page.read_text()
    # Alice foi resolvida (aceita); Bob permanece como marca CriticMarkup
    # intacta (modo parcial — sem Guarda B); a âncora de Bob NUNCA sobrevive,
    # mesmo com a marca dele ainda pendente.
    assert page_text == prefix + " ALICE" + mid + "{++ BOB++}" + suffix
    assert "{>>autor:" not in page_text


# --- 4. drop de citação sem confirmação → hard-fail -------------------------


def _jones_occurrence() -> CiteOccurrence:
    return CiteOccurrence(
        occ_id="00000002",
        citation_id="00000002",
        citekeys=["jones2021"],
        fingerprints={"jones2021": "doi:10.1/jones2021"},
        formatted="(Jones, 2021)",
        norm_start=0,
        norm_end=1,
    )


def _jones_drop_event() -> ReviewEvent:
    return ReviewEvent(
        kind="citation-drop",
        detail="citação (occ 00000002, citekeys jones2021) deletada no Word — confirme no apply.",
        occ_id="00000002",
        citekeys=["jones2021"],
    )


def test_apply_citation_drop_without_confirmation_hard_fails(tmp_path: Path) -> None:
    page_body = "Outro estudo [[@jones2021]] confirmou o achado."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    _write_review_dir(
        project_root,
        page,
        review_body=page_body,  # citação intocada em review.md — ingest nunca a transplanta
        events=[_jones_drop_event()],
        occurrences=[_jones_occurrence()],
    )

    with pytest.raises(ValueError) as exc:
        apply_review(page=page, accept_all=True, today="2026-07-24", project_root=project_root)

    message = str(exc.value)
    assert "00000002" in message
    assert "--confirm-citation-drops" in message

    # hard-fail antes de qualquer write-back.
    assert page.read_text() == page_body


# --- 5. com confirmação → página sem a citação e conservação ok ------------


def test_apply_confirmed_citation_drop_removes_citation_and_conserves(tmp_path: Path) -> None:
    page_body = "Outro estudo [[@jones2021]] confirmou o achado."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    # o humano já removeu a referência à citação em review.md (é o único
    # jeito de a citação de fato sair do corpo — o apply nunca transplanta
    # citação; só verifica a conservação do que está em review.md, I5).
    edited_review_body = "Outro estudo confirmou o achado."
    review_dir = _write_review_dir(
        project_root,
        page,
        review_body=edited_review_body,
        events=[_jones_drop_event()],
        occurrences=[_jones_occurrence()],
    )

    result = apply_review(
        page=page,
        accept_all=True,
        confirm_citation_drops=["00000002"],
        today="2026-07-24",
        project_root=project_root,
    )

    assert result.drops_confirmed == ["00000002"]
    assert page.read_text() == "Outro estudo confirmou o achado."
    assert "jones2021" not in page.read_text()

    events = _events_on_disk(review_dir)
    applied_event = events.events[-1]
    assert applied_event.kind == "applied"
    assert "2026-07-24" in applied_event.detail


def test_apply_confirmed_citation_drop_without_removing_from_review_md_raises_conservation_error(
    tmp_path: Path,
) -> None:
    """Auto-review edge case: confirmar o drop não remove a citação por
    mágica — se o humano esqueceu de editar `review.md`, a citação ainda
    aparece no corpo final e a conservação pós-apply pega isso."""
    page_body = "Outro estudo [[@jones2021]] confirmou o achado."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    _write_review_dir(
        project_root,
        page,
        review_body=page_body,  # NÃO editado — citação ainda presente
        events=[_jones_drop_event()],
        occurrences=[_jones_occurrence()],
    )

    with pytest.raises(CitationConservationError) as exc:
        apply_review(
            page=page,
            accept_all=True,
            confirm_citation_drops=["00000002"],
            today="2026-07-24",
            project_root=project_root,
        )

    assert "jones2021" in str(exc.value)


# --- 6. marca residual forjada → MarkLostError ------------------------------


def test_apply_forged_residual_mark_raises_mark_lost_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guarda B (apply-side): monkeypatch em `criticmarkup.apply` (seam já
    usado pelo próprio módulo) simula uma decisão que não resolveu nenhuma
    marca de verdade — a contagem não fecha (marcas ainda presentes no corpo
    final) e a função aborta com `MarkLostError` ANTES de qualquer
    write-back."""
    page_body = "Frase de prosa pura para o teste da guarda B."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    review_body = "Frase de {++prosa pura++}{>>autor: Coautor<<} para o teste da guarda B."
    _write_review_dir(project_root, page, review_body=review_body)

    monkeypatch.setattr(criticmarkup, "apply", lambda text, decisions: text)

    with pytest.raises(MarkLostError) as exc:
        apply_review(page=page, accept_all=True, today="2026-07-24", project_root=project_root)

    assert "prosa pura" in str(exc.value)

    # hard-fail antes de qualquer write-back.
    assert page.read_text() == page_body


# --- 7. exatamente um modo de decisão — senão ValueError pt-BR --------------


def test_apply_requires_exactly_one_decision_mode(tmp_path: Path) -> None:
    page_body = "Pagina sem nenhuma marca, só para testar validacao de modo."
    project_root, page = _init_project(tmp_path, page_body=page_body)
    _write_review_dir(project_root, page, review_body=page_body)

    with pytest.raises(ValueError):
        apply_review(page=page, today="2026-07-24", project_root=project_root)

    with pytest.raises(ValueError):
        apply_review(
            page=page,
            accept_all=True,
            reject_all=True,
            today="2026-07-24",
            project_root=project_root,
        )
