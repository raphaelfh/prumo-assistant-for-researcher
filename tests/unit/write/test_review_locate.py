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

Task 7 (`transplant_to_source`) é ANEXADA neste mesmo arquivo (per brief:
"Modify test_review_locate.py (append)") — `LocatedMark` é a interface
entre as duas tasks, então os testes convivem lado a lado. Os testes de
Task 7 usam `normalize_markdown_with_map` REAL (não fixtures locais) para
obter `span_frags` genuínos sempre que o teste depende da forma exata do
span-map (atributo central da task); `ReviewMark.start`/`.end` (offsets em
`clean_text`) são irrelevantes para `transplant_to_source` — só
`LocatedMark.norm_start`/`.norm_end` (offsets em `norm_text`) importam —,
por isso ficam com `start=0, end=0` (dummy) nesses testes.
"""

from __future__ import annotations

import pytest

import prumo_assist.domains.write.review as review_mod
from prumo_assist.core import criticmarkup
from prumo_assist.core.obsidian import normalize_markdown_with_map
from prumo_assist.domains.write.review import (
    DocxCitation,
    LocatedMark,
    MarkLostError,
    ReviewMark,
    locate_marks_in_norm,
    transplant_to_source,
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


# --- Fix após review (Fase 2/Task 6): achados Crítico + Importante -----------
#
# CRÍTICO: `_find_citation_spans_by_search` pareava citemap<->plain_text por
# ORDEM DE LISTA do citemap com cursor sequencial; o lado norm já reordenava
# por `norm_start`. Reprodução do reviewer: 2 occurrences com o MESMO
# `formatted`, ordem do citemap invertida em relação à ordem física — um del
# batendo EXATAMENTE no display da citação LIVE podia trocar de identidade
# com a OUTRA occurrence (genuinamente `deleted`) e ser consumido
# SILENCIOSAMENTE (`located == [] and events == []`, I1 violado).


def test_same_display_citations_order_mismatch_never_silent() -> None:
    """Reprodução EXATA do reviewer: 2 occurrences com o MESMO `formatted`,
    lista do citemap [A, B] só que a ORDEM FÍSICA (norm_start) é invertida
    (B vem antes de A no documento). O del bate EXATAMENTE no display da
    ocorrência física SEGUNDA (A, a LIVE — B é quem está em `deleted`).

    O resultado NUNCA pode ser (located == [] and events == []): ou a
    defesa (a) já pareia corretamente pela ordem física (e o del resolve
    para A, que não está em `deleted` -> `citation-touched-prose` pela
    regra já existente), ou a defesa (b) barraria um consumo indevido caso
    a identidade não fosse cross-validável. De um jeito ou de outro,
    `events != []` — nunca um swallow silencioso de uma deleção de citação
    não confirmada."""
    formatted = "(Mesmo Display, 2020)"
    prose_b = "Um estudo prévio "
    prose_mid = " mostrou tendência semelhante, e outro estudo "
    prose_after = " reforçou esse achado independentemente."

    # Lado adeu/plain: B (display) aparece fisicamente PRIMEIRO (texto
    # comum, não tocado); o del (pré-imagem = mesmo display) aparece
    # DEPOIS — fisicamente na posição de A.
    mark_syntax = "{--" + formatted + "--}"
    clean_text = prose_b + formatted + prose_mid + mark_syntax + prose_after
    start = len(prose_b + formatted + prose_mid)
    mark = ReviewMark(
        kind="del",
        a=formatted,
        b="",
        author="Coautor",
        chg_id="10",
        start=start,
        end=start + len(mark_syntax),
    )

    # Lado norm: MESMA ordem física (B primeiro, A depois) — a suposição de
    # ordem física que a defesa (a) depende.
    citekey_b = "[@bkey2020]"
    citekey_a = "[@akey2020]"
    norm_text = prose_b + citekey_b + prose_mid + citekey_a + prose_after
    b_start = len(prose_b)
    b_end = b_start + len(citekey_b)
    a_start = b_end + len(prose_mid)
    a_end = a_start + len(citekey_a)

    occ_a = _occ(
        occ_id="AAAAAAAA",
        citekeys=["akey2020"],
        formatted=formatted,
        norm_start=a_start,
        norm_end=a_end,
    )
    occ_b = _occ(
        occ_id="BBBBBBBB",
        citekeys=["bkey2020"],
        formatted=formatted,
        norm_start=b_start,
        norm_end=b_end,
    )
    # ORDEM DO CITEMAP (lista: A, B) invertida em relação à ordem FÍSICA
    # (B vem antes de A no norm_text) — reprodução literal do reviewer.
    citemap = _citemap([occ_a, occ_b])

    # B é a citação GENUINAMENTE deletada (confirmada pela conservação); o
    # del alvo é EXATAMENTE o display da OUTRA (A, a LIVE).
    deleted = [_deleted(occ_id="BBBBBBBB", citekeys=["bkey2020"], formatted=formatted)]

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, citemap, deleted)

    assert not (located == [] and events == [])
    # Nem a defesa (a) nem a (b) produzem `LocatedMark` neste ramo — o alvo
    # é sempre classificado como "citação" (silêncio OU evento), nunca vira
    # uma âncora de prosa comum.
    assert located == []
    assert len(events) == 1
    assert events[0].kind == "citation-touched-prose"
    assert events[0].author == "Coautor"


def test_same_display_citations_pair_by_document_order() -> None:
    """Mesmos 2 occurrences com display idêntico do teste anterior, mas com
    a ordem do citemap CONSISTENTE com a ordem física (norm_start) — o caso
    NORMAL que a correção não pode quebrar: del do display exato da citação
    genuinamente deletada (a segunda fisicamente) -> consumida
    silenciosamente (sem `LocatedMark`, sem evento), exatamente como
    projetado antes deste fix (ver teste 5, versão com 1 única
    occurrence)."""
    formatted = "(Dup, 2023)"
    prose_c = "Um estudo "
    prose_mid = " e também outro estudo "
    prose_after = " confirmaram o achado."

    mark_syntax = "{--" + formatted + "--}"
    clean_text = prose_c + formatted + prose_mid + mark_syntax + prose_after
    start = len(prose_c + formatted + prose_mid)
    mark = ReviewMark(
        kind="del",
        a=formatted,
        b="",
        author="Coautor",
        chg_id="11",
        start=start,
        end=start + len(mark_syntax),
    )

    citekey_c = "[@ckey2023]"
    citekey_d = "[@dkey2023]"
    norm_text = prose_c + citekey_c + prose_mid + citekey_d + prose_after
    c_start = len(prose_c)
    c_end = c_start + len(citekey_c)
    d_start = c_end + len(prose_mid)
    d_end = d_start + len(citekey_d)

    occ_c = _occ(
        occ_id="CCCCCCCC",
        citekeys=["ckey2023"],
        formatted=formatted,
        norm_start=c_start,
        norm_end=c_end,
    )
    occ_d = _occ(
        occ_id="DDDDDDDD",
        citekeys=["dkey2023"],
        formatted=formatted,
        norm_start=d_start,
        norm_end=d_end,
    )
    # Ordem do citemap (lista: C, D) == ordem FÍSICA (C primeiro nos dois
    # lados) — sem divergência.
    citemap = _citemap([occ_c, occ_d])
    # D é a citação genuinamente deletada; o del alvo é EXATAMENTE o
    # display da segunda ocorrência física (D).
    deleted = [_deleted(occ_id="DDDDDDDD", citekeys=["dkey2023"], formatted=formatted)]

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, citemap, deleted)

    assert located == []
    assert events == []  # consumida silenciosamente — comportamento preservado


def test_identity_unconfirmed_when_adeu_physical_order_diverges_from_norm() -> None:
    """Defesa (b) ISOLADA: verificado empiricamente (não só por inspeção)
    que, com SÓ a defesa (a) ativa (busca ordenada por `norm_start`), este
    cenário AINDA produz `located == [] and events == []` — porque aqui é a
    ORDEM FÍSICA do próprio lado adeu/plain_text que diverge da ordem
    física do norm_text (não a ordem de lista do citemap, que a defesa (a)
    já resolve sozinha — ver teste acima). O del (mesmo display das 2
    occurrences) aparece fisicamente PRIMEIRO no lado adeu; a citação
    genuinamente deletada (H) aparece fisicamente PRIMEIRO no norm_text —
    ordens opostas. A prosa ao redor de cada citação é DIFERENTE entre
    plain e norm (como no mundo real: o adeu não re-renderiza byte-a-byte
    igual ao norm_text) — só a defesa (b) (cross-check independente no
    lado norm) impede o consumo indevido aqui, porque o contexto
    genuinamente não bate em nenhuma posição do norm_text."""
    formatted = "(Divergente, 2021)"

    # Lado adeu/plain: o del (alvo) aparece fisicamente PRIMEIRO; a citação
    # não tocada (literal) aparece DEPOIS.
    plain_prefix = "No texto revisado pelo adeu, "
    plain_mid = " e mais adiante, segundo outro autor, "
    plain_suffix = " concluiu-se o capítulo."
    mark_syntax = "{--" + formatted + "--}"
    clean_text = plain_prefix + mark_syntax + plain_mid + formatted + plain_suffix
    start = len(plain_prefix)
    mark = ReviewMark(
        kind="del",
        a=formatted,
        b="",
        author="Coautor",
        chg_id="13",
        start=start,
        end=start + len(mark_syntax),
    )

    # Lado norm: prosa DIFERENTE da do plain, e ordem física INVERTIDA (H
    # primeiro, G depois) — H é quem está genuinamente em `deleted`.
    citekey_g = "[@gkey2021]"
    citekey_h = "[@hkey2021]"
    norm_prefix = "Na fonte normalizada, conforme "
    norm_mid = " e também conforme "
    norm_suffix = " conclui-se a seção final."
    norm_text = norm_prefix + citekey_h + norm_mid + citekey_g + norm_suffix
    h_start = len(norm_prefix)
    h_end = h_start + len(citekey_h)
    g_start = h_end + len(norm_mid)
    g_end = g_start + len(citekey_g)

    occ_g = _occ(
        occ_id="GGGGGGGG",
        citekeys=["gkey2021"],
        formatted=formatted,
        norm_start=g_start,
        norm_end=g_end,
    )
    occ_h = _occ(
        occ_id="HHHHHHHH",
        citekeys=["hkey2021"],
        formatted=formatted,
        norm_start=h_start,
        norm_end=h_end,
    )
    citemap = _citemap([occ_g, occ_h])
    deleted = [_deleted(occ_id="HHHHHHHH", citekeys=["hkey2021"], formatted=formatted)]

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, citemap, deleted)

    assert located == []
    assert len(events) == 1
    assert events[0].kind == "citation-touched-prose"
    assert "identidade" in events[0].detail
    assert events[0].author == "Coautor"


# --- Importante: colapso de espaços simétrico (lado norm também) ------------


def test_double_space_in_norm_still_locates() -> None:
    """Achado IMPORTANTE do review: o colapso de espaços era unilateral (só
    o lado adeu/plain era colapsado antes da busca; o norm era buscado
    CRU) — um espaço duplo GENUÍNO na fonte (norm_text), perto do alvo,
    produzia `unanchored-mark` espúrio mesmo quando o conteúdo realmente
    bate. Fix: colapso SIMÉTRICO (`_collapse_whitespace_with_segments`
    aplicado também ao lado norm) — localiza normalmente, e o span
    retornado está em offsets ORIGINAIS de `norm_text` (não colapsados)."""
    prefix = "Os resultados mostraram melhora"  # sem espaço final aqui de propósito
    target = "significativa"
    mark_syntax = "{--" + target + "--}"
    suffix = " nos escores de dor relatados pelos participantes."
    # Lado adeu: espaço ÚNICO entre o prefixo e o alvo.
    clean_text = prefix + " " + mark_syntax + suffix
    start = len(prefix + " ")
    mark = ReviewMark(
        kind="del",
        a=target,
        b="",
        author="Coautor",
        chg_id="21",
        start=start,
        end=start + len(mark_syntax),
    )
    # Lado norm: espaço DUPLO genuíno na fonte, no mesmo lugar.
    norm_text = prefix + "  " + target + suffix

    located, events = locate_marks_in_norm(clean_text, [mark], norm_text, _citemap([]), [])

    assert events == []
    assert len(located) == 1
    loc = located[0]
    assert norm_text[loc.norm_start : loc.norm_end] == target


# --- Task 7: transplante para o source + Guarda B (`transplant_to_source`) --
#
# 1. ins/del/sub transplantados no lugar certo do source, com wikilink e
#    citação AO REDOR intactos byte a byte ------------------------------------


def test_ins_del_sub_transplant_with_wikilink_and_citation_intact() -> None:
    """Os 3 kinds transplantáveis (ins/del/sub) num único `source_body` com
    `[[@key]]` e `[[Conceito|alias]]` — span_frags REAIS de
    `normalize_markdown_with_map` (não fixture local). Os 3 alvos vivem
    dentro do MESMO fragment `identity` (a prosa entre os dois átomos), sem
    tocar nenhuma fronteira — isso é coberto à parte pelos 2 edge cases de
    self-review mais abaixo. Verifica tanto os marcadores exatos quanto o
    round-trip `criticmarkup.reject(source_with_marks) == source_body`
    (prova mais forte: reconstrói o original, átomos inclusive)."""
    source_body = (
        "Paragrafo inicial cita o estudo [[@smith2020]] logo no comeco. "
        "Depois descreve um resultado antigo que precisa ser removido, "
        "e mais adiante indica onde um comentario novo deve entrar, "
        "e por fim menciona um termo errado que sera corrigido "
        "antes de encerrar com o conceito relacionado [[Conceito|alias]] final."
    )
    norm_text, span_frags = normalize_markdown_with_map(source_body)
    # sanity: os dois átomos normalizaram como o esperado (senão o teste
    # não estaria exercitando o que diz exercitar).
    assert "[@smith2020]" in norm_text
    assert "alias" in norm_text
    assert "[[@smith2020]]" not in norm_text

    del_target = "um resultado antigo"
    ins_anchor = "e mais adiante indica"
    sub_target = "um termo errado"

    del_start = norm_text.index(del_target)
    del_end = del_start + len(del_target)
    ins_point = norm_text.index(ins_anchor)
    sub_start = norm_text.index(sub_target)
    sub_end = sub_start + len(sub_target)

    del_mark = ReviewMark(
        kind="del", a=del_target, b="", author="Coautor", chg_id="1", start=0, end=0
    )
    ins_mark = ReviewMark(
        kind="ins", a="", b="URGENTE: ", author="Coautor", chg_id="2", start=0, end=0
    )
    sub_mark = ReviewMark(
        kind="sub",
        a=sub_target,
        b="um termo correto",
        author="Coautor",
        chg_id="3",
        start=0,
        end=0,
    )
    located = [
        LocatedMark(mark=del_mark, norm_start=del_start, norm_end=del_end),
        LocatedMark(mark=ins_mark, norm_start=ins_point, norm_end=ins_point),
        LocatedMark(mark=sub_mark, norm_start=sub_start, norm_end=sub_end),
    ]

    source_with_marks, events = transplant_to_source(source_body, span_frags, located)

    assert events == []
    assert "[[@smith2020]]" in source_with_marks
    assert "[[Conceito|alias]]" in source_with_marks
    assert criticmarkup.emit("del", del_target, "") in source_with_marks
    assert criticmarkup.emit("ins", "", "URGENTE: ") + "e mais adiante indica" in source_with_marks
    assert criticmarkup.emit("sub", sub_target, "um termo correto") in source_with_marks
    assert criticmarkup.reject(source_with_marks) == source_body


# --- 2. marca em fragment `citation` → evento `non-identity-span` -----------


def test_mark_in_citation_fragment_emits_non_identity_span_event() -> None:
    """`LocatedMark` cujo intervalo inteiro cai DENTRO do fragment `citation`
    (não `identity`) nunca transplanta — vira `non-identity-span`, e o
    `source_body` sai intocado (nenhuma marca aplicada)."""
    source_body = "Este estudo [[@jones2021]] mostrou resultados relevantes."
    norm_text, span_frags = normalize_markdown_with_map(source_body)
    citation_frag = next(f for f in span_frags if f.kind == "citation")

    mark = ReviewMark(
        kind="del",
        a=norm_text[citation_frag.norm_start : citation_frag.norm_end],
        b="",
        author="Coautor",
        chg_id="9",
        start=0,
        end=0,
    )
    located = [
        LocatedMark(mark=mark, norm_start=citation_frag.norm_start, norm_end=citation_frag.norm_end)
    ]

    source_with_marks, events = transplant_to_source(source_body, span_frags, located)

    assert source_with_marks == source_body
    assert len(events) == 1
    assert events[0].kind == "non-identity-span"
    assert events[0].author == "Coautor"


# --- 3. Guarda B: monkeypatch em helper interno força marca a "sumir" -------


def test_forced_marker_loss_raises_mark_lost_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarda B: monkeypatch no helper interno `_emit_marker` (seam isolado
    só para este teste) simula uma marca cujo texto nunca chega a ser
    escrito no source — a contagem (aplicadas + eventos) não fecha contra
    `len(located)`, e a função aborta com `MarkLostError` ANTES de devolver
    qualquer `source_with_marks` (nunca um resultado parcialmente
    corrompido)."""
    source_body = "Frase de prosa pura sem nenhum atomo obsidian aqui dentro."
    norm_text, span_frags = normalize_markdown_with_map(source_body)
    target = "prosa pura"
    start = norm_text.index(target)
    end = start + len(target)
    mark = ReviewMark(kind="del", a=target, b="", author="Coautor", chg_id="99", start=0, end=0)
    located = [LocatedMark(mark=mark, norm_start=start, norm_end=end)]

    monkeypatch.setattr(review_mod, "_emit_marker", lambda mark: "")

    with pytest.raises(MarkLostError) as exc_info:
        transplant_to_source(source_body, span_frags, located)

    assert "prosa pura" in str(exc_info.value)
    assert "Coautor" in str(exc_info.value)


