"""Export single-page e composição multi-página via Pandoc + CSL.

Pipeline por formato:

- ``docx`` — pipeline "Word-plugin parity": roda ``--citeproc`` para
  pré-renderizar as citações em texto formatado, depois aplica
  ``zotero_live_docx.lua`` que embrulha cada citação em campo
  ``ADDIN ZOTERO_ITEM CSL_CITATION`` (com display já formatado +
  metadados CSL_JSON + URIs vindos do BBT) e o ``Div#refs`` em campo
  ``ADDIN ZOTERO_BIBL CSL_BIBLIOGRAPHY``. Também seta
  ``ZOTERO_PREF_1``/``ZOTERO_PREF_2`` em ``docProps/custom.xml``, então
  o docx abre com a bibliografia já visível e o plugin Word reconhece o
  documento sem abrir o diálogo "Document Preferences" no primeiro
  Refresh. Exige Zotero + Better BibTeX rodando em ``127.0.0.1:23119``
  para fornecer as URIs dos itens (sem URIs, Refresh ainda funciona
  via CSL JSON embedado mas "Add/Edit Citation" não relinka).
- ``html`` / ``typst`` / ``pdf`` — usam ``--citeproc`` com CSL local
  (texto renderizado, não editável por nenhum plugin externo).
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from importlib import resources
from pathlib import Path
from typing import cast

import yaml

from prumo_assist.core.csl import list_zotero_styles, resolve_csl
from prumo_assist.core.obsidian import (
    SpanFragment,
    normalize_markdown,
    normalize_markdown_with_map,
    split_frontmatter,
)
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    SpanFragmentModel,
    SpanMapFile,
)

logger = logging.getLogger(__name__)

EXT_BY_FORMAT = {"docx": "docx", "typst": "typ", "pdf": "pdf", "html": "html"}

BBT_JSONRPC_URL = "http://127.0.0.1:23119/better-bibtex/json-rpc"


class ToolNotFoundError(FileNotFoundError):
    """Pandoc/Typst não encontrados no PATH."""


class ZoteroNotRunningError(RuntimeError):
    """Zotero + Better BibTeX não acessíveis localmente."""


class ZoteroCitekeyNotFoundError(RuntimeError):
    """``zotero.lua`` não encontrou uma ou mais citekeys na biblioteca ativa."""


class MissingBibliographyPlaceholderError(RuntimeError):
    """Docx tem citações vivas mas nenhum placeholder ``::: {#refs} :::``."""


class MissingZoteroPrefsError(RuntimeError):
    """Docx com citações vivas mas sem ZOTERO_PREF em ``docProps/custom.xml``."""


class MissingFieldLockError(RuntimeError):
    """Docx com citações vivas mas sem content control travado (``sdtContentLocked``)."""


class CiteMapMismatchError(RuntimeError):
    """Pareamento citação↔ocorrência (I2/I8) falhou.

    Dois motivos possíveis: (1) a contagem de campos ``ZOTERO_ITEM`` no docx
    diverge da contagem de grupos de citação ``[@...]`` no texto normalizado;
    (2) um campo Zotero carrega JSON inválido em ``word/document.xml``.
    """


def _check_pandoc() -> str:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise ToolNotFoundError(
            "pandoc não encontrado no PATH. Instale: `brew install pandoc` (macOS)."
        )
    return pandoc


def _check_typst() -> str:
    typst = shutil.which("typst")
    if not typst:
        raise ToolNotFoundError(
            "typst não encontrado no PATH. Instale: `brew install typst` (macOS)."
        )
    return typst


def _zotero_lua_filter() -> Path:
    """Caminho absoluto do filtro ``zotero.lua`` (Better BibTeX) — pipeline legado."""
    ref = resources.files("prumo_assist._filters").joinpath("zotero.lua")
    with resources.as_file(ref) as p:
        return Path(p)


def _zotero_bibliography_docx_filter() -> Path:
    """Companheiro do ``zotero.lua`` — pipeline legado."""
    ref = resources.files("prumo_assist._filters").joinpath("zotero_bibliography_docx.lua")
    with resources.as_file(ref) as p:
        return Path(p)


def _zotero_live_docx_filter() -> Path:
    """Filtro novo: embrulha cites já renderizadas por --citeproc em
    campos Zotero do Word, com display formatado + ZOTERO_PREF_1/2."""
    ref = resources.files("prumo_assist._filters").joinpath("zotero_live_docx.lua")
    with resources.as_file(ref) as p:
        return Path(p)


# Pandoc citation keys: alphanumeric/underscore start, then internal
# `:.#$%&-+?<>~/` punctuation that must be followed by more word chars
# (so we don't grab trailing sentence punctuation like the `.` in
# `[@key].`). Negative lookbehind on `@\w` skips emails (foo@bar).
CITEKEY_BODY = r"[A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*"
_CITEKEY_RE = re.compile(r"(?<![@\w])@(" + CITEKEY_BODY + r")")


def scan_citekeys(markdown_text: str) -> list[str]:
    """Extrai citekeys ``[@key]`` / ``@key`` do markdown.

    Não tenta substituir o parser do Pandoc — só precisa achar TODAS as
    chaves para o pre-fetch no BBT. False positives (ex. nomes de
    variáveis em code blocks) só geram queries extras sem-resultado,
    não afetam a correção do export.
    """
    keys: set[str] = set()
    in_code_block = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for match in _CITEKEY_RE.finditer(line):
            keys.add(match.group(1))
    return sorted(keys)


def fetch_bbt_zotero_metadata(
    citekeys: list[str], library: str | None, *, timeout: float = 10.0
) -> dict[str, dict[str, object]]:
    """Consulta o BBT JSON-RPC para mapear citekey → {itemID, uri}.

    Usa ``item.pandoc_filter`` (a mesma API que o ``zotero.lua`` chama
    internamente) com ``asCSL=true``. Retorna apenas as chaves
    encontradas — chaves ausentes simplesmente não aparecem no dict, e
    o filtro Lua cai num fallback emitindo o campo só com CSL embedado.
    """
    if not citekeys:
        return {}
    payload = {
        "jsonrpc": "2.0",
        "method": "item.pandoc_filter",
        "params": [citekeys, True, library or ""],
    }
    req = urllib.request.Request(
        BBT_JSONRPC_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        raise ZoteroNotRunningError(
            f"BBT JSON-RPC indisponível ({BBT_JSONRPC_URL}): {exc!r}"
        ) from exc
    result = body.get("result") or {}
    items = result.get("items") or {}
    out: dict[str, dict[str, object]] = {}
    for key, data in items.items():
        custom = (data or {}).get("custom") or {}
        item_id = custom.get("itemID")
        uri = custom.get("uri")
        if item_id is None and uri is None:
            continue
        out[key] = {"itemID": item_id, "uri": uri}
    return out


_DOI_FIELD_RE = re.compile(r"doi\s*=\s*[{\"]([^}\"]+)", re.I)


def _raw_bib_entry(bib_text: str, citekey: str) -> str | None:
    """Bloco cru do ``.bib`` correspondente a ``citekey`` (ou ``None`` se ausente).

    Split simples por ``@`` — não é um parser BibTeX completo. Serve só de
    material para o fingerprint: extrair o campo ``doi`` quando presente e,
    no fallback offline, hashear o entry inteiro.
    """
    marker = "{" + citekey + ","
    for chunk in bib_text.split("@")[1:]:
        header = chunk.split("\n", 1)[0]
        if marker in header:
            return "@" + chunk
    return None


def _fingerprint_for(
    citekey: str, bib_entry_raw: str | None, lookup: dict[str, object] | None
) -> str:
    """Impressão digital estável da referência ``citekey`` para o campo do Word.

    Prioridade: ``doi:<valor>`` quando o entry cru do ``.bib`` tem campo
    ``doi``; senão ``sha256:<hex>`` de ``itemID|uri`` quando há lookup do
    BBT; senão ``bib:<sha256>`` do entry cru (fallback offline); senão
    ``"none"`` (citekey sem entry no ``.bib`` — o export já falha antes por
    outros caminhos).
    """
    if bib_entry_raw is not None:
        m = _DOI_FIELD_RE.search(bib_entry_raw)
        if m:
            return f"doi:{m.group(1)}"
    if lookup is not None:
        raw = f"{lookup.get('itemID')}|{lookup.get('uri')}"
        return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
    if bib_entry_raw is not None:
        return f"bib:{hashlib.sha256(bib_entry_raw.encode('utf-8')).hexdigest()}"
    return "none"


_MISSING_CITEKEY_RE = re.compile(
    r"^@(\S+?)(?:: not found| not in Zotero| duplicates found)$", re.MULTILINE
)
_ZOTERO_PANE_ERROR = "could not fetch Zotero items"


def _assert_no_missing_citekeys(filter_stdout: str) -> None:
    """Promove o aviso silencioso do ``zotero.lua`` a erro acionável.

    O filtro escreve em stdout quando: a citekey não existe (``: not found``),
    quando o BBT respondeu sem o item (``not in Zotero``), ou quando uma
    chamada falhou (``could not fetch Zotero items``). Em todos os casos o
    pandoc termina com exit 0 deixando o ``[@key]`` cru no docx. Aqui
    falhamos rápido com instrução clara.
    """
    if _ZOTERO_PANE_ERROR in filter_stdout:
        raise ZoteroCitekeyNotFoundError(
            "Better BibTeX não conseguiu acessar a biblioteca do Zotero "
            "(``getActiveZoteroPane is null``). Abra a JANELA PRINCIPAL do "
            "Zotero (não basta o app em background) e tente de novo. "
            "Esse erro é tipicamente disparado quando ``zotero.library`` aponta "
            "para um grupo e o painel do Zotero não está aberto."
        )
    missing = sorted(set(_MISSING_CITEKEY_RE.findall(filter_stdout)))
    if not missing:
        return
    raise ZoteroCitekeyNotFoundError(
        f"zotero.lua não encontrou {len(missing)} citekey(s) na biblioteca ativa: "
        + ", ".join(missing)
        + ". Causas comuns: (1) os itens estão num grupo do Zotero — adicione "
        '`zotero: {library: "<Nome do Grupo>"}` no frontmatter da página '
        "e abra a janela principal do Zotero antes de exportar; (2) os "
        "citekeys do .bib divergem dos do BBT — rode `make sync-paper`."
    )


def _docx_zotero_field_counts(docx_path: Path) -> tuple[int, int]:
    """Conta ocorrências de ``ZOTERO_ITEM`` e ``ZOTERO_BIBL`` em ``word/document.xml``.

    Usado pela validação pós-build para flagrar o caso em que a página tem
    citações ``[@key]`` mas esqueceu o placeholder ``::: {#refs} :::`` —
    o docx fica com campos vivos de citação porém sem campo de
    bibliografia, e o Refresh do plugin Word do Zotero não tem onde
    materializar as referências.
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    return xml.count("ZOTERO_ITEM"), xml.count("ZOTERO_BIBL")


class CorruptDocxError(RuntimeError):
    """Docx falhou na validação estrutural mesmo após um retry do pandoc."""


_REQUIRED_DOCX_PARTS = ("[Content_Types].xml", "word/document.xml")


def _validate_docx_structure(docx_path: Path) -> list[str]:
    """Valida o zip do docx gerado. Retorna lista de problemas (vazia = são).

    Cobre a classe de defeito conhecida do pipeline pandoc+filtros Zotero
    (Word acusa "conteúdo ilegível"; docs do BBT recomendam re-rodar o
    pandoc; pandoc issues #8010/#11378): zip inválido/truncado, parte
    obrigatória ausente e ``[Content_Types].xml`` malformado.
    """
    if not docx_path.is_file():
        return [f"arquivo não foi criado: {docx_path}"]
    problems: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as z:
            names = set(z.namelist())
            for required in _REQUIRED_DOCX_PARTS:
                if required not in names:
                    problems.append(f"parte obrigatória ausente no zip: {required}")
            bad_member = z.testzip()
            if bad_member is not None:
                problems.append(f"membro corrompido no zip (CRC): {bad_member}")
            if "[Content_Types].xml" in names:
                try:
                    ET.fromstring(z.read("[Content_Types].xml"))
                except ET.ParseError as exc:
                    problems.append(f"[Content_Types].xml inválido: {exc}")
    except zipfile.BadZipFile:
        return [f"arquivo não é um zip válido: {docx_path}"]
    return problems


def _run_and_validate_docx(cmd: list[str], out: Path) -> None:
    """Roda o pandoc para docx garantindo saída estruturalmente válida.

    Defeito documentado do pipeline (docs do BBT): o Word ocasionalmente
    acusa o docx como corrompido e re-executar o mesmo comando conserta.
    Automatiza exatamente isso — valida, re-executa UMA vez, e falha alto
    se persistir. Nunca entrega arquivo suspeito silenciosamente.
    """
    subprocess.run(cmd, check=True, text=True)
    problems = _validate_docx_structure(out)
    if not problems:
        return
    logger.warning(
        "docx falhou na validação estrutural (%s); re-executando o pandoc",
        "; ".join(problems),
    )
    subprocess.run(cmd, check=True, text=True)
    problems = _validate_docx_structure(out)
    if problems:
        raise CorruptDocxError(
            "O docx gerado continua estruturalmente inválido mesmo após "
            f"re-executar o pandoc: {'; '.join(problems)}. Arquivo: {out}. "
            "Rode novamente `prumo write export --to docx`; se persistir, abra "
            "uma issue com o markdown de entrada: "
            "https://github.com/raphaelfh/prumo-assist/issues"
        )


def _assert_bibliography_present(docx_path: Path) -> None:
    items, bibl = _docx_zotero_field_counts(docx_path)
    if items > 0 and bibl == 0:
        raise MissingBibliographyPlaceholderError(
            f"O docx contém {items} citação(ões) vivas do Zotero mas nenhum "
            "campo de bibliografia. Causa: a página markdown tem `[@citekey]` "
            "mas não tem o placeholder onde a lista de referências deve "
            "aparecer. Adicione:\n\n"
            "    ::: {#refs}\n"
            "    :::\n\n"
            "Sem isso, o Refresh do plugin Word do Zotero atualiza as "
            "citações inline mas não tem onde renderizar a bibliografia."
        )


def _assert_zotero_prefs_present(docx_path: Path) -> None:
    """Guarda de regressão do ``zotero_live_docx.lua``.

    O filtro embute ``ZOTERO_PREF_1``/``ZOTERO_PREF_2`` para o plugin Word
    reconhecer o documento sem abrir o diálogo "Document Preferences" no
    primeiro Refresh. Se as prefs sumirem (regressão no filtro), o coautor
    Word-cêntrico é exatamente quem paga o pato — falha alto aqui.
    """
    items, _bibl = _docx_zotero_field_counts(docx_path)
    if items == 0:
        return
    with zipfile.ZipFile(docx_path) as z:
        try:
            custom = z.read("docProps/custom.xml").decode("utf-8", errors="replace")
        except KeyError:
            custom = ""
    if "ZOTERO_PREF_1" not in custom:
        raise MissingZoteroPrefsError(
            f"O docx tem {items} citação(ões) vivas mas docProps/custom.xml não "
            "carrega ZOTERO_PREF_1 — regressão do filtro zotero_live_docx.lua "
            "(sem as prefs, o plugin Word abre o diálogo 'Document Preferences' "
            "no primeiro Refresh). Re-exporte com `prumo write export --to docx`; "
            "se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assist/issues"
        )


def _assert_fields_locked(docx_path: Path) -> None:
    """Guarda de regressão do content control travado (I4).

    O filtro ``zotero_live_docx.lua`` embrulha cada campo ``ZOTERO_ITEM`` num
    content control (``w:sdt``) com ``w:lock w:val="sdtContentLocked"`` para
    que o coautor não redigite a citação — só pode deletar o campo inteiro
    (evento drop limpo) ou comentar. Se a contagem de locks em
    ``word/document.xml`` ficar abaixo da contagem de campos, é regressão do
    filtro — falha alto aqui.
    """
    items, _bibl = _docx_zotero_field_counts(docx_path)
    if items == 0:
        return
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    locks = xml.count("sdtContentLocked")
    if locks < items:
        raise MissingFieldLockError(
            f"O docx tem {items} citação(ões) vivas mas só {locks} campo(s) "
            "travado(s) (sdtContentLocked) em word/document.xml — regressão "
            "do filtro zotero_live_docx.lua (I4). Re-exporte com "
            "`prumo write export --to docx`; se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assist/issues"
        )


_INSTR_TEXT_RE = re.compile(r"<w:instrText[^>]*>(.*?)</w:instrText>", re.DOTALL)
_ZOTERO_ITEM_CSL_MARKER = "ADDIN ZOTERO_ITEM CSL_CITATION"


def _read_docx_citations(docx_path: Path) -> list[dict[str, object]]:
    """Lê as citações vivas do docx a partir do OOXML cru — MÉTODO I2.

    Única fonte de verdade para conservação de citações (NUNCA lê da saída
    do pandoc ou do lookup file). Varre ``word/document.xml`` por campos
    ``<w:instrText>`` que carregam ``ADDIN ZOTERO_ITEM CSL_CITATION``
    (emitidos por ``zotero_live_docx.lua``), desfaz o escaping XML
    (``html.unescape`` — cobre ``&quot;``/``&amp;``/``&lt;``/``&gt;``) e
    decodifica o JSON CSL_CITATION de cada um. Retorna, NA ORDEM DO
    DOCUMENTO, um dict por ocorrência com ``occ_id``, ``citation_id``,
    ``citekeys``, ``fingerprints`` (citekey → fingerprint) e ``formatted``.

    JSON inválido num campo é hard-fail (:class:`CiteMapMismatchError`) — um
    docx com um campo Zotero corrompido não tem citemap parcial.
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")

    occurrences: list[dict[str, object]] = []
    field_index = 0
    for match in _INSTR_TEXT_RE.finditer(xml):
        raw = match.group(1)
        if _ZOTERO_ITEM_CSL_MARKER not in raw:
            continue
        field_index += 1
        json_text = html.unescape(raw.split(_ZOTERO_ITEM_CSL_MARKER, 1)[1]).strip()
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise CiteMapMismatchError(
                f"Campo Zotero #{field_index} do docx tem JSON inválido em "
                f"word/document.xml ({docx_path}): {exc}. Re-exporte com "
                "`prumo write export --to docx`; se persistir, abra uma issue: "
                "https://github.com/raphaelfh/prumo-assist/issues"
            ) from exc
        citation_items = payload.get("citationItems") or []
        occurrences.append(
            {
                "occ_id": payload.get("prumoOcc", ""),
                "citation_id": payload.get("citationID", ""),
                "citekeys": [item["id"] for item in citation_items],
                "fingerprints": {
                    item["id"]: item.get("prumoFingerprint", "") for item in citation_items
                },
                "formatted": (payload.get("properties") or {}).get("formattedCitation", ""),
            }
        )
    return occurrences


_CITATION_GROUP_RE = re.compile(r"\[[^\[\]]*\]")


def _norm_citation_spans(norm_text: str) -> list[tuple[int, int]]:
    """Spans dos GRUPOS de citação ``[@a]``/``[@a; @b]`` em ``norm_text``, em ordem.

    Um span por bloco ``[...]`` sem colchetes internos que contenha ao menos
    um citekey (``@`` + :data:`CITEKEY_BODY`) — ``[@a]`` e ``[@a; @b]`` cada
    um conta como UM span, casando 1:1 com um campo Zotero do docx.

    LIMITAÇÃO conhecida: citação narrativa ``@key`` fora de colchetes não é
    contada (o pipeline docx do prumo usa exclusivamente a forma com
    colchetes — ver report da Task 7 do plano da ponte).
    """
    return [
        match.span()
        for match in _CITATION_GROUP_RE.finditer(norm_text)
        if _CITEKEY_RE.search(match.group(0))
    ]


def _export_git_sha(project_root: Path) -> str:
    """``git rev-parse --short HEAD`` rodado em ``project_root``; ``"unknown"`` se falhar."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _emit_review_sidecars(
    *,
    page: Path,
    project_root: Path,
    norm_text: str,
    span_frags: list[SpanFragment],
    docx_path: Path,
    bib: Path,
    source_text: str = "",
) -> Path:
    """Constrói e grava ``reviews/<slug>/{citemap.json,span-map.json}``.

    Pareia as ocorrências do docx (:func:`_read_docx_citations`, MÉTODO I2)
    com os spans de citação do texto normalizado (:func:`_norm_citation_spans`)
    1:1 na ordem do documento — nunca pareamento heurístico. Contagem
    divergente é hard-fail (:class:`CiteMapMismatchError`).

    ``source_sha256`` do ``SpanMapFile`` é o hash do texto-fonte SEM
    frontmatter (``source_text``); ``docx_sha256`` do ``CiteMapFile`` amarra
    o citemap ao docx gerado (I8). Retorna o diretório ``reviews/<slug>/``
    (criado se preciso).
    """
    occurrences_raw = _read_docx_citations(docx_path)
    spans = _norm_citation_spans(norm_text)
    if len(occurrences_raw) != len(spans):
        raise CiteMapMismatchError(
            "Pareamento citação↔ocorrência falhou (I2/I8): o docx tem "
            f"{len(occurrences_raw)} campo(s) ZOTERO_ITEM em word/document.xml, "
            f"mas o texto normalizado tem {len(spans)} grupo(s) de citação "
            "`[@...]`. Causas comuns: citação narrativa `@key` fora de "
            "colchetes (não suportada nesta fase — use sempre `[@key]`), ou o "
            "docx ficou dessincronizado da página. Re-exporte com "
            "`prumo write export --to docx`."
        )

    rel_page = page.relative_to(project_root) if page.is_absolute() else page

    occurrences = [
        CiteOccurrence(
            occ_id=str(occ_raw["occ_id"]),
            citation_id=str(occ_raw["citation_id"]),
            citekeys=cast(list[str], occ_raw["citekeys"]),
            fingerprints=cast(dict[str, str], occ_raw["fingerprints"]),
            formatted=str(occ_raw["formatted"]),
            norm_start=span[0],
            norm_end=span[1],
        )
        for occ_raw, span in zip(occurrences_raw, spans, strict=True)
    ]
    citemap = CiteMapFile(
        page=str(rel_page),
        export_git_sha=_export_git_sha(project_root),
        bib_sha256=hashlib.sha256(bib.read_bytes()).hexdigest(),
        docx_sha256=hashlib.sha256(docx_path.read_bytes()).hexdigest(),
        occurrences=occurrences,
    )
    span_map = SpanMapFile(
        page=str(rel_page),
        source_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        fragments=[
            SpanFragmentModel(
                source_start=f.source_start,
                source_end=f.source_end,
                norm_start=f.norm_start,
                norm_end=f.norm_end,
                kind=f.kind,
            )
            for f in span_frags
        ],
    )

    out_dir = project_root / "reviews" / _slugify(page, project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "citemap.json").write_text(citemap.model_dump_json(indent=2))
    (out_dir / "span-map.json").write_text(span_map.model_dump_json(indent=2))
    return out_dir


def _check_bbt_running(timeout: float = 2.0) -> None:
    """Confirma que Zotero + BBT estão acessíveis em ``127.0.0.1:23119``.

    O filtro ``zotero.lua`` chama essa API durante a conversão; se ela não
    estiver no ar o pandoc falha sem mensagem útil.
    """
    try:
        urllib.request.urlopen(BBT_JSONRPC_URL, timeout=timeout).close()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        raise ZoteroNotRunningError(
            "Zotero + Better BibTeX não respondem em "
            f"{BBT_JSONRPC_URL}. Abra o Zotero (com BBT instalado) e tente de novo. "
            "Detalhe: " + repr(exc)
        ) from exc


def _slugify(path: Path, project_root: Path) -> str:
    """``docs/findings/foo.md`` → ``findings__foo``."""
    rel = path.relative_to(project_root) if path.is_absolute() else path
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "docs":
        parts = parts[1:]
    return "__".join(parts)


def _build_pandoc_cmd(
    *,
    pandoc_bin: str,
    input_md: Path,
    output: Path,
    bib: Path,
    csl: Path,
    style: str,
    metadata_file: Path | None,
    template: Path | None,
    reference_doc: Path | None,
    to_format: str,
    zotero_lookup_file: Path | None = None,
) -> list[str]:
    """Monta o comando do pandoc.

    Para ``docx`` o pipeline é ``--citeproc`` (para pré-renderizar o texto
    formatado das citações e a bibliografia) + ``zotero_live_docx.lua`` que
    embrulha cada Cite/Div#refs em campo do Word reconhecido pelo plugin
    Zotero, com o display já formatado. Para os demais formatos usa
    apenas ``--citeproc``.
    """
    cmd = [
        pandoc_bin,
        str(input_md),
        "--from=markdown+yaml_metadata_block+pipe_tables+grid_tables+fenced_code_blocks",
        f"--output={output}",
        "--citeproc",
        f"--bibliography={bib}",
        f"--csl={csl}",
    ]
    if to_format == "docx":
        cmd += [
            "--to=docx",
            "--standalone",
            f"--lua-filter={_zotero_live_docx_filter()}",
            f"--metadata=zotero_csl_style:{style}",
        ]
        if zotero_lookup_file:
            cmd += [f"--metadata=zotero_lookup_file:{zotero_lookup_file}"]
        if reference_doc:
            cmd += [f"--reference-doc={reference_doc}"]
    elif to_format == "html":
        cmd += ["--to=html5", "--standalone", "--embed-resources"]
    elif to_format in ("typst", "pdf"):
        cmd += ["--to=typst"]
        if template:
            cmd += [f"--template={template}"]
    if metadata_file:
        cmd += [f"--metadata-file={metadata_file}"]
    return cmd


def detect_project_root(page: Path) -> Path:
    """Sobe da página até achar ``references/_references.bib``."""
    cur = page.resolve().parent
    for _ in range(10):
        if (cur / "references" / "_references.bib").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise FileNotFoundError(
        f"Raiz do projeto não localizada (procurando references/_references.bib) a partir de {page}"
    )


def export(
    *,
    page: Path,
    style: str = "apa",
    to: str = "docx",
    out: Path | None = None,
    bib: Path | None = None,
    template: Path | None = None,
    reference_doc: Path | None = None,
    project_root: Path | None = None,
) -> Path:
    """Exporta uma página `.md` para o formato escolhido. Retorna caminho do output."""
    if to not in EXT_BY_FORMAT:
        raise ValueError(f"--to deve ser um de {list(EXT_BY_FORMAT)}, recebeu {to}")

    pandoc_bin = _check_pandoc()
    if to == "pdf":
        _check_typst()
    if to == "docx":
        _check_bbt_running()

    project_root = project_root or detect_project_root(page)
    csl = resolve_csl(style)
    bib = bib or (project_root / "references" / "_references.bib")
    if not bib.is_file():
        raise FileNotFoundError(f"bibliografia não encontrada: {bib}")

    page_text = page.read_text()
    meta, body = split_frontmatter(page_text)
    body_norm, span_frags = normalize_markdown_with_map(body, page_dir=page.parent)

    out = out or (
        project_root / "build" / "exports" / f"{_slugify(page, project_root)}.{EXT_BY_FORMAT[to]}"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        input_md = td_path / "input.md"
        input_md.write_text(body_norm)

        meta_file: Path | None = None
        if meta:
            meta_file = td_path / "meta.yaml"
            meta_file.write_text(yaml.safe_dump(meta, allow_unicode=True))

        zotero_lookup_file: Path | None = None
        if to == "docx":
            library = (meta.get("zotero") or {}).get("library") if isinstance(meta, dict) else None
            citekeys = scan_citekeys(body_norm)
            lookup = fetch_bbt_zotero_metadata(citekeys, library)
            if lookup:
                bib_text = bib.read_text()
                for key, entry in lookup.items():
                    entry["fingerprint"] = _fingerprint_for(
                        key, _raw_bib_entry(bib_text, key), entry
                    )
                zotero_lookup_file = td_path / "zotero_lookup.json"
                zotero_lookup_file.write_text(json.dumps(lookup))

        target = out if to != "pdf" else td_path / f"{out.stem}.typ"
        cmd = _build_pandoc_cmd(
            pandoc_bin=pandoc_bin,
            input_md=input_md,
            output=target,
            bib=bib,
            csl=csl,
            style=style,
            metadata_file=meta_file,
            template=template,
            reference_doc=reference_doc,
            to_format=to,
            zotero_lookup_file=zotero_lookup_file,
        )
        logger.info("pandoc cmd: %s", " ".join(cmd))
        if to == "docx":
            _run_and_validate_docx(cmd, out)
            _assert_bibliography_present(out)
            _assert_zotero_prefs_present(out)
            _assert_fields_locked(out)
            _emit_review_sidecars(
                page=page,
                project_root=project_root,
                source_text=body,
                norm_text=body_norm,
                span_frags=span_frags,
                docx_path=out,
                bib=bib,
            )
        else:
            subprocess.run(cmd, check=True, text=True)

        if to == "pdf":
            typst_bin = _check_typst()
            subprocess.run([typst_bin, "compile", str(target), str(out)], check=True)

    return out


def compose(
    *,
    index: Path,
    to: str = "docx",
    style: str | None = None,
    out: Path | None = None,
    bib: Path | None = None,
    template: Path | None = None,
    reference_doc: Path | None = None,
    project_root: Path | None = None,
) -> Path:
    """Compõe várias páginas listadas no frontmatter ``pages:`` de um index.

    O frontmatter aceita: ``title``, ``author``, ``date``, ``style``, ``toc``,
    ``abstract``, ``pages: [list]``. O body do index é prepended ao conteúdo
    das páginas (serve de introdução/abstract).
    """
    project_root = project_root or detect_project_root(index)
    text = index.read_text()
    meta, intro_body = split_frontmatter(text)
    pages_meta = meta.get("pages") or []
    if not pages_meta:
        raise ValueError(f"{index}: frontmatter precisa ter 'pages: [...]'")

    style = style or meta.get("style") or "apa"

    parts: list[str] = []
    if intro_body.strip():
        parts.append(normalize_markdown(intro_body, page_dir=index.parent))
    for rel in pages_meta:
        page = (project_root / rel).resolve()
        if not page.is_file():
            raise FileNotFoundError(f"Página listada no index não existe: {page}")
        _meta_p, body = split_frontmatter(page.read_text())
        parts.append(normalize_markdown(body, page_dir=page.parent))

    combined = "\n\n".join(parts)

    out = out or (
        project_root
        / "build"
        / "exports"
        / f"{index.stem.removesuffix('.idx')}.{EXT_BY_FORMAT[to]}"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    pandoc_bin = _check_pandoc()
    if to == "pdf":
        _check_typst()
    if to == "docx":
        _check_bbt_running()
    csl = resolve_csl(style)
    bib = bib or (project_root / "references" / "_references.bib")
    if not bib.is_file():
        raise FileNotFoundError(f"bibliografia não encontrada: {bib}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        input_md = td_path / "combined.md"
        input_md.write_text(combined)

        meta_export = {k: v for k, v in meta.items() if k != "pages"}
        meta_file: Path | None = None
        if meta_export:
            meta_file = td_path / "meta.yaml"
            meta_file.write_text(yaml.safe_dump(meta_export, allow_unicode=True))

        zotero_lookup_file: Path | None = None
        if to == "docx":
            library = (meta.get("zotero") or {}).get("library") if isinstance(meta, dict) else None
            citekeys = scan_citekeys(combined)
            lookup = fetch_bbt_zotero_metadata(citekeys, library)
            if lookup:
                bib_text = bib.read_text()
                for key, entry in lookup.items():
                    entry["fingerprint"] = _fingerprint_for(
                        key, _raw_bib_entry(bib_text, key), entry
                    )
                zotero_lookup_file = td_path / "zotero_lookup.json"
                zotero_lookup_file.write_text(json.dumps(lookup))

        target = out if to != "pdf" else td_path / f"{out.stem}.typ"
        cmd = _build_pandoc_cmd(
            pandoc_bin=pandoc_bin,
            input_md=input_md,
            output=target,
            bib=bib,
            csl=csl,
            style=style,
            metadata_file=meta_file,
            template=template,
            reference_doc=reference_doc,
            to_format=to,
            zotero_lookup_file=zotero_lookup_file,
        )
        if meta.get("toc"):
            cmd += ["--toc", f"--toc-depth={meta.get('toc-depth', 2)}"]
        if to == "docx":
            _run_and_validate_docx(cmd, out)
            _assert_bibliography_present(out)
            _assert_zotero_prefs_present(out)
            _assert_fields_locked(out)
        else:
            subprocess.run(cmd, check=True, text=True)

        if to == "pdf":
            typst_bin = _check_typst()
            subprocess.run([typst_bin, "compile", str(target), str(out)], check=True)

    return out


def list_styles() -> list[str]:
    """Reexporta ``list_zotero_styles`` pra API externa."""
    return list_zotero_styles()
