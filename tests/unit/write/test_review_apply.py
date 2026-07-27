"""`apply_review()` — decisões por marca/autor, drops e write-back (Task 9).

Scaffold e sidecars via fixtures compartilhadas de `tests/unit/conftest.py`
(`init_project`/`write_review_artifacts` — achado do /simplify; a convenção
"cada arquivo tem seu próprio builder" segue valendo só para builders de
docx-zip, que este arquivo nem usa).
`review.md`/`events.yaml`/`citemap.json`/`span-map.json` são escritos à mão
simulando a saída de `ingest()` (Task 8) — sem rodar o pipeline adeu/docx de
verdade: o que importa aqui é o CONTRATO de `apply_review` (decisões,
guardas, conservação, write-back), já coberto em `test_review_ingest.py` na
outra ponta. `review.md` é escrito com a âncora `{>>prumo-autor: X<<}` já
colada depois de cada marca (per Task 9 — decisão do controller: âncora-
autor é como a autoria sobrevive no CriticMarkup puro; nunca vai para a
página final; prefixo `prumo-` — Fix pós-review, achado Menor — evita
colisão com um comentário humano genuíno `{>>autor: ...<<}`)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from prumo_assist.core import criticmarkup
from prumo_assist.domains.write.review import (
    ApplyResult,
    CitationConservationError,
    MarkLostError,
    ProposalResult,
    _reject_citation_divergence,
    apply_review,
    propose_prose_edit,
)
from prumo_assist.domains.write.schemas.v1 import (
    CiteOccurrence,
    ReviewEvent,
    ReviewEventsFile,
)
from tests.unit.conftest import InitProject, WriteReviewArtifacts


def _events_on_disk(review_dir: Path) -> ReviewEventsFile:
    return ReviewEventsFile.model_validate(yaml.safe_load((review_dir / "events.yaml").read_text()))


# --- 1. accept-all limpa e escreve na página --------------------------------


def test_apply_accept_all_resolves_marks_and_writes_page(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    prefix = "O paciente recebeu o tratamento"
    suffix = " conforme protocolo estabelecido pela equipe."
    page_body = prefix + suffix
    project_root, page = init_project(body=page_body)
    review_body = prefix + "{++ novo++}{>>prumo-autor: Coautor<<}" + suffix
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

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

    # `review.md` TAMBÉM é reescrito (Fix pós-review, achado Crítico 2 —
    # worklist viva): `accept_all` decide TODAS as marcas, então nada fica
    # pendente e `review.md` termina igual à página (sem marca nem âncora
    # restante) — nunca mais o `review_body` cru original.
    assert (review_dir / "review.md").read_text() == page.read_text()


# --- 2. reject-all restaura o original byte a byte --------------------------


def test_apply_reject_all_restores_original_bytes(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "O paciente recebeu tratamento adequado e cirurgia foi bem sucedida."
    project_root, page = init_project(body=page_body)
    review_body = page_body.replace("adequado ", "{--adequado --}{>>prumo-autor: Coautor<<}")
    assert review_body != page_body  # garante que a substituição de fato ocorreu
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

    result = apply_review(page=page, reject_all=True, today="2026-07-24", project_root=project_root)

    assert result.applied == 0
    assert result.rejected == 1
    assert page.read_text() == page_body
    # `reject_all` também decide TODAS as marcas — `review.md` (worklist)
    # termina sem marca nem âncora restante, igual à página.
    assert (review_dir / "review.md").read_text() == page_body


# --- 3. by-author aplica só as do autor -------------------------------------


def test_apply_by_author_applies_only_that_authors_marks(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    prefix = "Primeira frase da secao"
    mid = " e segunda frase completando o paragrafo"
    suffix = " e concluindo o texto."
    page_body = prefix + mid + suffix
    project_root, page = init_project(body=page_body)
    review_body = (
        prefix
        + "{++ ALICE++}{>>prumo-autor: Alice<<}"
        + mid
        + "{++ BOB++}{>>prumo-autor: Bob<<}"
        + suffix
    )
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

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
    # intacta (modo parcial — sem Guarda B); a âncora de Bob NUNCA sobrevive
    # à PÁGINA, mesmo com a marca dele ainda pendente.
    assert page_text == prefix + " ALICE" + mid + "{++ BOB++}" + suffix
    assert "{>>prumo-autor:" not in page_text

    # `review.md` (worklist viva — Fix pós-review, Crítico 2): Alice também
    # resolvida ali (idêntico à página para essa parte), mas a marca do Bob
    # MANTÉM sua âncora — é o que permite uma chamada `by_author="Bob"`
    # FUTURA ainda localizá-lo (ver o repro end-to-end mais abaixo).
    review_md_text = (review_dir / "review.md").read_text()
    assert review_md_text == prefix + " ALICE" + mid + "{++ BOB++}{>>prumo-autor: Bob<<}" + suffix


# --- 3b. repro do reviewer (Crítico 2): applies parciais sequenciais NÃO ----
#         revertem decisões anteriores -----------------------------------


def test_apply_sequential_by_author_calls_do_not_revert_earlier_decisions(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Repro end-to-end do reviewer (sem mocks): Alice e Bob intercalados;
    apply `by_author=Alice accept` seguido de apply `by_author=Bob accept`
    — a página final tem AMBAS resolvidas (nunca a marca crua da Alice de
    volta) e `review.md`, após a 2a chamada, fica sem marca restante.

    Antes do fix (Crítico 2), a 2a chamada reconstruía a página inteira a
    partir do `review.md` ORIGINAL (nunca consumido) — como só a decisão do
    Bob entrava nessa chamada, a marca da Alice (já resolvida na 1a chamada)
    reaparecia CRUA (`{++ ALICE++}`) na página final."""
    prefix = "Primeira frase da secao"
    mid = " e segunda frase completando o paragrafo"
    suffix = " e concluindo o texto."
    page_body = prefix + mid + suffix
    project_root, page = init_project(body=page_body)
    review_body = (
        prefix
        + "{++ ALICE++}{>>prumo-autor: Alice<<}"
        + mid
        + "{++ BOB++}{>>prumo-autor: Bob<<}"
        + suffix
    )
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

    result1 = apply_review(
        page=page,
        by_author="Alice",
        author_decision=True,
        today="2026-07-24",
        project_root=project_root,
    )
    assert result1.applied == 1
    # estado intermediário: Alice resolvida, Bob ainda pendente.
    assert page.read_text() == prefix + " ALICE" + mid + "{++ BOB++}" + suffix

    result2 = apply_review(
        page=page,
        by_author="Bob",
        author_decision=True,
        today="2026-07-24",
        project_root=project_root,
    )
    assert result2.applied == 1

    final_text = page.read_text()
    assert final_text == prefix + " ALICE" + mid + " BOB" + suffix
    assert "{++" not in final_text  # nunca a marca crua da Alice de volta
    assert "{>>" not in final_text

    # review.md, após a 2a chamada, sem marcas (nem âncoras) restantes.
    review_md_final = (review_dir / "review.md").read_text()
    assert criticmarkup.parse(review_md_final) == []
    assert review_md_final == final_text


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


