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

from prumo_assist.core.skills import SkillManifest, SkillRegistry, load_skill_registry  # noqa: E402

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


def render_skills_table(registry: SkillRegistry) -> str:
    lines = ["| Skill | Uso |", "|---|---|"]
    for name in registry.names():
        desc = " ".join(registry.get(name).description.split())
        lines.append(f"| `/prumo-assist:{name}` | {desc} |")
    return "\n".join(lines)


def render_skills_catalog(registry: SkillRegistry) -> str:
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


_PREFLIGHT_HEADER = (
    "> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**\n>"
)

_PF_CLI = (
    "**CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA\n"
    "operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com\n"
    "consentimento) e pare aqui."
)

_PF_DRIFT = (
    "**Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver\n"
    "definido, compare a versão do CLI com o campo `version` de\n"
    "`$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise\n"
    '("CLI X < plugin Y — comandos novos podem não existir") e ofereça\n'
    "`uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,\n"
    "pule este passo em silêncio."
)

_PF_INIT = (
    "**Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,\n"
    "oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente\n"
    "não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor."
)

_PF_QMD = (
    "**Busca semântica (qmd):** se as tools MCP do `qmd` não estiverem no seu\n"
    'inventário NESTA sessão, diga isso explicitamente ("busca semântica\n'
    'indisponível — resultados via leitura direta, mais lentos/parciais") e\n'
    "prossiga só no fallback documentado por esta skill; sem fallback, recuse a\n"
    "operação com o hint do `prumo doctor`."
)

# Skills só-qmd (sem `cli`) não ganham o item 1 — que roteia pro /start quando o
# CLI falta — então o item de qmd absorve essa frase de roteamento.
_PF_QMD_SEM_CLI = _PF_QMD + " Se precisar do stack completo, roteie para `/prumo-assist:start`."

_PF_ZOTERO = (
    "**Zotero:** confira `prumo doctor --json` → `external_deps[name=zotero].present`;\n"
    "ausente/fechado → recuse operações que dependem dele citando o hint do doctor\n"
    "(abrir o Zotero; instalar Better BibTeX)."
)

_PREFLIGHT_FOOTER = (
    ">\n"
    "> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):\n"
    "> operação exata nunca é simulada."
)

_PREFLIGHT_PURE = (
    "> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende\n"
    "> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de\n"
    "> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa\n"
    "> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada."
)


def _pf_item(n: int, text: str) -> str:
    """Prefixa a 1ª linha de ``text`` com ``> {n}. `` e o resto com ``>    `` (continuação)."""
    lines = text.split("\n")
    out = [f"> {n}. {lines[0]}"]
    out += [f">    {ln}" for ln in lines[1:]]
    return "\n".join(out)


def render_preflight(manifest: SkillManifest) -> str:
    """Compõe o bloco de preflight (ADR-0019) a partir de ``manifest.requires``.

    ``requires: []`` (julgamento puro) devolve a variante fixa ``_PREFLIGHT_PURE``.
    Caso contrário, concatena sub-blocos condicionados à classe de dependência
    presente em ``requires`` — ``cli`` (itens 1-3), ``qmd`` (item seguinte) e
    ``zotero`` (item seguinte) — renumerando 1..N conforme o que se aplica.
    Skills com ``qmd`` mas sem ``cli`` não têm o item 1 (que já cobre "CLI
    ausente → roteie pro /start"), então o item de qmd assume essa frase.
    """
    reqs = set(manifest.requires)
    if not reqs:
        return _PREFLIGHT_PURE
    parts = [_PREFLIGHT_HEADER]
    n = 1
    if "cli" in reqs:
        parts += [_pf_item(n, _PF_CLI), _pf_item(n + 1, _PF_DRIFT), _pf_item(n + 2, _PF_INIT)]
        n += 3
    if "qmd" in reqs:
        qmd_text = _PF_QMD if "cli" in reqs else _PF_QMD_SEM_CLI
        parts.append(_pf_item(n, qmd_text))
        n += 1
    if "zotero" in reqs:
        parts.append(_pf_item(n, _PF_ZOTERO))
        n += 1
    parts.append(_PREFLIGHT_FOOTER)
    return "\n".join(parts)


def stamp_preflight(text: str, body: str, *, where: str) -> str:
    """Insere/atualiza o bloco ``prumo:preflight`` no corpo (após frontmatter) de um SKILL.md.

    Idempotente: se os marcadores já existem, delega a ``replace_block``. Na
    primeira estampagem (marcadores ausentes), insere logo após a primeira
    linha ``# `` (H1) do corpo. Sem H1, aborta — não há onde ancorar o bloco.
    """
    begin = "<!-- prumo:preflight:begin -->"
    if begin in text:
        return replace_block(text, "preflight", body, where=where)
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            block = f"\n{begin}\n{body.strip()}\n<!-- prumo:preflight:end -->\n"
            return "".join(lines[: i + 1]) + block + "".join(lines[i + 1 :])
    raise SystemExit(f"gen_indexes: {where} sem H1 — não sei onde inserir o preflight")


def _targets(registry: SkillRegistry) -> list[tuple[Path, str, str]]:
    return [
        (REPO / "README.md", "skills-table", render_skills_table(registry)),
        (REPO / "skills" / "start" / "SKILL.md", "skills-catalog", render_skills_catalog(registry)),
        (REPO / "docs" / "_index.md", "kb-index", render_kb_index()),
        (REPO / "docs" / "adr" / "_index.md", "adr-index", render_adr_index()),
    ]


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []
    # Registry carregado UMA vez — tabela do README, catálogo do start e
    # estampagem de preflight consomem a mesma leitura.
    registry, _ = load_skill_registry(REPO / "skills", strict=True)

    def _sync(path: Path, rel: str, old: str, new: str) -> None:
        """Semântica única de --check/write — compartilhada pelos dois loops."""
        if new == old:
            return
        if check:
            stale.append(rel)
        else:
            path.write_text(new, encoding="utf-8")
            print(f"gen_indexes: atualizado {rel}")

    for path, tag, body in _targets(registry):
        rel = str(path.relative_to(REPO))
        if not path.exists():
            raise SystemExit(f"gen_indexes: alvo ausente: {rel}")
        old = path.read_text(encoding="utf-8")
        _sync(path, rel, old, replace_block(old, tag, body, where=rel))

    for name in registry.names():
        manifest = registry.get(name)
        rel = str(manifest.path.relative_to(REPO))
        old = manifest.path.read_text(encoding="utf-8")
        _sync(manifest.path, rel, old, stamp_preflight(old, render_preflight(manifest), where=rel))

    if check and stale:
        print("gen_indexes --check: índices dessincronizados:", ", ".join(stale))
        print("Rode: uv run python .github/scripts/gen_indexes.py")
        return 1
    if check:
        print("gen_indexes --check: tudo em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
