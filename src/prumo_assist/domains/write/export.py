"""Export single-page e composição multi-página via Pandoc + CSL.

Pipeline por formato:

- ``docx`` — usa o filtro Lua ``zotero.lua`` (Better BibTeX) e converte cada
  citação ``[@citekey]`` em um campo vivo do Word (``ADDIN ZOTERO_ITEM
  CSL_CITATION``) editável pelo plugin do Zotero. Exige Zotero + BBT
  rodando em ``127.0.0.1:23119``. NÃO usa ``--citeproc``.
- ``html`` / ``typst`` / ``pdf`` — usam ``--citeproc`` com CSL local (texto
  renderizado, não editável por nenhum plugin externo).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
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
    """Caminho absoluto do filtro ``zotero.lua`` empacotado."""
    ref = resources.files("prumo_assist._filters").joinpath("zotero.lua")
    with resources.as_file(ref) as p:
        return Path(p)


def _zotero_bibliography_docx_filter() -> Path:
    """Companheiro do ``zotero.lua`` que injeta ``ADDIN ZOTERO_BIBL`` no docx."""
    ref = resources.files("prumo_assist._filters").joinpath("zotero_bibliography_docx.lua")
    with resources.as_file(ref) as p:
        return Path(p)


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
) -> list[str]:
    """Monta o comando do pandoc.

    Para ``docx`` usa o filtro ``zotero.lua`` (citações viram campos vivos do
    Word). Para os demais formatos usa ``--citeproc`` com CSL local.
    """
    cmd = [
        pandoc_bin,
        str(input_md),
        "--from=markdown+yaml_metadata_block+pipe_tables+grid_tables+fenced_code_blocks",
        f"--output={output}",
    ]
    if to_format == "docx":
        cmd += [
            "--to=docx",
            "--standalone",
            f"--lua-filter={_zotero_lua_filter()}",
            f"--lua-filter={_zotero_bibliography_docx_filter()}",
            f"--metadata=zotero_csl_style:{style}",
        ]
        if reference_doc:
            cmd += [f"--reference-doc={reference_doc}"]
    else:
        cmd += [
            "--citeproc",
            f"--bibliography={bib}",
            f"--csl={csl}",
        ]
        if to_format == "html":
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
        )
        logger.info("pandoc cmd: %s", " ".join(cmd))
        proc = subprocess.run(cmd, check=True, capture_output=(to == "docx"), text=True)
        if to == "docx":
            _assert_no_missing_citekeys(proc.stdout or "")

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
        )
        if meta.get("toc"):
            cmd += ["--toc", f"--toc-depth={meta.get('toc-depth', 2)}"]
        subprocess.run(cmd, check=True)

        if to == "pdf":
            typst_bin = _check_typst()
            subprocess.run([typst_bin, "compile", str(target), str(out)], check=True)

    return out


def list_styles() -> list[str]:
    """Reexporta ``list_zotero_styles`` pra API externa."""
    return list_zotero_styles()
