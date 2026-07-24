"""Localizador de âncora única (`locate_marks_in_norm`) — Task 6 da ponte Fase 2.

Fixtures LOCAIS (`_occ`/`_citemap`), não importadas de `test_review_reader.py`:
o `_occ` de lá fixa `norm_start=0, norm_end=1` (irrelevante para
`check_conservation`, que só olha citekeys/fingerprints) — aqui `norm_start`/
`norm_end` são o cerne do teste (posição real da citação no `norm_text`),
então cada teste precisa controlá-los. Mesmo racional de
`test_review_guards.py` ("builder LOCAL, não reusa test_review_reader.py"
quando o formato da fixture diverge).

`ReviewMark`s são construídas DIRETO (dataclass), sem rodar
`parse_adeu_markdown` — per brief da Task 6: o que importa aqui é o
contrato de `locate_marks_in_norm` (offsets em `clean_text`), não o parser
da Task 4 (já coberto em `test_review_adeu.py`). `clean_text`/`norm_text`
são montados por CONCATENAÇÃO de variáveis Python (nunca índices contados à
mão) para que os offsets de cada `ReviewMark` sejam sempre exatos.
"""

from __future__ import annotations

from prumo_assist.domains.write.review import (
    DocxCitation,
    LocatedMark,
    ReviewMark,
    locate_marks_in_norm,
)
from prumo_assist.domains.write.schemas.v1 import CiteMapFile, CiteOccurrence


def _occ(
    *,
    occ_id: str,
    citekeys: list[str],
    formatted: str,
    norm_start: int,
    norm_end: int,
) -> CiteOccurrence:
    """Ocorrência do citemap com `norm_start`/`norm_end` explícitos — ao
    contrário do `_occ` de `test_review_reader.py` (que fixa `0, 1`), aqui a
    posição real no `norm_text` é o que o teste exercita."""
    return CiteOccurrence(
        occ_id=occ_id,
        citation_id=occ_id,
        citekeys=citekeys,
        fingerprints={key: f"doi:10.1/{key}" for key in citekeys},
        formatted=formatted,
        norm_start=norm_start,
        norm_end=norm_end,
    )


def _citemap(occurrences: list[CiteOccurrence]) -> CiteMapFile:
    """Citemap mínimo — só `occurrences` importa para `locate_marks_in_norm`."""
    return CiteMapFile(
        page="docs/page.md",
        export_git_sha="deadbee",
        bib_sha256="ab" * 32,
        docx_sha256="cd" * 32,
        occurrences=occurrences,
    )


def _deleted(*, occ_id: str, citekeys: list[str], formatted: str) -> DocxCitation:
    """`DocxCitation` no estado `deleted` — mesma forma que
    `check_conservation` (Task 2) devolve na lista `deleted`."""
    return DocxCitation(
        occ_id=occ_id,
        citation_id=occ_id,
        citekeys=tuple(citekeys),
        fingerprints={key: f"doi:10.1/{key}" for key in citekeys},
        formatted=formatted,
        state="deleted",
    )


# --- 1. ins com âncora única localiza ---------------------------------------


def test_ins_with_unique_anchor_locates() -> None:
    prefix = "O paciente recebeu o tratamento"
    mark_syntax = "{++ novo++}"
    suffix = " conforme protocolo estabelecido pela equipe."
    clean_text = prefix + mark_syntax + suffix
    mark = ReviewMark(
        kind="ins",
        a="",
        b=" novo",
        author="Coautor",
        chg_id="1",
        start=len(prefix),
        end=len(prefix) + len(mark_syntax),
    )
    norm_text = prefix + suffix

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([]), [])

    assert events == []
    assert len(located) == 1
    loc = located[0]
    assert isinstance(loc, LocatedMark)
    assert loc.mark is mark
    assert loc.norm_start == loc.norm_end == len(prefix)


# --- 2. del com alvo único localiza ------------------------------------------


def test_del_with_unique_target_locates() -> None:
    prefix = "Os resultados mostraram melhora "
    target = "significativa"
    mark_syntax = "{--" + target + "--}"
    suffix = " nos escores de dor relatados pelos participantes."
    clean_text = prefix + mark_syntax + suffix
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Coautor",
        chg_id="2",
        start=len(prefix),
        end=len(prefix) + len(mark_syntax),
    )
    norm_text = prefix + target + suffix

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([]), [])

    assert events == []
    assert len(located) == 1
    loc = located[0]
    assert loc.norm_start == len(prefix)
    assert loc.norm_end == len(prefix) + len(target)
    assert norm_text[loc.norm_start : loc.norm_end] == target


# --- 3. contexto ambíguo (frase repetida) → ambiguous-anchor -----------------