# --- 4. múltiplas marcas preservam offsets (aplicação em ordem reversa) -----


def test_multiple_marks_preserve_offsets_when_applied_back_to_front() -> None:
    """Aplicar N marcas com marcadores de comprimentos DIFERENTES precisa
    preservar os offsets pré-calculados de TODAS elas — se a implementação
    aplicasse na ordem do documento (frente pra trás), a primeira marca já
    deslocaria os offsets, ainda não consumidos, das seguintes. Compara o
    resultado com uma reconstrução EXATA (não só substring) e com o
    round-trip `criticmarkup.reject`."""
    source_body = "Alfa Bravo Charlie Delta Echo"
    norm_text, span_frags = normalize_markdown_with_map(source_body)
    assert norm_text == source_body  # nenhum átomo Obsidian aqui

    alfa_start = norm_text.index("Alfa")
    alfa_end = alfa_start + len("Alfa")
    charlie_start = norm_text.index("Charlie")
    charlie_end = charlie_start + len("Charlie")
    echo_start = norm_text.index("Echo")
    echo_end = echo_start + len("Echo")

    del_alfa = ReviewMark(kind="del", a="Alfa", b="", author="Coautor", chg_id="1", start=0, end=0)
    ins_novo = ReviewMark(kind="ins", a="", b="NOVO ", author="Coautor", chg_id="2", start=0, end=0)
    sub_charlie = ReviewMark(
        kind="sub", a="Charlie", b="CharlieX", author="Coautor", chg_id="3", start=0, end=0
    )
    del_echo = ReviewMark(kind="del", a="Echo", b="", author="Coautor", chg_id="4", start=0, end=0)

    located = [
        LocatedMark(mark=del_alfa, norm_start=alfa_start, norm_end=alfa_end),
        LocatedMark(mark=ins_novo, norm_start=charlie_start, norm_end=charlie_start),
        LocatedMark(mark=sub_charlie, norm_start=charlie_start, norm_end=charlie_end),
        LocatedMark(mark=del_echo, norm_start=echo_start, norm_end=echo_end),
    ]

    source_with_marks, events = transplant_to_source(source_body, span_frags, located)

    assert events == []
    expected = (
        criticmarkup.emit("del", "Alfa", "")
        + " Bravo "
        + criticmarkup.emit("ins", "", "NOVO ")
        + criticmarkup.emit("sub", "Charlie", "CharlieX")
        + " Delta "
        + criticmarkup.emit("del", "Echo", "")
    )
    assert source_with_marks == expected
    assert criticmarkup.reject(source_with_marks) == source_body


