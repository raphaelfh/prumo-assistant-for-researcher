"""Ponte docx↔CriticMarkup — Fase 2 (`prumo write review ingest`/`apply`).

Toda a lógica mora aqui; a fachada CLI (Task 10) só faz parsing + chamada
do domínio + saída via `core/output.Console` (regra de fachadas finas,
`.claude/rules/code.md`). Módulo cresce tarefa a tarefa conforme
`docs/superpowers/plans/2026-07-23-ponte-fase2-review-ingest-apply.md`.

Task 1 entrega o bloco de exceções (contrato usado por todas as tasks
seguintes — ver "Interfaces centrais" do plano) e o leitor OOXML
STATEFUL de citações: :func:`read_docx_citations_with_state` (I2b).
Task 2 entrega :func:`check_conservation` (I2/I2b/I3-lite): compara o
OBSERVADO (saída do leitor) contra o citemap (EXPECTED, gravado no
export) e hard-fail em qualquer divergência.
Task 3 entrega a Guarda A: :func:`assert_no_structural_changes` hard-fail
quando há mudança rastreada/comentário numa região que o transplante por
âncora de texto (Task 6/7, sobre a prosa linear do adeu) não sabe
localizar — tabela, nota de rodapé/fim, ou equação (oMath).
Task 4 entrega o seam do backend de PROSA (:func:`_run_adeu_extract`, adeu
PINADO via ``uvx adeu==1.29.0`` — nunca versão flutuante) e o parser das
marcas com autoria (:func:`parse_adeu_markdown`): pareia cada marca de
conteúdo CriticMarkup com a anotação `[Chg:<id> insert|delete] <Autor>` que
o adeu cola imediatamente depois, produzindo :class:`ReviewMark` com offsets
já no texto LIMPO (pós-remoção de anotações/rodapé) que a Task 6 vai usar.

É o sibling STATEFUL de
:func:`prumo_assist.domains.write.export._read_docx_citations` (MÉTODO
I2, sem estado — usado no export para montar o citemap). Aqui a leitura
anda por `word/document.xml` com ElementTree (não regex) porque
precisamos dos ancestrais `w:ins`/`w:del` de cada run do campo para
classificar o estado da citação no docx que VOLTA do coautor — algo que
o leitor stateless nunca precisou saber.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NoReturn, TypeVar, cast
from xml.etree import ElementTree as ET

import yaml
from pydantic import BaseModel, ValidationError

from prumo_assist.core import criticmarkup
from prumo_assist.core.citations import (
    CITEKEY_RE,
    iter_marked_citation_spans,
    iter_narrative_citation_spans,
)
from prumo_assist.core.obsidian import (
    SpanFragment,
    normalize_markdown,
    normalize_markdown_with_map,
    split_frontmatter_raw,
)
from prumo_assist.core.uvx import PinnedTool, run_pinned
from prumo_assist.domains.write.comments import extract_from_docx
from prumo_assist.domains.write.errors import WriteError
from prumo_assist.domains.write.export import (
    _ZOTERO_ITEM_CSL_MARKER,
    _norm_citation_spans,
    _parse_csl_payload,
    _validate_docx_structure,
    detect_project_root,
    slugify,
)
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
    ReviewEventsFile,
    SpanMapFile,
)

logger = logging.getLogger(__name__)

# Mesmo padrão de comments.py (W_NS + iteração ET sobre word/document.xml).
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Namespace math (ECMA-376 parte 1, §22) — usado só pela Guarda A (Task 3)
# para achar ancestral `m:oMath` de `w:ins`/`w:del` (mudança dentro de
# equação).
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# A marca de campo (`_ZOTERO_ITEM_CSL_MARKER`) vem de `export` — mesma
# constante que `_read_docx_citations` (MÉTODO I2) reconhece via regex —
# usada aqui só para decidir se um campo fechado é uma citação Zotero
# (antes de chamar `_parse_csl_payload`). O decode do payload em si
# (slice + json.loads + erro com índice) também é compartilhado via
# `export._parse_csl_payload` (achado do review da Fase 2/Task 1 —
# Finding 2), porque os dois leitores tinham decodes que divergiam
# sutilmente (`review.py` aplicava `html.unescape` sobre texto do
# ElementTree já resolvido, corrompendo entidades como `&para=`). Cada
# leitor mantém só o SEU estágio de unescape (aqui, nenhum).

# Vocabulário FECHADO dos kinds de evento gravados em `events.yaml`.
# Fonte única — as fachadas (`write/cli.py`, `mcp_server.py`) consomem
# estas constantes em vez de re-hardcodear as strings (a variante
# hardcoded já gerou drift real: o checklist do `review events` shipou
# comparando kinds que nunca são gravados — fix pós-review da Fase 3).
EVENT_KIND_APPLIED = "applied"
EVENT_KIND_CITATION_DROP = "citation-drop"
EVENT_KIND_CITATION_TOUCHED_PROSE = "citation-touched-prose"
EVENT_KIND_UNANCHORED_MARK = "unanchored-mark"
EVENT_KIND_AMBIGUOUS_ANCHOR = "ambiguous-anchor"
EVENT_KIND_NON_IDENTITY_SPAN = "non-identity-span"


@dataclass(frozen=True)
class DocxCitation:
    """Uma ocorrência de citação lida do OOXML, com o estado do campo.

    Mesmos 5 campos de identidade/conteúdo do leitor stateless (I2:
    ``occ_id``, ``citation_id``, ``citekeys``, ``fingerprints``,
    ``formatted``) mais ``state`` — o que só o leitor STATEFUL (I2b) sabe
    responder, porque exige andar pelos ancestrais `w:ins`/`w:del`.
    """

    occ_id: str
    citation_id: str
    citekeys: tuple[str, ...]
    fingerprints: dict[str, str]
    formatted: str
    state: Literal["live", "deleted", "touched"]


class SourceChangedError(WriteError):
    """Fonte mudou desde o export — sha256 do corpo diverge do span-map (Task 8)."""


class StructuralChangeError(WriteError):
    """Guarda A: mudança rastreada/comentário dentro de tabela, nota ou equação (Task 3)."""


class MarkLostError(WriteError):
    """Guarda B: uma marca extraída não pousou no destino — contagem não fecha (Task 7/9)."""


class CitationConservationError(WriteError):
    """Conservação de citação violada — I2/I2b/I8.

    Cobre, entre outros: campo `fldChar` desbalanceado ("campo colapsado",
    I2b — Task 1), payload JSON inválido num campo Zotero (I2 — Task 1),
    occ_id duplicado (Task 2), multiconjunto de occ/citekeys divergente do
    citemap (Task 2), fingerprint re-chaveado (I3-lite — Task 2), citação
    `touched` (decisão humana necessária — Task 2), docx igual ao
    exportado ou fora de sincronia (I8 — Task 8).
    """


class AdeuUnavailableError(WriteError):
    """Backend pinado `uvx adeu==1.29.0` ausente ou terminou com exit != 0 (Task 4)."""


@dataclass
class _FieldRun:
    """Um `<w:r>` do documento + se está sob ancestral `w:ins`/`w:del`.

    ElementTree não tem ponteiro de pai (diferente de lxml): a recursão em
    :func:`_collect_runs` carrega esse estado descendo pela árvore.
    """

    element: ET.Element
    in_ins: bool
    in_del: bool


def _local_tag(tag: str) -> str:
    """``{namespace}nome`` (Clark notation) → só ``nome``."""
    _, _, local = tag.rpartition("}")
    return local or tag


def _parse_document_xml(xml_bytes: bytes, docx_path: Path) -> ET.Element:
    """``ET.fromstring`` de ``word/document.xml`` traduzindo XML malformado
    em ``ValueError`` pt-BR acionável (achado do review final da Fase 2,
    Important #1 — ``reviewed_docx`` é o input mais hostil do sistema,
    chega por e-mail; um ``xml.etree.ElementTree.ParseError`` cru vazava
    traceback pelo CLI, fora de `_REVIEW_CATCHES`, que só reconhece
    `ValueError`/exceções próprias deste módulo). Ausência da parte em si
    (zip sem ``word/document.xml``) já é coberta antes, por
    `export._validate_docx_structure` (preflight de `ingest()`) — este
    helper só cobre a parte PRESENTE mas com XML inválido.

    Compartilhado pelos DOIS pontos deste módulo que fazem o parse bruto de
    `word/document.xml` do docx que VOLTA do coautor: a Guarda A
    (:func:`assert_no_structural_changes`) e o leitor stateful
    (:func:`read_docx_citations_with_state`) — sem os dois cobertos, a
    Guarda A (que roda primeiro dentro de `ingest()`) continuaria vazando o
    `ParseError` cru mesmo com o leitor corrigido."""
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(
            f"word/document.xml malformado em {docx_path}: {exc}. O docx "
            "revisado parece corrompido — confirme que o coautor enviou o "
            "arquivo .docx correto (não .doc renomeado/truncado) e rode "
            "novamente `prumo write review ingest ...`."
        ) from exc


def _collect_runs(root: ET.Element) -> list[_FieldRun]:
    """Percorre a árvore em ordem de documento coletando cada `<w:r>` com o
    estado de ancestralidade `w:ins`/`w:del` no momento em que aparece.

    Pré-ordem == ordem do documento (irmãos são visitados na ordem em que
    aparecem no XML); a profundidade da recursão é a profundidade da
    árvore OOXML (tipicamente ~5 níveis), não o número de elementos —
    sem risco de estouro de pilha em documentos grandes.
    """
    runs: list[_FieldRun] = []

    def _walk(elem: ET.Element, in_ins: bool, in_del: bool) -> None:
        tag = _local_tag(elem.tag)
        if tag == "ins":
            in_ins = True
        elif tag == "del":
            in_del = True
        if tag == "r":
            runs.append(_FieldRun(elem, in_ins, in_del))
        for child in elem:
            _walk(child, in_ins, in_del)

    _walk(root, False, False)
    return runs


def _run_instr_text(run: _FieldRun) -> str | None:
    """Texto de `<w:instrText>` (ou `<w:delInstrText>`, quando o Word
    renomeia o campo dentro de uma deleção rastreada — ECMA-376 §17.16.14,
    I2b) dentro do run, se houver (senão ``None``)."""
    node = run.element.find(f"{W_NS}instrText")
    if node is None:
        node = run.element.find(f"{W_NS}delInstrText")
    if node is None:
        return None
    return node.text or ""


def _run_fld_char_type(run: _FieldRun) -> str | None:
    """Valor de `w:fldCharType` do `<w:fldChar>` dentro do run, se houver."""
    node = run.element.find(f"{W_NS}fldChar")
    if node is None:
        return None
    return node.get(f"{W_NS}fldCharType")


def _frame_instr_text(frame: list[_FieldRun]) -> str | None:
    """Concatena o texto de todos os `<w:instrText>` do campo.

    Normalmente um único run carrega o instrText inteiro, mas o Word por
    vezes fragmenta em runs adjacentes (ex.: fronteira de revisão
    ortográfica) — concatenar é o comportamento seguro.
    """
    parts: list[str] = []
    found = False
    for run in frame:
        text = _run_instr_text(run)
        if text is not None:
            found = True
            parts.append(text)
    return "".join(parts) if found else None


def _frame_state(frame: list[_FieldRun]) -> Literal["live", "deleted", "touched"]:
    """``deleted`` se TODOS os runs do campo têm ancestral `w:del`; `touched`
    se ALGUM run tem ancestral `w:ins`/`w:del` (mas não todos `w:del`);
    senão `live`."""
    if frame and all(run.in_del for run in frame):
        return "deleted"
    if any(run.in_ins or run.in_del for run in frame):
        return "touched"
    return "live"


def _citation_from_frame(frame: list[_FieldRun], instr: str, occ_index: int) -> DocxCitation:
    """Monta o :class:`DocxCitation` de um campo Zotero já fechado (begin..end).

    O parse do JSON (slice a partir do marcador + ``json.loads``) é
    compartilhado com o leitor stateless via :func:`export._parse_csl_payload`
    — chamado aqui SEM ``html.unescape`` porque ``instr`` já veio do
    ElementTree, que resolve as entidades XML uma única vez ao montar a
    árvore. Aplicar ``html.unescape`` de novo por cima (como o código fazia
    antes do achado do review da Fase 2/Task 1 — Finding 2) corrompia
    fingerprints/formatted com padrões tipo ``&amp;para=``: o ET já resolve
    para ``&para=`` correto, e um segundo unescape reinterpreta ``&para``
    como a entidade HTML5 sem `;` (¶).
    """
    payload = cast(
        dict[str, Any],
        _parse_csl_payload(instr, occ_index, error_cls=CitationConservationError),
    )
    citation_items = payload.get("citationItems") or []
    citekeys = tuple(item["id"] for item in citation_items)
    fingerprints = {item["id"]: item.get("prumoFingerprint", "") for item in citation_items}
    formatted = (payload.get("properties") or {}).get("formattedCitation", "")
    return DocxCitation(
        occ_id=str(payload.get("prumoOcc", "")),
        citation_id=str(payload.get("citationID", "")),
        citekeys=citekeys,
        fingerprints=fingerprints,
        formatted=str(formatted),
        state=_frame_state(frame),
    )


def read_docx_citations_with_state(docx_path: Path) -> list[DocxCitation]:
    """Lê as citações do docx revisado com estado `live`/`deleted`/`touched` — I2b.

    Sibling STATEFUL de ``export._read_docx_citations`` (I2, sem estado):
    percorre `word/document.xml` com ElementTree (padrão de `comments.py`,
    `W_NS`) na ordem do documento, reconstrói cada campo (sequência
    `fldChar begin` … `instrText` … `fldChar end`) via pilha, e classifica
    o estado a partir dos ancestrais `w:ins`/`w:del` de TODOS os runs do
    campo (begin..end inclusive) — nunca do conteúdo textual, que o
    coautor não pode editar (campo travado, I4). Reconhece tanto
    `w:instrText` quanto `w:delInstrText` (Word renomeia o campo ao
    deletá-lo sob Track Changes — ECMA-376 §17.16.14, I2b).

    Não faz conservação (isso é ``check_conservation``, Task 2) nem decide
    se um campo sobreviveu contra o citemap — só lê e classifica o que
    está no XML agora, na ordem em que aparece.

    Levanta :class:`CitationConservationError` (I2b, "campo colapsado") se
    algum `fldChar` estiver desbalanceado (`begin` sem `end`, ou `end`
    órfão) — sinal de corrupção do XML (ex.: colar texto sobre um limite
    de campo) que invalida a leitura sequencial de campos daí em diante.
    Também levanta a mesma exceção (I2) se o JSON de um campo Zotero for
    inválido, nomeando o índice do campo (1-based, só entre campos
    Zotero). Levanta ``ValueError`` pt-BR (via :func:`_parse_document_xml`,
    achado do review final, Important #1) se `word/document.xml` em si for
    XML malformado — nunca o `ET.ParseError` cru do stdlib.
    """
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")
    root = _parse_document_xml(xml_bytes, docx_path)
    runs = _collect_runs(root)

    citations: list[DocxCitation] = []
    stack: list[list[_FieldRun]] = []
    fld_char_index = 0
    occ_index = 0

    for run in runs:
        fld_type = _run_fld_char_type(run)
        if fld_type is not None:
            fld_char_index += 1

        if fld_type == "begin":
            stack.append([run])
            continue

        if fld_type == "end":
            if not stack:
                raise CitationConservationError(
                    "Campo OOXML colapsado em word/document.xml "
                    f'({docx_path}): `fldChar type="end"` (#{fld_char_index}) '
                    "sem `begin` correspondente. Provável corrupção do XML "
                    "(ex.: colar texto sobre um limite de campo) — I2b. "
                    "Re-exporte com `prumo write export --to docx` e peça "
                    "nova revisão sobre um docx novo."
                )
            frame = stack.pop()
            frame.append(run)
            instr = _frame_instr_text(frame)
            if instr is not None and _ZOTERO_ITEM_CSL_MARKER in instr:
                occ_index += 1
                citations.append(_citation_from_frame(frame, instr, occ_index))
            continue

        if stack:
            stack[-1].append(run)

    if stack:
        raise CitationConservationError(
            "Campo OOXML colapsado em word/document.xml "
            f'({docx_path}): {len(stack)} campo(s) com `fldChar type="begin"` '
            "sem `end` correspondente. Provável corrupção do XML — I2b. "
            "Re-exporte com `prumo write export --to docx` e peça nova "
            "revisão sobre um docx novo."
        )

    return citations


def check_conservation(observed: list[DocxCitation], citemap: CiteMapFile) -> list[DocxCitation]:
    """Confere a conservação de citações do docx revisado (I2/I2b/I3-lite).

    ``observed`` é a saída do leitor stateful (:func:`read_docx_citations_with_state`)
    sobre o docx que voltou do coautor; ``citemap`` é o EXPECTED gravado no
    export (:class:`CiteMapFile`). Hard-fail (:class:`CitationConservationError`,
    pt-BR, nomeando occ_ids/citekeys) na primeira divergência encontrada, nesta
    ordem:

    1. **occ_id duplicado** no observado (paste-clone, I2b). Caso especial
       diagnosticado: se a duplicata é EXATAMENTE um par `deleted` + `touched`
       — a cópia sobrevivente está inteira dentro de `w:ins` (Word marca assim
       o texto colado sob Track Changes) — a mensagem vira um diagnóstico de
       possível MOVE (mover citação não é suportado; I2c permanece
       diagnóstico). Qualquer outra combinação de duplicatas usa a mensagem
       genérica. Continua hard-fail nos dois casos; só o diagnóstico melhora.
    2. **Multiconjunto** `{occ_id: citekeys}` de TODOS os estados (live +
       touched + deleted) precisa bater com o citemap: occ ausente do
       observado (campo achatado/hard-deleted sem rastro — deleção RASTREADA
       preserva o campo no XML, validado no spike do plano) ou occ extra (sem
       par no citemap) ou citekeys divergentes para o mesmo occ_id — qualquer
       um dos três dispara o gate.
    3. **Fingerprints** — para cada occ comum aos dois lados, o fingerprint
       por citekey observado precisa bater com o do citemap (re-key/shadow do
       Zotero/BBT desde o export, I3-lite; revalidação BBT plena fica para a
       Fase 4).
    4. **`touched`** — qualquer citação com campo tocado por `w:ins`/`w:del`
       (mas não inteiramente deletada) é fail-informativo: o MVP não
       transplanta CITATION-TOUCHED, decisão humana é necessária (I2c
       permanece diagnóstico).

    Retorna a lista das citações `deleted` (candidatas a evento de drop
    pendente de confirmação explícita no `apply`, Task 9) quando NENHUMA
    divergência dispara os gates acima.
    """
    by_occ: dict[str, list[DocxCitation]] = {}
    for citation in observed:
        by_occ.setdefault(citation.occ_id, []).append(citation)

    for occ_id, group in by_occ.items():
        if len(group) < 2:
            continue
        states = {citation.state for citation in group}
        if len(group) == 2 and states == {"deleted", "touched"}:
            raise CitationConservationError(
                f"possível MOVE de citação (occ {occ_id}) — mover citação "
                "não é suportado; rejeite a mudança no Word e mova via "
                "edição da fonte (I2c)."
            )
        duplicated_citekeys = sorted({key for c in group for key in c.citekeys})
        raise CitationConservationError(
            f"occ_id duplicado no docx revisado: occ {occ_id} (citekeys "
            f"{', '.join(duplicated_citekeys)}) aparece {len(group)}x em "
            "word/document.xml (paste-clone, I2b). Rejeite a mudança no "
            "Word e mantenha uma única ocorrência do campo por citação; "
            "re-exporte com `prumo write export --to docx` se precisar "
            "recomeçar a revisão."
        )

    observed_citekeys: dict[str, list[str]] = {
        citation.occ_id: list(citation.citekeys) for citation in observed
    }
    citemap_citekeys: dict[str, list[str]] = {
        occ.occ_id: occ.citekeys for occ in citemap.occurrences
    }

    missing = sorted(set(citemap_citekeys) - set(observed_citekeys))
    if missing:
        missing_desc = "; ".join(
            f"occ {occ_id} (citekeys {', '.join(citemap_citekeys[occ_id])})" for occ_id in missing
        )
        raise CitationConservationError(
            f"Citação(ões) ausente(s) no docx revisado: {missing_desc} não "
            "aparece(m) mais em word/document.xml (achatada(s)/hard "
            "delete, I2) — deleção RASTREADA preserva o campo no XML, "
            "então o(s) campo(s) sumiu(ram) sem rastro. Rejeite a mudança "
            "no Word (delete a citação com Track Changes ativo) ou "
            "restaure o campo, e re-ingira."
        )

    extra = sorted(set(observed_citekeys) - set(citemap_citekeys))
    if extra:
        extra_desc = "; ".join(
            f"occ {occ_id} (citekeys {', '.join(observed_citekeys[occ_id])})" for occ_id in extra
        )
        raise CitationConservationError(
            f"Citação(ões) extra(s) no docx revisado: {extra_desc} não "
            "consta(m) no citemap (I2). Citação nova não é suportada "
            "neste MVP; re-exporte com `prumo write export --to docx` e "
            "reaplique a revisão sobre o docx novo."
        )

    for occ_id, expected_keys in citemap_citekeys.items():
        if observed_citekeys[occ_id] != expected_keys:
            raise CitationConservationError(
                f"Citekeys divergentes para occ {occ_id}: docx revisado tem "
                f"{observed_citekeys[occ_id]!r}, citemap tem "
                f"{expected_keys!r} (campo re-chaveado, I2). Re-exporte com "
                "`prumo write export --to docx` e reaplique a revisão sobre "
                "o docx novo."
            )

    citemap_fingerprints: dict[str, dict[str, str]] = {
        occ.occ_id: occ.fingerprints for occ in citemap.occurrences
    }
    for citation in observed:
        expected_fingerprints = citemap_fingerprints[citation.occ_id]
        if citation.fingerprints != expected_fingerprints:
            mismatched = sorted(
                key
                for key in set(citation.fingerprints) | set(expected_fingerprints)
                if citation.fingerprints.get(key) != expected_fingerprints.get(key)
            )
            raise CitationConservationError(
                f"Fingerprint divergente na citação occ {citation.occ_id} "
                f"(citekey(s) {', '.join(mismatched)}) — possível "
                "re-chaveamento no Zotero/BBT desde o export (I3-lite). "
                "Re-exporte com `prumo write export --to docx` e reaplique "
                "a revisão sobre o docx novo."
            )

    touched = [citation for citation in observed if citation.state == "touched"]
    if touched:
        occ_ids = ", ".join(citation.occ_id for citation in touched)
        raise CitationConservationError(
            f"citação editada dentro do campo (occ {occ_ids}) — decisão "
            "humana necessária; MVP não transplanta CITATION-TOUCHED; "
            "rejeite a mudança no Word ou trate manualmente."
        )

    return [citation for citation in observed if citation.state == "deleted"]


# --- Guarda A: mudanças estruturais (Task 3) --------------------------------
#
# Tabela/nota/equação não têm contrapartida confiável no texto normalizado
# que o adeu extrai (prosa linear) — o localizador de âncora única (Task 6)
# não sabe onde transplantar uma mudança que vive só na estrutura OOXML.
# Guarda A hard-fail ANTES de chamar o adeu (Task 8 chama esta função no
# preflight do `ingest`, antes do leitor/conservação) para essas 3 regiões,
# nomeadas na ordem em que o brief as lista: tabela, nota, equação.

_STRUCTURAL_FIX_INSTRUCTION = (
    "peça ao coautor para mover a mudança para o corpo do texto ou aplique "
    "manualmente; re-exporte e re-ingira"
)

_STRUCTURAL_KIND_LABELS = {
    "ins": "inserção rastreada",
    "del": "deleção rastreada",
    "commentRangeStart": "comentário",
}


def _region_text(elem: ET.Element) -> str:
    """Concatena o texto de `w:t`/`m:t`/`w:delText` dentro do elemento,
    casando pelo NOME LOCAL (ignora namespace, via :func:`_local_tag`): `w:t`
    (texto normal) e `m:t` (texto de run matemático, ECMA-376 parte 1
    §22.1.2.147) têm o mesmo nome local `t` em namespaces diferentes, então
    um único filtro cobre tanto célula/nota quanto equação sem precisar de
    dois caminhos. Usado só para o trecho (60 chars) da mensagem da Guarda A
    — não precisa ser posicionalmente exato, só identificar a região para o
    coautor."""
    parts = [node.text or "" for node in elem.iter() if _local_tag(node.tag) in ("t", "delText")]
    return "".join(parts).strip()


def _first_table_hit(document_xml: ET.Element) -> tuple[str, str] | None:
    """Primeiro `w:ins`/`w:del`/`w:commentRangeStart` achado com ancestral
    `w:tbl` (regra (a) do brief, literal), em ordem de documento — ou `None`
    se nenhum.

    Ancestral é `w:tbl`, não `w:tc`, DE PROPÓSITO: cobre tanto a mudança de
    CONTEÚDO dentro de célula (`w:tbl > w:tr > w:tc > w:p > w:ins`, a forma
    mais comum, descrita no brief) quanto o marcador de linha INTEIRA
    inserida/deletada sob Track Changes (`w:tr > w:trPr > w:ins` — mesma tag
    `w:ins`, mas fora de qualquer `w:tc`, então um filtro por `w:tc` deixaria
    esse caso passar batido). Itera `w:tbl` diretamente (não desce por
    `w:tr`/`w:tc` manualmente): no caso raro de tabela aninhada, a mudança é
    reportada com o texto da tabela EXTERNA como trecho — mais abrangente
    que a célula específica, mas ainda identifica a região; precisão fina de
    aninhamento não é objetivo da Guarda A, só apontar a região pro coautor.

    Retorna `(kind, trecho)` com `trecho` já truncado em 60 chars — o texto
    vem da TABELA inteira, não só do `w:ins`/`w:del`, porque
    `w:commentRangeStart` (e o marcador de linha) são elementos vazios sem
    texto próprio.
    """
    for tbl in document_xml.iter(f"{W_NS}tbl"):
        for kind in ("ins", "del", "commentRangeStart"):
            if next(tbl.iter(f"{W_NS}{kind}"), None) is not None:
                return kind, _region_text(tbl)[:60]
    return None


def _first_note_hit(note_root: ET.Element, note_tag: str) -> tuple[str, str] | None:
    """Primeiro `w:ins`/`w:del` achado dentro de qualquer `w:footnote`/
    `w:endnote` da PARTE já parseada (`note_root` é a raiz de
    `footnotes.xml`/`endnotes.xml`) — ou `None` se nenhum. `note_tag` é
    `"footnote"` ou `"endnote"` conforme a parte lida pelo chamador."""
    for note in note_root.iter(f"{W_NS}{note_tag}"):
        for kind in ("ins", "del"):
            if next(note.iter(f"{W_NS}{kind}"), None) is not None:
                return kind, _region_text(note)[:60]
    return None


def _first_omath_hit(document_xml: ET.Element) -> tuple[str, str] | None:
    """Primeiro `w:ins`/`w:del` achado dentro de uma equação (`m:oMath`) —
    ou `None` se nenhum. Mesma lógica de :func:`_first_table_hit`: iterar
    `m:oMath` diretamente cobre equação aninhada sem contagem dupla."""
    for omath in document_xml.iter(f"{M_NS}oMath"):
        for kind in ("ins", "del"):
            if next(omath.iter(f"{W_NS}{kind}"), None) is not None:
                return kind, _region_text(omath)[:60]
    return None


def _structural_change_message(region: str, kind: str, excerpt: str) -> str:
    """Mensagem pt-BR única da Guarda A, compartilhada pelas 3 regiões
    (tabela/nota/equação) — nomeia a região, o rótulo humano de `kind` e o
    trecho (60 chars, já truncado pelo chamador), e embute o comando de
    correção (regra de mensagens de usuário, `.claude/rules/code.md`)."""
    label = _STRUCTURAL_KIND_LABELS.get(kind, kind)
    return (
        f"Mudança estrutural não suportada em região de {region}: {label} "
        f'(trecho: "{excerpt}"). O ingest de review não transplanta mudanças '
        "dentro de tabelas, notas de rodapé/fim ou equações — "
        f"{_STRUCTURAL_FIX_INSTRUCTION}."
    )


def assert_no_structural_changes(docx_path: Path) -> None:
    """Guarda A: hard-fail se o docx revisado tiver mudança rastreada ou
    comentário numa região estrutural que o transplante por âncora de texto
    (Task 6/7, sobre a prosa linear extraída pelo adeu) não sabe localizar —
    tabela, nota de rodapé/fim, ou equação (oMath). Mudança rastreada NO
    CORPO do texto (fora dessas 3 regiões) passa livre: é o caminho normal
    do pipeline.

    Verifica nesta ordem, parando no primeiro achado (mesmo estilo hard-fail
    de :func:`check_conservation` — primeira divergência encontrada):

    (a) **tabela** — `w:ins`/`w:del`/`w:commentRangeStart` com ancestral
        `w:tbl` (cobre tanto conteúdo dentro de célula quanto o marcador de
        linha inteira inserida/deletada).
    (b) **nota** — `word/footnotes.xml`/`word/endnotes.xml`, se existirem
        como parte do zip, contendo `w:ins`/`w:del` dentro de algum
        `w:footnote`/`w:endnote` (partes SEPARADAS de `word/document.xml`
        no formato OOXML — não aparecem lá).
    (c) **equação** — `w:ins`/`w:del` com ancestral `m:oMath` (namespace
        math, ECMA-376 parte 1).

    Levanta :class:`StructuralChangeError` nomeando a região, o tipo
    (inserção/deleção/comentário) e os 60 primeiros chars do texto da
    região (tabela/nota/equação inteira — não só do `w:ins`/`w:del`, porque
    `w:commentRangeStart` não tem texto próprio), instruindo a mover a
    mudança para o corpo do texto ou aplicar manualmente, re-exportar e
    re-ingerir. Levanta ``ValueError`` pt-BR (via :func:`_parse_document_xml`,
    achado do review final, Important #1) se `word/document.xml` em si for
    XML malformado — Guarda A roda ANTES do leitor stateful dentro de
    `ingest()`, então precisa da MESMA tradução para não vazar o
    `ET.ParseError` cru primeiro.
    """
    with zipfile.ZipFile(docx_path) as z:
        document_xml = _parse_document_xml(z.read("word/document.xml"), docx_path)
        note_parts: list[tuple[str, ET.Element]] = []
        for part_name, note_tag in (
            ("word/footnotes.xml", "footnote"),
            ("word/endnotes.xml", "endnote"),
        ):
            try:
                note_parts.append((note_tag, ET.fromstring(z.read(part_name))))
            except KeyError:
                continue

    table_hit = _first_table_hit(document_xml)
    if table_hit is not None:
        kind, excerpt = table_hit
        raise StructuralChangeError(_structural_change_message("tabela", kind, excerpt))

    for note_tag, note_root in note_parts:
        note_hit = _first_note_hit(note_root, note_tag)
        if note_hit is not None:
            kind, excerpt = note_hit
            raise StructuralChangeError(_structural_change_message("nota", kind, excerpt))

    omath_hit = _first_omath_hit(document_xml)
    if omath_hit is not None:
        kind, excerpt = omath_hit
        raise StructuralChangeError(_structural_change_message("equação", kind, excerpt))


# --- Task 4: seam do adeu pinado + parser de marcas com autoria -------------
#
# Prosa (NUNCA citação — Fase 0, decisão (b); citação é sempre
# `read_docx_citations_with_state` acima) vem do backend PINADO
# `uvx adeu==1.29.0`: o formato de saída — marcas CriticMarkup com a
# anotação `[Chg:<id> insert|delete] <Autor>` colada IMEDIATAMENTE depois de
# cada marca de conteúdo, validado no spike — é contrato implícito com o
# parser abaixo. Pinado de propósito (nunca `adeu` sem versão, nunca `>=`):
# uma versão nova do backend poderia mudar esse formato sem aviso e quebrar
# o pareamento em silêncio; a golden fixture do teste trava esse contrato.

_ADEU_FOOTER_MARKER = "\n---\n## Footnotes"

_UNKNOWN_AUTHOR = "(desconhecido)"

# Guia de remediação compartilhado pelas duas falhas do seam (uvx ausente e
# exit != 0) — o brief pede a MESMA orientação pt-BR nos dois casos: instalar
# o uv e confirmar a versão pinada do adeu.
_ADEU_INSTALL_HINT = (
    "Instale o uv (https://docs.astral.sh/uv/), confirme com `uv --version` "
    "e rode `uvx adeu==1.29.0 --version` para confirmar/baixar a versão "
    "pinada do backend de PROSA."
)

# Identidade de erro do adeu para o motor comum de ferramenta pinada
# (`core/uvx.run_pinned`) — rótulos byte-idênticos ao wording que este
# módulo emitia antes da extração (travados pelos testes do seam).
_ADEU_TOOL = PinnedTool(
    error_cls=AdeuUnavailableError,
    hint=_ADEU_INSTALL_HINT,
    missing_label="adeu (backend de PROSA pinado, `uvx adeu==1.29.0`)",
    timeout_label="adeu (backend de PROSA pinado, `uvx adeu==1.29.0`)",
    timeout_detail="rede lenta no primeiro download do uvx? Re-rode.",
    exit_label="adeu (backend de PROSA pinado, `uvx adeu==1.29.0`)",
)


def _check_uvx_on_path() -> None:
    """Preflight 3a: o backend de prosa (adeu via uvx) precisa existir antes de começar."""
    if shutil.which("uvx") is None:
        raise AdeuUnavailableError(
            "uvx não encontrado no PATH — o backend de prosa (adeu pinado) roda via uv. "
            "Instale o uv (https://docs.astral.sh/uv/) e confirme: `uvx adeu==1.29.0 --version`."
        )


# Corpo de anotação: `[Chg:<id> insert|delete] <Autor>`. `search` (não
# `match`/`fullmatch`) de propósito: o formato alternativo markup-path do
# adeu (`{>>Diff: ...<<}`) pode trazer o padrão em QUALQUER posição do
# corpo, não só no início — brief: "a menos que contenha [Chg:...]".
_CHG_ANNOTATION_RE = re.compile(r"\[Chg:(?P<chg_id>\d+) (?:insert|delete)\]\s+(?P<author>.+)$")


def _run_adeu_extract(docx_path: Path) -> str:
    """Roda ``uvx adeu==1.29.0 extract --json <docx> -o -`` e devolve o
    campo ``markdown`` do JSON de stdout — cru, sem parse de marcas (isso é
    :func:`parse_adeu_markdown`).

    Seam isolado de propósito para mock nos testes (regra deste repo:
    dependência externa SEMPRE mockada no seam — `.claude/rules/code.md`).
    Versão PINADA (``adeu==1.29.0``, nunca flutuante) pelo motivo descrito no
    comentário da seção acima.

    ``uvx`` ausente no PATH, timeout e exit != 0 (adeu resolvido mas falhou
    — docx incompatível, versão incorreta, etc.) viram a MESMA
    :class:`AdeuUnavailableError`, via o motor comum
    :func:`prumo_assist.core.uvx.run_pinned` (rótulos em ``_ADEU_TOOL``): o
    chamador (Task 8, ``ingest``) só precisa tratar um único tipo de falha
    do backend de prosa. O mesmo vale para stdout que não é o JSON esperado
    (:class:`json.JSONDecodeError`) ou JSON válido sem o campo ``markdown``
    (:class:`KeyError`) — achado do review da Task 4, endossado como
    MUST-DO para a Task 8: sem este catch, as duas exceções vazavam cruas
    (tipo Python interno, sem o comando de correção pt-BR que este módulo
    garante em todo outro hard-fail).
    """
    proc = run_pinned(
        _ADEU_TOOL,
        ["uvx", "adeu==1.29.0", "extract", "--json", str(docx_path), "-o", "-"],
        timeout=120,
    )

    try:
        payload = cast(dict[str, Any], json.loads(proc.stdout))
        return str(payload["markdown"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AdeuUnavailableError(
            "saída do adeu não é o JSON esperado (campo 'markdown') — confirme "
            "a versão pinada: `uvx adeu==1.29.0 --version`; detalhe: "
            f"{exc!r}"
        ) from exc


@dataclass(frozen=True)
class ReviewMark:
    """Marca CriticMarkup do adeu pareada com a anotação de autoria `[Chg:...]`.

    ``kind``/``a``/``b`` têm a MESMA semântica de
    :class:`prumo_assist.core.criticmarkup.Mark` (kind ∈
    ins/del/sub/highlight/comment; ``a``/``b`` conforme o kind — ver
    docstring daquele módulo). ``author``/``chg_id`` vêm do corpo
    `[Chg:<id> insert|delete] <Autor>` da anotação que o adeu cola
    IMEDIATAMENTE depois da marca de conteúdo (uma marca ``comment`` cujo
    ``start`` == ``end`` da marca anterior — ver :func:`parse_adeu_markdown`
    para a regra exata de pareamento). Ficam ``chg_id=None`` e
    ``author="(desconhecido)"`` quando: (1) a marca de conteúdo não tem
    anotação colada em seguida; ou (2) a anotação existe (pareada OU órfã)
    mas o corpo não casa o padrão — cobre o formato alternativo
    markup-path do adeu, `{>>Diff: ...<<}`, que também pareia mas raramente
    carrega um `[Chg:...]` reconhecível.

    ``start``/``end`` — DECISÃO DE DESIGN (Task 4): offsets no TEXTO LIMPO
    (primeiro elemento da tupla que :func:`parse_adeu_markdown` retorna),
    ou seja, APÓS remover as anotações PAREADAS e o rodapé
    `\\n---\\n## Footnotes` — NUNCA offsets do markdown cru que o adeu
    emite. Motivo: é o ``clean_text`` que a Task 6 (``locate_marks_in_norm``)
    usa para localizar cada marca por âncora de contexto no texto
    normalizado; expor offsets do markdown cru obrigaria a Task 6 a
    recalcular o mesmo shift de anotações removidas para nenhum ganho — o
    ``clean_text`` é a única representação textual que sai deste módulo.
    """

    kind: criticmarkup.MarkKind
    a: str
    b: str
    author: str
    chg_id: str | None
    start: int
    end: int


def _extract_annotation(body: str) -> tuple[str | None, str]:
    """``(chg_id, author)`` do corpo de uma anotação, ou
    ``(None, "(desconhecido)")`` se o corpo não casar o padrão
    `[Chg:<id> insert|delete] <Autor>` em lugar nenhum (``search``, não
    ``match``: cobre também `{>>Diff: ...<<}` quando o padrão aparece
    embutido em vez de ocupar o corpo inteiro).

    Mesma extração usada tanto para anotação PAREADA (corpo da marca
    ``comment`` seguinte à marca de conteúdo) quanto para comment-annotation
    ÓRFÃ (corpo da própria marca ``comment``, sem marca de conteúdo
    imediatamente antes) — per design da Task 4: a autoria de uma anotação
    nunca depende de estar pareada.
    """
    match = _CHG_ANNOTATION_RE.search(body)
    if match is None:
        return None, _UNKNOWN_AUTHOR
    return match.group("chg_id"), match.group("author").strip()


def parse_adeu_markdown(markdown: str) -> tuple[str, list[ReviewMark]]:
    """Extrai as marcas de prosa do markdown do adeu, pareadas com autoria.

    Descarta primeiro o rodapé `\\n---\\n## Footnotes` (e tudo depois) —
    ANTES de rodar :func:`core.criticmarkup.parse` — para que o rodapé nunca
    apareça no ``clean_text`` nem influencie nenhum offset. Sobre o
    restante, ``criticmarkup.parse`` extrai as marcas planas (ins/del/sub/
    highlight/comment) na ordem em que aparecem no texto.

    Pareamento (marca de conteúdo → anotação): uma marca ``comment`` é a
    anotação de PAREAMENTO da marca imediatamente anterior quando (a) a
    marca anterior NÃO é ela mesma um ``comment`` (evita encadear
    anotação→anotação, ex.: duas comments encostadas) e (b)
    ``comment.start == anterior.end`` (adjacência zero-gap no texto cru —
    nenhum caractere entre as duas marcas). Marca de conteúdo sem anotação
    colada, ou ``comment`` sem marca de conteúdo IMEDIATAMENTE anterior
    (órfã), ficam com ``author="(desconhecido)"`` — a órfã AINDA vira seu
    próprio :class:`ReviewMark` de ``kind="comment"`` (nunca é descartada,
    só não pareia). O formato markup-path `{>>Diff: ...<<}` pareia pela
    MESMA regra de adjacência; só a extração de autor/chg_id (via
    :func:`_extract_annotation`) costuma falhar para esse formato.

    Anotações PAREADAS são removidas do ``clean_text`` retornado (elas não
    transplantam — Task 6/7 trabalham só com a marca de conteúdo);
    comentários órfãos permanecem no texto (não há o que remover: nada os
    "contém"). Offsets de cada :class:`ReviewMark` são recalculados para o
    ``clean_text`` — ver docstring de :class:`ReviewMark` para a
    justificativa completa dessa decisão.

    Returns:
        Tupla ``(clean_text, review_marks)``, NESTA ordem.
    """
    footer_idx = markdown.find(_ADEU_FOOTER_MARKER)
    raw = markdown if footer_idx == -1 else markdown[:footer_idx]
    marks = criticmarkup.parse(raw)

    # índice da marca de CONTEÚDO -> índice da marca comment que a anota.
    paired_annotation_at: dict[int, int] = {}
    for i in range(1, len(marks)):
        previous = marks[i - 1]
        current = marks[i]
        if (
            current.kind == "comment"
            and previous.kind != "comment"
            and current.start == previous.end
        ):
            paired_annotation_at[i - 1] = i

    removed_indices = set(paired_annotation_at.values())

    clean_parts: list[str] = []
    clean_len = 0
    cursor = 0
    review_marks: list[ReviewMark] = []

    for i, mark in enumerate(marks):
        if i in removed_indices:
            # Anotação PAREADA: some do clean_text (não transplanta) — só o
            # texto entre o cursor e o início dela é preservado.
            clean_parts.append(raw[cursor : mark.start])
            clean_len += mark.start - cursor
            cursor = mark.end
            continue

        segment = raw[cursor : mark.end]
        clean_parts.append(segment)
        new_end = clean_len + len(segment)
        new_start = new_end - (mark.end - mark.start)
        clean_len = new_end
        cursor = mark.end

        if i in paired_annotation_at:
            chg_id, author = _extract_annotation(marks[paired_annotation_at[i]].b)
        elif mark.kind == "comment":
            chg_id, author = _extract_annotation(mark.b)
        else:
            chg_id, author = None, _UNKNOWN_AUTHOR

        review_marks.append(
            ReviewMark(
                kind=mark.kind,
                a=mark.a,
                b=mark.b,
                author=author,
                chg_id=chg_id,
                start=new_start,
                end=new_end,
            )
        )

    clean_parts.append(raw[cursor:])
    return "".join(clean_parts), review_marks


# --- Task 5: coleta de comentários (ReviewCommentsFile) ----------------------


def collect_review_comments(docx_path: Path, page: str) -> ReviewCommentsFile:
    """Extrai comentários de um docx revisado e retorna ReviewCommentsFile.

    Reusar `extract_from_docx` (de `domains/write/comments.py`) para coletar
    comentários do docx; mapear cada `Comment` para `ReviewComment` com:
    - id: do comment
    - author: do comment
    - date: do comment (pode ser None)
    - text: do comment
    - anchor_text: do comment (pode ser None)
    - reply_of: None no MVP

    Returns:
        `ReviewCommentsFile` com schema_version e page preenchidos, lista de
        comentários mapeados.
    """
    result = extract_from_docx(docx_path)

    review_comments: list[ReviewComment] = []
    for comment in result.comments:
        review_comments.append(
            ReviewComment(
                id=comment.id,
                author=comment.author,
                date=comment.date,
                text=comment.text,
                anchor_text=comment.anchor_text,
                reply_of=None,
            )
        )

    return ReviewCommentsFile(page=page, comments=review_comments)


# --- Task 6: localizador de âncora única (`locate_marks_in_norm`) -----------
#
# DESIGN GERAL (documentado per brief da Task 6 — decisão desta task):
#
# `clean_text` (saída da Task 4) ainda contém a sintaxe CriticMarkup de TODAS
# as marcas de conteúdo (`{++...++}` etc.) — o contexto before/after de uma
# marca não pode conter a sintaxe de OUTRAS marcas vizinhas, só texto plano.
# A representação "texto plano" escolhida aqui é a de PRÉ-IMAGEM: cada marca
# vira o texto que existia ANTES da edição do coautor — exatamente a
# semântica de `criticmarkup.reject` (ins/comment -> ""; del/sub/highlight ->
# `a`) — porque essa pré-imagem é o que deveria bater com `norm_text` (o
# texto ANTES da rodada de revisão). `_plain_reject_rendering` produz esse
# texto (`plain_text`) e, de brinde, o span de CADA marca dentro dele — que
# já É o "alvo" pedido pelo brief (`a` para del/sub/highlight, ponto vazio
# para ins/comment), sem precisar reparsear `clean_text` (os offsets de
# `ReviewMark` já são relativos a ele, per Task 4).
#
# SENTINELA (citação): displays de citação (`(Smith, 2020)`) no lado adeu não
# existem no lado norm (`[@smith2020]`) — sem normalizar os dois para o MESMO
# token, nenhum contexto que contenha uma citação bateria textualmente. Cada
# `occurrence.formatted` é achado por BUSCA SEQUENCIAL em `plain_text` (nunca
# por valor — displays repetidos pareiam pela ORDEM FÍSICA do documento, ou
# seja, `occurrences` ordenadas por `norm_start` ANTES da busca, NUNCA pela
# ordem de LISTA do citemap — ver nota "FIX APÓS REVIEW" abaixo) e cada
# `(occ.norm_start, occ.norm_end)` é substituído DIRETO (já sabemos onde
# está) no lado norm — ambos os lados usam o MESMO índice `i` (posição
# ORIGINAL da occurrence em `citemap.occurrences`, preservada mesmo após o
# reordenamento local para a busca) como id do token `\x00CIT<i>\x00`,
# garantindo que o MESMO token nos dois lados sempre se refere à MESMA
# citação — desde que a ordem FÍSICA concorde entre as duas renderizações
# (ver defesa b abaixo para quando essa suposição falha).
#
# BOOKKEEPING (token-space -> offset original): substituir um span por um
# token de tamanho diferente desloca todo offset posterior — `_OffsetSegment`
# + `_map_offset` mantêm essa correspondência dos DOIS lados (original<->
# sentinela) via uma lista de segmentos cobrindo o texto inteiro (passthrough
# + token, em ordem); os spans localizados são sempre convertidos de volta
# para os OFFSETS ORIGINAIS do `norm_text` antes de retornar — nunca
# vazam offset em espaço-token. O MESMO mecanismo (`_OffsetSegment` +
# `_map_offset`) é reusado por `_collapse_whitespace_with_segments` para o
# colapso de espaços do lado norm (ver "FIX APÓS REVIEW" abaixo) — os dois
# mapas (sentinela + colapso) são COMPOSTOS em sequência (colapsado ->
# sentinela -> original) na busca geral de `locate_marks_in_norm`.
#
# ORDEM contexto vs. sentinela vs. colapso: sentinela PRIMEIRO (texto inteiro
# antes/depois do alvo, sem cortar), colapso de espaços DEPOIS, truncagem
# para 48 chars por ÚLTIMO — nessa ordem porque (a) colapsar antes de
# substituir citação arriscaria corromper o match de `occ.formatted` caso o
# display tenha espaços internos que o colapso mexesse; (b) truncar antes de
# colapsar sub-contaria o orçamento de 48 chars (colapso só encolhe texto,
# nunca cresce). A truncagem é CIENTE de token: nunca corta um
# `\x00CIT<i>\x00` ao meio — empurra o corte para incluir/excluir o token
# INTEIRO (o resultado pode passar de 48 chars nesse caso raro; preferível a
# um token mutilado que nunca bateria com o lado norm).
#
# CLASSIFICAÇÃO do alvo vs. citação (antes de qualquer busca de âncora):
# - ZERO interseção com qualquer span de citação -> segue para a busca normal
#   de âncora (é aqui que o sentinela do CONTEXTO importa).
# - Interseção com EXATAMENTE 1 span, esse span TOTALMENTE contido no alvo, e
#   o que sobra do alvo fora do span é só espaço em branco (ou nada) -> "del
#   de citação": se `kind == "del"` E a identidade da occurrence é CONFIRMADA
#   de forma independente no lado norm (`_confirm_citation_identity_in_norm`,
#   defesa b — ver "FIX APÓS REVIEW" abaixo) E a occurrence está em `deleted`
#   (Task 2/conservação) -> consumida SILENCIOSAMENTE (nem `LocatedMark` nem
#   evento — o evento de drop é da conservação, não duplicamos aqui); se a
#   identidade NÃO é confirmada, ou está confirmada mas não está em
#   `deleted` -> `citation-touched-prose` (adeu "viu" uma deleção que o
#   OOXML não confirma, OU a identidade do lado adeu não é confiável — I1,
#   nunca confiar no adeu para decisão de citação). Mesma classificação
#   geométrica mas `kind != "del"` (ex.: `sub`/`highlight` cobrindo a citação
#   inteira) também vira `citation-touched-prose` — só `del` tem o caminho de
#   "casar com deleted" suportado no MVP.
# - Qualquer OUTRA interseção (parcial, ou múltiplos spans) -> sempre
#   `citation-touched-prose` (decisão humana — I1, nunca auto-aplica).
#
# --- FIX APÓS REVIEW (Fase 2/Task 6, achados Crítico + Importante) ----------
#
# CRÍTICO: `_find_citation_spans_by_search` pareava citemap<->plain_text por
# ORDEM DE LISTA do citemap com um cursor sequencial, enquanto o lado norm já
# reordenava por `norm_start` — quando 2+ occurrences compartilhavam o mesmo
# `formatted` E a ordem do citemap divergia da ordem física, o cursor casava
# o display seguinte com o `occ_index` ERRADO (identity swap). Um `del`
# batendo EXATAMENTE no display da citação LIVE podia então ser resolvido
# para a OUTRA occurrence (a genuinamente `deleted`), sendo consumido
# SILENCIOSAMENTE (`located == [] and events == []`) — uma deleção de
# citação nunca confirmada pelo OOXML desaparecia sem rastro (I1 violado).
# DUAS defesas, nenhuma sozinha suficiente:
#   (a) `_find_citation_spans_by_search` agora ordena `occurrences` por
#       `norm_start` ANTES da busca sequencial (mesma suposição de ordem
#       física dos dois lados) — resolve o caso relatado pelo reviewer, mas
#       depende da ordem física do adeu/plain_text concordar com a do
#       norm_text (pode falhar em casos mais patológicos).
#   (b) `_confirm_citation_identity_in_norm` cross-valida de forma
#       INDEPENDENTE, rodando a mesma busca de âncora do caminho geral com o
#       PRÓPRIO token do `occ_index` como alvo — só consome silenciosamente
#       se o cross-check confirma EXATAMENTE 1 match; caso contrário, emite
#       `citation-touched-prose` via `_citation_identity_unconfirmed_event`
#       (nunca silencioso, mesmo que o `occ_index` atribuído aponte para uma
#       occurrence que ESTÁ em `deleted`).
#
# IMPORTANTE: o colapso de espaços era unilateral — só `plain_text_sentinel`
# (lado adeu) era colapsado antes da busca; `norm_text_sentinel` (lado norm)
# era buscado CRU. Um espaço duplo GENUÍNO na fonte (norm_text) perto do alvo
# quebrava o match (contexto colapsado do lado adeu nunca batia com o texto
# cru do lado norm) -> `unanchored-mark` espúrio. Caminho ESCOLHIDO: colapso
# SIMÉTRICO via `_collapse_whitespace_with_segments` (mesma máquina
# `_OffsetSegment`/`_map_offset` de `_substitute_spans`, com `" "` no lugar
# do token sentinela) aplicado também a `norm_text_sentinel`; a busca final
# roda sobre `norm_text_collapsed`, e os offsets encontrados são convertidos
# de volta para `norm_text` ORIGINAL compondo os dois mapas (colapsado ->
# sentinela -> original) via `_map_offset` chamado duas vezes. A composição
# não se mostrou patológica: tokens de citação (sem espaço interno) nunca são
# tocados pelo colapso (`\s` não casa `\x00`), e cada segmento de colapso tem
# largura 1 no lado colapsado — nenhum offset cai estritamente dentro de um
# segmento de colapso, então a fronteira de token de citação (garantida pela
# truncagem ciente de token do lado adeu) sempre sobrevive intacta pelos dois
# mapas.

_CONTEXT_CHARS = 48

_SENTINEL_TOKEN_RE = re.compile(r"\x00CIT\d+\x00")


def _sentinel_token(occ_index: int) -> str:
    """Token opaco `\x00CIT<i>\x00` — o mesmo índice `i` (posição da
    occurrence em `citemap.occurrences`, ordem do documento) é usado nos dois
    lados (adeu/plain e norm) para a MESMA citação."""
    return f"\x00CIT{occ_index}\x00"


@dataclass(frozen=True)
class LocatedMark:
    """Uma `ReviewMark` localizada no texto normalizado.

    ``norm_start``/``norm_end`` são o span do ALVO no ``norm_text``
    (offsets ORIGINAIS — nunca em espaço-token): para ``del``/``sub`` (e
    ``highlight``), o span do texto que a marca substitui/marca; para
    ``ins``/``comment``, um PONTO (``norm_start == norm_end``) — o lugar
    onde a marca ancora, sem substituir nada existente.
    """

    mark: ReviewMark
    norm_start: int
    norm_end: int


@dataclass(frozen=True)
class _SentinelSpan:
    """Um span (coordenadas do texto ORIGINAL, antes da substituição) que
    vira o token sentinela da occurrence ``occ_index`` (índice em
    ``citemap.occurrences``)."""

    start: int
    end: int
    occ_index: int


@dataclass(frozen=True)
class _OffsetSegment:
    """Um segmento (passthrough OU token) cobrindo `[orig_start, orig_end)`
    no texto ORIGINAL e `[sent_start, sent_end)` no texto SENTINELA — usado
    por :func:`_map_offset` para converter offset nos dois sentidos. Uma
    lista de segmentos cobre o texto INTEIRO, em ordem, sem lacunas."""

    orig_start: int
    orig_end: int
    sent_start: int
    sent_end: int


def _plain_reject_rendering(
    clean_text: str, marks: list[ReviewMark]
) -> tuple[str, list[tuple[int, int]]]:
    """Renderiza `clean_text` trocando cada marca pela sua PRÉ-IMAGEM (texto
    que existia antes da edição — semântica de `criticmarkup.reject`):
    `del`/`sub`/`highlight` -> `mark.a`; `ins`/`comment` -> `""` (não
    existiam antes; ancoram por PONTO). `marks` já traz offsets relativos a
    `clean_text` (Task 4) — não precisa reparsear.

    Retorna `(plain_text, spans)` onde `spans[i]` é `(start, end)` do alvo de
    `marks[i]` dentro de `plain_text` — para del/sub/highlight,
    `plain_text[start:end] == marks[i].a`; para ins/comment, `start == end`.
    """
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    plain_len = 0
    for mark in marks:
        gap = clean_text[cursor : mark.start]
        parts.append(gap)
        plain_len += len(gap)

        pre_image = mark.a if mark.kind in ("del", "sub", "highlight") else ""
        start = plain_len
        parts.append(pre_image)
        plain_len += len(pre_image)
        spans.append((start, plain_len))

        cursor = mark.end
    parts.append(clean_text[cursor:])
    return "".join(parts), spans


def _find_citation_spans_by_search(
    text: str, occurrences: list[CiteOccurrence]
) -> list[_SentinelSpan]:
    """Acha o span de CADA `occurrence.formatted` em `text`, busca SEQUENCIAL
    com cursor avançando NA ORDEM FÍSICA do documento (`occurrences`
    reordenadas por `norm_start` ANTES da busca, não na ordem de LISTA do
    citemap) — achado CRÍTICO do review da Fase 2/Task 6 (defesa a): usar a
    ordem de LISTA causava IDENTITY SWAP sempre que 2+ occurrences
    compartilhavam o mesmo `formatted` E a ordem do citemap divergia da
    ordem física (ex.: citemap reordenado por outro motivo entre export e
    revisão) — o cursor, avançando na ordem ERRADA, casava o display
    seguinte com o `occ_index` da occurrence ERRADA. Reordenar por
    `norm_start` faz os dois lados (adeu/plain aqui, norm em
    `locate_marks_in_norm`) compartilharem a MESMA suposição de ordem
    física: displays repetidos pareiam pela ORDEM FÍSICA, nunca pela ordem
    de lista do citemap nem por valor. O índice do token sentinela
    (`occ_index`) continua sendo a posição ORIGINAL em `citemap.occurrences`
    (preservada mesmo após o reordenamento local para a busca) — o lado
    norm usa esse MESMO índice original como id do token, então a
    correspondência de identidade entre os dois lados depende só da ordem
    FÍSICA concordar entre as duas renderizações (adeu/plain e norm), não
    da ordem de lista.

    Isso NÃO elimina o risco de identity swap sozinho — a ordem física do
    adeu/plain_text ainda PODE divergir da ordem física do norm_text em
    casos patológicos (ex.: o adeu reordena/reflui conteúdo de um jeito que
    o norm_text não reflete). Por isso o chamador faz uma segunda
    verificação INDEPENDENTE antes de consumir silenciosamente qualquer
    deleção de citação (`_confirm_citation_identity_in_norm`, defesa b,
    `locate_marks_in_norm`) — nunca confia SÓ nesta função para decisão de
    citação (I1).

    Occurrence cujo `formatted` está vazio, ou não é encontrado a partir do
    cursor atual (ex.: adeu reformatou o display), é PULADA — sem span
    sentinela para ela; o cursor não avança nesse caso."""
    ordered = sorted(enumerate(occurrences), key=lambda pair: pair[1].norm_start)
    spans: list[_SentinelSpan] = []
    cursor = 0
    for occ_index, occ in ordered:
        if not occ.formatted:
            continue
        idx = text.find(occ.formatted, cursor)
        if idx == -1:
            continue
        end = idx + len(occ.formatted)
        spans.append(_SentinelSpan(start=idx, end=end, occ_index=occ_index))
        cursor = end
    return spans


def _substitute_spans(text: str, spans: list[_SentinelSpan]) -> tuple[str, list[_OffsetSegment]]:
    """Substitui cada `span` (ordenado, não sobreposto, coordenadas de
    `text`) pelo token sentinela, retornando o texto resultante e os
    segmentos (passthrough + token, cobrindo `text` inteiro em ordem) que
    `_map_offset` usa para converter offsets nos dois sentidos."""
    parts: list[str] = []
    segments: list[_OffsetSegment] = []
    cursor = 0
    sent_len = 0
    for span in spans:
        if span.start > cursor:
            gap = text[cursor : span.start]
            parts.append(gap)
            segments.append(_OffsetSegment(cursor, span.start, sent_len, sent_len + len(gap)))
            sent_len += len(gap)
        token = _sentinel_token(span.occ_index)
        parts.append(token)
        segments.append(_OffsetSegment(span.start, span.end, sent_len, sent_len + len(token)))
        sent_len += len(token)
        cursor = span.end
    tail = text[cursor:]
    parts.append(tail)
    segments.append(_OffsetSegment(cursor, len(text), sent_len, sent_len + len(tail)))
    return "".join(parts), segments


def _map_offset(offset: int, segments: list[_OffsetSegment], *, to_sentinel: bool) -> int:
    """Converte `offset` entre coordenadas ORIGINAL e SENTINELA usando os
    `segments` de `_substitute_spans`. `to_sentinel=True`: original->sentinela
    (lado adeu, antes da busca); `False`: sentinela->original (lado norm,
    depois da busca — nunca reportar offset em espaço-token). Só é seguro
    chamar com `offset` numa FRONTEIRA de segmento ou dentro de um segmento
    PASSTHROUGH — nunca estritamente dentro de um token (o chamador garante
    isso: do lado adeu, `_classify_target_citation` já desviou qualquer alvo
    que caia dentro de um token; do lado norm, a posição do match cai sempre
    em fronteira de token por construção — before/target/after nunca contêm
    um token PARCIAL, ver `_truncate_tail`/`_truncate_head`)."""
    for seg in segments:
        lo, hi = (seg.orig_start, seg.orig_end) if to_sentinel else (seg.sent_start, seg.sent_end)
        if lo <= offset <= hi:
            to_lo, to_hi = (
                (seg.sent_start, seg.sent_end) if to_sentinel else (seg.orig_start, seg.orig_end)
            )
            if offset == lo:
                return to_lo
            if offset == hi:
                return to_hi
            return to_lo + (offset - lo)
    # Inalcançável em contrato: os dois produtores (`_substitute_spans`,
    # `_collapse_whitespace_with_segments`) SEMPRE emitem um segmento de
    # cauda cobrindo até len(text), então os segments tilham [0, len] e
    # qualquer offset em-range cai no loop acima.
    raise AssertionError(
        f"offset {offset} fora dos segmentos — violação de contrato do chamador de _map_offset"
    )


def _collapse_whitespace(text: str) -> str:
    """Colapsa QUALQUER sequência de espaço em branco (espaço/tab/quebra de
    linha) em um único espaço — "texto plano" per brief; interpretação
    deliberadamente mais ampla que só "espaços múltiplos" (o requisito duro
    citado no brief) para absorver possível reformatação/quebra de linha do
    adeu ao extrair do OOXML sem mudar o comportamento no caso comum (já sem
    quebras). Não toca os bytes `\x00` do token sentinela (`\\s` não casa
    NUL)."""
    return re.sub(r"\s+", " ", text)


_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _collapse_whitespace_with_segments(text: str) -> tuple[str, list[_OffsetSegment]]:
    """Colapsa cada sequência de espaço em branco (`\\s+`) em `text` para um
    único espaço, retornando o texto colapsado e os `_OffsetSegment`s
    (passthrough + colapso, cobrindo `text` inteiro em ordem) que
    `_map_offset` usa para converter offsets nos dois sentidos — MESMA
    máquina de bookkeeping de `_substitute_spans`/`_map_offset`, mas o
    "token" substituído é sempre `" "` (não o token sentinela de citação).

    Achado IMPORTANTE do review da Fase 2/Task 6: o colapso de espaços era
    unilateral (só o lado adeu/plain era colapsado antes da busca; o lado
    norm era buscado CRU) — um espaço duplo GENUÍNO na fonte (norm_text)
    perto do alvo produzia `unanchored-mark` espúrio, porque o contexto
    colapsado (adeu) nunca batia com o texto cru (norm) naquele ponto. Esta
    função aplica o MESMO colapso ao lado norm (`locate_marks_in_norm`
    chama isto sobre `norm_text_sentinel`, ANTES de qualquer busca), e o
    chamador compõe os dois mapas de offset (este + o de
    `_substitute_spans`/citação) para que `LocatedMark` continue reportando
    offsets ORIGINAIS de `norm_text` — nunca em espaço colapsado nem em
    espaço sentinela.

    Segmentos de colapso têm SEMPRE largura 1 no lado colapsado
    (`sent_end - sent_start == 1`) — nenhum offset pode cair ESTRITAMENTE
    dentro de um segmento de colapso (não há inteiro entre `n` e `n+1`), o
    que torna QUALQUER offset em espaço colapsado seguro para `_map_offset`
    (ao contrário do token sentinela de citação, de largura > 1, que exige
    a proteção de `_truncate_head`/`_truncate_tail`). Não casa os bytes
    `\\x00` do token sentinela de citação (`\\s` não casa NUL) — tokens já
    substituídos atravessam o colapso intactos, como um segmento passthrough
    comum."""
    parts: list[str] = []
    segments: list[_OffsetSegment] = []
    cursor = 0
    collapsed_len = 0
    for m in _WHITESPACE_RUN_RE.finditer(text):
        ws_start, ws_end = m.start(), m.end()
        if ws_start > cursor:
            gap = text[cursor:ws_start]
            parts.append(gap)
            segments.append(
                _OffsetSegment(cursor, ws_start, collapsed_len, collapsed_len + len(gap))
            )
            collapsed_len += len(gap)
        parts.append(" ")
        segments.append(_OffsetSegment(ws_start, ws_end, collapsed_len, collapsed_len + 1))
        collapsed_len += 1
        cursor = ws_end
    tail = text[cursor:]
    parts.append(tail)
    segments.append(_OffsetSegment(cursor, len(text), collapsed_len, collapsed_len + len(tail)))
    return "".join(parts), segments


def _truncate_tail(text: str, limit: int) -> str:
    """Últimos `limit` chars de `text`, nunca cortando um token sentinela ao
    meio — se o corte cair dentro de um token, empurra o corte para TRÁS
    (início do token), incluindo o token inteiro (o resultado pode passar de
    `limit` chars nesse caso — preferível a um token mutilado, que nunca
    bateria com o lado norm)."""
    if len(text) <= limit:
        return text
    cut = len(text) - limit
    for m in _SENTINEL_TOKEN_RE.finditer(text):
        if m.start() < cut < m.end():
            cut = m.start()
            break
    return text[cut:]


def _truncate_head(text: str, limit: int) -> str:
    """Primeiros `limit` chars de `text` — mesma proteção de token que
    `_truncate_tail`, empurrando o corte para a FRENTE (fim do token)."""
    if len(text) <= limit:
        return text
    cut = limit
    for m in _SENTINEL_TOKEN_RE.finditer(text):
        if m.start() < cut < m.end():
            cut = m.end()
            break
    return text[:cut]


def _find_all(haystack: str, needle: str) -> list[int]:
    """Todas as posições de início de `needle` em `haystack`, INCLUSIVE
    sobrepostas (avança 1 char por vez, não `len(needle)`) — conservador de
    propósito: melhor superestimar ambiguidade (`ambiguous-anchor`) do que
    arriscar uma âncora espúria."""
    positions: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Interseção ESTRITA de intervalos meio-abertos `[start, end)` — encostar
    na fronteira (`a_end == b_start`) NÃO conta como interseção. Um alvo
    zero-largura (`ins`/`comment`) só intersecta se cair ESTRITAMENTE dentro
    do outro intervalo (nunca só tocando a borda)."""
    return a_start < b_end and a_end > b_start


def _classify_target_citation(
    target_start: int,
    target_end: int,
    citation_spans: list[_SentinelSpan],
    plain_text: str,
) -> tuple[str, int | None]:
    """Classifica o alvo de uma marca (`[target_start, target_end)` em
    `plain_text`) contra os spans de citação achados (`_SentinelSpan`).

    Retorna `(classificação, occ_index)`:
    - `("none", None)`: zero interseção — segue para busca normal de âncora.
    - `("exact_del_candidate", i)`: intersecta EXATAMENTE 1 span (occurrence
      `i`), esse span TOTALMENTE contido no alvo, e o que sobra do alvo fora
      do span é só espaço em branco (ou nada) — candidato a "del de citação"
      (o chamador decide o desfecho conforme `kind` e `deleted`).
    - `("touched", None)`: qualquer OUTRA interseção (parcial, múltiplos
      spans, ou span exato mas com sobra não-espaço) — sempre
      `citation-touched-prose`.
    """
    overlapping = [
        cs for cs in citation_spans if _ranges_overlap(target_start, target_end, cs.start, cs.end)
    ]
    if not overlapping:
        return "none", None
    if len(overlapping) == 1:
        cs = overlapping[0]
        if cs.start >= target_start and cs.end <= target_end:
            prefix = plain_text[target_start : cs.start]
            suffix = plain_text[cs.end : target_end]
            if prefix.strip() == "" and suffix.strip() == "":
                return "exact_del_candidate", cs.occ_index
    return "touched", None


def _anchor_context(
    plain_text_sentinel: str,
    plain_segments: list[_OffsetSegment],
    target_start: int,
    target_end: int,
) -> tuple[str, str, int, int]:
    """Receita ÚNICA da âncora de busca: mapeia o alvo (offsets ORIGINAIS de
    `plain_text`) para o espaço sentinela e colapsa+trunca os contextos
    before/after (48 chars, sem partir token). Compartilhada pela busca
    geral (`locate_marks_in_norm`) e pela defesa (b)
    (`_confirm_citation_identity_in_norm`) — a equivalência das duas
    receitas, de que a defesa (b) depende para ser um cross-check válido, é
    por construção (antes era por copy-paste). Retorna
    `(before_ctx, after_ctx, sent_target_start, sent_target_end)`."""
    sent_target_start = _map_offset(target_start, plain_segments, to_sentinel=True)
    sent_target_end = _map_offset(target_end, plain_segments, to_sentinel=True)
    before_ctx = _truncate_tail(
        _collapse_whitespace(plain_text_sentinel[:sent_target_start]), _CONTEXT_CHARS
    )
    after_ctx = _truncate_head(
        _collapse_whitespace(plain_text_sentinel[sent_target_end:]), _CONTEXT_CHARS
    )
    return before_ctx, after_ctx, sent_target_start, sent_target_end


def _confirm_citation_identity_in_norm(
    target_start: int,
    target_end: int,
    plain_text_sentinel: str,
    plain_segments: list[_OffsetSegment],
    norm_text_collapsed: str,
) -> bool:
    """Defesa (b) do review da Fase 2/Task 6 (achado CRÍTICO): cross-valida
    de forma INDEPENDENTE que o `occ_index` que `_classify_target_citation`
    atribuiu ao alvo de um del "exato" de citação é o MESMO que aparece no
    lado norm NA MESMA posição física — nunca confia cegamente no
    `occ_index` do lado adeu para decidir se uma citação foi
    genuinamente deletada (I1).

    A defesa (a) (`_find_citation_spans_by_search` ordenada por
    `norm_start`) já resolve o caso relatado pelo reviewer (ordem do
    citemap divergente da ordem física), mas depende de uma suposição que
    pode falhar em casos mais patológicos (ordem física do adeu/plain_text
    divergindo da ordem física do norm_text) — esta função é o backstop:
    roda a MESMA busca de âncora do caminho geral (contexto before/after em
    espaço sentinela colapsado, truncado a 48 chars sem partir token), mas
    com o "alvo" sendo o PRÓPRIO token sentinela do `occ_index` recebido
    (fatiado de `plain_text_sentinel`, já contém o token exato por
    construção — nunca precisa ser passado à parte). Se essa busca achar
    EXATAMENTE 1 posição em `norm_text_collapsed`, a identidade está
    confirmada: o match só é possível se o MESMO token aparecer lá, cercado
    do MESMO contexto que envolve o alvo no lado adeu. 0 (contexto não bate
    em lugar nenhum — sinal de identity swap) ou >1 (ambíguo) -> NÃO
    confirmado; o chamador NUNCA consome silenciosamente nesse caso,
    sempre emite `citation-touched-prose` (fail-toward-human).

    `target_start`/`target_end` são offsets em `plain_text` (o texto ORIGINAL
    pré-sentinela, mesmo espaço de `_classify_target_citation`) — seguro
    para `_map_offset(..., plain_segments, to_sentinel=True)` pela MESMA
    razão documentada em `_classify_target_citation`: o span de citação
    está TOTALMENTE contido no alvo com sobra só de espaço em branco, então
    `target_start`/`target_end` nunca caem estritamente dentro de um token
    (só na fronteira do span de citação, ou dentro do passthrough da sobra
    de espaço)."""
    before_ctx, after_ctx, sent_target_start, sent_target_end = _anchor_context(
        plain_text_sentinel, plain_segments, target_start, target_end
    )
    target_sentinel_str = plain_text_sentinel[sent_target_start:sent_target_end]
    search_str = before_ctx + target_sentinel_str + after_ctx
    positions = _find_all(norm_text_collapsed, search_str)
    return len(positions) == 1


def _mark_excerpt(mark: ReviewMark, limit: int = 80) -> str:
    """Trecho representativo da marca para mensagens de evento (pt-BR, regra
    deste repo: contexto útil no `detail`) — `a` para del/sub/highlight (o
    texto afetado), `b` para ins/comment (o texto inserido/comentário)."""
    text = (mark.a if mark.kind in ("del", "sub", "highlight") else mark.b).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _unanchored_event(mark: ReviewMark) -> ReviewEvent:
    excerpt = _mark_excerpt(mark)
    return ReviewEvent(
        kind=EVENT_KIND_UNANCHORED_MARK,
        detail=(
            f"Marca {mark.kind} de {mark.author} não foi localizada no texto "
            f'normalizado (0 ocorrências do contexto de âncora): trecho "{excerpt}". '
            "Resolva manualmente em review.md, ou peça revisão sobre um docx "
            "re-exportado se a fonte mudou muito desde o export."
        ),
        author=mark.author,
        mark_excerpt=excerpt,
    )


def _ambiguous_event(mark: ReviewMark, count: int | None = None) -> ReviewEvent:
    excerpt = _mark_excerpt(mark)
    if count is None:
        contagem = "contexto vazio (nada antes/depois da marca no texto do adeu)"
    else:
        contagem = f"{count} ocorrências do mesmo contexto"
    return ReviewEvent(
        kind=EVENT_KIND_AMBIGUOUS_ANCHOR,
        detail=(
            f"Marca {mark.kind} de {mark.author} tem âncora ambígua no texto "
            f'normalizado ({contagem}): trecho "{excerpt}". Amplie o contexto '
            "manualmente ou aplique a mudança direto em review.md."
        ),
        author=mark.author,
        mark_excerpt=excerpt,
    )


def _citation_touched_event(
    mark: ReviewMark,
    occurrences: list[CiteOccurrence],
    *,
    confirmed_by_ooxml: bool,
) -> ReviewEvent:
    """Evento `citation-touched-prose` — decisão humana (I1), nunca
    auto-aplica. `confirmed_by_ooxml=False` é o caso especial em que o alvo
    é EXATAMENTE um display de citação (`kind == "del"`) mas a occurrence não
    está na lista `deleted` da conservação (Task 2) — inconsistência entre o
    que o adeu mostra e o que o OOXML confirma; `True` é o caso geral de
    interseção parcial/múltipla (mensagem sem menção a essa inconsistência
    específica)."""
    excerpt = _mark_excerpt(mark)
    occ_ids = ", ".join(occ.occ_id for occ in occurrences)
    citekeys = [key for occ in occurrences for key in occ.citekeys]
    if not confirmed_by_ooxml:
        detail = (
            f"Marca {mark.kind} de {mark.author} parece deletar a citação "
            f"(occ {occ_ids}), mas a conservação não confirma essa deleção no "
            f'OOXML: trecho "{excerpt}". Nunca confie no adeu para decisão de '
            "citação (I1) — confira o docx revisado e trate manualmente, ou "
            "re-exporte e re-ingira."
        )
    else:
        detail = (
            f"Marca {mark.kind} de {mark.author} toca uma citação (occ {occ_ids}) "
            f"na prosa — decisão humana necessária (I1), nunca auto-aplicada: "
            f'trecho "{excerpt}".'
        )
    return ReviewEvent(
        kind=EVENT_KIND_CITATION_TOUCHED_PROSE,
        detail=detail,
        occ_id=occurrences[0].occ_id if occurrences else None,
        citekeys=citekeys,
        author=mark.author,
        mark_excerpt=excerpt,
    )


def _citation_identity_unconfirmed_event(mark: ReviewMark, occ: CiteOccurrence) -> ReviewEvent:
    """Evento `citation-touched-prose` para quando a defesa (b) (cross-check
    de identidade, `_confirm_citation_identity_in_norm`) NÃO confirma o
    `occ_index` atribuído pelo lado adeu — achado CRÍTICO do review da Fase
    2/Task 6: displays idênticos (2+ occurrences com o mesmo `formatted`)
    combinados com ordem física divergente entre citemap/adeu/norm podem
    trocar a identidade de qual occurrence um del "exato" realmente afeta.
    NUNCA consome silenciosamente neste caso, mesmo que o `occ_index`
    (possivelmente errado) atribuído aponte para uma occurrence que ESTÁ em
    `deleted` — é exatamente essa confiança cega que causava o "silent
    swallow" (I1 violado): sem a confirmação cruzada, o evento de
    conservação (Task 2/8) nunca dispara para a citação REALMENTE afetada,
    e a mudança do coautor é descartada sem rastro. `occ` é o melhor
    palpite disponível (o `occ_index` do lado adeu) — reportado com a
    ressalva explícita de que não pôde ser confirmado."""
    excerpt = _mark_excerpt(mark)
    detail = (
        f"Marca {mark.kind} de {mark.author} parece deletar a citação "
        f"(occ {occ.occ_id}, melhor palpite — NÃO confirmado) — a identidade "
        "da citação deletada não pôde ser confirmada (displays idênticos e/ou "
        f'ordem divergente entre citemap e texto normalizado): trecho "{excerpt}". '
        "Decisão humana necessária — nunca confie no adeu para decisão de "
        "citação (I1). Confira o docx revisado manualmente, ou re-exporte e "
        "re-ingira."
    )
    return ReviewEvent(
        kind=EVENT_KIND_CITATION_TOUCHED_PROSE,
        detail=detail,
        occ_id=occ.occ_id,
        citekeys=list(occ.citekeys),
        author=mark.author,
        mark_excerpt=excerpt,
    )


def locate_marks_in_norm(
    clean_text: str,
    marks: list[ReviewMark],
    norm_text: str,
    citemap: CiteMapFile,
    deleted: list[DocxCitation],
) -> tuple[list[LocatedMark], list[ReviewEvent]]:
    """Localiza cada `ReviewMark` no `norm_text` por âncora única de contexto
    (ver docstring da seção acima para o design completo: pré-imagem,
    sentinela de citação, bookkeeping de offset, classificação de
    interseção).

    Para cada marca, NESTA ordem:
    1. Classifica o alvo contra os spans de citação achados em `plain_text`
       (`_classify_target_citation`). Interseção -> vira SEMPRE
       `citation-touched-prose` (decisão humana, I1), EXCETO o caso "del de
       citação" confirmado por `deleted` (Task 2), que é consumido
       silenciosamente (sem `LocatedMark` nem evento próprio — o evento de
       drop já é da conservação) — mas SÓ depois que a identidade do
       `occ_index` atribuído é CROSS-VALIDADA de forma independente no lado
       norm (`_confirm_citation_identity_in_norm`, defesa b do review da
       Fase 2/Task 6, achado CRÍTICO): displays idênticos (2+ occurrences
       com o mesmo `formatted`) combinados com ordem física divergente
       podiam trocar a identidade da occurrence e consumir silenciosamente
       uma deleção de citação NÃO confirmada (I1 violado) — a cross-
       validação nunca deixa esse consumo acontecer sem confirmação; se a
       identidade não bate, vira `citation-touched-prose` em vez de
       silêncio (fail-toward-human, nunca vazio).
    2. Sem interseção: monta `before`/`after` (texto plano, sentinela
       aplicada, colapsado, truncado a 48 chars sem partir token) e
       `alvo` (`a` para del/sub/highlight, vazio/ponto para ins/comment);
       busca `before + alvo + after` no `norm_text` — TAMBÉM com sentinela
       de citação E colapso de espaços aplicados (achado IMPORTANTE do
       review: o colapso era unilateral, só do lado adeu; um espaço duplo
       genuíno na fonte perto do alvo produzia `unanchored-mark` espúrio —
       agora os offsets encontrados são convertidos de volta para
       `norm_text` original compondo os DOIS mapas de offset, colapso e
       sentinela, nessa ordem). Exatamente 1 match -> `LocatedMark`; 0 ->
       `unanchored-mark`; >1 -> `ambiguous-anchor`.

    Retorna `(located, events)` — a ORDEM de `located`/`events` segue a
    ordem de `marks` (documento).
    """
    plain_text, plain_spans = _plain_reject_rendering(clean_text, marks)

    citation_spans_plain = _find_citation_spans_by_search(plain_text, citemap.occurrences)
    plain_text_sentinel, plain_segments = _substitute_spans(plain_text, citation_spans_plain)

    norm_spans = sorted(
        (
            _SentinelSpan(occ.norm_start, occ.norm_end, i)
            for i, occ in enumerate(citemap.occurrences)
        ),
        key=lambda s: s.start,
    )
    norm_text_sentinel, norm_segments = _substitute_spans(norm_text, norm_spans)
    norm_text_collapsed, norm_collapse_segments = _collapse_whitespace_with_segments(
        norm_text_sentinel
    )

    deleted_occ_ids = {c.occ_id for c in deleted}

    located: list[LocatedMark] = []
    events: list[ReviewEvent] = []

    for mark, (target_start, target_end) in zip(marks, plain_spans, strict=True):
        classification, occ_index = _classify_target_citation(
            target_start, target_end, citation_spans_plain, plain_text
        )

        if classification == "exact_del_candidate" and mark.kind == "del":
            assert occ_index is not None  # invariante de _classify_target_citation
            occ = citemap.occurrences[occ_index]
            if not _confirm_citation_identity_in_norm(
                target_start,
                target_end,
                plain_text_sentinel,
                plain_segments,
                norm_text_collapsed,
            ):
                # Defesa (b): identidade NÃO confirmada de forma
                # independente — NUNCA consumir silenciosamente, mesmo que
                # `occ.occ_id` esteja em `deleted_occ_ids` (esse é
                # exatamente o cenário do "silent swallow" achado no
                # review: confiar no `occ_index` do lado adeu sem
                # cross-check).
                events.append(_citation_identity_unconfirmed_event(mark, occ))
                continue
            if occ.occ_id not in deleted_occ_ids:
                events.append(_citation_touched_event(mark, [occ], confirmed_by_ooxml=False))
            continue  # confirmado: consumida silenciosamente (evento é da conservação)

        if classification in ("exact_del_candidate", "touched"):
            overlapping_occs = [
                citemap.occurrences[cs.occ_index]
                for cs in citation_spans_plain
                if _ranges_overlap(target_start, target_end, cs.start, cs.end)
            ]
            events.append(_citation_touched_event(mark, overlapping_occs, confirmed_by_ooxml=True))
            continue

        target_str = mark.a if mark.kind in ("del", "sub", "highlight") else ""
        before_ctx, after_ctx, _sent_start, _sent_end = _anchor_context(
            plain_text_sentinel, plain_segments, target_start, target_end
        )
        search_str = before_ctx + target_str + after_ctx

        if search_str == "":
            if norm_text == "":
                located.append(LocatedMark(mark=mark, norm_start=0, norm_end=0))
            else:
                events.append(_ambiguous_event(mark, count=None))
            continue

        positions = _find_all(norm_text_collapsed, search_str)
        if not positions:
            events.append(_unanchored_event(mark))
        elif len(positions) > 1:
            events.append(_ambiguous_event(mark, count=len(positions)))
        else:
            # Compõe os DOIS mapas de offset, nesta ordem: colapsado ->
            # sentinela (pré-colapso) -> original de `norm_text` — nunca
            # reporta offset em espaço colapsado nem em espaço sentinela.
            collapsed_start = positions[0] + len(before_ctx)
            collapsed_end = collapsed_start + len(target_str)
            sent_norm_start = _map_offset(
                collapsed_start, norm_collapse_segments, to_sentinel=False
            )
            sent_norm_end = _map_offset(collapsed_end, norm_collapse_segments, to_sentinel=False)
            norm_start = _map_offset(sent_norm_start, norm_segments, to_sentinel=False)
            norm_end = _map_offset(sent_norm_end, norm_segments, to_sentinel=False)
            located.append(LocatedMark(mark=mark, norm_start=norm_start, norm_end=norm_end))

    return located, events


# --- Task 7: transplante para o source + Guarda B (`transplant_to_source`) --
#
# Cada `LocatedMark` (Task 6, offsets em `norm_text`) só transplanta
# DETERMINISTICAMENTE quando o intervalo INTEIRO cai em UM fragment
# `kind="identity"` do span-map (spec: prosa-pura-âncora-única-zero-overlap)
# — cruzar fronteira de fragment, ou pousar num átomo (citação/wikilink/
# callout/embed/block-id/code), vira evento `non-identity-span` (decisão
# humana; nunca auto-aplica). Offset source = `frag.source_start + (norm_off
# - frag.norm_start)` — válido porque um fragment `identity` é sempre uma
# cópia VERBATIM (`core.obsidian.normalize_markdown_with_map`,
# `emit_verbatim`): mesmo comprimento e mesmo conteúdo nos dois lados, então
# a mesma fórmula linear resolve tanto o início quanto o fim do intervalo.
#
# NUANCE DO `ins`/`comment` (span vazio, `norm_start == norm_end`, PONTO):
# como os fragments são contíguos (cobrem `[0, len(norm))` sem buracos nem
# sobreposição — invariante de `SpanFragment`), um ponto que não é a borda
# EXATA de um fragment pertence, sem ambiguidade, ao único fragment que o
# contém estritamente. Na fronteira EXATA entre dois fragments (`norm_end`
# de um == `norm_start` do outro) a escolha é DETERMINÍSTICA por decisão de
# design desta task: pertence ao fragment que TERMINA ali se ele é
# `identity` (o ponto ancora no fim da prosa, imediatamente ANTES do átomo
# seguinte — permite `ins` logo antes de uma citação/wikilink sem tocá-la);
# senão, ao que COMEÇA ali (permite `ins` logo DEPOIS de um átomo, quando a
# prosa seguinte é identity — mesmo que o fragment anterior, que termina
# ali, não seja identity). Fragments ZERO-WIDTH em norm (`norm_start ==
# norm_end`, ex.: block-id `^anchor` — replacement vazio) podem se
# sanduichar EXATAMENTE no ponto, entre o fragment que termina ali e o
# fragment real que começa ali: eles nunca são o dono do ponto (só o
# fragment `identity` REAL que segue é, se existir) — ver nota do fix pós-
# review em `_owning_fragment_for_point`. Ver `_owning_fragment_for_point`;
# os 2 edge cases de self-review em `test_review_locate.py` isolam cada
# ramo da regra, e `test_ins_after_atom_with_zero_width_block_id_transplants`
# isola o caso zero-width.
#
# ORDEM DE APLICAÇÃO: de trás pra frente (maior offset SOURCE primeiro) —
# substituir/inserir num offset maior nunca desloca os offsets, já
# calculados, das marcas anteriores no documento.
#
# GUARDA B (ingest-side): nº de `LocatedMark`s recebidas == nº de marcas
# efetivamente ESCRITAS no texto + nº de eventos gerados. "Escritas" é
# roteado por `_emit_marker` (seam isolado, não confundir com chamar
# `criticmarkup.emit` direto no laço principal) — só para permitir o teste
# forçar uma marca a "sumir" (monkeypatch retornando `""`) e comprovar que
# a guarda de fato dispara ANTES de devolver qualquer coisa (nunca um
# `source_with_marks` parcialmente corrompido: a checagem acontece antes do
# `return`). Em uso normal a contagem SEMPRE fecha — cada `LocatedMark` cai
# em exatamente um destino (aplicada ou evento) por construção; a guarda é
# defesa contra regressão futura, não um caminho esperado.


def _owning_fragment_for_point(point: int, span_frags: list[SpanFragment]) -> SpanFragment | None:
    """Fragment que "possui" um PONTO (alvo de `ins`/`comment`, onde
    `norm_start == norm_end`) — ver nota de design acima para a regra de
    fronteira exata. `None` só se `span_frags` não cobrir o ponto
    (defensivo; não deveria ocorrer com um span-map bem formado, que cobre
    `[0, len(norm_text))` sem buracos nem sobreposição).

    `starting` guarda o ÚLTIMO fragment (não o primeiro) cujo `norm_start
    == point` — fix pós-review (achado Importante): fragments ZERO-WIDTH em
    norm (ex.: block-id `^anchor`, `norm_start == norm_end == point`) podem
    aparecer sanduichados exatamente na fronteira, ANTES do fragment real
    (`identity` ou não) que também começa ali. Como `span_frags` é
    construído em ordem crescente de posição, e um fragment zero-width só
    ocorre PRECEDENDO o fragment real que assume aquele mesmo `norm_start`
    (nunca depois), sobrescrever a cada match garante que `starting` acabe
    no fragment real — não no zero-width. Já `ending` mantém o PRIMEIRO
    match: o fragment real que termina no ponto sempre aparece ANTES de
    qualquer zero-width que também "termine" ali (mesmo raciocínio, sentido
    oposto), então o primeiro match já é o certo."""
    ending: SpanFragment | None = None
    starting: SpanFragment | None = None
    for frag in span_frags:
        if frag.norm_start < point < frag.norm_end:
            return frag
        if ending is None and frag.norm_end == point:
            ending = frag
        if frag.norm_start == point:
            starting = frag
    if ending is not None and ending.kind == "identity":
        return ending
    return starting


def _covering_identity_fragment(
    start: int, end: int, span_frags: list[SpanFragment]
) -> SpanFragment | None:
    """Fragment `kind="identity"` que cobre `[start, end)` INTEIRO (alvo de
    `del`/`sub`/`highlight`) — ou `None` se o intervalo cruza fronteira de
    fragment, cai fora do span-map, ou o fragment que o contém não é
    `identity`. Sem ambiguidade de fronteira (ao contrário do ponto): um
    intervalo de largura > 0 só pode estar inteiramente contido em UM
    fragment, dada a contiguidade sem sobreposição do span-map."""
    for frag in span_frags:
        if frag.norm_start <= start and end <= frag.norm_end:
            return frag if frag.kind == "identity" else None
    return None


def _classify_located_mark(
    loc: LocatedMark, span_frags: list[SpanFragment]
) -> tuple[int, int] | None:
    """Offsets SOURCE `(start, end)` de `loc` quando transplantável
    deterministicamente, ou `None` quando não (o chamador emite
    `non-identity-span`). Ponto (`ins`/`comment`, `norm_start == norm_end`)
    via :func:`_owning_fragment_for_point`; span (`del`/`sub`/`highlight`)
    via :func:`_covering_identity_fragment`."""
    if loc.norm_start == loc.norm_end:
        frag = _owning_fragment_for_point(loc.norm_start, span_frags)
        if frag is None or frag.kind != "identity":
            return None
        offset = frag.source_start + (loc.norm_start - frag.norm_start)
        return offset, offset

    frag = _covering_identity_fragment(loc.norm_start, loc.norm_end, span_frags)
    if frag is None:
        return None
    src_start = frag.source_start + (loc.norm_start - frag.norm_start)
    src_end = frag.source_start + (loc.norm_end - frag.norm_start)
    return src_start, src_end


def _non_identity_span_event(mark: ReviewMark) -> ReviewEvent:
    """Evento `non-identity-span` — o alvo da marca não cai inteiro em UM
    fragment `kind="identity"` do span-map (cruza fronteira de fragment, ou
    pousa num átomo: citação/wikilink/callout/embed/block-id/code).
    Transplante determinístico não suportado; decisão humana necessária."""
    excerpt = _mark_excerpt(mark)
    return ReviewEvent(
        kind=EVENT_KIND_NON_IDENTITY_SPAN,
        detail=(
            f"Marca {mark.kind} de {mark.author} não cai inteiramente numa "
            f'região de prosa pura da fonte (trecho: "{excerpt}"). O '
            "transplante determinístico só localiza mudanças que caem "
            "inteiras em texto puro (fora de citação/wikilink/callout/embed/"
            "bloco de código, e sem cruzar fronteira de fragment). Resolva "
            "manualmente comparando o docx revisado com a página fonte, ou "
            "aplique a mudança direto na página."
        ),
        author=mark.author,
        mark_excerpt=excerpt,
    )


def _emit_marker(mark: ReviewMark) -> str:
    """Serializa `mark` via `criticmarkup.emit` — seam isolado (não chamado
    como `criticmarkup.emit` direto no laço principal de
    :func:`transplant_to_source`) só para permitir o teste de Guarda B
    forçar uma marca a "sumir" (monkeypatch retornando `""` para simular um
    bug em que o texto da marca nunca chega a ser escrito no source)."""
    return criticmarkup.emit(mark.kind, mark.a, mark.b)


def _mark_lost_message(lost: list[ReviewMark], total: int, applied: int, event_count: int) -> str:
    """Mensagem pt-BR da Guarda B — nomeia a contagem que não fechou e o
    excerpt de cada marca perdida (`lost`, sempre não-vazia quando a guarda
    dispara nesta implementação: é a única fonte possível de divergência
    de contagem)."""
    excerpts = "; ".join(f'"{_mark_excerpt(m)}" ({m.author})' for m in lost)
    return (
        f"Guarda B: contagem não fecha no transplante para o source — "
        f"{total} ReviewMark(s) localizada(s), mas só {applied} aplicada(s) + "
        f"{event_count} evento(s) = {applied + event_count}. Marca(s) "
        f"perdida(s): {excerpts}. Isso é um BUG interno do transplante (nunca "
        "deveria acontecer em uso normal) — não prossiga; reporte o problema "
        "com o docx revisado e a página em questão."
    )


def transplant_to_source(
    source_body: str,
    span_frags: list[SpanFragment],
    located: list[LocatedMark],
    *,
    author_anchors: bool = False,
) -> tuple[str, list[ReviewEvent]]:
    """Transplanta cada `LocatedMark` (Task 6) para offsets do `source_body`
    (corpo da página SEM frontmatter — o chamador, Task 8, preserva o
    frontmatter na escrita de `review.md`) via o span-map (`span_frags`,
    saída de `core.obsidian.normalize_markdown_with_map` sobre o mesmo
    `source_body`).

    ``author_anchors`` (Task 9, default ``False`` — mantém o comportamento
    de Task 7 intacto): quando ``True``, cada marcador colocado ganha, colado
    IMEDIATAMENTE depois, um comentário-âncora ``{>>prumo-autor: <Autor><<}``
    (prefixo ``prumo-`` — Fix pós-review da Fase 2/Task 9, achado Menor:
    evita colisão com um comentário HUMANO genuíno ``{>>autor: ...<<}``, que
    seria confundido com a âncora e removido silenciosamente do apply) com o
    ``mark.author`` daquele placement especificamente (nunca pareado
    depois — o autor só existe aqui, no momento em que a marca ainda carrega
    o `ReviewMark` original). É a SIMPLIFICAÇÃO DO MVP decidida no plano da
    Fase 2/Task 9 para autoria sobreviver no CriticMarkup puro: `apply_review`
    pareia essa âncora com a marca de conteúdo por adjacência estrita (mesma
    regra de :func:`parse_adeu_markdown`) e a filtra por autor; a âncora
    NUNCA vai para a página final (é consumida na aplicação — ver
    `apply_review` para a semântica de âncoras que sobrevivem em `review.md`
    quando a marca pareada fica pendente). ``ingest()`` chama sempre com
    ``author_anchors=True``; os testes de Task 7 (`test_review_locate.py`)
    usam o default ``False`` e permanecem idênticos.

    Para cada `loc` em `located` (índice `idx` == posição original na
    lista), NESTA ordem: classifica o alvo contra `span_frags`
    (:func:`_classify_located_mark` — só identity, intervalo inteiro, ver
    nota de design da seção acima); sem classificação possível -> evento
    `non-identity-span`; senão, serializa a marca (:func:`_emit_marker`) e
    enfileira `(source_start, source_end, idx, marker)` para aplicação.
    Aplica todas as marcas enfileiradas DE TRÁS PRA FRENTE — ordenadas por
    `(source_start, source_end, idx)` DESCENDENTE, não só `source_start` —
    substituindo `source_body[start:end]` pelo marcador serializado. Para
    `ins`/`comment` (ponto, `start == end`), isso é uma inserção pura; para
    `del`/`sub`/`highlight` (span), o marcador já reincorpora `mark.a`
    (semântica de `criticmarkup.emit`), então a substituição preserva a
    reconstrução via `criticmarkup.reject`.

    A chave de ordenação inclui `source_end` (não só `source_start`) por
    causa de um caso real: um `ins` (ponto) cujo offset coincide EXATAMENTE
    com o início de outro span adjacente (`ins.start == span.start`, ambos
    com o MESMO `source_start`) — ordenar só por `source_start` deixa a
    ordem relativa dos dois indefinida (empate), e aplicar o ponto ANTES do
    span corrompe o span (o ponto desloca tudo a partir dali, invalidando o
    `source_end` já calculado do span). Desempatar por `source_end`
    descendente aplica sempre o span (maior `source_end`) primeiro — como
    ele começa exatamente onde o ponto seria inserido, aplicá-lo primeiro
    não desloca a posição do ponto (que continua válida logo antes do
    resultado), e só então o ponto é inserido, corretamente, imediatamente
    antes do marcador do span.

    A chave inclui, por fim, `idx` (fix pós-review, achado Menor #1): dois
    pontos (`ins`/`comment`) que colidem EXATAMENTE no mesmo
    `(source_start, source_end)` — mesma posição, ambos largura zero —
    ficam empatados nas duas chaves acima. Sem desempate, a ordem de
    aplicação segue a ordem de `located` (estável em `sorted(...,
    reverse=True)`), e como cada aplicação SUBSEQUENTE no mesmo ponto
    insere à ESQUERDA da anterior (empurrando-a pra direita), aplicar na
    ordem de `located` produz o texto final INVERTIDO relativo a
    `located`. Desempatar por `idx` descendente (junto de `source_start`/
    `source_end`, também descendentes) aplica primeiro a marca de índice
    MAIOR (mais tardia em `located`) — ela fica mais à direita — e por
    último a de índice MENOR (mais cedo em `located`), que por ser a
    ÚLTIMA a inserir no ponto fica mais à ESQUERDA: o texto final passa a
    preservar a ordem de `located`. Ver
    `test_two_point_marks_same_offset_preserve_located_order` (as duas
    ordens de entrada).

    **Guarda B (ingest-side):** ao final, nº de `LocatedMark`s recebidas
    tem que fechar com nº de marcas efetivamente aplicadas + nº de eventos
    gerados — qualquer divergência (só possível hoje via o seam
    `_emit_marker` devolvendo `""`, o que esta função trata como "marca
    perdida" e NÃO aplica) levanta `MarkLostError` com o excerpt de cada
    marca perdida, antes de retornar (o chamador nunca recebe um
    `source_with_marks` parcialmente corrompido).

    Retorna `(source_with_marks, events)`.
    """
    events: list[ReviewEvent] = []
    placements: list[tuple[int, int, int, str]] = []
    lost: list[ReviewMark] = []

    for idx, loc in enumerate(located):
        offsets = _classify_located_mark(loc, span_frags)
        if offsets is None:
            events.append(_non_identity_span_event(loc.mark))
            continue
        marker = _emit_marker(loc.mark)
        if not marker:
            lost.append(loc.mark)
            continue
        if author_anchors:
            marker += criticmarkup.emit("comment", "", f"prumo-autor: {loc.mark.author}")
        placements.append((offsets[0], offsets[1], idx, marker))

    source_with_marks = source_body
    for src_start, src_end, _idx, marker in sorted(
        placements, key=lambda p: (p[0], p[1], p[2]), reverse=True
    ):
        source_with_marks = source_with_marks[:src_start] + marker + source_with_marks[src_end:]

    # Guarda B: cada `loc` cai em exatamente um de events/lost/placements —
    # marca perdida ⟺ `lost` não-vazio (as contagens vivem na mensagem).
    if lost:
        raise MarkLostError(_mark_lost_message(lost, len(located), len(placements), len(events)))

    return source_with_marks, events


# --- Task 8: ingest() — orquestração + preflight + escrita dos sidecars -----
#
# `ingest()` é o único ponto que amarra T1-T7: nenhuma lógica NOVA de
# guarda/conservação/localização/transplante mora aqui — só a SEQUÊNCIA (o
# fluxo "3a-3h" do spec) e a escrita dos 3 sidecars desta fase
# (`review.md`, `review-comments.yaml`, `events.yaml`). Passos, nesta ordem
# (cada um hard-fail antes do próximo quando aplicável — nenhum caminho
# prossegue parcial, per Global Constraints do plano):
#
#   ANTES de 3a (achado do review final da Fase 2, Important #1):
#       `reviewed_docx` — o input mais hostil do sistema, chega por e-mail —
#       é validado estruturalmente via `export._validate_docx_structure`
#       (zip inválido/truncado, parte obrigatória ausente, membro
#       corrompido). Sem isso, `BadZipFile`/`KeyError` cru vazava pelo CLI,
#       fora de `_REVIEW_CATCHES` (que só reconhece `ValueError`).
#   3a. resolve `project_root` (`export.detect_project_root`, se não
#       fornecido) e o `slug` (`export.slugify`) — juntos apontam
#       `reviews/<slug>/`, onde tanto os sidecars do export (entrada) quanto
#       os desta fase (saída) moram.
#   3b. carrega `citemap.json`/`span-map.json` — ausência de QUALQUER um dos
#       dois é `FileNotFoundError` pt-BR (não `SourceChangedError`: sidecar
#       ausente significa "nunca foi exportado", não "mudou depois"). JSON
#       presente mas corrompido/fora do schema vira `ValueError` pt-BR
#       (`pydantic.ValidationError` traduzido — mesmo achado Important #1).
#   3c. preflight de fonte: sha256 do corpo ATUAL da página (sem
#       frontmatter) precisa bater com `span_map.source_sha256` — página
#       mudou desde o export invalida qualquer offset derivado do span-map
#       antigo (spec: "offsets derivados nunca são confiados").
#   3d. I8: sha256 do docx REVISADO precisa DIVERGIR de `citemap.docx_sha256`
#       — se bater, o arquivo que voltou do coautor é literalmente o mesmo
#       que foi exportado (nada foi revisado, ou o coautor mandou o arquivo
#       errado). Usa `CitationConservationError` (mesma família do I8 geral,
#       per docstring da classe — não introduz exceção nova só para este
#       caso; ver "Interfaces centrais" do plano).
#   3e. Guarda A (`assert_no_structural_changes`) sobre o docx revisado.
#   3f. leitor com estado (`read_docx_citations_with_state`) + conservação
#       (`check_conservation`) — devolve `deleted` (citações removidas sob
#       Track Changes, candidatas a `citation-drop`).
#   3g. adeu extract+parse (`_run_adeu_extract` + `parse_adeu_markdown`),
#       recomputa `norm_text`/`span_frags` via
#       `normalize_markdown_with_map(body, page_dir=page.parent)` — MESMA
#       chamada que o export fez (nunca lê `span_map.fragments`: como o
#       preflight 3c já confirmou que `body` é byte-idêntico ao que o export
#       normalizou, recalcular é determinístico e produz o MESMO span-map,
#       sem precisar desserializar `SpanFragmentModel` de volta pro
#       dataclass `SpanFragment` que `transplant_to_source` espera) —,
#       localiza (`locate_marks_in_norm`) e transplanta
#       (`transplant_to_source`).
#   3h. monta os eventos finais (eventos da localização + eventos do
#       transplante + um `citation-drop` por citação `deleted`) e escreve os
#       3 sidecars. Retorna `IngestResult`.
#
# NADA disto toca a página original (`page`): ela só é LIDA (para o corpo e
# o frontmatter); toda saída vai para `reviews/<slug>/`. O `apply` (Task 9)
# é quem eventualmente escreve de volta na página, com confirmação humana.

_SIDECAR_MISSING_HINT = "rode `prumo write export --to docx` antes"


@dataclass(frozen=True)
class IngestResult:
    """Resultado de `ingest()` — nada aqui já foi escrito na página original.

    ``review_md`` é o caminho de `reviews/<slug>/review.md` (frontmatter da
    página + corpo com as marcas transplantadas, Task 7); ``marks_applied``
    é a contagem de `LocatedMark`s que efetivamente viraram marcador
    CriticMarkup em ``review_md`` (`len(located) - len(eventos do
    transplante)` — as demais marcas localizadas viraram evento
    `non-identity-span`, e as NUNCA localizadas nem entram nessa conta,
    per Guarda B de `transplant_to_source`); ``events``/``comments`` são os
    objetos JÁ gravados em `events.yaml`/`review-comments.yaml`
    (retornados também em memória para o chamador — CLI da Task 10 — não
    precisar reler do disco); ``deleted`` é a lista de `DocxCitation` que
    `check_conservation` (Task 2) devolveu (mesmas citações por trás dos
    eventos `citation-drop` em ``events``), exposta separadamente porque o
    `apply` (Task 9) precisa dela para validar `--confirm-citation-drops`.
    """

    review_md: Path
    marks_applied: int
    events: ReviewEventsFile
    comments: ReviewCommentsFile
    deleted: list[DocxCitation]


def _corrupt_sidecar_message(path: Path, exc: ValidationError) -> str:
    """Mensagem pt-BR única para sidecar (citemap/span-map) corrompido —
    compartilhada pelas duas leituras de :func:`_read_sidecars` (achado do
    review final da Fase 2, Important #1: ``pydantic.ValidationError`` cru
    vazava traceback pelo CLI, fora de `_REVIEW_CATCHES`). ``exc.errors()``
    dá o resumo curto — uma linha por erro, sem a URL de documentação que
    ``str(exc)`` inclui; cai para ``str(exc)`` só se ``errors()`` vier
    vazio (não deveria acontecer na prática, mas evita mensagem sem
    detalhe nenhum)."""
    detail = "; ".join(err["msg"] for err in exc.errors()) or str(exc)
    return (
        f"sidecar corrompido ({path}): re-exporte com `prumo write export "
        f"--to docx` para regenerá-lo. Detalhe: {detail}"
    )


def _read_sidecars(review_dir: Path) -> tuple[CiteMapFile, SpanMapFile]:
    """Carrega `citemap.json`/`span-map.json` de `review_dir` (passo 3b).

    Ausência de QUALQUER um dos dois é `FileNotFoundError` (não uma
    exceção nova deste módulo — regra do repo: hard-fail de arquivo ausente
    usa o tipo stdlib direto, mensagem pt-BR com o comando embutido, mesmo
    padrão de `export.export`/`export.compose` para `bib` ausente). JSON
    presente mas corrompido/fora do schema (``pydantic.ValidationError`` —
    achado do review final, Important #1) vira ``ValueError`` pt-BR via
    :func:`_corrupt_sidecar_message`, nomeando qual dos dois arquivos
    falhou — nunca o traceback cru do pydantic."""
    citemap_path = review_dir / "citemap.json"
    span_map_path = review_dir / "span-map.json"
    missing = [p.name for p in (citemap_path, span_map_path) if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Sidecar(s) de review ausente(s) em {review_dir}: {', '.join(missing)}. "
            f"A página nunca foi exportada para docx (ou o diretório "
            f"`reviews/` foi apagado) — {_SIDECAR_MISSING_HINT}."
        )
    try:
        citemap = CiteMapFile.model_validate_json(citemap_path.read_text())
    except ValidationError as exc:
        raise ValueError(_corrupt_sidecar_message(citemap_path, exc)) from exc
    try:
        span_map = SpanMapFile.model_validate_json(span_map_path.read_text())
    except ValidationError as exc:
        raise ValueError(_corrupt_sidecar_message(span_map_path, exc)) from exc
    return citemap, span_map


def _citation_drop_event(citation: DocxCitation) -> ReviewEvent:
    """Evento `citation-drop` para uma citação `deleted` (Task 2 —
    `check_conservation`), passo 3h.

    ``author`` fica sempre ``None`` aqui: `DocxCitation` (leitor T1, I2b)
    NÃO expõe o autor do `w:del` que envolve o campo — só o ESTADO
    (`live`/`deleted`/`touched`), decidido em `_frame_state` a partir da
    ancestralidade `w:ins`/`w:del` de cada run, sem guardar o atributo
    `w:author` do elemento `w:del` em si. Diferente do `"(desconhecido)"`
    textual que o parser do adeu usa para PROSA sem anotação pareada
    (`_UNKNOWN_AUTHOR`) — aqui é `None` porque citação nunca passa pelo
    adeu (I1: citação é sempre OOXML próprio), então não há um valor
    "desconhecido" a preencher, só um dado que o leitor atual não coleta.
    Registrado no relatório da Task 8 como melhoria futura (exigiria
    `read_docx_citations_with_state` devolver o `w:author` do primeiro
    `w:del` do frame)."""
    citekeys = ", ".join(citation.citekeys)
    return ReviewEvent(
        kind=EVENT_KIND_CITATION_DROP,
        detail=(
            f"citação (occ {citation.occ_id}, citekeys {citekeys}) deletada "
            "no Word — confirme no apply."
        ),
        occ_id=citation.occ_id,
        citekeys=list(citation.citekeys),
        author=None,
        mark_excerpt=citation.formatted or None,
    )


def _compose_page(raw_fm: str, body: str) -> str:
    """Concatenação trivial: `raw_fm` (bloco de frontmatter VERBATIM, com os
    delimitadores `---` inclusos, ou `""` se a página não tinha frontmatter —
    saída de `core.obsidian.split_frontmatter_raw`) + `body`.

    Substitui a antiga `_render_review_md` (Fix pós-review da Fase 2/Task 9,
    achado Crítico 1): a versão anterior fazia `yaml.safe_dump(meta, ...)`
    sobre o frontmatter JÁ PARSEADO, o que deleta comentários YAML e reflui
    a formatação (indentação, ordem de chaves, aspas) — perda irreversível
    num arquivo que o humano edita e espera ver intacto. Sem NENHUM
    `yaml.safe_dump` no caminho de frontmatter: nem `ingest()` (que escreve
    `review.md`) nem `apply_review()` (que escreve a página) tocam o YAML —
    só concatenam bytes."""
    return raw_fm + body


def ingest(
    reviewed_docx: Path, page: Path, project_root: Path | None = None, *, force: bool = False
) -> IngestResult:
    """Orquestra o ingest de um docx revisado (fluxo 3a-3h — ver comentário
    da seção acima para o design completo de cada passo).

    Nunca escreve ou modifica ``page`` (a página-fonte original): ela só é
    lida (corpo + frontmatter). Toda saída vai para
    ``reviews/<slug>/{review.md,review-comments.yaml,events.yaml}`` —
    ``review.md`` é o artefato que o humano revisa e eventualmente aplica de
    volta na página via ``apply_review`` (Task 9); o `git add`/commit desses
    sidecars é do humano (portão, per Global Constraints do plano).

    Levanta (na ordem em que os passos checam, parando na primeira falha):
    ``ValueError`` (ANTES de 3a — docx revisado estruturalmente inválido,
    via `export._validate_docx_structure`; ou, logo após resolver
    `review_dir`, se já existe `review.md` com marca(s) pendente(s) e
    `force=False` — fila herdada do archive da F3, protege propostas do
    agente de sobrescrita silenciosa; ou, dentro de 3b, sidecar JSON
    corrompido, `pydantic.ValidationError` traduzido — achado do review
    final da Fase 2, Important #1: `reviewed_docx` é o input mais hostil
    do sistema, chega por e-mail); ``FileNotFoundError`` (sidecars
    ausentes, 3b); :class:`SourceChangedError` (fonte mudou desde o
    export, 3c); :class:`CitationConservationError` (I8 — docx idêntico ao
    exportado, 3d; ou qualquer divergência de conservação de citação, 3f);
    :class:`StructuralChangeError` (Guarda A, 3e — que também pode levantar
    ``ValueError`` se `word/document.xml` for XML malformado, mesmo achado
    do Important #1); :class:`AdeuUnavailableError` (backend de prosa
    indisponível, 3g); :class:`MarkLostError` (Guarda B, dentro de
    `transplant_to_source`, 3g).
    """
    # Preflight 3a: check uvx availability before any other work
    _check_uvx_on_path()

    # Preflight de estrutura (achado do review final da Fase 2, Important
    # #1, ANTES de 3a): reusa `export._validate_docx_structure` — o mesmo
    # docx revisado que chega por e-mail é o input mais hostil do sistema;
    # zip inválido/truncado, parte obrigatória ausente (`word/document.xml`,
    # `[Content_Types].xml`) ou membro corrompido (CRC) vazavam
    # `BadZipFile`/`KeyError` cru pelo CLI antes deste fix. Roda ANTES de
    # `_read_sidecars`: não vale carregar sidecar nenhum se o arquivo
    # revisado nem é um docx válido.
    problems = _validate_docx_structure(reviewed_docx)
    if problems:
        raise ValueError(
            f"o docx revisado não é um .docx válido: {'; '.join(problems)}. "
            "Confirme que o coautor enviou o arquivo .docx correto (não .doc "
            "renomeado/truncado) e rode novamente `prumo write review ingest ...`."
        )

    project_root = project_root or detect_project_root(page)
    slug = slugify(page, project_root)
    review_dir = project_root / "reviews" / slug

    # Guarda herdada da fila F2+F3 (archive da F3, 711c0c0): re-ingest
    # SOBRESCREVE o worklist — se há marcas pendentes (inclusive propostas do
    # agente via propose_prose_edit), destruí-las exige opt-in explícito.
    existing_review_md = review_dir / "review.md"
    if existing_review_md.exists() and not force:
        _fm, existing_body = split_frontmatter_raw(existing_review_md.read_text(encoding="utf-8"))
        pending = len(criticmarkup.parse(existing_body))
        if pending:
            raise ValueError(
                f"{existing_review_md} já existe com {pending} marca(s) pendente(s) — "
                "re-ingerir SOBRESCREVE o worklist (inclusive propostas do agente). "
                f"Decida primeiro com `prumo write review apply --page {page}` "
                "(--accept-all/--reject-all/--by-author/--mark) ou re-rode o ingest "
                "com --force para descartar as pendências."
            )

    citemap, span_map = _read_sidecars(review_dir)

    page_text = page.read_text()
    raw_fm, body = split_frontmatter_raw(page_text)

    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if body_sha256 != span_map.source_sha256:
        raise SourceChangedError(
            "A fonte mudou desde o export: sha256 do corpo atual de "
            f"{page} ({body_sha256}) diverge de `source_sha256` em "
            f"{review_dir / 'span-map.json'} ({span_map.source_sha256}) — "
            "página mudou desde o export — re-exporte e peça nova revisão "
            "sobre o docx novo."
        )

    docx_sha256 = hashlib.sha256(reviewed_docx.read_bytes()).hexdigest()
    if docx_sha256 == citemap.docx_sha256:
        raise CitationConservationError(
            f"O docx revisado ({reviewed_docx}) tem o MESMO sha256 do docx "
            f"exportado registrado em {review_dir / 'citemap.json'} (I8): "
            "docx não contém revisão (é o exportado) — confirme que o "
            "coautor devolveu o arquivo certo, com as mudanças salvas."
        )

    assert_no_structural_changes(reviewed_docx)

    observed = read_docx_citations_with_state(reviewed_docx)
    deleted = check_conservation(observed, citemap)

    markdown = _run_adeu_extract(reviewed_docx)
    clean_text, marks = parse_adeu_markdown(markdown)

    norm_text, span_frags = normalize_markdown_with_map(body, page_dir=page.parent)

    located, locate_events = locate_marks_in_norm(clean_text, marks, norm_text, citemap, deleted)
    source_with_marks, transplant_events = transplant_to_source(
        body, span_frags, located, author_anchors=True
    )

    drop_events = [_citation_drop_event(citation) for citation in deleted]
    all_events = [*locate_events, *transplant_events, *drop_events]
    marks_applied = len(located) - len(transplant_events)

    rel_page = page.relative_to(project_root) if page.is_absolute() else page
    comments = collect_review_comments(reviewed_docx, str(rel_page))
    events_file = ReviewEventsFile(page=str(rel_page), events=all_events)

    review_dir.mkdir(parents=True, exist_ok=True)
    review_md_path = review_dir / "review.md"
    review_md_path.write_text(_compose_page(raw_fm, source_with_marks), encoding="utf-8")
    (review_dir / "review-comments.yaml").write_text(
        yaml.safe_dump(comments.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (review_dir / "events.yaml").write_text(
        yaml.safe_dump(events_file.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return IngestResult(
        review_md=review_md_path,
        marks_applied=marks_applied,
        events=events_file,
        comments=comments,
        deleted=deleted,
    )


# --- Task 9: apply_review() — decisões por marca/autor + write-back --------
#
# `apply_review()` fecha o loop: lê `review.md` (marcas CriticMarkup + âncoras
# de autor emitidas por `transplant_to_source(..., author_anchors=True)`) e
# `events.yaml` (Task 8), resolve as marcas conforme o modo de decisão
# escolhido, e reescreve a PÁGINA original.
#
# `review.md` COMO WORKLIST VIVA (Fix pós-review, achado Crítico 2): a
# versão original desta função NUNCA reescrevia `review.md` — cada chamada
# relia o arquivo do zero, sempre com TODAS as marcas originais. Isso fazia
# applies parciais SEQUENCIAIS reverterem decisões anteriores: um apply
# `by_author=Alice` seguido de um apply `by_author=Bob` devolvia a marca da
# Alice CRUA na página (ela nunca tinha sido "esquecida" por `review.md`,
# então a segunda chamada reconstruía a página a partir do texto ORIGINAL,
# onde a marca da Alice ainda está pendente). A correção: TODA chamada
# bem-sucedida reescreve `review.md` = `raw_fm` + o mesmo corpo, mas com as
# marcas DECIDIDAS nesta chamada já resolvidas (viram texto puro, nunca mais
# marcas CriticMarkup) e as marcas AINDA PENDENTES preservadas com sua âncora
# de autor intacta (para que uma chamada `by_author` futura ainda consiga
# localizá-las). A PÁGINA usa o MESMO corpo resolvido, mas com TODAS as
# âncoras removidas (decidida ou pendente) — pendências ficam visíveis na
# fonte como marcas CriticMarkup puras, sem a âncora interna de
# `review.md`. Como uma marca decidida vira texto puro (nunca mais uma marca
# CriticMarkup), ela desaparece de `criticmarkup.parse(review_body)` na
# PRÓXIMA chamada — não há como uma decisão já resolvida "reaparecer" crua.
#
# `events.yaml` SEGUE O MESMO PRINCÍPIO para `citation-drop`: ao reescrever,
# os eventos `citation-drop` recém-confirmados são REMOVIDOS (não persistem
# como pendência) e um evento `kind="applied"` é apendado registrando os
# citekeys confirmados nesta chamada — o histórico completo sobrevive na
# CADEIA de eventos `applied` (nunca removidos) + Git. Isso é o que permite
# uma segunda chamada de `apply` NÃO exigir `--confirm-citation-drops` de
# novo para um drop já resolvido (nada mais pendente para confirmar) e,
# simetricamente, manter a conservação pós-apply correta em chamadas
# futuras: o multiconjunto "já confirmado como drop" é reconstruído somando
# os `citekeys` de TODOS os eventos `applied` passados (histórico
# acumulado) com os do `citation-drop` sendo confirmado agora — nunca só o
# do momento atual, senão uma segunda chamada (sem nenhum `citation-drop`
# pendente sobrando) veria o citekey já removido do corpo como uma violação
# de conservação (falso positivo).
#
# CITAÇÃO NUNCA É TOCADA POR MARCA CRITICMARKUP (I1): um `citation-drop`
# confirmado não é "aplicado" por transplante nenhum — `ingest()` já deixa a
# citação intocada em `review.md` mesmo quando `deleted` (Task 8). Só o
# HUMANO, editando `review.md` (git-tracked, é o gate per spec), de fato
# remove a referência à citação; `apply_review` apenas VERIFICA, via
# conservação pós-apply, que o corpo final tem o multiconjunto de citekeys
# esperado (citemap − drops confirmados, histórico + atual) — I5:
# bibliografia é função da fonte, nada a transplantar. Confirmar o drop sem
# editar `review.md` não remove a citação sozinho: a conservação pega essa
# divergência (hard-fail).
#
# FRONTMATTER BYTE-FIEL (Fix pós-review, achado Crítico 1): `raw_fm` (bloco
# `---\n...\n---\n` VERBATIM, via `core.obsidian.split_frontmatter_raw`) é
# extraído de `review.md` — nunca re-parseado/re-serializado via YAML — e é
# o MESMO `raw_fm` usado tanto para reescrever `review.md` quanto a PÁGINA;
# ambos ficam em lockstep até o review terminar (última chamada sem marcas
# pendentes). Isso também significa que `apply_review` NÃO relê o
# frontmatter da própria página nesta chamada: `review.md` (capturado no
# `ingest()`, a partir da página NAQUELE momento) é a fonte de verdade do
# frontmatter durante todo o ciclo de vida do review.
#
# ÂNCORA DE AUTOR: `{>>prumo-autor: X<<}` (prefixo `prumo-` — Fix pós-review,
# achado Menor: evita colidir com um comentário HUMANO genuíno
# `{>>autor: ...<<}`) é pareada com a marca de conteúdo IMEDIATAMENTE
# anterior pela MESMA regra de adjacência de `parse_adeu_markdown` (Task 4)
# — ver `_pair_author_anchors`. Nunca sobrevive à PÁGINA final: TODA âncora
# reconhecida (pareada ou órfã) é removida do resultado, independente de a
# marca de conteúdo pareada (se houver) ter sido decidida ou não — `comment`
# resolve para "" nos dois sentidos (accept/reject), então o valor do bool
# não importa para ela. Em `review.md`, porém, a âncora SOBREVIVE quando a
# marca de conteúdo pareada continua pendente (ver "worklist viva" acima) —
# só desaparece de `review.md` quando a marca que ela anota é decidida
# (nesta chamada ou numa anterior) ou quando é órfã.
#
# MODOS DE DECISÃO (exatamente um por chamada — `_validate_apply_mode`):
# `accept_all`/`reject_all` decidem TODAS as marcas de conteúdo de uma vez —
# únicos modos com Guarda B apply-side (nenhuma marca pode sobrar depois).
# `by_author` + `author_decision` decidem só as marcas cujo autor pareado
# bate com `by_author`; `marks` decide por ÍNDICE na lista de marcas de
# CONTEÚDO (índice ignora âncoras — é a posição entre as marcas DECIDÍVEIS,
# não a posição bruta de `criticmarkup.parse`). Nos dois modos parciais,
# marca sem decisão explícita permanece intacta na página (semântica de
# `criticmarkup.apply`: "marca sem decisão permanece intacta") — sem Guarda
# B, documentado, não é bug.

_NON_BLOCKING_EVENT_KINDS = frozenset({EVENT_KIND_CITATION_DROP, EVENT_KIND_APPLIED})

_AUTHOR_ANCHOR_RE = re.compile(r"^prumo-autor: (?P<author>.*)$")


@dataclass(frozen=True)
class ApplyResult:
    """Resultado de `apply_review()` — quando retorna sem erro, a página já
    foi reescrita, `review.md` também (worklist viva — marcas pendentes
    permanecem com sua âncora de autor; Fix pós-review, Crítico 2) e
    `events.yaml` já ganhou o registro `applied`."""

    page: Path
    applied: int
    rejected: int
    drops_confirmed: list[str]


def _validate_apply_mode(
    *,
    accept_all: bool,
    reject_all: bool,
    by_author: str | None,
    author_decision: bool | None,
    marks: dict[int, bool] | None,
) -> None:
    """Exatamente UM modo de decisão por chamada — `accept_all` XOR
    `reject_all` XOR (`by_author` + `author_decision`) XOR `marks` — senão
    `ValueError` pt-BR. `by_author`/`author_decision` têm que vir SEMPRE
    juntos (um sem o outro não é modo válido, mesmo que só `by_author`
    entre na contagem XOR abaixo)."""
    selected = (accept_all, reject_all, by_author is not None, marks is not None)
    if sum(1 for s in selected if s) != 1:
        raise ValueError(
            "escolha exatamente um modo de decisão por chamada: `accept_all`, "
            "`reject_all`, `by_author` (junto de `author_decision`), ou "
            "`marks` (dict índice->decisão) — nunca zero, nunca mais de um."
        )
    if (by_author is not None) != (author_decision is not None):
        raise ValueError(
            "`by_author` exige `author_decision` (True aceitar/False "
            "rejeitar) explícito junto, e vice-versa — os dois formam UM "
            "único modo de decisão, nunca isolados."
        )


def _pair_author_anchors(
    marks: list[criticmarkup.Mark],
) -> tuple[dict[int, int], dict[int, str], set[int]]:
    """Pareia cada marca de CONTEÚDO com a âncora `{>>prumo-autor: X<<}` que
    a segue IMEDIATAMENTE (adjacência estrita — MESMA regra de pareamento de
    :func:`parse_adeu_markdown`/Task 4: `current.kind == "comment"`,
    `previous.kind != "comment"` e `current.start == previous.end`, zero
    caracteres entre as duas).

    Retorna `(anchor_of_content, anchor_author, anchor_indices)`:
    ``anchor_of_content`` mapeia índice da marca de conteúdo (posição em
    ``marks``, saída de `criticmarkup.parse`) -> índice da âncora pareada;
    ``anchor_author`` mapeia índice de âncora -> autor extraído do corpo;
    ``anchor_indices`` é o conjunto de TODOS os índices reconhecidos como
    âncora de autor — pareados OU órfãos. NUNCA sobrevivem à PÁGINA final
    (per design do módulo); em `review.md` (a worklist viva — ver comentário
    da seção acima), só a âncora pareada com uma marca de conteúdo que segue
    PENDENTE após esta chamada sobrevive — o chamador (`apply_review`)
    decide qual conjunto manter, esta função só entrega o pareamento.

    Âncora ÓRFÃ (corpo casa `prumo-autor: X` mas sem marca de conteúdo
    NÃO-comment imediatamente antes — ex.: duas âncoras encostadas, ou
    âncora logo no início do texto) é reconhecida no segundo laço e um aviso
    é emitido via `logger.warning` — nunca hard-fail: um `review.md` com
    âncora órfã ainda precisa ser aplicável (o chamador remove a âncora
    órfã do mesmo jeito que uma pareada, em ambos os corpos que escreve)."""
    anchor_of_content: dict[int, int] = {}
    anchor_author: dict[int, str] = {}
    anchor_indices: set[int] = set()

    for i in range(1, len(marks)):
        previous, current = marks[i - 1], marks[i]
        if current.kind != "comment" or previous.kind == "comment" or current.start != previous.end:
            continue
        match = _AUTHOR_ANCHOR_RE.match(current.b)
        if match is None:
            continue
        anchor_of_content[i - 1] = i
        anchor_author[i] = match.group("author")
        anchor_indices.add(i)

    for i, mark in enumerate(marks):
        if mark.kind != "comment" or i in anchor_indices:
            continue
        match = _AUTHOR_ANCHOR_RE.match(mark.b)
        if match is None:
            continue
        anchor_indices.add(i)
        anchor_author[i] = match.group("author")
        logger.warning(
            "âncora de autor órfã em review.md (marca #%d, corpo %r) — "
            "ignorada (âncoras nunca vão para a página final).",
            i,
            mark.b,
        )

    return anchor_of_content, anchor_author, anchor_indices


def _citekey_multiset(text: str) -> Counter[str]:
    """Multiconjunto de citekeys em `text` (fonte, normalizado antes da
    contagem — `normalize_markdown`) — a conservação pós-apply precisa do
    MULTIconjunto exato (uma citação repetida conta 2x), não da lista
    deduplicada de `core.citations.scan_citekeys`. Mesmo caminho de detecção
    do export (`export._norm_citation_spans` sobre o texto normalizado):
    cada grupo `[@a]`/`[@a; @b]` contribui os citekeys que contém, via
    `CITEKEY_RE`.

    LIMITAÇÃO conhecida (consistente com `export._norm_citation_spans`):
    citação narrativa `@key` fora de colchetes não é contada — o pipeline
    docx do prumo usa exclusivamente a forma com colchetes."""
    norm = normalize_markdown(text)
    counter: Counter[str] = Counter()
    for start, end in _norm_citation_spans(norm):
        counter.update(CITEKEY_RE.findall(norm[start:end]))
    return counter


def _corrupt_ingest_sidecar_message(path: Path) -> str:
    """Mensagem pt-BR única para sidecar de INGEST (`events.yaml`/
    `review-comments.yaml`) corrompido/fora do schema — o comando de
    correção é re-INGERIR (diferente de :func:`_corrupt_sidecar_message`,
    dos sidecars de EXPORT citemap/span-map, cujo comando é re-exportar).
    MESMA mensagem que `mcp_server` compunha isoladamente (achado
    Important #3 do review da Fase 3: a tradução de
    `pydantic.ValidationError`/erro de YAML pra `ValueError` pt-BR estava
    duplicada, e DIVERGENTE, entre `mcp_server.py` (traduzia) e `cli.py`
    (não traduzia — `pydantic.ValidationError` cru vazava pelo comando
    `prumo write review events`). Consolidada aqui, junto dos leitores
    read-side, pra nunca mais divergir."""
    return (
        f"sidecar corrompido ({path}): re-rode `prumo write review ingest "
        "<reviewed.docx> --page <page>` para regenerá-lo."
    )


def _review_dir_for(page: Path, project_root: Path | None) -> Path:
    """`reviews/<slug>/` de `page` — resolução compartilhada pelos leitores
    read-side (:func:`read_events_file`/:func:`read_comments_file`/
    :func:`read_worklist`), MESMO padrão de `ingest()`/`apply_review()`:
    `export.detect_project_root` se `project_root` não for fornecido,
    `export.slugify`."""
    project_root = project_root or detect_project_root(page)
    return project_root / "reviews" / slugify(page, project_root)


def _missing_ingest_sidecar_error(review_dir: Path, name: str) -> FileNotFoundError:
    """`FileNotFoundError` pt-BR (comando de ingest embutido) para artefato
    de `reviews/<slug>/` ausente — a página nunca foi ingerida, ou os
    artefatos de `reviews/` foram apagados."""
    return FileNotFoundError(
        f"Sidecar de review ausente em {review_dir}: {name}. Rode "
        "`prumo write review ingest <reviewed.docx> --page <page.md>` antes."
    )


_SidecarT = TypeVar("_SidecarT", bound=BaseModel)


def _read_ingest_sidecar_yaml(path: Path, model: type[_SidecarT]) -> _SidecarT:
    """Carrega+valida um sidecar YAML de ingest. YAML malformado
    (`yaml.YAMLError`) ou fora do schema (`pydantic.ValidationError`) vira
    `ValueError` pt-BR via :func:`_corrupt_ingest_sidecar_message` — nunca o
    traceback cru de pydantic/PyYAML vazando pro CLI ou pro agente MCP."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(_corrupt_ingest_sidecar_message(path)) from exc

    try:
        return model.model_validate(raw or {})
    except ValidationError as exc:
        raise ValueError(_corrupt_ingest_sidecar_message(path)) from exc


def read_events_file(page: Path, project_root: Path | None = None) -> ReviewEventsFile:
    """Lê e valida `events.yaml` de `reviews/<slug>/` para `page` — ÚNICO
    ponto de leitura de `events.yaml` usado por `cli.py` (comando `prumo
    write review events`) e por `mcp_server` (`review_status`/
    `review_events`); achado Important #3 do review da Fase 3, ver
    :func:`_corrupt_ingest_sidecar_message`.

    Contrato de erro compartilhado com os siblings
    (:func:`read_comments_file`/:func:`read_worklist`): `FileNotFoundError`
    pt-BR (comando de ingest embutido) se o artefato ainda não existir;
    `ValueError` pt-BR ("sidecar corrompido") se existir mas for YAML
    malformado ou fora do schema."""
    events_path = _review_dir_for(page, project_root) / "events.yaml"
    if not events_path.is_file():
        raise _missing_ingest_sidecar_error(events_path.parent, "events.yaml")
    return _read_ingest_sidecar_yaml(events_path, ReviewEventsFile)


def read_comments_file(page: Path, project_root: Path | None = None) -> ReviewCommentsFile:
    """Lê e valida `review-comments.yaml` de `reviews/<slug>/` para `page` —
    sibling de :func:`read_events_file`, MESMO contrato de erro (consolidação
    do achado do /simplify 2026-07-25: `mcp_server._read_comments` duplicava
    esta leitura com wording divergente)."""
    comments_path = _review_dir_for(page, project_root) / "review-comments.yaml"
    if not comments_path.is_file():
        raise _missing_ingest_sidecar_error(comments_path.parent, "review-comments.yaml")
    return _read_ingest_sidecar_yaml(comments_path, ReviewCommentsFile)


def read_worklist(page: Path, project_root: Path | None = None) -> str:
    """Conteúdo cru de `review.md` (o worklist vivo do ciclo de revisão) de
    `reviews/<slug>/` para `page` — sibling de :func:`read_events_file`,
    MESMO contrato de `FileNotFoundError` (não há schema a validar: o
    worklist é Markdown livre, frontmatter + marcas CriticMarkup)."""
    worklist_path = _review_dir_for(page, project_root) / "review.md"
    if not worklist_path.is_file():
        raise _missing_ingest_sidecar_error(worklist_path.parent, "review.md")
    return worklist_path.read_text(encoding="utf-8")


def count_pending_drops(events: Iterable[ReviewEvent]) -> int:
    """Drops de citação (`kind == "citation-drop"`) ainda pendentes de
    confirmação explícita no `apply` — contagem única compartilhada por
    :func:`status` e pela fachada CLI (`write/cli.py`, comando `ingest`),
    que a duplicavam (achado opcional do /simplify 2026-07-25)."""
    return sum(1 for event in events if event.kind == EVENT_KIND_CITATION_DROP)


def status(page: Path, project_root: Path | None = None) -> dict[str, Any]:
    """Contagens do ciclo de revisão de `page`: marcas pendentes em
    `review.md` (`criticmarkup.parse`), eventos por `kind`, comentários
    extraídos do docx revisado e drops de citação pendentes
    (:func:`count_pending_drops`).

    Agrega os três leitores read-side (:func:`read_worklist`/
    :func:`read_events_file`/:func:`read_comments_file`) — nesta ordem, que
    define a prioridade do erro quando mais de um artefato falta — e
    propaga o contrato de erro deles inalterado. Retorna dado plano
    (`dict`), pronto pra fachada MCP (`review_status`) emitir sem
    reempacotar."""
    review_md_text = read_worklist(page, project_root)
    events_file = read_events_file(page, project_root)
    comments_file = read_comments_file(page, project_root)

    return {
        "page": events_file.page,
        "pending_marks": len(criticmarkup.parse(review_md_text)),
        "events_by_kind": dict(Counter(event.kind for event in events_file.events)),
        "comments": len(comments_file.comments),
        "pending_drops": count_pending_drops(events_file.events),
    }


def _read_review_md_and_events(review_dir: Path) -> tuple[str, str, ReviewEventsFile]:
    """Carrega `review.md` + `events.yaml` de `review_dir`.

    Retorna `(raw_fm, review_body, events_file)`: `raw_fm` é o bloco de
    frontmatter VERBATIM (via `split_frontmatter_raw` — Fix pós-review,
    Crítico 1), extraído de `review.md` (não da página) porque `review.md`
    é a fonte de verdade do frontmatter durante todo o ciclo de vida do
    review (ver comentário da seção "Task 9" acima) — o MESMO `raw_fm` é
    usado para reescrever tanto a página quanto `review.md` nesta chamada.
    Ausência de QUALQUER um dos dois arquivos é `FileNotFoundError` pt-BR
    (mesmo padrão de `_read_sidecars`, Task 8)."""
    review_md_path = review_dir / "review.md"
    events_path = review_dir / "events.yaml"
    missing = [p.name for p in (review_md_path, events_path) if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Sidecar(s) de review ausente(s) em {review_dir}: {', '.join(missing)}. "
            "Rode `prumo write review ingest <reviewed.docx> --page <page.md>` antes."
        )
    raw_fm, review_body = split_frontmatter_raw(review_md_path.read_text())
    events_file = ReviewEventsFile.model_validate(yaml.safe_load(events_path.read_text()) or {})
    return raw_fm, review_body, events_file


def _missing_drop_confirmation_message(missing: list[str]) -> str:
    occ_list = ", ".join(missing)
    return (
        f"Evento(s) `citation-drop` pendente(s) sem confirmação explícita "
        f"(I6 — decisão humana explícita em Git): occ {occ_list}. Rode de "
        f"novo com `--confirm-citation-drops {','.join(missing)}` (cobrindo "
        "TODOS os drops listados) para confirmar a remoção dessa(s) "
        "citação(ões) — lembre de também remover a referência à citação do "
        "corpo de `review.md` antes do apply — ou reverta a deleção no Word "
        "e re-ingira."
    )


def _apply_mark_lost_message(residual: list[criticmarkup.Mark]) -> str:
    excerpts = "; ".join(f'"{(m.a or m.b).strip()[:80]}"' for m in residual)
    return (
        f"Guarda B (apply-side): {len(residual)} marca(s) residual(is) em "
        "review.md após aplicar TODAS as decisões pedidas "
        f"(--accept-all/--reject-all): {excerpts}. Isso é um BUG interno do "
        "apply (nunca deveria acontecer em uso normal) — não prossiga; "
        "reporte o problema com o review.md em questão."
    )


def apply_review(
    page: Path,
    *,
    accept_all: bool = False,
    reject_all: bool = False,
    by_author: str | None = None,
    author_decision: bool | None = None,
    marks: dict[int, bool] | None = None,
    confirm_citation_drops: list[str] | None = None,
    today: str,
    project_root: Path | None = None,
) -> ApplyResult:
    """Aplica as decisões de revisão de `reviews/<slug>/review.md` de volta
    na PÁGINA original (Task 9 — fecha o loop aberto por `ingest()`, Task 8).

    Modo de decisão — EXATAMENTE um por chamada (`_validate_apply_mode`):
    `accept_all`/`reject_all` decidem TODAS as marcas; `by_author` +
    `author_decision` decidem só as marcas cujo autor pareado (via âncora
    `{>>prumo-autor: X<<}`, emitida por `transplant_to_source(...,
    author_anchors=True)` no `ingest()`) bate com `by_author`; `marks`
    decide por ÍNDICE na lista de marcas de CONTEÚDO (âncoras nunca contam
    para esse índice). Marca de conteúdo sem decisão explícita permanece
    intacta — só `accept_all`/`reject_all` recebem Guarda B (nenhum residual
    pode sobrar).

    Pré-condições (nesta ordem, cada uma hard-fail antes da próxima, sem
    NENHUM write-back até todas passarem):
    1. eventos `citation-drop` pendentes precisam estar TODOS cobertos por
       `confirm_citation_drops` (I6 — decisão humana explícita em Git);
       `confirm_citation_drops` com occ_id que não corresponde a nenhum
       drop pendente também é erro (evita confirmação "morta"). Um drop já
       confirmado numa chamada ANTERIOR não conta mais como pendente (o
       evento já foi removido de `events.yaml` — ver "write-back" abaixo),
       então uma segunda chamada não precisa re-confirmá-lo.
    2. qualquer OUTRO kind de evento pendente (`unanchored-mark`,
       `ambiguous-anchor`, `non-identity-span`, `citation-touched-prose`)
       bloqueia o apply — modo degradado do spec: resolva manualmente.

    Aplicação: `criticmarkup.parse(review_body)` + `criticmarkup.apply` com
    as decisões computadas. Guarda B (só `accept_all`/`reject_all`):
    `criticmarkup.parse(corpo_final_da_página) == []` senão `MarkLostError`.
    Conservação pós-apply (SEMPRE, todos os modos): `_citekey_multiset` do
    corpo final == citekeys do citemap MENOS os confirmados como drop — TANTO
    os desta chamada QUANTO os de chamadas anteriores (histórico acumulado
    via os eventos `applied` já em `events.yaml`, que nunca são removidos;
    ver "write-back" abaixo) — I5, bibliografia é função da fonte; a citação
    em si só sai do corpo se o HUMANO já a removeu de `review.md` (este
    módulo nunca transplanta citação, só verifica a conservação do que está
    lá).

    Write-back (`review.md` como WORKLIST VIVA — Fix pós-review, Crítico 2;
    ver comentário da seção "Task 9" acima para o raciocínio completo):
    - PÁGINA reescrita com `raw_fm` (frontmatter VERBATIM, extraído de
      `review.md` — nunca re-parseado/re-serializado via YAML, nem relido da
      própria página; Fix pós-review, Crítico 1) + o corpo com as marcas
      DECIDIDAS resolvidas e as PENDENTES intactas, mas SEM NENHUMA âncora de
      autor (decidida ou pendente).
    - `review.md` TAMBÉM é reescrito (`raw_fm` + o mesmo corpo), mas as
      marcas PENDENTES mantêm sua âncora de autor colada — só as âncoras de
      marcas já decididas (nesta chamada ou antes) somem. Uma marca decidida
      vira texto puro (nunca mais uma marca CriticMarkup), então uma chamada
      futura não pode "desdecidi-la" por acidente.
    - `events.yaml`: eventos `citation-drop` confirmados nesta chamada são
      REMOVIDOS (deixam de ser pendência); um evento `kind="applied"` é
      apendado (timestamp via `today`, nunca `datetime.now()` —
      determinismo em teste) com os citekeys confirmados agora — histórico
      completo preservado na cadeia de eventos `applied` (nunca removidos)
      + Git.
    """
    _validate_apply_mode(
        accept_all=accept_all,
        reject_all=reject_all,
        by_author=by_author,
        author_decision=author_decision,
        marks=marks,
    )

    project_root = project_root or detect_project_root(page)
    slug = slugify(page, project_root)
    review_dir = project_root / "reviews" / slug

    raw_fm, review_body, events_file = _read_review_md_and_events(review_dir)
    citemap, _span_map = _read_sidecars(review_dir)

    drop_events = [event for event in events_file.events if event.kind == EVENT_KIND_CITATION_DROP]
    drop_occ_ids = {event.occ_id for event in drop_events if event.occ_id}
    confirm_set = set(confirm_citation_drops or [])

    missing_confirmation = sorted(drop_occ_ids - confirm_set)
    if missing_confirmation:
        raise ValueError(_missing_drop_confirmation_message(missing_confirmation))

    extraneous = sorted(confirm_set - drop_occ_ids)
    if extraneous:
        raise ValueError(
            "`confirm_citation_drops` cita occ_id(s) sem evento `citation-drop` "
            f"pendente correspondente: {', '.join(extraneous)}. Confira "
            f"{review_dir / 'events.yaml'}."
        )

    other_pending = [
        event for event in events_file.events if event.kind not in _NON_BLOCKING_EVENT_KINDS
    ]
    if other_pending:
        kinds = ", ".join(sorted({event.kind for event in other_pending}))
        raise ValueError(
            f"Evento(s) pendente(s) em events.yaml além de citation-drop "
            f"(kind(s): {kinds}) impedem o apply (modo degradado do spec). "
            "Resolva cada evento — editando review.md manualmente ou aceitando "
            "uma proposta da skill /prumo-assist:review-reconcile — e depois "
            "REMOVA a entrada correspondente de events.yaml (o bloco YAML "
            "inteiro do evento, não só um campo): nem a edição manual nem a "
            "proposta da skill removem o evento sozinhas. AVISO: NÃO rode "
            "`prumo write review ingest` de novo para tentar limpar isso — o "
            "ingest reescreve review.md do zero e destrói qualquer proposta "
            "pendente no worklist atual."
        )

    flat_marks = criticmarkup.parse(review_body)
    anchor_of_content, anchor_author, anchor_indices = _pair_author_anchors(flat_marks)
    content_flat_indices = [i for i in range(len(flat_marks)) if i not in anchor_indices]

    if marks is not None:
        invalid = sorted(k for k in marks if k < 0 or k >= len(content_flat_indices))
        if invalid:
            valid_range = (
                f"0..{len(content_flat_indices) - 1}"
                if content_flat_indices
                else "nenhum (review.md sem marca de conteúdo)"
            )
            raise ValueError(
                f"índice(s) de marca fora do intervalo: {invalid} — review.md "
                f"tem {len(content_flat_indices)} marca(s) de conteúdo "
                f"(índices válidos: {valid_range})."
            )

    flat_decisions: dict[int, bool] = {}

    if accept_all:
        for i in content_flat_indices:
            flat_decisions[i] = True
    elif reject_all:
        for i in content_flat_indices:
            flat_decisions[i] = False
    elif by_author is not None:
        assert author_decision is not None  # _validate_apply_mode já garantiu
        for content_idx in content_flat_indices:
            anchor_idx = anchor_of_content.get(content_idx)
            author = anchor_author.get(anchor_idx) if anchor_idx is not None else None
            if author != by_author:
                continue
            flat_decisions[content_idx] = author_decision
    else:
        assert marks is not None  # _validate_apply_mode já garantiu
        for content_position, content_idx in enumerate(content_flat_indices):
            if content_position in marks:
                flat_decisions[content_idx] = marks[content_position]

    # Contagens DERIVADAS de `flat_decisions` — neste ponto ele só contém
    # marcas de conteúdo (âncoras entram depois, em cópias por destino).
    applied_count = sum(1 for accepted in flat_decisions.values() if accepted)
    rejected_count = len(flat_decisions) - applied_count

    # Marcas de conteúdo NÃO decididas nesta chamada continuam pendentes — a
    # âncora que as anota precisa sobreviver em `review.md` (worklist viva,
    # Fix pós-review Crítico 2) para uma chamada `by_author` futura ainda
    # conseguir localizá-las; qualquer OUTRA âncora (pareada com conteúdo já
    # decidido agora, ou órfã) é descartada nos DOIS corpos abaixo.
    pending_content_indices = [i for i in content_flat_indices if i not in flat_decisions]
    keep_anchor_indices = {
        anchor_of_content[i] for i in pending_content_indices if i in anchor_of_content
    }

    # PÁGINA: NENHUMA âncora sobrevive — decidida ou pendente. O valor do
    # bool é irrelevante: `comment` resolve para "" nos dois sentidos
    # (accept/reject) — ver `core/criticmarkup._resolve`.
    page_decisions = dict(flat_decisions)
    for anchor_idx in anchor_indices:
        page_decisions.setdefault(anchor_idx, False)
    final_body = criticmarkup.apply(review_body, page_decisions)

    if accept_all or reject_all:
        residual = criticmarkup.parse(final_body)
        if residual:
            raise MarkLostError(_apply_mark_lost_message(residual))

    citemap_multiset: Counter[str] = Counter(
        key for occ in citemap.occurrences for key in occ.citekeys
    )
    # Multiconjunto "já confirmado como drop": HISTÓRICO acumulado nos
    # eventos `applied` anteriores (nunca removidos — ver write-back abaixo)
    # somado aos `citation-drop` confirmados NESTA chamada. Sem o histórico,
    # uma segunda chamada (sem NENHUM `citation-drop` pendente sobrando,
    # porque a primeira já os removeu de `events.yaml`) recalcularia
    # `expected_multiset` como se o drop nunca tivesse acontecido — falso
    # positivo de `CitationConservationError` (Fix pós-review, Crítico 2).
    historical_drop_multiset: Counter[str] = Counter()
    for event in events_file.events:
        if event.kind == EVENT_KIND_APPLIED:
            historical_drop_multiset.update(event.citekeys)
    newly_confirmed_multiset: Counter[str] = Counter(
        key for event in drop_events for key in event.citekeys
    )
    confirmed_drop_multiset = historical_drop_multiset + newly_confirmed_multiset
    expected_multiset = citemap_multiset - confirmed_drop_multiset
    final_multiset = _citekey_multiset(final_body)
    if final_multiset != expected_multiset:
        raise CitationConservationError(
            "Conservação de citações violada pós-apply (I5): multiconjunto "
            f"de citekeys no corpo final ({dict(final_multiset)}) diverge do "
            f"esperado — citemap menos drops confirmados ({dict(expected_multiset)}). "
            "Se confirmou um drop, remova a citação correspondente também do "
            "corpo de `review.md` antes do apply; senão, confira se "
            "`review.md` foi editado incorretamente."
        )

    # `review.md`: marcas DECIDIDAS (nesta chamada) resolvem igual à página;
    # marcas PENDENTES mantêm sua âncora (`keep_anchor_indices`) — só âncoras
    # de conteúdo já decidido (ou órfãs) são removidas. Parte do MESMO
    # `review_body` de entrada (nunca do `final_body` da página, que já não
    # tem âncora nenhuma) — as duas escritas partem do mesmo texto-fonte, só
    # a árvore de decisões por índice difere.
    worklist_decisions = dict(flat_decisions)
    for anchor_idx in anchor_indices:
        if anchor_idx not in keep_anchor_indices:
            worklist_decisions.setdefault(anchor_idx, False)
    review_worklist_body = criticmarkup.apply(review_body, worklist_decisions)

    page.write_text(_compose_page(raw_fm, final_body), encoding="utf-8")
    (review_dir / "review.md").write_text(
        _compose_page(raw_fm, review_worklist_body), encoding="utf-8"
    )

    drops_confirmed = sorted(drop_occ_ids)
    applied_event = ReviewEvent(
        kind=EVENT_KIND_APPLIED,
        detail=(
            f"apply em {today}: {applied_count} marca(s) aceita(s), "
            f"{rejected_count} marca(s) rejeitada(s), {len(drops_confirmed)} "
            "drop(s) de citação confirmado(s)."
        ),
        citekeys=sorted(key for event in drop_events for key in event.citekeys),
    )
    # Eventos `citation-drop` recém-confirmados NÃO persistem como pendência
    # (Fix pós-review, Crítico 2) — removidos aqui; o histórico sobrevive no
    # `citekeys`/`detail` do `applied_event` acima (nunca removido) + Git.
    remaining_events = [
        event for event in events_file.events if event.kind != EVENT_KIND_CITATION_DROP
    ]
    updated_events = ReviewEventsFile(
        page=events_file.page, events=[*remaining_events, applied_event]
    )
    (review_dir / "events.yaml").write_text(
        yaml.safe_dump(updated_events.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return ApplyResult(
        page=page,
        applied=applied_count,
        rejected=rejected_count,
        drops_confirmed=drops_confirmed,
    )


# --- Fase 3/Task 2: propose_prose_edit() — proposta do agente vira marca ----
#     pendente no worklist (I1/I3b) -------------------------------------------
#
# `propose_prose_edit` é a ÚNICA função de ESCRITA que um AGENTE (via
# prumo-MCP, `mcp_server.py`, Fase 3 do spec) pode chamar sobre `review.md` —
# mecânica literal de "código garante, agente propõe, humano decide": a
# proposta NÃO é um caminho novo de aplicação, é uma marca CriticMarkup
# NORMAL inserida no MESMO worklist que `apply_review` (Task 9, acima) já
# sabe ler, com a MESMA âncora de autor `{>>prumo-autor: X<<}` que
# `_pair_author_anchors` já pareia — aqui `X` é `author` (default
# `"agente"`), o que permite `apply_review(by_author="agente", ...)` decidir
# todas as propostas de uma vez, sem tocar marca humana nenhuma.
#
# Guardas I1/I3b são o PONTO desta função (Global Constraints da Fase 3): um
# agente nunca pode cunhar citação (I3b — vínculo semântico atestado só
# entra por seleção humana, metadados completos, registrado em Git) nem
# decidir por uma edição que encoste numa citação existente (I1 — citação é
# átomo opaco; toda edição que a toque vai inteira ao reconciliador HUMANO).
# As duas guardas hard-fail ANTES de qualquer escrita em disco — nesta
# ordem: (1) âncora precisa ocorrer EXATAMENTE 1x no corpo do worklist (senão
# nem sabemos qual span checar contra citação); (2) payload (I3b); (3)
# tangência/interseção da âncora com citação (I1); (4) validação estrutural
# de `position="replace"` (kind del/sub, `a == anchor_excerpt`).
#
# FIX PÓS-REVIEW (2 Críticos + 1 Important — review da própria Task 2):
# as guardas (1)-(4) acima validam INPUTS em ISOLAMENTO — `a`/`b` sozinhos,
# `body` original sozinho — e NUNCA o resultado da composição. Dois repros
# do reviewer provam que isso é insuficiente: (Crítico 1) `author` é colado
# SEM escape em `"{>>prumo-autor: " + author + "<<}"` — um `author` hostil
# (`"agente<<} [[@injetado]] {>>x"`) fecha a âncora PREMATURAMENTE e solta
# texto LIVRE (inclusive citação fabricada) no corpo; (Crítico 2) um payload
# inofensivo ISOLADO (`b="[["`, sem `@` nem `[@`/`[[@`) pode, ao ser ACEITO
# (`criticmarkup.accept`), ficar adjacente a texto pré-existente do corpo
# (ex.: `"...@fake2020]]..."`) e COMPLETAR uma citação nunca cunhada por
# humano — as guardas de payload/tangência não veem isso porque nenhuma das
# duas, isoladamente, "parece" uma citação.
#
# A correção é estrutural, não mais um caso a mais de allowlist: (a)
# `_reject_invalid_author` — allowlist barata (sem I/O) rodada ANTES de
# qualquer outra coisa; (b) um ROUND-TRIP GUARD pós-splice, DEPOIS de montar
# `new_body` e ANTES de escrever, que reprova qualquer divergência entre o
# que foi PEDIDO e o que o RESULTADO re-parseado realmente contém — contagem
# de marcas, identidade da marca inserida (kind/a/b) e da âncora de autor
# seguinte, e conservação do multiconjunto de citações (marcadas e
# `CITEKEY_RE` cru) simulando os DOIS desfechos da proposta — aceite E
# rejeição (achado C1: só o aceite deixava `{--@--}` cunhar citação na
# rejeição). Ver
# `_reject_composed_result`/`_reject_citation_divergence` abaixo para os
# detalhes de cada sub-checagem. (Important, mesmo review): `kind="comment"`
# deixou de ser proponível — não é pareável por `_pair_author_anchors`
# (vira âncora órfã, perde autoria) — ver o `if` logo no topo do corpo da
# função.

# Guarda NOVA (Fix pós-review, achado Crítico 1): `author` é colado DIRETO
# na âncora `"{>>prumo-autor: " + author + "<<}"` sem NENHUM escape — allowlist
# (não denylist) é a defesa correta: só letras (inclusive acentuadas
# `À-ÿ`), dígitos, espaço, ponto, hífen e underscore passam. Nenhum
# delimitador de CriticMarkup (`{`, `}`, `<`, `>`) nem de citação (`[`, `]`)
# está na lista — um `author` que os contivesse poderia fechar a âncora
# prematuramente (`<<}`) e/ou abrir uma marca/citação nova fora de qualquer
# CriticMarkup válido. Roda ANTES de tudo — é barata (nem `project_root` nem
# `review.md` precisam existir para este check falhar).
_AUTHOR_ALLOWED_RE = re.compile(r"^[A-Za-z0-9À-ÿ _.\-]+$")


def _reject_invalid_author(author: str) -> None:
    """Guarda: `author` só pode conter letras (incl. acentuadas)/dígitos/
    espaço/ponto/hífen/underscore — ver comentário de `_AUTHOR_ALLOWED_RE`
    acima para o raciocínio completo (injeção de delimitador via `author`,
    achado Crítico 1 do review desta função)."""
    if not _AUTHOR_ALLOWED_RE.fullmatch(author):
        raise ValueError(
            "author inválido — use apenas letras/números/espaços "
            f"(recebido: {author!r}). `author` é colado direto na âncora "
            "`{>>prumo-autor: X<<}` sem escape — caracteres de delimitador "
            "de CriticMarkup/citação (`{`, `}`, `<`, `>`, `[`, `]`) "
            "poderiam fechar a âncora prematuramente e injetar texto fora "
            "de qualquer marca. Use um nome simples (letras, dígitos, "
            "espaço, ponto, hífen ou underscore)."
        )


_COMPOSED_RESULT_REFUSAL_PREFIX = (
    "propose_prose_edit recusado: a proposta alteraria/fabricaria citação ou "
    "quebraria a sintaxe de marcas — recusada (I1/I3b); detalhe: "
)


def _reject_composed_result(detail: str) -> NoReturn:
    """Levanta a recusa ÚNICA do round-trip guard pós-splice (Fix pós-review,
    Críticos 1+2) — prefixo fixo + `detail` identificando qual sub-checagem
    falhou (contagem de marcas, identidade da marca/âncora após re-parse, ou
    conservação de citação — ver chamadores em `propose_prose_edit` e em
    `_reject_citation_divergence`)."""
    raise ValueError(
        f"{_COMPOSED_RESULT_REFUSAL_PREFIX}{detail}. Escolha outro "
        "anchor_excerpt/payload que não componha com o texto adjacente do "
        "worklist, ou deixe o evento para decisão humana."
    )


def _reject_citation_divergence(
    before_text: str, after_text: str, *, moment: str = "aceite"
) -> None:
    """Guarda NOVA (Fix pós-review, achado Crítico 2): compara os
    multiconjuntos de citação de `before_text`/`after_text` — o CHAMADOR
    passa o par JÁ RESOLVIDO (`criticmarkup.accept` ou `criticmarkup.reject`
    de `body`/`new_body`), NUNCA o texto cru com marcas ainda pendentes: o
    payload `b="["` do repro do reviewer nunca aparece adjacente ao texto
    pré-existente no `new_body` CRU (fica preso dentro do `{++...++}` da
    própria marca) — só se torna `"[@fake2020]"` depois que a marca é
    resolvida. `moment` nomeia QUAL simulação está sendo checada, e entra na
    mensagem de recusa.

    `propose_prose_edit` roda a guarda DUAS vezes, sobre os DOIS desfechos
    possíveis da marca proposta (achado C1): o aceite
    (`apply_review(by_author=author, author_decision=True)`) e a REJEIÇÃO
    (`author_decision=False`). Simular só o aceite deixava passar a classe
    inteira de fabricação por `kind` `del`/`sub` fora de
    `position="replace"`: uma marca `{--@--}` colada antes de um token sem
    sigilo (`Segundo {--@--}Smith2020`) é invisível no aceite (o `@` some) e
    cunha `@Smith2020` na rejeição — citação fabricada justamente quando o
    humano REJEITA a proposta do agente.

    Duas checagens independentes por desfecho, sobre o corpo INTEIRO (sem
    restringir a spans de citação — pega até citação narrativa `@key` solta,
    fora de colchetes): (i) citekeys crus (``CITEKEY_RE``); (ii) GRUPOS de
    citação (``_citation_atom_spans``). A (ii) existe porque a (i) é cega à
    composição: embrulhar ``@key`` em ``[@key]`` não muda o multiconjunto de
    chave — só o conjunto de grupos marcados. QUALQUER divergência entre
    antes/depois — em qualquer uma das duas, em qualquer um dos dois
    desfechos — recusa: não importa COMO a fabricação aconteceria, só
    importa que o multiconjunto de citações do resultado seja idêntico ao de
    antes."""
    before_keys = Counter(CITEKEY_RE.findall(before_text))
    after_keys = Counter(CITEKEY_RE.findall(after_text))
    if before_keys != after_keys:
        _reject_composed_result(
            "o multiconjunto de citekeys (`CITEKEY_RE`, corpo inteiro, "
            f"simulando {moment} da proposta) mudou entre antes e depois da "
            f"composição — antes: {dict(before_keys)}, depois: {dict(after_keys)}"
        )

    before_spans = Counter(before_text[s:e] for s, e in _citation_atom_spans(before_text))
    after_spans = Counter(after_text[s:e] for s, e in _citation_atom_spans(after_text))
    if before_spans != after_spans:
        _reject_composed_result(
            "o multiconjunto de GRUPOS de citação (gramática única de "
            "`core.citations`, as duas sintaxes) mudou entre antes e depois "
            f"da composição, simulando {moment} da proposta — antes: "
            f"{dict(before_spans)}, depois: {dict(after_spans)}"
        )


@dataclass(frozen=True)
class ProposalResult:
    """Resultado de `propose_prose_edit()` — quando retorna sem erro, a marca
    JÁ foi inserida em `review.md` (o worklist — NUNCA a página original: a
    proposta só vira mudança de fato quando um HUMANO a decide via
    `apply_review`, tipicamente `by_author="agente"`).

    ``inserted_mark_index`` é o índice da marca recém-inserida na ordem de
    `criticmarkup.parse` sobre o corpo NOVO do worklist (após a inserção) —
    identificado por POSIÇÃO de inserção (o offset onde o texto da marca foi
    colado), NUNCA por igualdade de conteúdo: duas marcas com texto idêntico
    (ex.: duas propostas ``{++ extra++}`` em pontos diferentes do mesmo
    `review.md`) colidiriam numa busca por conteúdo, mas cada uma tem um
    offset de início único no texto pós-inserção.
    """

    review_md: Path
    inserted_mark_index: int


def _reject_citation_payload_in_proposal(a: str, b: str) -> None:
    """Guarda I3b: nenhuma proposta de agente pode cunhar citekey/sintaxe de
    citação no payload (``a``/``b``) — citekey só entra por seleção humana
    explícita, com metadados completos, atestada em Git (I3b, spec). Checa
    `CITEKEY_RE` (mesma gramática de `core/citations`, único reconhecedor de
    citekey do pacote) e também o colchete cru ``[@`` — a checagem literal de
    substring cobre até uma citação malformada que `CITEKEY_RE` sozinho
    poderia não casar (ex.: colchete aberto sem fechar)."""
    if CITEKEY_RE.search(a or "") or CITEKEY_RE.search(b or "") or "[@" in (a + b):
        raise ValueError(
            "propose_prose_edit recusado (I3b — vínculo semântico atestado): "
            f"payload contém citekey/sintaxe de citação (a={a!r}, b={b!r}). "
            "Citekey só entra por seleção humana explícita, com metadados "
            "completos, registrada em Git — nunca via proposta de agente. Se "
            "a intenção é citar algo, deixe o evento para decisão humana em "
            "vez de chamar propose_prose_edit com esse payload."
        )


def _citation_atom_spans(body: str) -> Iterator[tuple[int, int]]:
    """Spans de citação protegidos pela Guarda I1. União de DUAS fontes.

    União de duas fontes, porque nenhuma sozinha basta:

    - ``iter_marked_citation_spans`` (gramática única de ``core/citations``)
      — cobre o Pandoc ``[@key]``/``[@a; @b]``, única sintaxe do repo
      (spec 2026-07-22).
    - ``iter_narrative_citation_spans`` — cobre ``@key`` narrativa, forma
      legítima da MESMA gramática Pandoc que a primeira não enxerga (fora
      de colchetes). Sem ela, a MESMA edição é recusada em ``[@k]`` e
      aplicada em ``@k`` — e nesse caminho chega à página.

    Sobreposição entre as fontes é inofensiva: a guarda recusa no primeiro
    span que encostar.

    Roda sobre o corpo CRU, sem filtrar code fences (ao contrário de
    ``scan_marked_citekeys``, que passa por ``_body_lines``): super-proteção
    deliberada — um ``@key`` dentro de bloco de código vira átomo protegido
    e o agente leva recusa. É o lado certo do trade-off (fail-toward-human):
    o custo do falso positivo é o humano decidir uma edição; o do falso
    negativo seria edição silenciosa de citação.
    """
    yield from iter_marked_citation_spans(body)
    yield from iter_narrative_citation_spans(body)


def _reject_anchor_tangent_to_citation(body: str, start: int, end: int) -> None:
    """Guarda I1: âncora ``[start, end)`` que INTERSECTA ou TANGENCIA
    (adjacência imediata, distância zero) um span de citação no corpo do
    worklist é recusada — citação é átomo opaco (I1, spec): qualquer
    edição que a encoste é decisão HUMANA, nunca aproximada por agente.
    Vale nas duas formas da gramática Pandoc (``[@key]`` marcada e ``@key``
    narrativa) — ver :func:`_citation_atom_spans`.
    ``not (end < cs or ce < start)`` é a negação de "os dois intervalos têm
    ao menos 1 caractere de distância" — cobre interseção E adjacência
    (``end == cs`` ou ``ce == start``) com o MESMO teste, `<` estrito nos
    dois lados de propósito (o brief manda tangência recusar, não só
    sobreposição)."""
    for cs, ce in _citation_atom_spans(body):
        if not (end < cs or ce < start):
            raise ValueError(
                "propose_prose_edit recusado (I1 — citação é átomo): a âncora "
                f"encosta em ou intersecta a citação {body[cs:ce]!r} — citação "
                "nunca é editável/aproximada por agente; qualquer edição que a "
                "toque é decisão humana. Escolha uma âncora que não encoste na "
                "citação, ou deixe o evento para o humano decidir."
            )


def propose_prose_edit(
    page: Path,
    *,
    anchor_excerpt: str,
    position: Literal["before", "after", "replace"],
    kind: Literal["ins", "del", "sub"],
    a: str = "",
    b: str = "",
    author: str = "agente",
    project_root: Path | None = None,
) -> ProposalResult:
    """Insere uma marca CriticMarkup PENDENTE no worklist (`review.md`) de
    `page`, proposta por um AGENTE — a ÚNICA escrita que um agente pode fazer
    no ciclo de revisão (Fase 3 do spec; fachada MCP em `mcp_server.py`).

    A marca é ``criticmarkup.emit(kind, a, b) + "{>>prumo-autor: " + author +
    "<<}"`` — IDÊNTICA em formato à âncora de autor que `ingest()`/Task 4-7
    já produzem para coautores humanos; `apply_review` (Task 9) não precisa
    de nenhuma lógica nova para decidir uma proposta de agente, incluindo o
    modo `by_author=author` (default `"agente"`).

    Localiza `anchor_excerpt` SÓ no CORPO do worklist (após
    `split_frontmatter_raw` — nunca no frontmatter, para offsets seguros) e
    exige ocorrência EXATAMENTE única: 0 ocorrências → "âncora não
    encontrada"; 2+ (inclusive sobrepostas — `_find_all` é conservador de
    propósito) → "âncora ambígua". `position` decide onde o texto da marca
    entra em relação ao excerto localizado: ``"before"``/`"after"` colam
    a marca imediatamente antes/depois dele (o excerto em si nunca muda);
    ``"replace"`` substitui o excerto pela marca — e por isso EXIGE `kind`
    `"del"` ou `"sub"` E `a == anchor_excerpt` (o alvo da substituição É o
    próprio excerto localizado; qualquer outro `a` seria inconsistente com
    o que a marca resolvida deveria produzir na rejeição).

    Guardas I1/I3b (hard-fail ValueError pt-BR, ANTES de qualquer escrita):
    ver `_reject_citation_payload_in_proposal` (I3b — payload nunca cunha
    citação) e `_reject_anchor_tangent_to_citation` (I1 — âncora nunca
    intersecta/tangencia citação (`[@key]` ou `@key`)) — um agente nunca decide nada
    que toque um átomo de citação; esses eventos ficam para o reconciliador
    HUMANO (`prumo write review events --checklist`, modo degradado).

    Guardas ADICIONAIS (Fix pós-review — ver comentário de seção acima para
    o raciocínio completo): `author` passa por allowlist
    (`_reject_invalid_author`) ANTES de tudo — só letras/dígitos/espaço/
    ponto/hífen/underscore, nenhum delimitador de CriticMarkup/citação;
    `kind="comment"` é recusado explicitamente (não pareável por
    `_pair_author_anchors` — vira âncora órfã); e, DEPOIS de montar
    `new_body` e ANTES de escrever, um round-trip guard reprova qualquer
    divergência entre o PEDIDO e o RESULTADO re-parseado (contagem de
    marcas, identidade kind/a/b da marca inserida e da âncora seguinte,
    conservação do multiconjunto de citações simulando os DOIS desfechos da
    proposta, aceite E rejeição — `_reject_citation_divergence`).

    Reescreve `review.md` = `raw_fm` (frontmatter VERBATIM, extraído por
    `split_frontmatter_raw` — nunca a página original, que só muda quando um
    humano aplica a proposta) + corpo com a marca inserida. Nunca toca a
    PÁGINA nem `events.yaml`/sidecars de citação — a proposta é só uma marca
    a mais no worklist, decidida pelo MESMO fluxo humano de qualquer outra.
    """
    _reject_invalid_author(author)
    if cast(str, kind) == "comment":
        raise ValueError(
            "kind comment não é proponível — comentários do agente vão no "
            "resumo da skill (achado Important do review da Task 2): uma "
            "marca `comment` sem marca de CONTEÚDO associada não é pareável "
            "por `_pair_author_anchors` (Task 9) — vira âncora ÓRFÃ e perde "
            "a autoria. Registre a observação em prosa no resumo entregue "
            "ao humano, nunca como proposta CriticMarkup."
        )

    project_root = project_root or detect_project_root(page)
    slug = slugify(page, project_root)
    review_dir = project_root / "reviews" / slug

    raw_fm, body, _events_file = _read_review_md_and_events(review_dir)

    occurrences = _find_all(body, anchor_excerpt)
    if not occurrences:
        raise ValueError(
            f"âncora não encontrada: {anchor_excerpt!r} não ocorre no corpo de "
            f"{review_dir / 'review.md'}. Amplie ou corrija o excerto para um "
            "trecho que exista literalmente no worklist."
        )
    if len(occurrences) > 1:
        raise ValueError(
            f"âncora ambígua — amplie o excerto: {anchor_excerpt!r} ocorre "
            f"{len(occurrences)}x no corpo de {review_dir / 'review.md'}. "
            "Inclua mais contexto ao redor até que o excerto identifique um "
            "único ponto no worklist."
        )

    start = occurrences[0]
    end = start + len(anchor_excerpt)

    _reject_citation_payload_in_proposal(a, b)
    _reject_anchor_tangent_to_citation(body, start, end)

    if position == "replace" and (kind not in ("del", "sub") or a != anchor_excerpt):
        raise ValueError(
            "`position='replace'` exige `kind` 'del' ou 'sub' e `a` idêntico "
            "a `anchor_excerpt` (o alvo da substituição é o próprio excerto "
            f"localizado) — recebido kind={kind!r}, a={a!r}, "
            f"anchor_excerpt={anchor_excerpt!r}."
        )

    mark_text = criticmarkup.emit(kind, a, b) + "{>>prumo-autor: " + author + "<<}"

    if position == "before":
        insertion_offset = start
        new_body = body[:start] + mark_text + body[start:]
    elif position == "after":
        insertion_offset = end
        new_body = body[:end] + mark_text + body[end:]
    else:  # replace
        insertion_offset = start
        new_body = body[:start] + mark_text + body[end:]

    # Round-trip guard pós-splice (Fix pós-review, Críticos 1+2 — "mata a
    # classe inteira"): as guardas de entrada acima checam `a`/`b`/`body`
    # ISOLADOS; esta seção valida o RESULTADO da composição, ANTES de
    # qualquer escrita (mesma disciplina de "hard-fail antes de qualquer
    # escrita" que já valia para o recálculo de `inserted_mark_index` desta
    # função). Também cobre o caso PRÉ-EXISTENTE (corpo já malformado — ex.:
    # humano no meio de uma edição manual, marca não fechada):
    # `criticmarkup.parse` levanta `ValueError` (já pt-BR) antes de tudo.
    marks_before = criticmarkup.parse(body)
    marks_after = criticmarkup.parse(new_body)

    if len(marks_after) != len(marks_before) + 2:
        _reject_composed_result(
            "a contagem de marcas após a composição diverge do esperado "
            f"(esperado {len(marks_before) + 2} = {len(marks_before)} "
            f"pré-existente(s) + 2 novas, obtido {len(marks_after)}) — a "
            "inserção pode ter se fundido com uma marca vizinha ou quebrado "
            "a sintaxe de marcas já presente no worklist"
        )

    inserted_mark_index = next(
        (i for i, mark in enumerate(marks_after) if mark.start == insertion_offset), None
    )
    if inserted_mark_index is None:
        _reject_composed_result(
            "nenhuma marca do corpo pós-composição começa no offset de "
            f"inserção esperado ({insertion_offset}) — a marca proposta não "
            "foi localizada por posição após o re-parse"
        )

    content_mark = marks_after[inserted_mark_index]
    if content_mark.kind != kind or content_mark.a != a or content_mark.b != b:
        _reject_composed_result(
            "a marca inserida, após re-parse, não corresponde exatamente ao "
            f"pedido — esperado kind={kind!r}/a={a!r}/b={b!r}, obtido "
            f"kind={content_mark.kind!r}/a={content_mark.a!r}/"
            f"b={content_mark.b!r}"
        )

    anchor_mark_index = inserted_mark_index + 1
    anchor_mark = marks_after[anchor_mark_index] if anchor_mark_index < len(marks_after) else None
    expected_anchor_body = f"prumo-autor: {author}"
    if (
        anchor_mark is None
        or anchor_mark.kind != "comment"
        or anchor_mark.b != expected_anchor_body
    ):
        _reject_composed_result(
            "a âncora de autor esperada logo após a marca inserida está "
            f"ausente ou seu corpo, após re-parse, diverge de "
            f"{expected_anchor_body!r}"
        )

    # Os DOIS desfechos da marca proposta (achado C1): simular só o aceite
    # deixava a rejeição fabricar citação (`{--@--}` antes de `Smith2020`).
    _reject_citation_divergence(
        criticmarkup.accept(body), criticmarkup.accept(new_body), moment="aceite"
    )
    _reject_citation_divergence(
        criticmarkup.reject(body), criticmarkup.reject(new_body), moment="rejeição"
    )

    review_md_path = review_dir / "review.md"
    review_md_path.write_text(_compose_page(raw_fm, new_body), encoding="utf-8")

    return ProposalResult(review_md=review_md_path, inserted_mark_index=inserted_mark_index)