def test_ambiguous_context_when_unit_repeats_in_norm() -> None:
    # Unidade de texto usada duas vezes no norm_text; before/after têm >= 48
    # chars cada um DENTRO da própria unidade, garantindo que a janela de
    # contexto (48 chars) nunca escapa para fora dela — as duas repetições
    # ficam byte-a-byte idênticas na vizinhança do alvo.
    unit_before = (
        "Introducao extensa deste paragrafo para garantir que sobre bastante "
        "texto antes do alvo dentro desta mesma unidade repetida, ok entao? "
    )
    unit_target = "dor intensa"
    unit_after = (
        " e a equipe registrou os sinais vitais no prontuario logo em seguida, "
        "concluindo esta unidade de texto repetida sem cortes no meio."
    )
    assert len(unit_before) >= 48
    assert len(unit_after) >= 48

    mark_syntax = "{--" + unit_target + "--}"
    clean_text = unit_before + mark_syntax + unit_after
    mark = ReviewMark(
        kind="del",
        a=unit_target,
        b="",
        author="Coautor",
        chg_id="3",
        start=len(unit_before),
        end=len(unit_before) + len(mark_syntax),
    )

    unit = unit_before + unit_target + unit_after
    norm_text = unit + unit  # mesma unidade 2x -> contexto ambíguo

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([]), [])

    assert located == []
    assert len(events) == 1
    assert events[0].kind == "ambiguous-anchor"
    assert events[0].author == "Coautor"


# --- 4. marca encostando no token de citação → citation-touched-prose -------


def test_mark_overlapping_citation_token_emits_citation_touched_prose() -> None:
    formatted = "(Smith, 2020)"
    prose_before = "Conforme "
    prose_after = " resultados semelhantes ao esperado pela equipe."

    # Alvo do del começa DENTRO do display da citação (a partir do 6º char,
    # ") 2020)") e se estende para a prosa seguinte — interseção PARCIAL
    # genuína (nem token inteiro, nem fora da citação).
    overlap_from = 6
    head_of_citation = formatted[:overlap_from]  # "(Smith"
    tail_of_citation = formatted[overlap_from:]  # ", 2020)"
    target = tail_of_citation + " demonstrou"

    mark_syntax = "{--" + target + "--}"
    clean_text = prose_before + head_of_citation + mark_syntax + prose_after
    start = len(prose_before + head_of_citation)
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Revisor",
        chg_id="9",
        start=start,
        end=start + len(mark_syntax),
    )

    citekey_form = "[@smith2020]"
    norm_prefix = "Conforme "
    norm_text = norm_prefix + citekey_form + " demonstrou" + prose_after
    cit_start = len(norm_prefix)
    cit_end = cit_start + len(citekey_form)
    occ = _occ(
        occ_id="00000001",
        citekeys=["smith2020"],
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([occ]), [])

    assert located == []
    assert len(events) == 1
    event = events[0]
    assert event.kind == "citation-touched-prose"
    assert event.occ_id == "00000001"
    assert event.citekeys == ["smith2020"]
    assert event.author == "Revisor"


# --- 5. del de citação casa com deleted (sem evento duplicado) --------------


def test_citation_deletion_matches_deleted_without_duplicate_event() -> None:
    formatted = "(Jones, 2021)"
    prose_before = "Outro estudo "
    prose_after = " confirmou o achado principal."
    mark_syntax = "{--" + formatted + "--}"
    clean_text = prose_before + mark_syntax + prose_after
    start = len(prose_before)
    mark = ReviewMark(
        kind="del",
        a=formatted,
        b="",
        author="Coautor",
        chg_id="4",
        start=start,
        end=start + len(mark_syntax),
    )

    citekey_form = "[@jones2021]"
    norm_text = prose_before + citekey_form + prose_after
    cit_start = len(prose_before)
    cit_end = cit_start + len(citekey_form)
    occ = _occ(
        occ_id="00000002",
        citekeys=["jones2021"],
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )
    deleted = [_deleted(occ_id="00000002", citekeys=["jones2021"], formatted=formatted)]

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([occ]), deleted)

    assert located == []
    assert events == []  # consumida silenciosamente — drop é evento da conservação (Task 2/8)


# --- 6. citação no MEIO da âncora → localiza via sentinela -------------------


def test_locates_via_sentinel_when_citation_sits_inside_anchor_context() -> None:
    formatted = "(Alves, 2019)"
    before_ctx = "Conforme " + formatted + " apontou, o efeito foi "
    target = "significativo"
    after_ctx = " nos resultados finais da coorte."
    assert len(before_ctx) <= 48  # cabe inteiro na janela — sem truncar

    mark_syntax = "{--" + target + "--}"
    clean_text = before_ctx + mark_syntax + after_ctx
    start = len(before_ctx)
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Coautor",
        chg_id="5",
        start=start,
        end=start + len(mark_syntax),
    )

    citekey_form = "[@alves2019]"
    norm_before = "Conforme " + citekey_form + " apontou, o efeito foi "
    norm_text = norm_before + target + after_ctx
    cit_start = len("Conforme ")
    cit_end = cit_start + len(citekey_form)
    occ = _occ(
        occ_id="00000003",
        citekeys=["alves2019"],
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([occ]), [])

    assert events == []
    assert len(located) == 1
    loc = located[0]
    assert loc.norm_start == len(norm_before)
    assert loc.norm_end == len(norm_before) + len(target)
    assert norm_text[loc.norm_start : loc.norm_end] == target


