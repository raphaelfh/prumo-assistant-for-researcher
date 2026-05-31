"""Helpers para session log de ``active-learning``.

Mantém o log em Markdown com YAML frontmatter (``SessionLog/v1``). Cada
step vira seção ``## N. <Step Name>`` com pergunta/resposta/feedback/citations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml

from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog

_STEP_TITLES = {
    "recall": "Recall",
    "anchor": "Anchor",
    "connect": "Connect",
    "apply": "Apply",
    "reflect": "Reflect",
}
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def session_log_path(pj_path: Path, topic: str, date: str) -> Path:
    """``docs/wiki/study-sessions/<topic>-<date>.md`` ou fallback ``docs/study-sessions/...``."""
    extended = pj_path / "docs" / "wiki"
    if extended.exists():
        out = extended / "study-sessions" / f"{topic}-{date}.md"
    else:
        out = pj_path / "docs" / "study-sessions" / f"{topic}-{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def create_session_log(
    *,
    pj_path: Path,
    topic: str,
    date: str,
    sources_consulted: list[str],
) -> Path:
    """Cria arquivo com YAML + heading; corpo aguarda ``append_step``."""
    log = SessionLog(topic=topic, date=date, sources_consulted=sources_consulted)
    path = session_log_path(pj_path, topic, date)
    path.write_text(_render_skeleton(log), encoding="utf-8")
    return path


def append_step(log_path: Path, step: StepLog) -> None:
    """Anexa seção ``## N. <Step Name>`` ao final do log com p/r/f/citations."""
    text = log_path.read_text(encoding="utf-8")
    n = _count_existing_steps(text) + 1
    title = _STEP_TITLES[step.step_name]
    block = [
        f"## {n}. {title}",
        "",
        f"**Pergunta:** {step.question}",
        "",
        f"**Resposta:** {step.answer or '_(sem resposta)_'}",
        "",
        f"**Feedback:** {step.feedback or '_(sem feedback)_'}",
        "",
    ]
    if step.citations:
        block.append("**Citações:** " + " ".join(step.citations))
        block.append("")
    if step.references_missing:
        block.append("**Refs faltando:**")
        for r in step.references_missing:
            block.append(f"- {r}")
        block.append("")
    appended = text.rstrip() + "\n\n" + "\n".join(block) + "\n"
    log_path.write_text(appended, encoding="utf-8")


def finalize_session(
    log_path: Path,
    *,
    duration_minutes: int,
    status: Literal["completed", "abandoned", "partial"],
    references_missing: list[str],
    finding_archived: Path | None,
) -> None:
    """Atualiza YAML frontmatter com fechamento da sessão."""
    text = log_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{log_path}: sem frontmatter YAML.")
    fm: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
    fm["duration_minutes"] = duration_minutes
    fm["status"] = status
    fm["references_missing"] = references_missing
    fm["finding_archived"] = str(finding_archived) if finding_archived else None
    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    body = text[m.end() :]
    log_path.write_text(f"---\n{new_yaml}\n---\n{body}", encoding="utf-8")


def _render_skeleton(log: SessionLog) -> str:
    fm = log.model_dump(mode="python", exclude={"steps"})
    fm["finding_archived"] = None  # explicito no YAML
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    body = [
        f"# Study session — {log.topic} ({log.date})",
        "",
        "## Fontes consultadas",
        "",
    ]
    body.extend(f"- {s}" for s in log.sources_consulted)
    body.append("")
    return f"---\n{yaml_block}\n---\n\n" + "\n".join(body) + "\n"


def _count_existing_steps(text: str) -> int:
    return len(re.findall(r"^## \d+\. ", text, flags=re.MULTILINE))
