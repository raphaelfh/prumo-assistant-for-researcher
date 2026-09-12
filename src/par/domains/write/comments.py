"""Extrai comentários + revisões (track changes) de ``.docx`` revisado.

Migrado de ``extract_comments.py``. Saída: arquivo ``.md`` com checklists
``- [ ]`` por comentário/revisão pra autor endereçar."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Comment:
    id: str
    author: str
    text: str
    anchor_text: str | None
    date: str | None


@dataclass
class Revision:
    kind: str  # "insertion" | "deletion"
    author: str | None
    text: str
    date: str | None


@dataclass
class ExtractResult:
    comments: list[Comment]
    revisions: list[Revision]


def _text_of(element: ET.Element) -> str:
    parts = [t.text or "" for t in element.iter(f"{W_NS}t")]
    return "".join(parts).strip()


def extract_from_docx(path: Path) -> ExtractResult:
    """Lê ``.docx`` e retorna comentários + revisões encontrados."""
    with zipfile.ZipFile(path) as z:
        document_xml = ET.fromstring(z.read("word/document.xml"))
        try:
            comments_xml: ET.Element | None = ET.fromstring(z.read("word/comments.xml"))
        except KeyError:
            comments_xml = None

    anchors = _extract_anchors_simple(document_xml)

    comments: list[Comment] = []
    if comments_xml is not None:
        for c in comments_xml.iter(f"{W_NS}comment"):
            cid = c.get(f"{W_NS}id") or ""
            comments.append(
                Comment(
                    id=cid,
                    author=c.get(f"{W_NS}author") or "(autor desconhecido)",
                    text=_text_of(c),
                    anchor_text=anchors.get(cid),
                    date=c.get(f"{W_NS}date"),
                )
            )

    revisions: list[Revision] = []
    for ins in document_xml.iter(f"{W_NS}ins"):
        revisions.append(
            Revision(
                kind="insertion",
                author=ins.get(f"{W_NS}author"),
                text=_text_of(ins),
                date=ins.get(f"{W_NS}date"),
            )
        )
    for de in document_xml.iter(f"{W_NS}del"):
        revisions.append(
            Revision(
                kind="deletion",
                author=de.get(f"{W_NS}author"),
                text=_text_of(de),
                date=de.get(f"{W_NS}date"),
            )
        )

    return ExtractResult(comments=comments, revisions=revisions)


def _extract_anchors_simple(doc_xml: ET.Element) -> dict[str, str]:
    """Anchors: percorre parágrafos buscando ``commentRangeStart/End`` com mesmo id."""
    anchors: dict[str, str] = {}
    for p in doc_xml.iter(f"{W_NS}p"):
        active_ids: list[str] = []
        for child in p.iter():
            tag = child.tag
            if tag == f"{W_NS}commentRangeStart":
                cid = child.get(f"{W_NS}id")
                if cid:
                    active_ids.append(cid)
            elif tag == f"{W_NS}commentRangeEnd":
                cid = child.get(f"{W_NS}id")
                if cid in active_ids:
                    active_ids.remove(cid)
            elif tag == f"{W_NS}t" and active_ids and child.text:
                for cid in active_ids:
                    anchors.setdefault(cid, "")
                    anchors[cid] += child.text
        full = _text_of(p)
        for cid in {c.get(f"{W_NS}id") for c in p.iter(f"{W_NS}commentRangeStart")}:
            if cid and not anchors.get(cid):
                anchors[cid] = full
    return anchors


def render_checklist(
    *,
    comments: list[Comment],
    revisions: list[Revision],
    source: str,
) -> str:
    """Markdown com 2 seções (Comentários + Track changes), cada item como ``- [ ]``."""
    today = _date.today().isoformat()
    lines = [
        "---",
        "type: review-checklist",
        f'source: "{source}"',
        f"extracted_at: {today}",
        "---",
        "",
        f"# Revisão recebida ({source})",
        "",
        "## Comentários",
        "",
    ]
    if not comments:
        lines.append("(nenhum)")
    else:
        for c in comments:
            anchor = f' (sobre: "{c.anchor_text}")' if c.anchor_text else ""
            lines.append(f"- [ ] **{c.author}**{anchor}: {c.text}")
    lines += ["", "## Track changes", ""]
    if not revisions:
        lines.append("(nenhum)")
    else:
        for r in revisions:
            label = "Inserção" if r.kind == "insertion" else "Deleção"
            who = f" por {r.author}" if r.author else ""
            lines.append(f'- [ ] **{label}**{who}: "{r.text}"')
    lines.append("")
    return "\n".join(lines)


def extract_to_file(docx_path: Path, out_dir: Path) -> Path:
    """Extrai comentários + revisões e escreve em ``<out_dir>/<YYYY-MM-DD>_<slug>.md``."""
    if not docx_path.is_file():
        raise FileNotFoundError(f"{docx_path} não existe.")
    result = extract_from_docx(docx_path)
    md = render_checklist(
        comments=result.comments,
        revisions=result.revisions,
        source=docx_path.name,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    today = _date.today().isoformat()
    slug = docx_path.stem.replace(" ", "-")
    out = out_dir / f"{today}_{slug}.md"
    out.write_text(md)
    return out