# --- self-review: edge case 1 — del "exato" de citação sem confirmação -----
# (I2: adeu viu uma deleção de display que o OOXML/conservação NÃO confirma
# como `deleted` — nunca confiar no adeu para decisão de citação.)


def test_citation_exact_delete_without_matching_deleted_emits_touched_prose() -> None:
    formatted = "(Costa, 2022)"
    prose_before = "Segundo o autor "
    prose_after = " o efeito persistiu."
    mark_syntax = "{--" + formatted + "--}"
    clean_text = prose_before + mark_syntax + prose_after
    start = len(prose_before)
    mark = ReviewMark(
        kind="del",
        a=formatted,
        b="",
        author="Coautor",
        chg_id="6",
        start=start,
        end=start + len(mark_syntax),
    )

    citekey_form = "[@costa2022]"
    norm_text = prose_before + citekey_form + prose_after
    cit_start = len(prose_before)
    cit_end = cit_start + len(citekey_form)
    occ = _occ(
        occ_id="00000004",
        citekeys=["costa2022"],
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )
    # `deleted` fica VAZIO de propósito: conservação (OOXML real) NÃO viu
    # esta citação como deletada — inconsistência com o que o adeu mostra.

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([occ]), [])

    assert located == []
    assert len(events) == 1
    event = events[0]
    assert event.kind == "citation-touched-prose"
    assert event.occ_id == "00000004"
    assert "confirma" in event.detail or "confirmação" in event.detail


# --- self-review: edge case 2 — token sentinela na fronteira dos 48 chars --
# (truncamento nunca deve partir um token \x00CIT<i>\x00 ao meio — o corte
# empurra para incluir/excluir o token INTEIRO, mesmo passando de 48 chars.)


def test_truncation_never_splits_sentinel_token_at_48_char_boundary() -> None:
    formatted = "(Longo Sobrenome Composto, 2024)"  # citação propositalmente longa
    # Padding calculado para que o corte "ingênuo" dos 48 chars caia bem no
    # MEIO do display da citação, caso a implementação substituísse o
    # sentinela e SÓ DEPOIS colapsasse/truncasse sem respeitar fronteira de
    # token.
    padding = "x" * 30
    before_ctx = padding + formatted
    target = "alvo"
    after_ctx = " resto da frase depois do alvo para fechar o periodo."
    clean_text = before_ctx + "{--" + target + "--}" + after_ctx
    start = len(before_ctx)
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Coautor",
        chg_id="7",
        start=start,
        end=start + len("{--" + target + "--}"),
    )

    citekey_form = "[@longo2024]"
    norm_before = padding + citekey_form
    norm_text = norm_before + target + after_ctx
    cit_start = len(padding)
    cit_end = cit_start + len(citekey_form)
    occ = _occ(
        occ_id="00000005",
        citekeys=["longo2024"],
        formatted=formatted,
        norm_start=cit_start,
        norm_end=cit_end,
    )

    # Não deve levantar exceção nem corromper o token — resultado esperado:
    # ou localiza corretamente (contexto expandido pra não partir o token),
    # ou reporta unanchored-mark; NUNCA um match espúrio/corrompido.
    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([occ]), [])

    assert len(located) + len(events) == 1
    if located:
        loc = located[0]
        assert loc.norm_start == len(norm_before)
        assert loc.norm_end == len(norm_before) + len(target)
    else:
        assert events[0].kind in ("unanchored-mark", "ambiguous-anchor")


# --- extra: 0 matches → unanchored-mark --------------------------------------


def test_zero_matches_emits_unanchored_mark() -> None:
    prefix = "Frase que não existe de jeito nenhum no texto normalizado "
    target = "alvoinexistente"
    suffix = " no restante do documento revisado."
    mark_syntax = "{--" + target + "--}"
    clean_text = prefix + mark_syntax + suffix
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Coautor",
        chg_id="8",
        start=len(prefix),
        end=len(prefix) + len(mark_syntax),
    )
    # norm_text completamente diferente — contexto não aparece em lugar nenhum.
    norm_text = "Um texto totalmente diferente, sem nenhuma relação com a marca acima."

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([]), [])

    assert located == []
    assert len(events) == 1
    assert events[0].kind == "unanchored-mark"
    assert events[0].author == "Coautor"
