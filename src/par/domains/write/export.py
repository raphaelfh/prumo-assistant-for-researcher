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
  Refresh. Usa o Better BibTeX, se estiver aberto, para vincular as
  citações à biblioteca: o lookup é melhor-esforço (2 s); sem vínculo,
  cada citação sai com ``uris`` vazio e ``itemData`` embutido, e
  :func:`docx_link_warning` avisa com o comando de refazer (ADR-0037).
- ``html`` / ``typst`` / ``pdf`` — usam ``--citeproc`` com CSL local
  (texto renderizado, não editável por nenhum plugin externo).
"""

from __future__ import annotations

import hashlib
import html
import http.client
import json
import logging
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from par.core import pj_layout
from par.core.citations import iter_marked_citation_spans, scan_citekeys
from par.core.config import load_project_config
from par.core.csl import list_zotero_styles, resolve_csl
from par.core.deps import bbt_rpc_url, in_claude_sandbox, pandoc_path, zotero_base
from par.core.markdown import (
    SpanFragment,
    normalize_markdown,
    normalize_markdown_with_map,
    split_frontmatter,
)
from par.core.provenance import build_meta, hash_input
from par.domains.write.errors import WriteError
from par.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    SpanFragmentModel,
    SpanMapFile,
)

logger = logging.getLogger(__name__)

EXT_BY_FORMAT = {"docx": "docx", "typst": "typ", "pdf": "pdf", "html": "html"}


class ToolNotFoundError(FileNotFoundError):
    """Pandoc/Typst não encontrados no PATH."""


class PandocFailedError(WriteError):
    """Pandoc terminou com exit ≠ 0 — stderr embutido na mensagem."""


class MissingResourceError(WriteError):
    """Pandoc não encontrou um recurso referenciado (imagem, tabela incluída).

    O pandoc sai com exit 0 e só avisa no stderr (``[WARNING] Could not
    fetch resource ...``) — sem isso, o docx/html/typst sai sem a figura,
    sem avisar o usuário (achado medido com pandoc 3.9.0.2). Ver
    :func:`_assert_no_missing_resource`.
    """


class ZoteroCitekeyNotFoundError(WriteError):
    """O citeproc não encontrou uma ou mais citekeys na biblioteca ativa."""


class MissingBibliographyPlaceholderError(WriteError):
    """Docx tem citações vivas mas nenhum placeholder ``::: {#refs} :::``."""


class MissingZoteroPrefsError(WriteError):
    """Docx com citações vivas mas sem ZOTERO_PREF em ``docProps/custom.xml``."""


class MissingFieldLockError(WriteError):
    """Docx com citações vivas mas sem content control travado (``sdtContentLocked``)."""


class CiteMapMismatchError(WriteError):
    """Pareamento citação↔ocorrência (I2/I8) falhou.

    Dois motivos possíveis: (1) a contagem de campos ``ZOTERO_ITEM`` no docx
    diverge da contagem de grupos de citação ``[@...]`` no texto normalizado;
    (2) um campo Zotero carrega JSON inválido em ``word/document.xml``.
    """


class OutputExistsError(WriteError):
    """``out`` já existe e ``force`` não foi passado.

    Descende de ``WriteError`` (não do ``FileExistsError`` builtin, que não
    é ``PrumoError`` e vazaria como traceback cru através de ``cli_run`` —
    achado da própria Task 8) para que a fachada capture e mostre mensagem
    pt-BR limpa. Guarda compartilhada por :func:`export` e :func:`compose`:
    evita sobrescrever em silêncio um export anterior — em particular o
    docx que pode ter voltado do coautor com revisões (ver
    ``review.ingest``).
    """


def _project_language(project_root: Path) -> str:
    """Idioma de escrita do projeto (``writing.language`` do ``prumo.toml``)."""
    return str(load_project_config(project_root)["writing"]["language"])


def _check_pandoc() -> str:
    """pandoc do PATH ou o do Zettlr.app (:func:`par.core.deps.pandoc_path`).

    O export **não** checa a versão: o piso 3.8.2 é avisado pelo ``prumo doctor``
    (ADR-0037).
    """
    pandoc = pandoc_path()
    if not pandoc:
        raise ToolNotFoundError(
            "pandoc não encontrado (nem no PATH nem dentro do Zettlr.app). Instale o pandoc "
            "3.8.2 ou mais novo (macOS: `brew install pandoc`; Linux: pacote oficial em "
            "https://github.com/jgm/pandoc/releases) e confira com: prumo doctor"
        )
    return pandoc


def _check_typst() -> str:
    typst = shutil.which("typst")
    if not typst:
        raise ToolNotFoundError(
            "typst não encontrado no PATH. Instale: `brew install typst` (macOS)."
        )
    return typst


def _zotero_live_docx_filter() -> Path:
    """Filtro novo: embrulha cites já renderizadas por --citeproc em
    campos Zotero do Word, com display formatado + ZOTERO_PREF_1/2."""
    ref = resources.files("par._filters").joinpath("zotero_live_docx.lua")
    with resources.as_file(ref) as p:
        return Path(p)


def _crossref_filter() -> Path:
    """Filtro que numera figuras/tabelas e resolve ``@fig:x``/``@tbl:x`` (ADR-0035)."""
    ref = resources.files("par._filters").joinpath("crossref.lua")
    return Path(str(ref))


@dataclass(frozen=True)
class BbtLookup:
    """Resultado do ``item.pandoc_filter`` — nunca levanta (ADR-0037)."""

    items: dict[str, dict[str, object]]  # citekey → {"itemID": int, "uri": str}, só os presentes
    failure: Literal["", "unreachable", "rpc_error"] = ""
    detail: str = ""  # mensagem do BBT (rpc_error) ou repr da falha de rede
    library: str | None = None  # biblioteca consultada; None = My Library
    duplicates: tuple[str, ...] = ()  # citekeys com mais de um item no Zotero (errors[k] > 0)


_UNEXPECTED_RPC_DETAIL = "resposta JSON-RPC inesperada"


def fetch_bbt_zotero_metadata(
    citekeys: list[str], library: str | None, *, timeout: float = 2.0
) -> BbtLookup:
    """Consulta o BBT JSON-RPC para mapear citekey → {itemID, uri}.

    Usa ``item.pandoc_filter`` com ``asCSL=true`` em :func:`par.core.deps.bbt_rpc_url`.
    Melhor-esforço, nunca levanta (ADR-0037): a falha volta em
    :attr:`BbtLookup.failure` — ``"unreachable"`` (rede, timeout, HTTP 404 do
    Zotero sem o BBT) ou ``"rpc_error"`` (outro HTTP, ``error`` no corpo
    JSON-RPC, corpo fora do contrato). Chaves não achadas não aparecem em
    :attr:`BbtLookup.items` e saem sem vínculo (``uris`` vazio no docx).
    """
    lib = str(library) if library else None
    if not citekeys:
        return BbtLookup({}, library=lib)
    params: list[object] = [citekeys, True]
    if library:
        params.append(library)  # sem biblioteca o BBT usa a My Library; "" faz o BBT recusar
    payload = {"jsonrpc": "2.0", "method": "item.pandoc_filter", "params": params}
    try:
        # O Request entra no try: base malformada (``PRUMO_ZOTERO_BASE``) levanta ValueError aqui.
        req = urllib.request.Request(
            bbt_rpc_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        failure: Literal["unreachable", "rpc_error"] = (
            "unreachable" if exc.code == 404 else "rpc_error"
        )
        return BbtLookup({}, failure=failure, detail=f"HTTP {exc.code}", library=lib)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return BbtLookup({}, failure="unreachable", detail=repr(exc), library=lib)
    try:
        body = json.loads(raw)
    except ValueError:  # algo respondeu, mas não JSON (vazio, HTML, truncado)
        return BbtLookup({}, failure="rpc_error", detail=_UNEXPECTED_RPC_DETAIL, library=lib)

    if not isinstance(body, dict):
        return BbtLookup({}, failure="rpc_error", detail=_UNEXPECTED_RPC_DETAIL, library=lib)
    error = body.get("error")
    if error is not None:
        message = error.get("message") if isinstance(error, dict) else None
        detail = str(message) if message else str(error)
        return BbtLookup({}, failure="rpc_error", detail=detail, library=lib)
    result = body.get("result")
    items = result.get("items") if isinstance(result, dict) else None
    if not isinstance(result, dict) or not isinstance(items, dict):
        return BbtLookup({}, failure="rpc_error", detail=_UNEXPECTED_RPC_DETAIL, library=lib)
    # ``errors[citekey]``: 0 = não achada, n > 0 = citekey duplicada (filtro oficial do BBT).
    errors = result.get("errors")
    duplicates = tuple(
        str(key)
        for key, count in (errors.items() if isinstance(errors, dict) else ())
        if isinstance(count, int) and not isinstance(count, bool) and count > 0
    )
    out: dict[str, dict[str, object]] = {}
    for key, data in items.items():
        custom = data.get("custom") if isinstance(data, dict) else None
        if not isinstance(custom, dict):
            continue  # null do BBT (chave não achada) ou item fora do contrato
        # Só campos bem tipados: um ``null`` no lookup viraria ``"uris":[null]`` no docx.
        entry: dict[str, object] = {}
        item_id = custom.get("itemID")
        if isinstance(item_id, int) and not isinstance(item_id, bool):
            entry["itemID"] = item_id
        uri = custom.get("uri")
        if isinstance(uri, str) and uri:
            entry["uri"] = uri
        if entry:
            out[str(key)] = entry
    return BbtLookup(out, library=lib, duplicates=duplicates)


_DOI_FIELD_RE = re.compile(r"doi\s*=\s*[{\"]([^}\"]+)", re.I)


def _bib_entries_by_key(bib_text: str) -> dict[str, str]:
    """Bloco cru do ``.bib`` por citekey, num único split por ``@``.

    Não é um parser BibTeX completo — a chave é o trecho entre o primeiro
    ``{`` e a primeira ``,`` do header (``@article{key,``), primeira
    ocorrência vence. Serve só de material para o fingerprint: extrair o
    campo ``doi`` quando presente e, no fallback offline, hashear o entry
    inteiro.
    """
    entries: dict[str, str] = {}
    for chunk in bib_text.split("@")[1:]:
        header = chunk.split("\n", 1)[0]
        brace = header.find("{")
        comma = header.find(",", brace)
        if brace == -1 or comma == -1:
            continue
        key = header[brace + 1 : comma]
        if key and key not in entries:
            entries[key] = "@" + chunk
    return entries


def _fingerprint_for(bib_entry_raw: str | None, lookup: dict[str, object] | None) -> str:
    """Impressão digital estável de uma referência para o campo do Word.

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


def _write_zotero_lookup(
    td_path: Path, meta: dict[str, Any], text: str, bib: Path
) -> tuple[Path | None, BbtLookup]:
    """Resolve citekeys→{itemID, uri, fingerprint} via BBT e grava o lookup file.

    Bloco único compartilhado por :func:`export` e :func:`compose` (era
    duplicado byte a byte): extrai a library do frontmatter, consulta o BBT
    (:func:`fetch_bbt_zotero_metadata`, melhor-esforço) e anexa o fingerprint
    de cada entry (``.bib`` splitado UMA vez) num dict novo, sem mutar o
    lookup. Retorna ``(zotero_lookup.json em td_path, lookup)``; o caminho é
    ``None`` quando o BBT não devolveu nenhum item (o filtro Lua emite cada
    citação com ``uris`` vazio). O ``lookup`` segue para
    :func:`docx_link_warning`, que lê dele a causa da falha.
    """
    library = (meta.get("zotero") or {}).get("library") if isinstance(meta, dict) else None
    lookup = fetch_bbt_zotero_metadata(scan_citekeys(text), library)
    if not lookup.items:
        return None, lookup
    entries_raw = _bib_entries_by_key(bib.read_text())
    enriched = {
        key: {**entry, "fingerprint": _fingerprint_for(entries_raw.get(key), entry)}
        for key, entry in lookup.items.items()
    }
    lookup_file = td_path / "zotero_lookup.json"
    lookup_file.write_text(json.dumps(enriched))
    return lookup_file, lookup


_CITEPROC_MISSING_RE = re.compile(r"\[WARNING\] Citeproc: citation (\S+) not found")


def _assert_no_citeproc_missing(stderr: str) -> None:
    """Promove o warning do citeproc (citekey ausente do ``.bib``) a erro.

    O pandoc sai com exit 0 deixando a citação como ``(key?, ...)`` no
    docx — inaceitável num artefato de entrega (spec 2026-07-22).
    """
    missing = sorted(set(_CITEPROC_MISSING_RE.findall(stderr)))
    if missing:
        raise ZoteroCitekeyNotFoundError(
            f"{len(missing)} citekey(s) não existem no .bib: "
            + ", ".join(missing)
            + ". Confira a grafia da citekey; se o paper é novo, adicione-o à coleção "
            "conectada no Zotero — o Better BibTeX regrava o .bib automaticamente "
            "(`prumo paper connect` liga a coleção, se ainda não ligou)."
        )


_MISSING_RESOURCE_RE = re.compile(r"Could not fetch resource ([^\s:]+)")


def _assert_no_missing_resource(stderr: str) -> None:
    """Promove o warning do pandoc (recurso não encontrado, ex. figura) a erro.

    Mesmo padrão de :func:`_assert_no_citeproc_missing`: o pandoc sai com
    exit 0 e só avisa no stderr — sem isso, ``![](figures/x.png)`` some do
    docx/html/typst em silêncio quando o markdown normalizado é gravado num
    diretório diferente do da página (ex. o tempdir de :func:`export`).
    """
    faltando = _MISSING_RESOURCE_RE.findall(stderr)
    if faltando:
        alvos = ", ".join(sorted(set(faltando)))
        raise MissingResourceError(
            f"Recurso não encontrado no export: {alvos}. "
            "Confira o caminho relativo à página (ex.: `figures/x.png` ao lado do .md)."
        )


def _docx_texts(docx_path: Path) -> tuple[str, str]:
    """``word/document.xml`` e ``docProps/custom.xml`` decodificados, zip aberto UMA vez.

    ``custom.xml`` ausente vira ``""`` — as guardas pós-build tratam ausência
    e conteúdo-sem-pref do mesmo jeito.
    """
    with zipfile.ZipFile(docx_path) as z:
        document_xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        try:
            custom_xml = z.read("docProps/custom.xml").decode("utf-8", errors="replace")
        except KeyError:
            custom_xml = ""
    return document_xml, custom_xml


def _docx_zotero_field_counts(docx_path: Path) -> tuple[int, int]:
    """Conta ocorrências de ``ZOTERO_ITEM`` e ``ZOTERO_BIBL`` em ``word/document.xml``.

    Conveniência por caminho sobre :func:`_docx_texts` — as guardas pós-build
    contam direto nas strings (uma leitura do zip para a cadeia inteira).
    """
    xml = _docx_texts(docx_path)[0]
    return xml.count("ZOTERO_ITEM"), xml.count("ZOTERO_BIBL")


class CorruptDocxError(WriteError):
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


def _run_pandoc_checked(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Roda o pandoc capturando stderr; exit ≠ 0 vira erro acionável.

    O stderr capturado alimenta ``_assert_no_citeproc_missing`` no caminho
    docx (o pandoc sai com exit 0 em citekey ausente — só avisa no stderr).
    Também roda :func:`_assert_no_missing_resource` aqui — vale pra TODOS os
    formatos (docx/html/typst/pdf), não só docx, porque um recurso ausente
    (figura) é silencioso do mesmo jeito em qualquer um deles.
    """
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise PandocFailedError(
            f"pandoc falhou (exit {proc.returncode}):\n{proc.stderr.strip()[-2000:]}"
        )
    _assert_no_missing_resource(proc.stderr)
    return proc


def _run_and_validate_docx(cmd: list[str], out: Path) -> subprocess.CompletedProcess[str]:
    """Roda o pandoc para docx garantindo saída estruturalmente válida.

    Defeito documentado do pipeline (docs do BBT): o Word ocasionalmente
    acusa o docx como corrompido e re-executar o mesmo comando conserta.
    Automatiza exatamente isso — valida, re-executa UMA vez, e falha alto
    se persistir. Nunca entrega arquivo suspeito silenciosamente. Retorna
    o ``CompletedProcess`` da execução final (stderr alimenta a checagem
    de citekeys ausentes do citeproc).
    """
    proc = _run_pandoc_checked(cmd)
    problems = _validate_docx_structure(out)
    if not problems:
        return proc
    logger.warning(
        "docx falhou na validação estrutural (%s); re-executando o pandoc",
        "; ".join(problems),
    )
    proc = _run_pandoc_checked(cmd)
    problems = _validate_docx_structure(out)
    if problems:
        raise CorruptDocxError(
            "O docx gerado continua estruturalmente inválido mesmo após "
            f"re-executar o pandoc: {'; '.join(problems)}. Arquivo: {out}. "
            "Rode novamente `prumo write export --to docx`; se persistir, abra "
            "uma issue com o markdown de entrada: "
            "https://github.com/raphaelfh/prumo-assistant-for-researcher/issues"
        )
    return proc


def _assert_bibliography_present(document_xml: str) -> None:
    items = document_xml.count("ZOTERO_ITEM")
    bibl = document_xml.count("ZOTERO_BIBL")
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


def _assert_zotero_prefs_present(document_xml: str, custom_xml: str) -> None:
    """Guarda de regressão do ``zotero_live_docx.lua``.

    O filtro embute ``ZOTERO_PREF_1``/``ZOTERO_PREF_2`` para o plugin Word
    reconhecer o documento sem abrir o diálogo "Document Preferences" no
    primeiro Refresh. Se as prefs sumirem (regressão no filtro), o coautor
    Word-cêntrico é exatamente quem paga o pato — falha alto aqui.
    """
    items = document_xml.count("ZOTERO_ITEM")
    if items == 0:
        return
    if "ZOTERO_PREF_1" not in custom_xml:
        raise MissingZoteroPrefsError(
            f"O docx tem {items} citação(ões) vivas mas docProps/custom.xml não "
            "carrega ZOTERO_PREF_1 — regressão do filtro zotero_live_docx.lua "
            "(sem as prefs, o plugin Word abre o diálogo 'Document Preferences' "
            "no primeiro Refresh). Re-exporte com `prumo write export --to docx`; "
            "se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assistant-for-researcher/issues"
        )


def _assert_fields_locked(document_xml: str) -> None:
    """Guarda de regressão do content control travado (I4).

    O filtro ``zotero_live_docx.lua`` embrulha cada campo ``ZOTERO_ITEM`` num
    content control (``w:sdt``) com ``w:lock w:val="sdtContentLocked"`` para
    que o coautor não redigite a citação — só pode deletar o campo inteiro
    (evento drop limpo) ou comentar. Se a contagem de locks em
    ``word/document.xml`` ficar abaixo da contagem de campos, é regressão do
    filtro — falha alto aqui.
    """
    items = document_xml.count("ZOTERO_ITEM")
    if items == 0:
        return
    locks = document_xml.count("sdtContentLocked")
    if locks < items:
        raise MissingFieldLockError(
            f"O docx tem {items} citação(ões) vivas mas só {locks} campo(s) "
            "travado(s) (sdtContentLocked) em word/document.xml — regressão "
            "do filtro zotero_live_docx.lua (I4). Re-exporte com "
            "`prumo write export --to docx`; se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assistant-for-researcher/issues"
        )


def _finalize_docx(cmd: list[str], out: Path, *, locked: bool = True) -> None:
    """Roda o pandoc para docx e aplica a cadeia completa de guardas pós-build.

    Cadeia única compartilhada por :func:`export` e :func:`compose` (era
    duplicada nos dois): validação estrutural com retry, citekey ausente do
    citeproc, e as três guardas de regressão do filtro (bibliografia, prefs,
    locks) — com o zip lido UMA vez via :func:`_docx_texts`.
    """
    proc = _run_and_validate_docx(cmd, out)
    _assert_no_citeproc_missing(proc.stderr)
    document_xml, custom_xml = _docx_texts(out)
    _assert_bibliography_present(document_xml)
    _assert_zotero_prefs_present(document_xml, custom_xml)
    if locked:
        _assert_fields_locked(document_xml)


_INSTR_TEXT_RE = re.compile(r"<w:instrText[^>]*>(.*?)</w:instrText>", re.DOTALL)
_ZOTERO_ITEM_CSL_MARKER = "ADDIN ZOTERO_ITEM CSL_CITATION"


def _parse_csl_payload(
    decoded_instr: str, field_index: int, *, error_cls: type[WriteError]
) -> dict[str, object]:
    """Isola e decodifica o JSON ``CSL_CITATION`` de um instrText já decodificado.

    Ponto único da lógica compartilhada entre os dois leitores de citação do
    docx (achado do review da ponte Fase 2/Task 1 — Finding 2): ``decoded_instr``
    chega aqui no estágio final de decode do CHAMADOR — ``_read_docx_citations``
    aplica ``html.unescape`` sobre o XML cru ANTES de chamar; o leitor stateful
    (``review._citation_from_frame``) não aplica nada, porque seu texto já veio
    do ElementTree, que resolve as entidades XML uma única vez ao montar a
    árvore (aplicar ``html.unescape`` de novo sobre texto já resolvido
    reinterpreta entidades HTML5 sem `;` — ex.: ``&amp;para=`` vira ``&para=``
    corretamente uma vez, mas ``&para=`` de novo vira ``¶=``). Este helper só
    faz o slice (a partir do marcador ``ADDIN ZOTERO_ITEM CSL_CITATION``) +
    ``json.loads`` — nunca unescape; cada leitor mantém o SEU estágio correto.

    ``field_index`` é 1-based, contando só os campos Zotero encontrados (não
    todo ``fldChar``), na ordem do documento — usado na mensagem de erro.
    ``error_cls`` deixa cada leitor levantar sua própria exceção
    (:class:`CiteMapMismatchError` aqui, ``CitationConservationError`` no
    leitor stateful) com o mesmo texto.
    """
    json_text = decoded_instr.split(_ZOTERO_ITEM_CSL_MARKER, 1)[1].strip()
    try:
        return cast(dict[str, object], json.loads(json_text))
    except json.JSONDecodeError as exc:
        raise error_cls(
            f"Campo Zotero #{field_index} do docx tem JSON inválido em "
            f"word/document.xml: {exc}. Re-exporte com "
            "`prumo write export --to docx`; se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assistant-for-researcher/issues"
        ) from exc


def _read_docx_citations(docx_path: Path) -> list[dict[str, object]]:
    """Lê as citações vivas do docx a partir do OOXML cru — MÉTODO I2.

    Única fonte de verdade para conservação de citações (NUNCA lê da saída
    do pandoc ou do lookup file). Varre ``word/document.xml`` por campos
    ``<w:instrText>`` que carregam ``ADDIN ZOTERO_ITEM CSL_CITATION``
    (emitidos por ``zotero_live_docx.lua``), desfaz o escaping XML
    (``html.unescape`` — cobre ``&quot;``/``&amp;``/``&lt;``/``&gt;``) e
    decodifica o JSON CSL_CITATION de cada um via :func:`_parse_csl_payload`
    (compartilhado com o leitor stateful de ``review.py``, que reaproveita o
    slice+``json.loads`` mas pula este ``html.unescape`` — seu texto já vem
    resolvido pelo ElementTree). Retorna, NA ORDEM DO DOCUMENTO, um dict por
    ocorrência com ``occ_id``, ``citation_id``, ``citekeys``, ``fingerprints``
    (citekey → fingerprint), ``formatted`` e ``unlinked`` (as citekeys cujo
    item saiu com ``uris`` ausente ou vazio, isto é, sem vínculo com a
    biblioteca do Zotero — lido por :func:`docx_link_warning`).

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
        decoded_instr = html.unescape(raw)
        payload = cast(
            dict[str, Any],
            _parse_csl_payload(decoded_instr, field_index, error_cls=CiteMapMismatchError),
        )
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
                "unlinked": [item["id"] for item in citation_items if not _has_uri(item)],
            }
        )
    return occurrences


def _has_uri(item: dict[str, Any]) -> bool:
    """``True`` quando ``uris`` traz ao menos uma string não vazia (``[null]`` não vincula)."""
    uris = item.get("uris")
    return isinstance(uris, list) and any(isinstance(u, str) and u for u in uris)


_LINK_UNREACHABLE_MSG = (
    "Não consegui falar com o Better BibTeX (Zotero fechado, sem o Better BibTeX, ainda "
    "iniciando ou sem resposta em 2 s): {n} citekey(s) saíram sem vínculo com a sua "
    "biblioteca. O docx abre, e o Refresh do Word funciona com os dados embutidos. Para "
    "vincular, abra o Zotero e rode: {redo}"
)
_LINK_SANDBOX_MSG = (
    "O sandbox do Claude Code não deixou o export falar com o Zotero em {base}: {n} "
    "citekey(s) saíram sem vínculo com a sua biblioteca (o docx abre e o Refresh funciona). "
    "Para vincular, peça para repetir fora do sandbox (o Claude pede permissão): {redo}. "
    'Para o `prumo` rodar sempre fora do sandbox, acrescente `"prumo *"` em '
    "`sandbox.excludedCommands` no `~/.claude/settings.json`."
)
_LINK_RPC_ERROR_MSG = (
    "O Better BibTeX recusou a consulta ({detail}): {n} citekey(s) saíram sem vínculo com "
    "a sua biblioteca. Causas comuns: `zotero.library` no frontmatter com um nome que não "
    "existe no Zotero, ou Better BibTeX anterior a 9.0.65 com a janela principal do Zotero "
    "fechada. Corrija (Tools → Plugins atualiza o Better BibTeX; abra a janela do Zotero) "
    "e rode: {redo}"
)
_LINK_NOT_FOUND_MSG = (
    "{n} citekey(s) não foram achadas pelo Better BibTeX na biblioteca consultada "
    "({library}): {keys}. Saem sem vínculo. Se estão numa biblioteca de grupo, ponha "
    '`zotero: {{library: "<nome do grupo>"}}` no frontmatter e rode: {redo}'
)
_LINK_DUPLICATE_MSG = (
    "{n} citekey(s) estão duplicadas no Zotero (mais de um item com a mesma chave): {keys}. "
    "O Better BibTeX não sabe qual vincular, e elas saem sem vínculo. Deixe cada chave única "
    "(no Zotero, Better BibTeX → Refresh/Pin BibTeX key) e rode: {redo}"
)


def docx_link_warning(docx_path: Path, lookup: BbtLookup, redo_command: str) -> str | None:
    """Uma mensagem pt-BR por causa, para as citekeys que saíram com ``uris`` vazio no OOXML;
    ``None`` quando todas têm vínculo.

    A lista vem do próprio docx (:func:`_read_docx_citations`), não do texto:
    ``scan_citekeys`` admite falso positivo, que viraria uma citekey "não
    achada" inexistente no docx (B1). ``{n}`` conta citekeys distintas, na
    ordem da primeira aparição. A causa vem de ``lookup.failure``:
    ``"unreachable"`` dá E1 (ou E2, dentro do sandbox do Claude Code),
    ``"rpc_error"`` dá E3 e ``""`` dá E4 (o BBT respondeu sem algumas
    chaves); as chaves em ``lookup.duplicates`` saem do E4 e ganham frase
    própria, numa segunda linha. Toda mensagem termina no ``redo_command``
    (ADR-0037).
    """
    keys = list(
        dict.fromkeys(
            key
            for occurrence in _read_docx_citations(docx_path)
            for key in cast(list[str], occurrence["unlinked"])
        )
    )
    if not keys:
        return None
    n = len(keys)
    if lookup.failure == "unreachable":
        if in_claude_sandbox():
            return _LINK_SANDBOX_MSG.format(base=zotero_base(), n=n, redo=redo_command)
        return _LINK_UNREACHABLE_MSG.format(n=n, redo=redo_command)
    if lookup.failure == "rpc_error":
        return _LINK_RPC_ERROR_MSG.format(detail=lookup.detail, n=n, redo=redo_command)
    duplicated = [key for key in keys if key in lookup.duplicates]
    not_found = [key for key in keys if key not in lookup.duplicates]
    messages: list[str] = []
    if not_found:
        messages.append(
            _LINK_NOT_FOUND_MSG.format(
                n=len(not_found),
                library=lookup.library or "My Library, a padrão",
                keys=_first_keys(not_found),
                redo=redo_command,
            )
        )
    if duplicated:
        messages.append(
            _LINK_DUPLICATE_MSG.format(
                n=len(duplicated), keys=_first_keys(duplicated), redo=redo_command
            )
        )
    return "\n".join(messages)


def _first_keys(keys: list[str]) -> str:
    """Até 5 chaves, depois ``…`` (E4)."""
    return ", ".join(keys[:5]) + (", …" if len(keys) > 5 else "")


def _redo_command(
    subcommand: Literal["export", "compose"],
    target: Path,
    *,
    style: str | None = None,
    bib: Path | None = None,
    out_dir: Path | None = None,
    reference_doc: Path | None = None,
    final: bool = False,
) -> str:
    """Comando ``prumo`` que refaz o docx com as mesmas opções da chamada (``{redo}``, B1).

    ``prumo write export {page}`` ou ``prumo write compose --index {index}``,
    depois ``--to docx --force`` e, nessa ordem, ``--style``, ``--bib``,
    ``--out-dir`` e ``--reference-doc`` para cada um que veio (``None`` fica
    de fora), com ``shlex.quote``. Um redo com os defaults reescreveria, com
    ``--force``, outro documento. ``out`` não entra: não tem flag na CLI.
    """
    q = shlex.quote
    if subcommand == "export":
        parts = ["prumo write export", q(str(target))]
    else:
        parts = ["prumo write compose --index", q(str(target))]
    parts.append("--to docx --force")
    if style is not None:
        parts.append(f"--style {q(style)}")
    for flag, path in (("--bib", bib), ("--out-dir", out_dir), ("--reference-doc", reference_doc)):
        if path is not None:
            parts.append(f"{flag} {q(str(path))}")
    if final:
        parts.append("--final")
    return " ".join(parts)


def _norm_citation_spans(norm_text: str) -> list[tuple[int, int]]:
    """Spans dos GRUPOS de citação ``[@a]``/``[@a; @b]`` em ``norm_text``, em ordem.

    Delegado à gramática única de ``core/citations``
    (:func:`iter_marked_citation_spans` — invariante I7): um span por bloco
    ``[...]`` contendo ao menos um citekey, casando 1:1 com um campo Zotero
    do docx.

    LIMITAÇÃO conhecida: citação narrativa ``@key`` fora de colchetes não é
    contada (o pipeline docx do prumo usa exclusivamente a forma com
    colchetes — ver report da Task 7 do plano da ponte). Também não filtra
    spans dentro de código (fence/inline) — quem faz isso é o call site
    (:func:`_emit_review_sidecars`), via os fragments ``kind="code"`` do
    span-map.
    """
    return list(iter_marked_citation_spans(norm_text))


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
    code_ranges = [(f.norm_start, f.norm_end) for f in span_frags if f.kind == "code"]
    spans = [
        span
        for span in _norm_citation_spans(norm_text)
        if not any(s <= span[0] < e for s, e in code_ranges)
    ]
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
    citemap.meta = build_meta(
        schema="CiteMapFile/v1", skill="write/export", input_hash=hash_input(norm_text)
    ).to_dict()
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

    out_dir = project_root / "reviews" / slugify(page, project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "citemap.json").write_text(citemap.model_dump_json(indent=2, by_alias=True))
    (out_dir / "span-map.json").write_text(span_map.model_dump_json(indent=2))
    return out_dir


def slugify(path: Path, project_root: Path) -> str:
    """``docs/studies/principal/notes/foo.md`` → ``studies__principal__notes__foo``."""
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
    resource_path: Path | str | None = None,
    lang: str | None = None,
    lock_citations: bool = True,
) -> list[str]:
    """Monta o comando do pandoc.

    Para ``docx`` o pipeline é ``--citeproc`` (para pré-renderizar o texto
    formatado das citações e a bibliografia) + ``zotero_live_docx.lua`` que
    embrulha cada Cite/Div#refs em campo do Word reconhecido pelo plugin
    Zotero, com o display já formatado. Para os demais formatos usa
    apenas ``--citeproc``.

    ``resource_path``, quando dado, vira ``--resource-path`` — necessário
    porque ``input_md`` é o markdown normalizado gravado num diretório
    TEMPORÁRIO (nunca o diretório da página): sem isso, ``![](figures/x.png)``
    resolve relativo ao tempdir, nunca encontra o arquivo, e o pandoc some
    com a figura em silêncio (exit 0, só um warning no stderr — achado
    medido com pandoc 3.9.0.2). Aceita um ``Path`` único (:func:`export`,
    uma página só) ou uma ``str`` já no formato do pandoc — múltiplos
    diretórios separados por ``:`` (:func:`compose`, que combina páginas de
    diretórios potencialmente diferentes).

    ``crossref.lua`` entra ANTES de ``--citeproc`` em todo formato (ADR-0035):
    ``@fig:x`` tem forma de citekey e o citeproc a daria como ausente. ``lang``
    (``[writing].language``) vira ``prumo_lang`` só para o rótulo — nunca
    ``lang``, que trocaria o locale do CSL.
    """
    cmd = [
        pandoc_bin,
        str(input_md),
        "--from=markdown+yaml_metadata_block+pipe_tables+grid_tables+fenced_code_blocks",
        f"--output={output}",
        f"--lua-filter={_crossref_filter()}",
        "--citeproc",
        f"--bibliography={bib}",
        f"--csl={csl}",
    ]
    if resource_path is not None:
        cmd += ["--resource-path", str(resource_path)]
    if lang:
        cmd += [f"--metadata=prumo_lang:{lang}"]
    if to_format == "docx":
        cmd += [
            "--to=docx",
            "--standalone",
            f"--lua-filter={_zotero_live_docx_filter()}",
            f"--metadata=zotero_csl_style:{style}",
        ]
        if zotero_lookup_file:
            cmd += [f"--metadata=zotero_lookup_file:{zotero_lookup_file}"]
        if not lock_citations:
            cmd += ["--metadata=prumo_unlocked_citations:true"]
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
    """Delegação para ``pj_layout.find_pj_root`` — sentinela é ``.claude/pj_config.toml``.

    Nome preservado (não ``pj_layout.find_pj_root`` direto) porque
    ``review.py`` e os testes importam ``export.detect_project_root`` — trocar
    a chamada por dentro evita quebrar esses callers.
    """
    return pj_layout.find_pj_root(page)


def export(
    page: Path,
    *,
    style: str = "apa",
    to: str = "docx",
    out: Path | None = None,
    out_dir: Path | None = None,
    bib: Path | None = None,
    template: Path | None = None,
    reference_doc: Path | None = None,
    project_root: Path | None = None,
    force: bool = False,
    on_warning: Callable[[str], None] | None = None,
    final: bool = False,
) -> Path:
    """Exporta uma página `.md` para o formato escolhido. Retorna caminho do output.

    ``out`` fixa o caminho completo; ``out_dir`` troca só o diretório,
    mantendo a regra de nome default (``slugify(page)`` + extensão) — a
    regra vive AQUI, nunca recomputada pela fachada. ``force`` autoriza
    sobrescrever um ``out`` já existente (default recusa — ver a guarda
    logo abaixo).

    O docx não exige o Zotero aberto (ADR-0037): o vínculo com a biblioteca
    é melhor-esforço, e as citações que saírem sem ele viram UM aviso
    (:func:`docx_link_warning`, com o comando de refazer) entregue a
    ``on_warning`` — a fachada imprime; o padrão é ``logger.warning``.
    """
    if to not in EXT_BY_FORMAT:
        raise ValueError(f"--to deve ser um de {list(EXT_BY_FORMAT)}, recebeu {to}")
    if final and to != "docx":
        raise ValueError(
            f"--final só vale para docx (recebeu --to {to}). Rode: "
            f"prumo write export {page} --to docx --final"
        )

    # Raiz do projeto ANTES das checagens de dependência — preserva a
    # precedência de erro da fachada antiga (que resolvia a raiz antes de
    # chamar o domínio) e alinha com compose(): página fora de projeto
    # reporta "Raiz do projeto não localizada" sem sondar o pandoc.
    project_root = project_root or detect_project_root(page)

    pandoc_bin = _check_pandoc()
    if to == "pdf":
        _check_typst()
    csl = resolve_csl(style)
    bib_arg = bib
    bib = bib or pj_layout.bib_path(project_root)
    if not bib.is_file():
        raise FileNotFoundError(f"bibliografia não encontrada: {bib}")

    page_text = page.read_text()
    meta, body = split_frontmatter(page_text)
    body_norm, span_frags = normalize_markdown_with_map(body, page_dir=page.parent)

    out = out or (
        (out_dir or project_root / "build" / "exports")
        / f"{slugify(page, project_root)}.{EXT_BY_FORMAT[to]}"
    )
    if out.exists() and not force:
        raise OutputExistsError(
            f"{out} já existe. Rode `prumo write export {page} --force` para "
            "sobrescrever — atenção: se este for o docx que voltou do coautor, "
            "sobrescrever perde a revisão."
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
        lookup = BbtLookup({})
        if to == "docx":
            zotero_lookup_file, lookup = _write_zotero_lookup(td_path, meta, body_norm, bib)

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
            resource_path=page.parent,
            lang=_project_language(project_root),
            lock_citations=not final,
        )
        logger.info("pandoc cmd: %s", " ".join(cmd))
        if to == "docx":
            _finalize_docx(cmd, out, locked=not final)
            _emit_review_sidecars(
                page=page,
                project_root=project_root,
                source_text=body,
                norm_text=body_norm,
                span_frags=span_frags,
                docx_path=out,
                bib=bib,
            )
            redo = _redo_command(
                "export",
                page,
                style=None if style == "apa" else style,
                bib=bib_arg,
                out_dir=out_dir,
                reference_doc=reference_doc,
                final=final,
            )
            if aviso := docx_link_warning(out, lookup, redo):
                (on_warning or logger.warning)(aviso)
        else:
            _run_pandoc_checked(cmd)

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
    out_dir: Path | None = None,
    bib: Path | None = None,
    template: Path | None = None,
    reference_doc: Path | None = None,
    project_root: Path | None = None,
    force: bool = False,
    on_warning: Callable[[str], None] | None = None,
) -> Path:
    """Compõe várias páginas listadas no frontmatter ``pages:`` de um index.

    O frontmatter aceita: ``title``, ``author``, ``date``, ``style``, ``toc``,
    ``abstract``, ``pages: [list]``. O body do index é prepended ao conteúdo
    das páginas (serve de introdução/abstract). ``out`` fixa o caminho
    completo; ``out_dir`` troca só o diretório, mantendo a regra de nome
    default (stem do index sem ``.idx``). ``force`` autoriza sobrescrever um
    ``out`` já existente (default recusa — mesma guarda de :func:`export`).

    Figuras (``![](figures/x.png)``) resolvem via ``--resource-path`` com o
    diretório de CADA página combinada (index + toda página listada em
    ``pages:``), sem duplicatas, na ordem em que entram no ``combined`` —
    o pandoc aceita múltiplos diretórios separados por ``:`` (achado do fix
    round 3 da Task 8: sem isso, ``_assert_no_missing_resource`` compartilhado
    com :func:`export` via :func:`_run_pandoc_checked` fazia TODA figura em
    página composta falhar sempre, já que ``compose()`` nunca passava
    ``resource_path`` nenhum).

    ``on_warning`` recebe o aviso de vínculo do docx, como em :func:`export`
    (ADR-0037); o padrão é ``logger.warning``.
    """
    project_root = project_root or detect_project_root(index)
    text = index.read_text()
    meta, intro_body = split_frontmatter(text)
    pages_meta = meta.get("pages") or []
    if not pages_meta:
        raise ValueError(f"{index}: frontmatter precisa ter 'pages: [...]'")

    style_arg = style
    style = style or meta.get("style") or "apa"

    parts: list[str] = []
    resource_dirs: list[Path] = [index.parent]
    if intro_body.strip():
        parts.append(normalize_markdown(intro_body, page_dir=index.parent))
    for rel in pages_meta:
        page = (project_root / rel).resolve()
        if not page.is_file():
            raise FileNotFoundError(f"Página listada no index não existe: {page}")
        _meta_p, body = split_frontmatter(page.read_text())
        parts.append(normalize_markdown(body, page_dir=page.parent))
        if page.parent not in resource_dirs:
            resource_dirs.append(page.parent)

    combined = "\n\n".join(parts)

    out = out or (
        (out_dir or project_root / "build" / "exports")
        / f"{index.stem.removesuffix('.idx')}.{EXT_BY_FORMAT[to]}"
    )
    if out.exists() and not force:
        raise OutputExistsError(
            f"{out} já existe. Rode `prumo write compose --index {index} --force` "
            "para sobrescrever — atenção: se este for o docx que voltou do coautor, "
            "sobrescrever perde a revisão."
        )
    out.parent.mkdir(parents=True, exist_ok=True)

    pandoc_bin = _check_pandoc()
    if to == "pdf":
        _check_typst()
    csl = resolve_csl(style)
    bib_arg = bib
    bib = bib or pj_layout.bib_path(project_root)
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
        lookup = BbtLookup({})
        if to == "docx":
            zotero_lookup_file, lookup = _write_zotero_lookup(td_path, meta, combined, bib)

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
            resource_path=":".join(str(d) for d in resource_dirs),
            lang=_project_language(project_root),
        )
        if meta.get("toc"):
            cmd += ["--toc", f"--toc-depth={meta.get('toc-depth', 2)}"]
        if to == "docx":
            _finalize_docx(cmd, out)
            redo = _redo_command(
                "compose",
                index,
                style=style_arg,
                bib=bib_arg,
                out_dir=out_dir,
                reference_doc=reference_doc,
            )
            if aviso := docx_link_warning(out, lookup, redo):
                (on_warning or logger.warning)(aviso)
        else:
            _run_pandoc_checked(cmd)

        if to == "pdf":
            typst_bin = _check_typst()
            subprocess.run([typst_bin, "compile", str(target), str(out)], check=True)

    return out


def list_styles() -> list[str]:
    """Reexporta ``list_zotero_styles`` pra API externa."""
    return list_zotero_styles()