# --- self-review (Task 7): 2 edge cases próprios — fronteira exata do `ins` -
#
# Nuance documentada na Task 7: um ponto de `ins`/`comment` (`norm_start ==
# norm_end`) que cai EXATAMENTE na fronteira entre dois fragments (norm_end
# de um == norm_start do outro) resolve deterministicamente para o fragment
# que TERMINA ali se ele é `identity`; senão, para o que COMEÇA ali. Os 2
# testes abaixo isolam cada ramo da regra.


def test_ins_point_at_boundary_uses_ending_identity_fragment() -> None:
    """Ponto de `ins` EXATAMENTE na fronteira entre um fragment `identity`
    que TERMINA ali e um fragment `citation` que COMEÇA ali — a regra
    escolhe o fragment que termina (é identity): o `ins` ancora IMEDIATAMENTE
    ANTES da citação, sem tocá-la. Se a implementação preferisse sempre o
    fragment que começa (a citação, não-identity), isto viraria
    `non-identity-span` por engano."""
    prose = "Texto de prosa antes"
    citation_src = "[[@key2020]]"
    rest = " resto depois."
    source_body = prose + citation_src + rest
    _norm_text, span_frags = normalize_markdown_with_map(source_body)

    point = len(prose)  # fim exato do fragment identity == início do fragment citation
    mark = ReviewMark(kind="ins", a="", b="NOVO ", author="Coautor", chg_id="5", start=0, end=0)
    located = [LocatedMark(mark=mark, norm_start=point, norm_end=point)]

    source_with_marks, events = transplant_to_source(source_body, span_frags, located)

    assert events == []
    expected = prose + criticmarkup.emit("ins", "", "NOVO ") + citation_src + rest
    assert source_with_marks == expected


def test_ins_point_at_boundary_falls_back_to_starting_identity_fragment() -> None:
    """Ponto de `ins` na fronteira entre um fragment `citation` que TERMINA
    ali (não é identity) e um fragment `identity` que COMEÇA ali — a regra
    cai para o fragment que começa ("senão ao que começa"): o `ins` ainda
    transplanta, ancorado IMEDIATAMENTE DEPOIS da citação. Prova que a
    implementação não rejeita cegamente só por checar o fragment que
    termina ali."""
    citation_src = "[[@key2021]]"
    rest_prose = " resto de prosa depois do ponto."
    source_body = citation_src + rest_prose
    _norm_text, span_frags = normalize_markdown_with_map(source_body)
    citation_frag = next(f for f in span_frags if f.kind == "citation")
    point = citation_frag.norm_end

    mark = ReviewMark(kind="ins", a="", b="NOVO ", author="Coautor", chg_id="6", start=0, end=0)
    located = [LocatedMark(mark=mark, norm_start=point, norm_end=point)]

    source_with_marks, events = transplant_to_source(source_body, span_frags, located)

    assert events == []
    expected = citation_src + criticmarkup.emit("ins", "", "NOVO ") + rest_prose
    assert source_with_marks == expected
