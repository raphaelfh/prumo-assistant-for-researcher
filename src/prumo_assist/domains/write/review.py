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

import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from xml.etree import ElementTree as ET

from prumo_assist.core import criticmarkup
from prumo_assist.domains.write.comments import extract_from_docx
from prumo_assist.domains.write.export import _parse_csl_payload
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
)

# Mesmo padrão de comments.py (W_NS + iteração ET sobre word/document.xml).
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Namespace math (ECMA-376 parte 1, §22) — usado só pela Guarda A (Task 3)
# para achar ancestral `m:oMath` de `w:ins`/`w:del` (mudança dentro de
# equação).
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# Mesma marca de campo que `export._read_docx_citations` (MÉTODO I2)
# reconhece via regex — usada aqui só para decidir se um campo fechado é
# uma citação Zotero (antes de chamar `_parse_csl_payload`). O decode do
# payload em si (slice + json.loads + erro com índice) NÃO é mais
# duplicado: foi extraído para `export._parse_csl_payload` e importado
# (achado do review da Fase 2/Task 1 — Finding 2), porque os dois leitores
# tinham decodes que divergiam sutilmente (`review.py` aplicava
# `html.unescape` sobre texto do ElementTree já resolvido, corrompendo
# entidades como `&para=`). Cada leitor mantém só o SEU estágio de
# unescape (aqui, nenhum); a marca continua duplicada como constante local
# porque é trivial e cada laço de detecção de campo precisa dela
# independentemente.
_ZOTERO_ITEM_CSL_MARKER = "ADDIN ZOTERO_ITEM CSL_CITATION"


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


class SourceChangedError(RuntimeError):
    """Fonte mudou desde o export — sha256 do corpo diverge do span-map (Task 8)."""


class StructuralChangeError(RuntimeError):
    """Guarda A: mudança rastreada/comentário dentro de tabela, nota ou equação (Task 3)."""


class MarkLostError(RuntimeError):
    """Guarda B: uma marca extraída não pousou no destino — contagem não fecha (Task 7/9)."""


class CitationConservationError(RuntimeError):
    """Conservação de citação violada — I2/I2b/I8.

    Cobre, entre outros: campo `fldChar` desbalanceado ("campo colapsado",
    I2b — Task 1), payload JSON inválido num campo Zotero (I2 — Task 1),
    occ_id duplicado (Task 2), multiconjunto de occ/citekeys divergente do
    citemap (Task 2), fingerprint re-chaveado (I3-lite — Task 2), citação
    `touched` (decisão humana necessária — Task 2), docx igual ao
    exportado ou fora de sincronia (I8 — Task 8).
    """