def test_apply_citation_drop_without_confirmation_hard_fails(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Outro estudo [@jones2021] confirmou o achado."
    project_root, page = init_project(body=page_body)
    write_review_artifacts(
        project_root,
        page,
        review_md=page_body,  # citação intocada em review.md — ingest nunca a transplanta
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


def test_apply_confirmed_citation_drop_removes_citation_and_conserves(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Outro estudo [@jones2021] confirmou o achado."
    project_root, page = init_project(body=page_body)
    # o humano já removeu a referência à citação em review.md (é o único
    # jeito de a citação de fato sair do corpo — o apply nunca transplanta
    # citação; só verifica a conservação do que está em review.md, I5).
    edited_review_body = "Outro estudo confirmou o achado."
    review_dir = write_review_artifacts(
        project_root,
        page,
        review_md=edited_review_body,
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
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Auto-review edge case: confirmar o drop não remove a citação por
    mágica — se o humano esqueceu de editar `review.md`, a citação ainda
    aparece no corpo final e a conservação pós-apply pega isso."""
    page_body = "Outro estudo [@jones2021] confirmou o achado."
    project_root, page = init_project(body=page_body)
    write_review_artifacts(
        project_root,
        page,
        review_md=page_body,  # NÃO editado — citação ainda presente
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
    init_project: InitProject,
    write_review_artifacts: WriteReviewArtifacts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarda B (apply-side): monkeypatch em `criticmarkup.apply` (seam já
    usado pelo próprio módulo) simula uma decisão que não resolveu nenhuma
    marca de verdade — a contagem não fecha (marcas ainda presentes no corpo
    final) e a função aborta com `MarkLostError` ANTES de qualquer
    write-back."""
    page_body = "Frase de prosa pura para o teste da guarda B."
    project_root, page = init_project(body=page_body)
    review_body = "Frase de {++prosa pura++}{>>prumo-autor: Coautor<<} para o teste da guarda B."
    write_review_artifacts(project_root, page, review_md=review_body)

    monkeypatch.setattr(criticmarkup, "apply", lambda text, decisions: text)

    with pytest.raises(MarkLostError) as exc:
        apply_review(page=page, accept_all=True, today="2026-07-24", project_root=project_root)

    assert "prosa pura" in str(exc.value)

    # hard-fail antes de qualquer write-back.
    assert page.read_text() == page_body


# --- 7. exatamente um modo de decisão — senão ValueError pt-BR --------------


def test_apply_requires_exactly_one_decision_mode(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Pagina sem nenhuma marca, só para testar validacao de modo."
    project_root, page = init_project(body=page_body)
    write_review_artifacts(project_root, page, review_md=page_body)

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


# --- 8. modo marks={i: bool} — mistura accept/reject por índice (Important) -


def test_apply_marks_by_index_mixed_accept_reject(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Achado Importante do review: modo `marks={i: bool}` não tinha
    cobertura própria. 2 marcas de conteúdo (um `ins`, um `del`) na MESMA
    chamada — índice 0 aceito, índice 1 rejeitado — exercitando a mistura na
    mesma chamada (índice ignora âncoras, é a posição entre as marcas
    DECIDÍVEIS)."""
    prefix = "Frase base"
    mid = " ainda sem revisao"
    suffix = " ate aqui."
    page_body = prefix + mid + suffix
    project_root, page = init_project(body=page_body)
    review_body = (
        prefix
        + "{++ NOVO++}{>>prumo-autor: Alice<<}"
        + "{--"
        + mid
        + "--}{>>prumo-autor: Bob<<}"
        + suffix
    )
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

    result = apply_review(
        page=page,
        marks={0: True, 1: False},
        today="2026-07-24",
        project_root=project_root,
    )

    assert result.applied == 1
    assert result.rejected == 1
    assert result.drops_confirmed == []

    page_text = page.read_text()
    # índice 0 (ins da Alice) aceito -> "NOVO" inserido; índice 1 (del do
    # Bob) rejeitado -> mantém o texto original (a deleção não vinga).
    assert page_text == prefix + " NOVO" + mid + suffix
    assert "{>>prumo-autor:" not in page_text
    assert "{++" not in page_text
    assert "{--" not in page_text

    # as duas marcas foram decididas nesta única chamada -> review.md
    # (worklist) também termina sem marca nem âncora restante.
    assert (review_dir / "review.md").read_text() == page_text


# --- 9. drop de citação confirmado sobrevive a uma 2a chamada ---------------
#        (sem re-confirmação, sem falso positivo de conservação) -----------


def test_apply_second_call_after_confirmed_drop_needs_no_reconfirmation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Achado Crítico 2 (parte do fix de `events.yaml` consumido): depois de
    uma chamada confirmar um `citation-drop`, uma 2a chamada (mesmo sem
    NENHUM `--confirm-citation-drops`) não é bloqueada por confirmação
    pendente E a conservação pós-apply continua correta (o multiconjunto
    "já confirmado" soma o HISTÓRICO do evento `applied` da 1a chamada, não
    só o `citation-drop` pendente desta — que já não existe)."""
    prefix = "Primeiro paragrafo. Segundo estudo "
    suffix = " confirmou."
    page_body = prefix + "[@jones2021]" + suffix
    project_root, page = init_project(body=page_body)
    # humano já removeu a referência à citação em review.md, e há 1 marca de
    # prosa pendente (Alice) ao lado — mesmo padrão dos outros testes de drop.
    edited_review_body = prefix + "{++ EXTRA++}{>>prumo-autor: Alice<<}" + suffix
    review_dir = write_review_artifacts(
        project_root,
        page,
        review_md=edited_review_body,
        events=[_jones_drop_event()],
        occurrences=[_jones_occurrence()],
    )

    result1 = apply_review(
        page=page,
        by_author="Alice",
        author_decision=True,
        confirm_citation_drops=["00000002"],
        today="2026-07-24",
        project_root=project_root,
    )
    assert result1.drops_confirmed == ["00000002"]
    assert "jones2021" not in page.read_text()

    events_after_1 = _events_on_disk(review_dir)
    # o `citation-drop` pendente foi consumido (removido) — só o histórico
    # no evento `applied` sobrevive.
    assert [e.kind for e in events_after_1.events] == ["applied"]

    # 2a chamada: SEM `confirm_citation_drops` — não deveria ser exigido de
    # novo (nada mais pendente) nem quebrar a conservação (o jones2021 já
    # saiu do corpo desde a 1a chamada; o histórico precisa cobrir isso).
    result2 = apply_review(
        page=page, accept_all=True, today="2026-07-24", project_root=project_root
    )
    assert result2.applied == 0  # nada mais para decidir
    assert result2.drops_confirmed == []
    assert "jones2021" not in page.read_text()


# =============================================================================
# propose_prose_edit() — Fase 3/Task 2: proposta do agente vira marca
# pendente no worklist (I1/I3b)
# =============================================================================
#
# `write_review_artifacts` (conftest) é reusado tal qual — `propose_prose_edit` só
# toca `review.md`; `citemap.json`/`span-map.json` continuam existindo só
# para satisfazer o formato de `reviews/<slug>/`, nunca lidos por esta
# função (ela nunca decide nada sobre citação, só recusa qualquer proposta
# que a toque — ver testes I1/I3b abaixo).


# --- 10. ins after com âncora única -> worklist ganha marca+âncora, e ------
#         `apply(by_author="agente")` aplica (E2E curto reusando fluxo T9) --


def test_propose_prose_edit_ins_after_unique_anchor_then_apply_by_author_agente(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    prefix = "Frase base do paragrafo"
    suffix = " que continua depois da ancora."
    page_body = prefix + suffix
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    result = propose_prose_edit(
        page=page,
        anchor_excerpt="paragrafo",
        position="after",
        kind="ins",
        b=" extra",
        project_root=project_root,
    )

    assert isinstance(result, ProposalResult)
    assert result.review_md == review_dir / "review.md"

    review_md_text = result.review_md.read_text()
    assert review_md_text == prefix + "{++ extra++}{>>prumo-autor: agente<<}" + suffix
    marks = criticmarkup.parse(review_md_text)
    inserted = marks[result.inserted_mark_index]
    assert inserted.kind == "ins"
    assert inserted.b == " extra"

    # a proposta é uma marca PENDENTE — a página original não muda até um
    # humano decidir via apply_review (aqui, `by_author="agente"`, o mesmo
    # autor default da proposta).
    assert page.read_text() == page_body

    apply_result = apply_review(
        page=page,
        by_author="agente",
        author_decision=True,
        today="2026-07-24",
        project_root=project_root,
    )

    assert apply_result.applied == 1
    assert page.read_text() == prefix + " extra" + suffix
    assert (review_dir / "review.md").read_text() == page.read_text()


# --- 11. âncora ausente (0 ocorrências) -> ValueError pt-BR -----------------


def test_propose_prose_edit_anchor_not_found_raises(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Texto qualquer sem a ancora pedida."
    project_root, page = init_project(body=page_body)
    write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="não existe em lugar nenhum deste texto",
            position="after",
            kind="ins",
            b=" x",
            project_root=project_root,
        )

    assert "não encontrada" in str(exc.value)
    # hard-fail antes de qualquer escrita.
    assert page.read_text() == page_body


# --- 12. âncora ambígua (>1 ocorrência) -> ValueError pt-BR -----------------


def test_propose_prose_edit_ambiguous_anchor_raises(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "repete repete no mesmo texto."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="repete",
            position="after",
            kind="ins",
            b=" x",
            project_root=project_root,
        )

    assert "ambígua" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 13. payload com citekey/sintaxe de citação -> recusa I3b ---------------


def test_propose_prose_edit_rejects_citation_payload_i3b(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Frase-alvo para a proposta aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Frase-alvo",
            position="after",
            kind="ins",
            b=" conforme [@smith2020]",
            project_root=project_root,
        )

    assert "I3b" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 15. replace com kind != del/sub OU a != excerto -> erro ----------------


def test_propose_prose_edit_replace_requires_del_or_sub_kind_and_matching_a(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    page_body = "Frase-alvo para a proposta aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Frase-alvo",
            position="replace",
            kind="ins",  # kind errado para replace
            b=" outro texto",
            project_root=project_root,
        )
    assert "replace" in str(exc.value)

    with pytest.raises(ValueError):
        propose_prose_edit(
            page=page,
            anchor_excerpt="Frase-alvo",
            position="replace",
            kind="sub",
            a="outra coisa",  # `a` diverge do anchor_excerpt
            b="Frase-alvo",
            project_root=project_root,
        )

    assert (review_dir / "review.md").read_text() == page_body


# --- 16. self-review: marca nova identificada por POSIÇÃO, não conteúdo ----
#         (corpo já tem uma marca de conteúdo IDÊNTICO à proposta nova) -----


def test_propose_prose_edit_identifies_inserted_mark_by_position_not_content(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Achado do brief (Context): `inserted_mark_index` precisa ser calculado
    por POSIÇÃO de inserção, nunca por igualdade de conteúdo — uma busca por
    conteúdo (`kind=="ins" and b==" extra"`) acharia a marca PRÉ-EXISTENTE
    (índice 0), não a nova (índice 2), porque as duas têm texto idêntico."""
    pre_existing_mark = "{++ extra++}{>>prumo-autor: agente<<}"
    page_body = "Primeiro trecho. Segundo trecho-alvo aqui."
    review_body = "Primeiro trecho." + pre_existing_mark + " Segundo trecho-alvo aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=review_body)

    result = propose_prose_edit(
        page=page,
        anchor_excerpt="trecho-alvo",
        position="after",
        kind="ins",
        b=" extra",  # MESMO payload da marca pré-existente, de propósito
        project_root=project_root,
    )

    review_md_text = (review_dir / "review.md").read_text()
    marks = criticmarkup.parse(review_md_text)
    # 4 marcas ao todo: [pré-existente ins, pré-existente comment, NOVA ins, NOVA comment].
    assert len(marks) == 4
    assert result.inserted_mark_index == 2
    new_mark = marks[result.inserted_mark_index]
    assert new_mark.kind == "ins"
    assert new_mark.b == " extra"
    # a marca nova fica DEPOIS da pré-existente no texto — nunca a confunde
    # com ela mesma só porque o conteúdo bate.
    assert new_mark.start > marks[1].end


# --- 17. self-review: tangência do OUTRO lado (âncora logo APÓS a citação) -


def test_propose_prose_edit_rejects_anchor_immediately_after_citation_i1(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Completa a cobertura da fronteira estrita da Guarda I1: o teste 23
    cobre `end == cs` (âncora termina onde a citação começa); este cobre
    `ce == start` (âncora começa onde a citação termina) — sem espaço algum
    entre a citação e a vírgula que seria a âncora."""
    page_body = "Ver [@jones2021], confirmando o achado."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt=",",
            position="before",
            kind="ins",
            b=" (grifo nosso)",
            project_root=project_root,
        )

    assert "I1" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 18. self-review: corpo pré-existente malformado -> hard-fail ANTES ----
#         de qualquer escrita (achado do self-review, não do brief) --------


def test_propose_prose_edit_malformed_preexisting_body_raises_before_any_write(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Achado do self-review: `inserted_mark_index` era recalculado via
    `criticmarkup.parse(new_body)` DEPOIS de `review_md_path.write_text(...)`
    — se o corpo PRÉ-EXISTENTE de `review.md` já tivesse uma marca
    malformada (ex.: humano no meio de uma edição manual, `{++` sem
    fechamento), o arquivo já teria sido escrito quando o `ValueError` do
    parse aparecesse, violando "hard-fail antes de qualquer escrita". Fix:
    o re-parse agora acontece ANTES do `write_text`. Este teste around a
    marca JÁ malformada, sem relação nenhuma com a âncora proposta."""
    malformed_review_body = "Texto com marca-alvo {++ nao fechada corretamente."
    page_body = "Texto com marca-alvo  nao fechada corretamente."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=malformed_review_body)

    with pytest.raises(ValueError):
        propose_prose_edit(
            page=page,
            anchor_excerpt="marca-alvo",
            position="after",
            kind="ins",
            b=" x",
            project_root=project_root,
        )

    # a escrita NUNCA aconteceu — review.md permanece byte a byte o mesmo.
    assert (review_dir / "review.md").read_text() == malformed_review_body


# =============================================================================
# Fix pós-review (2 Críticos + 1 Important) — guardas validavam INPUTS em
# isolamento (a/b, body original), nunca o RESULTADO da composição. Ver
# comentário de `_reject_citation_divergence`/`_reject_composed_result` em
# `review.py` para a arquitetura completa do round-trip guard.
# =============================================================================

# --- 19. Crítico 1 (repro do reviewer): `author` hostil injeta delimitador --
#         e deixa texto livre (inclusive citação fabricada) no worklist -----


def test_propose_prose_edit_rejects_author_delimiter_injection(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """`author` é colado SEM escape em `"{>>prumo-autor: " + author + "<<}"`
    — um `author` hostil (`"agente<<} [@injetado] {>>x"`) fecha a âncora
    PREMATURAMENTE (`<<}`), solta `"[@injetado] {>>x"` como texto LIVRE
    (não marcado — inclusive uma citação fabricada) no corpo do worklist, e
    reabre um comentário (`{>>x`) que consumiria o resto do corpo. A
    allowlist de `author` recusa ANTES de qualquer leitura/escrita."""
    page_body = "Frase-alvo para a proposta aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Frase-alvo",
            position="after",
            kind="ins",
            b=" extra",
            author="agente<<} [@injetado] {>>x",
            project_root=project_root,
        )

    assert "author inválido" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 20. Crítico 2 (repro do reviewer): payload inofensivo ISOLADO completa
#         citação pré-existente ao compor com o corpo -----------------------


def test_propose_prose_edit_rejects_composition_that_fabricates_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """`b="[["` sozinho não bate em NENHUMA guarda de entrada: não tem `@`,
    não tem `[@`/`[[@`, e o corpo original (`"Prefixo @fake2020]] sufixo"`)
    não tem `[[@...]]` nenhum (falta o `[[` de abertura). Ao aceitar a
    proposta (`criticmarkup.accept`), o `"[["` ficaria adjacente ao
    `"@fake2020]]"` pré-existente e COMPLETARIA uma citação `[[@fake2020]]`
    nunca cunhada por humano — mas desde que a narrativa `@key` virou átomo
    protegido (D2), a Guarda I1 já recusa a âncora `position="before"`
    colada em `@fake2020` ANTES disso: ela roda mais cedo que o round-trip
    guard (`_reject_citation_divergence`/`_reject_composed_result`), que
    fica como defesa em profundidade atrás dela para qualquer composição
    que I1 não alcance (ver Teste 27, que exercita essa defesa
    diretamente)."""
    page_body = "Prefixo @fake2020]] sufixo"
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="@fake2020",
            position="before",
            kind="ins",
            b="[[",
            project_root=project_root,
        )

    assert "I1" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 21. author unicode legítimo (nome próprio de coautor humano) -> aceita -


def test_propose_prose_edit_accepts_legitimate_unicode_author(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """A allowlist cobre letras acentuadas (`À-ÿ`) — um `author` real de
    coautor humano (ex.: alguém rodando a skill em nome de "José da Silva")
    continua sendo aceito, não só ASCII puro."""
    page_body = "Frase-alvo para a proposta aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    result = propose_prose_edit(
        page=page,
        anchor_excerpt="Frase-alvo",
        position="after",
        kind="ins",
        b=" extra",
        author="José da Silva",
        project_root=project_root,
    )

    assert isinstance(result, ProposalResult)
    review_md_text = (review_dir / "review.md").read_text()
    assert (
        review_md_text
        == "Frase-alvo{++ extra++}{>>prumo-autor: José da Silva<<} para a proposta aqui."
    )


# --- 22. Important: kind="comment" não é proponível (órfã, perde autoria) --


def test_propose_prose_edit_rejects_kind_comment(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """`kind="comment"` não é pareável por `_pair_author_anchors` (Task 9):
    uma marca `comment` sem marca de CONTEÚDO associada vira âncora ÓRFÃ e
    perde a autoria. Recusado explicitamente mesmo com o tipo estático
    (`Literal["ins","del","sub"]`) já excluindo `"comment"` — uma chamada
    que bypassa o type-checker (MCP/`**kwargs`) ainda pode passar a string
    em runtime."""
    page_body = "Frase-alvo para a proposta aqui."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Frase-alvo",
            position="after",
            kind="comment",  # type: ignore[arg-type]
            b=" observação",
            project_root=project_root,
        )

    assert "comment" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 23. Guarda I1 em sintaxe Pandoc `[@key]` (projeto Zettlr-front) -------


def test_propose_prose_edit_rejects_anchor_tangent_to_pandoc_citation_i1(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Guarda I1 na fronteira estrita ``end == cs`` (âncora termina exatamente
    onde a citação começa), gramática Pandoc única do repo (spec 2026-07-22):
    a citação se escreve ``[@key]``. Par do teste 17 (``ce == start``, o
    outro lado da fronteira)."""
    page_body = "Estudo anterior [@jones2021] confirmou o achado."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="anterior ",  # termina exatamente onde a citação começa
            position="after",
            kind="ins",
            b=" recente",
            project_root=project_root,
        )

    assert "I1" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 24. composição de citação em sintaxe Pandoc -> recusa (D1) -------------


def test_propose_prose_edit_rejects_pandoc_composition_that_fabricates_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Par Pandoc de `test_..._rejects_composition_that_fabricates_citation`.

    O agente insere só `[` para embrulhar a narrativa `@fake2020` num grupo
    `[@fake2020]` — citação que humano nenhum cunhou. Desde que a citação
    narrativa `@key` virou átomo protegido (`_citation_atom_spans`), a
    Guarda I1 (`_reject_anchor_tangent_to_citation`) já recusa ANTES de
    `propose_prose_edit` chegar a compor o resultado: a âncora `"Prefixo "`
    termina exatamente onde `@fake2020` começa (tangência, distância zero).
    A terceira sub-checagem de `_reject_citation_divergence` (multiconjunto
    de GRUPOS de citação) é defesa em profundidade — fica atrás da I1 neste
    caminho e nunca chega a rodar aqui; sua cobertura DIRETA, isolada da
    ordem das guardas, vive na seção 27 (`test_reject_citation_divergence_*`,
    que chama a sub-checagem sem passar por `propose_prose_edit`).
    """
    page_body = "Prefixo @fake2020] sufixo."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Prefixo ",
            position="after",
            kind="ins",
            b="[",
            project_root=project_root,
        )

    assert "I1 — citação é átomo" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 25. colchete legítimo longe de citação NÃO é "citação fabricada" ------


def test_propose_prose_edit_allows_bracket_far_from_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Guarda D1 compara grupos de citação, não colchetes: `[sic]` num
    parágrafo que tem `[@k2020]` noutro ponto é edição legítima de prosa."""
    page_body = "Primeira frase com [@k2020] aqui. Segunda frase separada."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    result = propose_prose_edit(
        page=page,
        anchor_excerpt="Segunda frase",
        position="after",
        kind="ins",
        b=" [sic]",
        project_root=project_root,
    )

    written = (review_dir / "review.md").read_text()
    assert written == (
        "Primeira frase com [@k2020] aqui. Segunda frase{++ [sic]++}"
        "{>>prumo-autor: agente<<} separada."
    )
    # A citação pré-existente sai íntegra nos DOIS desfechos da marca.
    assert "[@k2020]" in criticmarkup.accept(written)
    assert "[@k2020]" in criticmarkup.reject(written)
    assert criticmarkup.parse(written)[result.inserted_mark_index].b == " [sic]"


# --- 26. Guarda I1 protege narrativa igual a bracketed (D2) ----------------


def test_propose_prose_edit_rejects_anchor_tangent_to_narrative_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Par narrativa-vs-bracketed no MESMO documento: a MESMA edição colada
    no fim de cada átomo tem de ter o MESMO veredito. Antes deste fix, a
    narrativa era aceita e chegava à página."""
    page_body = "Como @smith2024 mostrou, ver tambem [@jones2020]."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Como @smith2024",
            position="after",
            kind="ins",
            b=" [sic]",
            project_root=project_root,
        )

    assert "I1" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


# --- 27. terceira checagem de conservação, isolada da ordem das guardas ----


def test_reject_citation_divergence_pega_grupo_composto() -> None:
    """A terceira sub-checagem (Task 1) é defesa em profundidade atrás da
    I1: desde que a narrativa virou átomo protegido, a I1 recusa antes em
    todo cenário de composição alcançável por `propose_prose_edit`. Este
    teste a exercita DIRETAMENTE, para que a guarda não fique sem cobertura
    caso a ordem upstream mude de novo."""
    antes = "Como discute @silva2020, o desfecho melhora."
    depois = "Como discute [@silva2020], o desfecho melhora."

    with pytest.raises(ValueError) as exc:
        _reject_citation_divergence(antes, depois)

    assert "GRUPOS de citação" in str(exc.value)


def test_reject_citation_divergence_permite_prosa_sem_mexer_em_citacao() -> None:
    antes = "Frase [@k2020] aqui. Outra frase."
    depois = "Frase [@k2020] aqui. Outra frase [sic]."

    _reject_citation_divergence(antes, depois)  # não levanta


# --- 28. conservação também no caminho de REJEIÇÃO (achado C1) -------------


def test_propose_prose_edit_rejects_del_that_fabricates_citation_on_reject(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Achado C1: a guarda de conservação simulava só o ACEITE.

    Uma marca ``{--@--}`` colada antes de `Smith2020` (token que NÃO é
    citação — não tem sigilo) é invisível no aceite (o `@` some, corpo
    idêntico) e fabrica `@Smith2020` na REJEIÇÃO — citekey que humano
    nenhum cunhou, injetada justamente quando o humano REJEITA a proposta
    do agente. Nem a I1 (não há citação no corpo para tangenciar), nem a
    I3b (`a="@"` sozinho não casa `CITEKEY_RE`), nem `apply_review`
    (`_citekey_multiset` é marked-only) pegavam.
    """
    page_body = "Segundo Smith2020, o efeito e claro."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Segundo ",
            position="after",
            kind="del",
            a="@",
            project_root=project_root,
        )

    assert "rejeição" in str(exc.value)
    assert "Smith2020" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body


def test_reject_citation_divergence_reporta_o_lado_que_divergiu() -> None:
    """A mensagem diz QUAL simulação divergiu — sem isso o humano não sabe
    se o problema está no aceite ou na rejeição da proposta."""
    with pytest.raises(ValueError) as exc:
        _reject_citation_divergence("Segundo Smith2020.", "Segundo @Smith2020.", moment="aceite")

    assert "aceite" in str(exc.value)
