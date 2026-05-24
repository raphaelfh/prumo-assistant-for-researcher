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

import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path

import yaml

from prumo_assist.core.csl import list_zotero_styles, resolve_csl
from prumo_assist.core.obsidian import normalize_markdown, split_frontmatter

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
_CITEKEY_RE = re.compile(r"(?<![@\w])@([A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*)")


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
        "`zotero: {library: \"<Nome do Grupo>\"}` no frontmatter da página "
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
    body_norm = normalize_markdown(body, page_dir=page.parent)

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
        subprocess.run(cmd, check=True, text=True)
        if to == "docx":
            _assert_bibliography_present(out)

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
        subprocess.run(cmd, check=True, text=True)
        if to == "docx":
            _assert_bibliography_present(out)

        if to == "pdf":
            typst_bin = _check_typst()
            subprocess.run([typst_bin, "compile", str(target), str(out)], check=True)

    return out


def list_styles() -> list[str]:
    """Reexporta ``list_zotero_styles`` pra API externa."""
    return list_zotero_styles()