class AdeuUnavailableError(RuntimeError):
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
    Zotero).
    """
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
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
       possível MOVE (mover citação não é suportado no MVP; I2c fica para a
       Fase 3). Qualquer outra combinação de duplicatas usa a mensagem
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
       transplanta CITATION-TOUCHED, decisão humana é necessária (I2c vira
       evento reconciliável só na Fase 3).

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
                "não é suportado no MVP; rejeite a mudança no Word e mova "
                "via edição da fonte, ou aguarde a Fase 3 (I2c)."
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
    re-ingerir.
    """
    with zipfile.ZipFile(docx_path) as z:
        document_xml = ET.fromstring(z.read("word/document.xml"))
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

    ``uvx`` ausente no PATH (``FileNotFoundError`` do próprio
    ``subprocess.run``) e exit != 0 (adeu resolvido mas falhou — docx
    incompatível, versão incorreta, etc.) viram a MESMA
    :class:`AdeuUnavailableError`: o chamador (Task 8, ``ingest``) só
    precisa tratar um único tipo de falha do backend de prosa.
    """
    try:
        proc = subprocess.run(
            ["uvx", "adeu==1.29.0", "extract", "--json", str(docx_path), "-o", "-"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AdeuUnavailableError(
            "uv/uvx não encontrado no PATH — adeu (backend de PROSA pinado, "
            f"`uvx adeu==1.29.0`) não pode ser invocado. {_ADEU_INSTALL_HINT}"
        ) from exc

    if proc.returncode != 0:
        raise AdeuUnavailableError(
            "adeu (backend de PROSA pinado, `uvx adeu==1.29.0`) terminou com "
            f"exit {proc.returncode}. stderr:\n{proc.stderr.strip()[-2000:]}\n"
            f"{_ADEU_INSTALL_HINT}"
        )

    payload = cast(dict[str, Any], json.loads(proc.stdout))
    return str(payload["markdown"])


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
# por valor — displays repetidos pareiam pela ORDEM do citemap, documento
# afora) e cada `(occ.norm_start, occ.norm_end)` é substituído DIRETO (já
# sabemos onde está) no lado norm — ambos os lados usam o MESMO índice `i`
# (posição da occurrence em `citemap.occurrences`) como id do token
# `\x00CIT<i>\x00`, garantindo que o MESMO token nos dois lados sempre se
# refere à MESMA citação.
#
# BOOKKEEPING (token-space -> offset original): substituir um span por um
# token de tamanho diferente desloca todo offset posterior — `_OffsetSegment`
# + `_map_offset` mantêm essa correspondência dos DOIS lados (original<->
# sentinela) via uma lista de segmentos cobrindo o texto inteiro (passthrough
# + token, em ordem); os spans localizados são sempre convertidos de volta
# para os OFFSETS ORIGINAIS do `norm_text` antes de retornar — nunca
# vazam offset em espaço-token.
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
#   de citação": se `kind == "del"` E a occurrence está em `deleted` (Task
#   2/conservação) -> consumida SILENCIOSAMENTE (nem `LocatedMark` nem
#   evento — o evento de drop é da conservação, não duplicamos aqui); se não
#   está em `deleted` -> `citation-touched-prose` (adeu "viu" uma deleção que
#   o OOXML não confirma — I1, nunca confiar no adeu para citação). Mesma
#   classificação geométrica mas `kind != "del"` (ex.: `sub`/`highlight`
#   cobrindo a citação inteira) também vira `citation-touched-prose` — só
#   `del` tem o caminho de "casar com deleted" suportado no MVP.
# - Qualquer OUTRA interseção (parcial, ou múltiplos spans) -> sempre
#   `citation-touched-prose` (decisão humana — I1, nunca auto-aplica).

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
    """Acha o span de CADA `occurrence.formatted` em `text`, occurrence a
    occurrence NA ORDEM do citemap (documento) — busca SEQUENCIAL com cursor
    avançando: displays repetidos (mesmo `formatted` em 2+ occurrences)
    pareiam pela ORDEM em que aparecem, nunca por valor. Occurrence cujo
    `formatted` está vazio, ou não é encontrado a partir do cursor atual
    (ex.: adeu reformatou o display), é PULADA — sem span sentinela para
    ela; o cursor não avança nesse caso."""
    spans: list[_SentinelSpan] = []
    cursor = 0
    for i, occ in enumerate(occurrences):
        if not occ.formatted:
            continue
        idx = text.find(occ.formatted, cursor)
        if idx == -1:
            continue
        end = idx + len(occ.formatted)
        spans.append(_SentinelSpan(start=idx, end=end, occ_index=i))
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
    if not segments:
        return offset
    last = segments[-1]
    return last.sent_end if to_sentinel else last.orig_end


def _collapse_whitespace(text: str) -> str:
    """Colapsa QUALQUER sequência de espaço em branco (espaço/tab/quebra de
    linha) em um único espaço — "texto plano" per brief; interpretação
    deliberadamente mais ampla que só "espaços múltiplos" (o requisito duro
    citado no brief) para absorver possível reformatação/quebra de linha do
    adeu ao extrair do OOXML sem mudar o comportamento no caso comum (já sem
    quebras). Não toca os bytes `\x00` do token sentinela (`\\s` não casa
    NUL)."""
    return re.sub(r"\s+", " ", text)


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
        kind="unanchored-mark",
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
        kind="ambiguous-anchor",
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
        kind="citation-touched-prose",
        detail=detail,
        occ_id=occurrences[0].occ_id if occurrences else None,
        citekeys=citekeys,
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
       drop já é da conservação).
    2. Sem interseção: monta `before`/`after` (texto plano, sentinela
       aplicada, colapsado, truncado a 48 chars sem partir token) e
       `alvo` (`a` para del/sub/highlight, vazio/ponto para ins/comment);
       busca `before + alvo + after` em `norm_text` (com sentinela também
       aplicada). Exatamente 1 match -> `LocatedMark`; 0 -> `unanchored-mark`;
       >1 -> `ambiguous-anchor`.

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

        sent_target_start = _map_offset(target_start, plain_segments, to_sentinel=True)
        sent_target_end = _map_offset(target_end, plain_segments, to_sentinel=True)
        target_str = mark.a if mark.kind in ("del", "sub", "highlight") else ""

        before_ctx = _truncate_tail(
            _collapse_whitespace(plain_text_sentinel[:sent_target_start]), _CONTEXT_CHARS
        )
        after_ctx = _truncate_head(
            _collapse_whitespace(plain_text_sentinel[sent_target_end:]), _CONTEXT_CHARS
        )
        search_str = before_ctx + target_str + after_ctx

        if search_str == "":
            if norm_text == "":
                located.append(LocatedMark(mark=mark, norm_start=0, norm_end=0))
            else:
                events.append(_ambiguous_event(mark, count=None))
            continue

        positions = _find_all(norm_text_sentinel, search_str)
        if not positions:
            events.append(_unanchored_event(mark))
        elif len(positions) > 1:
            events.append(_ambiguous_event(mark, count=len(positions)))
        else:
            sent_norm_start = positions[0] + len(before_ctx)
            sent_norm_end = sent_norm_start + len(target_str)
            norm_start = _map_offset(sent_norm_start, norm_segments, to_sentinel=False)
            norm_end = _map_offset(sent_norm_end, norm_segments, to_sentinel=False)
            located.append(LocatedMark(mark=mark, norm_start=norm_start, norm_end=norm_end))

    return located, events
