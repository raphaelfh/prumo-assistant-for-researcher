"""Ponte docx↔CriticMarkup — Fase 2 (`prumo write review ingest`/`apply`).

Toda a lógica mora aqui; a fachada CLI (Task 10) só faz parsing + chamada
do domínio + saída via `core/output.Console` (regra de fachadas finas,
`.claude/rules/code.md`). Módulo cresce tarefa a tarefa conforme
`docs/superpowers/plans/2026-07-23-ponte-fase2-review-ingest-apply.md`.

Task 1 entrega o bloco de exceções (contrato usado por todas as tasks
seguintes — ver "Interfaces centrais" do plano) e o leitor OOXML
STATEFUL de citações: :func:`read_docx_citations_with_state` (I2b).

É o sibling STATEFUL de
:func:`prumo_assist.domains.write.export._read_docx_citations` (MÉTODO
I2, sem estado — usado no export para montar o citemap). Aqui a leitura
anda por `word/document.xml` com ElementTree (não regex) porque
precisamos dos ancestrais `w:ins`/`w:del` de cada run do campo para
classificar o estado da citação no docx que VOLTA do coautor — algo que
o leitor stateless nunca precisou saber.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from xml.etree import ElementTree as ET

from prumo_assist.domains.write.export import _parse_csl_payload

# Mesmo padrão de comments.py (W_NS + iteração ET sobre word/document.xml).
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

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
