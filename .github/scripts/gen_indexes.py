"""Regenera os blocos delimitados de índice a partir das fontes únicas.

Fontes (constitution, princípio VII):
- skills/<nome>/SKILL.md  → tabela do README + catálogo do router `start`
- docs/superpowers/{specs,plans,plans/archive}/*.md (frontmatter) → docs/_index.md
- docs/adr/adr-*.md → docs/adr/_index.md

Uso:
    uv run python .github/scripts/gen_indexes.py          # reescreve os blocos
    uv run python .github/scripts/gen_indexes.py --check  # exit 1 se algo está stale (CI)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from prumo_assist.core.skills import load_skill_registry  # noqa: E402

_FRONT_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


def replace_block(text: str, tag: str, body: str, *, where: str = "") -> str:
    """Substitui o miolo entre os marcadores `prumo:<tag>` preservando o resto.

    O corpo é inserido via lambda pra não ser interpretado como template de
    replacement do ``re.sub`` (um ``\\d`` ou ``\\g<0>`` em texto livre quebraria).
    """
    begin = f"<!-- prumo:{tag}:begin -->"
    end = f"<!-- prumo:{tag}:end -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    suffix = f" em {where}" if where else ""
    if not pattern.search(text):
        raise SystemExit(f"gen_indexes: marcadores 'prumo:{tag}' não encontrados{suffix}.")
    return pattern.sub(lambda _: begin + "\n" + body.strip() + "\n" + end, text)


def _front_field(path: Path, field: str) -> str:
    match = _FRONT_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return "—"
    found = re.search(rf"^{field}:\s*(.+)$", match.group(1), re.MULTILINE)
    return found.group(1).strip().strip('"') if found else "—"


def render_skills_table() -> str:
    registry, _ = load_skill_registry(REPO / "skills", strict=True)
    lines = ["| Skill | Uso |", "|---|---|"]
    for name in registry.names():
        desc = " ".join(registry.get(name).description.split())
        lines.append(f"| `/prumo-assist:{name}` | {desc} |")
    return "\n".join(lines)


def render_skills_catalog() -> str:
    registry, _ = load_skill_registry(REPO / "skills", strict=True)
    lines = []
    for name in registry.names():
        desc = " ".join(registry.get(name).description.split())
        lines.append(f"- `/prumo-assist:{name}` — {desc}")
    return "\n".join(lines)


def render_kb_index() -> str:
    sp = REPO / "docs" / "superpowers"
    lines = ["**Specs** (não-perecíveis):", ""]
    for p in sorted((sp / "specs").glob("*.md")):
        lines.append(f"- [[superpowers/specs/{p.stem}]] · {_front_field(p, 'status')}")
    lines += ["", "**Plans ativos:**", ""]
    active = sorted((sp / "plans").glob("*.md"))
    if active:
        lines += [f"- [[superpowers/plans/{p.stem}]] · {_front_field(p, 'status')}" for p in active]
    else:
        lines.append("- (nenhum)")
    archived = sorted((sp / "plans" / "archive").glob("*.md"))
    lines += ["", f"**Plans arquivados:** {len(archived)} em `superpowers/plans/archive/`", ""]
    lines += ["**ADRs:** ver [[adr/_index|índice de ADRs]]"]
    return "\n".join(lines)


def render_adr_index() -> str:
    lines = []
    for p in sorted((REPO / "docs" / "adr").glob("adr-*.md")):
        text = p.read_text(encoding="utf-8")
        h1 = next(
            (ln.removeprefix("# ").strip() for ln in text.splitlines() if ln.startswith("# ")),
            p.stem,
        )
        status_m = re.search(r"^- Status:\s*(.+)$", text, re.MULTILINE)
        status = status_m.group(1).strip() if status_m else "—"
        title = h1.split("—", 1)[1].strip() if "—" in h1 else h1
        lines.append(f"- [[adr/{p.stem}]] — {title} · {status}")
    return "\n".join(lines)


def _targets() -> list[tuple[Path, str, str]]:
    return [
        (REPO / "README.md", "skills-table", render_skills_table()),
        (REPO / "skills" / "start" / "SKILL.md", "skills-catalog", render_skills_catalog()),
        (REPO / "docs" / "_index.md", "kb-index", render_kb_index()),
        (REPO / "docs" / "adr" / "_index.md", "adr-index", render_adr_index()),
    ]


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []
    for path, tag, body in _targets():
        rel = str(path.relative_to(REPO))
        if not path.exists():
            raise SystemExit(f"gen_indexes: alvo ausente: {rel}")
        old = path.read_text(encoding="utf-8")
        new = replace_block(old, tag, body, where=rel)
        if new != old:
            if check:
                stale.append(rel)
            else:
                path.write_text(new, encoding="utf-8")
                print(f"gen_indexes: atualizado {rel}")
    if check and stale:
        print("gen_indexes --check: índices dessincronizados:", ", ".join(stale))
        print("Rode: uv run python .github/scripts/gen_indexes.py")
        return 1
    if check:
        print("gen_indexes --check: tudo em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
