"""Export single-page e composição multi-página via Pandoc + CSL.

Migrado de ``export_page.py``. Comportamento preservado. Mudanças:

- Imports relativos do pacote (``prumo_assist.core.csl``, ``...obsidian``).
- ``_check_pandoc`` / ``_check_typst`` levantam ``FileNotFoundError`` em vez
  de ``SystemExit`` (CLI traduz pra exit code; biblioteca não decide saída).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from prumo_assist.core.csl import list_zotero_styles, resolve_csl
from prumo_assist.core.obsidian import normalize_markdown, split_frontmatter

logger = logging.getLogger(__name__)

EXT_BY_FORMAT = {"docx": "docx", "typst": "typ", "pdf": "pdf", "html": "html"}


class ToolNotFoundError(FileNotFoundError):
    """Pandoc/Typst não encontrados no PATH."""


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
    metadata_file: Path | None,
    template: Path | None,
    reference_doc: Path | None,
    to_format: str,
) -> list[str]:
    cmd = [
        pandoc_bin,
        str(input_md),
        "--from=markdown+yaml_metadata_block+pipe_tables+grid_tables+fenced_code_blocks",
        "--citeproc",
        f"--bibliography={bib}",
        f"--csl={csl}",
        f"--output={output}",
    ]
    if to_format == "html":
        cmd += ["--to=html5", "--standalone", "--embed-resources"]
    elif to_format == "docx":
        cmd += ["--to=docx"]
        if reference_doc:
            cmd += [f"--reference-doc={reference_doc}"]
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
            metadata_file=meta_file,
            template=template,
            reference_doc=reference_doc,
            to_format=to,
        )
        logger.info("pandoc cmd: %s", " ".join(cmd))
        subprocess.run(cmd, check=True)

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
