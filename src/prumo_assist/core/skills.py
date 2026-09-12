"""Parser de ``SKILL.md`` (frontmatter rico) + registry de descoberta.

Decisão arquitetural (DRY):
``SKILL.md`` é a **única** fonte de metadata por skill. Não temos ``manifest.yaml``
separado. Tudo que precisa ser declarado vai no frontmatter YAML, sob a chave
``prumo:`` pra não conflitar com convenções universais (``name``, ``description``)
que outros agent-hosts (Cursor, Codex, Gemini) já consomem.

Exemplo mínimo (campos obrigatórios em **bold**):

    ---
    name: paper                      # **obrigatório** — id único
    description: Extrai PDF → callout estruturado.   # **obrigatório**
    prumo:
      version: 1.0.0                 # default "0.0.0" se omitido
      schema: PaperCallout/v1        # contrato de saída versionado
      determinism: agentic           # agentic | deterministic | hybrid
      agent_compat: [claude-code]    # hosts onde foi validada
      cost_estimate: ~4k tokens      # informativo
      inputs:
        citekey: required
    ---

    # Paper Extract — corpo Markdown/Jinja2 que vira o prompt
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from prumo_assist import ManifestError
from prumo_assist.core.config import WRITING_LANGUAGES

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)

VALID_DETERMINISM = frozenset({"agentic", "deterministic", "hybrid"})
VALID_REQUIRES = frozenset({"cli", "qmd", "zotero"})

# Token de ``allowed-tools``: ``Bash(prumo paper *)`` tem espaço dentro do
# parêntese e precisa sair inteiro; o resto é separado por espaço.
_TOOL_TOKEN_RE = re.compile(r"[^\s(]+\([^)]*\)|\S+")


def _str_tuple(raw: object, *, field_name: str, path: Path) -> tuple[str, ...]:
    """Normaliza string-ou-lista em tupla sem vazios nem duplicatas (ordem preservada)."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        raise ManifestError(f"{path}: {field_name} deve ser string ou lista.")
    return tuple(dict.fromkeys(i.strip() for i in items if i.strip()))


@dataclass(frozen=True)
class SkillRef:
    """Endereço de um modo: ``skill`` + ``mode`` (ex.: ``paper`` + ``extract``).

    ``slug`` é a forma gravada em proveniência nova (``paper/extract``);
    ``invocation`` é a forma que o pesquisador digita no agent-host.
    """

    skill: str
    mode: str

    @property
    def slug(self) -> str:
        return f"{self.skill}/{self.mode}"

    @property
    def invocation(self) -> str:
        return f"prumo-assist:{self.skill} {self.mode}"


@dataclass(frozen=True)
class SkillManifest:
    """Metadados parseados de um ``SKILL.md``.

    ``body`` é o conteúdo Markdown após o frontmatter (vira o prompt
    quando a skill é instalada num agent-host)."""

    name: str
    description: str
    body: str
    path: Path

    version: str = "0.0.0"
    schema: str | None = None
    determinism: str = "agentic"
    agent_compat: tuple[str, ...] = ()
    cost_estimate: str | None = None
    guidelines_reviewed: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    requires: tuple[str, ...] = ()
    prose: bool = False
    locale_lock: str | None = None
    # Superfície por domínio (spec 2026-09-12): campos de modo.
    phrases: tuple[str, ...] = ()
    legacy: tuple[str, ...] = ()
    write_kind: str | None = None
    disclosure_task: str | None = None
    allowed_tools: tuple[str, ...] = ()
    argument_hint: str | None = None
    modes: tuple[SkillManifest, ...] = ()

    extra: dict[str, Any] = field(default_factory=dict)


def parse_skill_file(path: Path) -> SkillManifest:
    """Lê e valida um ``SKILL.md``. Levanta ``ManifestError`` em qualquer falha.

    O parser preserva campos desconhecidos sob ``extra`` pra forward-compatibility.
    """
    if not path.is_file():
        raise ManifestError(f"SKILL.md não encontrado: {path}")
    text = path.read_text(encoding="utf-8")

    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ManifestError(f"{path}: frontmatter YAML ausente (esperado entre '---').")

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ManifestError(f"{path}: frontmatter YAML inválido: {e}") from e

    if not isinstance(meta, dict):
        raise ManifestError(f"{path}: frontmatter deve ser um mapping YAML.")

    body = text[match.end() :].lstrip("\n")

    name = meta.get("name")
    description = meta.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError(f"{path}: campo 'name' obrigatório (string não-vazia).")
    if not isinstance(description, str) or not description.strip():
        raise ManifestError(f"{path}: campo 'description' obrigatório (string não-vazia).")

    prumo_block = meta.get("prumo") or {}
    if not isinstance(prumo_block, dict):
        raise ManifestError(f"{path}: bloco 'prumo:' deve ser um mapping.")

    determinism = str(prumo_block.get("determinism", "agentic"))
    if determinism not in VALID_DETERMINISM:
        raise ManifestError(
            f"{path}: prumo.determinism='{determinism}' inválido; use {sorted(VALID_DETERMINISM)}"
        )

    agent_compat_raw = prumo_block.get("agent_compat")
    if agent_compat_raw is None:
        agent_compat: tuple[str, ...] = ()
    elif isinstance(agent_compat_raw, str):
        agent_compat = (agent_compat_raw,)
    elif isinstance(agent_compat_raw, list):
        agent_compat = tuple(str(x) for x in agent_compat_raw)
    else:
        raise ManifestError(f"{path}: prumo.agent_compat deve ser string ou lista.")

    inputs_raw = prumo_block.get("inputs") or {}
    if not isinstance(inputs_raw, dict):
        raise ManifestError(f"{path}: prumo.inputs deve ser um mapping.")
    inputs = {str(k): str(v) for k, v in inputs_raw.items()}

    requires_raw = prumo_block.get("requires")
    if requires_raw is None:
        requires: tuple[str, ...] = ()
    elif isinstance(requires_raw, str):
        requires = (requires_raw,)
    elif isinstance(requires_raw, list):
        requires = tuple(str(x) for x in requires_raw)
    else:
        raise ManifestError(f"{path}: prumo.requires deve ser string ou lista.")
    invalid = [r for r in requires if r not in VALID_REQUIRES]
    if invalid:
        raise ManifestError(
            f"{path}: prumo.requires inválido {invalid}; use {sorted(VALID_REQUIRES)}"
        )
    # dedup preservando ordem (emenda pós-review T1: o campo dirige GERAÇÃO —
    # duplicata silenciosa viraria bloco de preflight duplicado).
    requires = tuple(dict.fromkeys(requires))

    prose_raw = prumo_block.get("prose", False)
    if not isinstance(prose_raw, bool):
        raise ManifestError(f"{path}: prumo.prose deve ser booleano (true/false).")
    prose = prose_raw

    locale_lock_raw = prumo_block.get("locale_lock")
    locale_lock: str | None = None
    if locale_lock_raw is not None:
        locale_lock = str(locale_lock_raw)
        if locale_lock not in WRITING_LANGUAGES:
            raise ManifestError(
                f"{path}: prumo.locale_lock='{locale_lock}' inválido; "
                f"use um de {sorted(WRITING_LANGUAGES)}"
            )
        if not prose:
            raise ManifestError(
                f"{path}: prumo.locale_lock só faz sentido com prumo.prose: true "
                "(a trava dirige o bloco de prosa gerado)."
            )

    allowed_raw = meta.get("allowed-tools")
    if allowed_raw is None:
        allowed_tools: tuple[str, ...] = ()
    elif isinstance(allowed_raw, str):
        allowed_tools = tuple(dict.fromkeys(_TOOL_TOKEN_RE.findall(allowed_raw)))
    elif isinstance(allowed_raw, list):
        allowed_tools = tuple(dict.fromkeys(str(x) for x in allowed_raw))
    else:
        raise ManifestError(f"{path}: allowed-tools deve ser string ou lista.")
    argument_hint_raw = meta.get("argument-hint")

    extra_keys = set(prumo_block) - {
        "version",
        "schema",
        "determinism",
        "agent_compat",
        "cost_estimate",
        "guidelines_reviewed",
        "inputs",
        "requires",
        "prose",
        "locale_lock",
        "phrases",
        "legacy",
        "write_kind",
        "disclosure_task",
    }
    extra = {k: prumo_block[k] for k in extra_keys}

    return SkillManifest(
        name=name.strip(),
        description=description.strip(),
        body=body,
        path=path,
        version=str(prumo_block.get("version", "0.0.0")),
        schema=(str(prumo_block["schema"]) if prumo_block.get("schema") else None),
        determinism=determinism,
        agent_compat=agent_compat,
        cost_estimate=(
            str(prumo_block["cost_estimate"]) if prumo_block.get("cost_estimate") else None
        ),
        guidelines_reviewed=(
            str(prumo_block["guidelines_reviewed"])
            if prumo_block.get("guidelines_reviewed")
            else None
        ),
        inputs=inputs,
        requires=requires,
        prose=prose,
        locale_lock=locale_lock,
        phrases=_str_tuple(prumo_block.get("phrases"), field_name="prumo.phrases", path=path),
        legacy=_str_tuple(prumo_block.get("legacy"), field_name="prumo.legacy", path=path),
        write_kind=(str(prumo_block["write_kind"]) if prumo_block.get("write_kind") else None),
        disclosure_task=(
            str(prumo_block["disclosure_task"]) if prumo_block.get("disclosure_task") else None
        ),
        allowed_tools=allowed_tools,
        argument_hint=(str(argument_hint_raw) if argument_hint_raw else None),
        extra=extra,
    )


def load_modes(skill_dir: Path) -> tuple[SkillManifest, ...]:
    """Modos de uma skill: ``<skill_dir>/modes/*.md``, em ordem alfabética.

    Cada arquivo é parseado como um ``SKILL.md`` (mesmo contrato de frontmatter).
    ``name`` precisa bater com o nome do arquivo — é o endereço usado na
    invocação — e todo modo declara ao menos uma frase em ``prumo.phrases``,
    porque é dela que o gerador deriva o roteamento.
    """
    modes_dir = skill_dir / "modes"
    if not modes_dir.is_dir():
        return ()
    out: list[SkillManifest] = []
    for mode_path in sorted(modes_dir.glob("*.md")):
        mode = parse_skill_file(mode_path)
        if mode.name != mode_path.stem:
            raise ManifestError(
                f"{mode_path}: name '{mode.name}' difere do arquivo '{mode_path.name}'."
            )
        if not mode.phrases:
            raise ManifestError(
                f"{mode_path}: prumo.phrases obrigatório (ao menos uma frase) em modo."
            )
        out.append(mode)
    return tuple(out)


@dataclass(frozen=True)
class SkillRegistry:
    """Coleção de skills indexada por ``name``.

    Construída a partir de um diretório com layout ``<root>/<skill-name>/SKILL.md``."""

    skills: dict[str, SkillManifest]

    def get(self, name: str) -> SkillManifest:
        if name not in self.skills:
            raise ManifestError(f"Skill '{name}' não encontrada no registry.")
        return self.skills[name]

    def names(self) -> list[str]:
        return sorted(self.skills)

    def iter_modes(self) -> list[tuple[SkillRef, SkillManifest]]:
        """Todos os modos do registry, ordenados por skill e depois por modo."""
        return [(SkillRef(n, m.name), m) for n in self.names() for m in self.skills[n].modes]

    def find_mode(self, ref: SkillRef) -> SkillManifest | None:
        skill = self.skills.get(ref.skill)
        if skill is None:
            return None
        return next((m for m in skill.modes if m.name == ref.mode), None)

    def legacy_map(self) -> dict[str, SkillRef]:
        """Nome de skill antiga → modo novo. Levanta se um nome aparece em dois modos."""
        out: dict[str, SkillRef] = {}
        for ref, mode in self.iter_modes():
            for old in mode.legacy:
                if old in out:
                    raise ManifestError(
                        f"nome legado '{old}' declarado em {out[old].slug} e {ref.slug}."
                    )
                out[old] = ref
        return out

    def resolve(self, value: str) -> SkillRef | None:
        """Resolve ``paper/extract``, ``prumo-assist:paper extract`` ou um nome legado.

        Devolve ``None`` para valor que não aponta um modo existente — quem chama
        decide o fallback (ex.: disclosure mantém o valor cru).
        """
        raw = value.strip().removeprefix("/").removeprefix("prumo-assist:")
        for sep in ("/", " "):
            if sep in raw:
                skill, _, mode = raw.partition(sep)
                ref = SkillRef(skill.strip(), mode.strip())
                return ref if self.find_mode(ref) else None
        return self.legacy_map().get(raw)


def load_skill_registry(
    skills_dir: Path,
    *,
    strict: bool = True,
) -> tuple[SkillRegistry, list[str]]:
    """Varre ``skills_dir/<name>/SKILL.md`` e retorna registry + warnings.

    Args:
        skills_dir: raiz com layout ``<root>/<skill-name>/SKILL.md``.
        strict: se ``True`` (default), qualquer ``SKILL.md`` malformado aborta a
            leitura inteira — preferimos falhar cedo a entregar registry parcial.
            ``prumo init`` passa ``strict=False`` pra não impedir scaffolding
            quando uma skill legacy tiver YAML levemente fora do padrão.

    Returns:
        Par ``(registry, warnings)``. Warnings é lista vazia em modo estrito
        (qualquer problema vira exceção); em modo tolerante, contém uma string
        por skill ignorada.

    Raises:
        ManifestError: em modo estrito, qualquer falha de parse ou nome
            duplicado. Em modo tolerante, só nomes duplicados.
    """
    warnings: list[str] = []
    if not skills_dir.is_dir():
        return SkillRegistry(skills={}), warnings

    found: dict[str, SkillManifest] = {}
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            manifest = replace(parse_skill_file(skill_md), modes=load_modes(child))
        except ManifestError as e:
            if strict:
                raise
            warnings.append(str(e))
            continue
        if manifest.name in found:
            raise ManifestError(
                f"Skill '{manifest.name}' duplicada: {manifest.path} e {found[manifest.name].path}"
            )
        found[manifest.name] = manifest

    registry = SkillRegistry(skills=found)
    registry.legacy_map()  # nome legado em dois modos é erro em qualquer modo de leitura
    return registry, warnings


def stale_guideline_warnings(
    registry: SkillRegistry,
    *,
    today: date,
    max_age_days: int = 180,
) -> list[str]:
    """Avisos para skills cujo ``guidelines_reviewed`` está velho ou inválido.

    Só considera skills que **declaram** o campo — é opt-in por skill. Mantém o
    julgamento de validade fora do LLM (Princípio II): living guidelines como
    TRIPOD-LLM mudam a cada ~3 meses; sem revisão a prose envelhece em silêncio.
    """
    out: list[str] = []
    labeled: list[tuple[str, SkillManifest]] = [(n, registry.get(n)) for n in registry.names()]
    labeled += [(f"{ref.skill} {ref.mode}", mode) for ref, mode in registry.iter_modes()]
    for name, manifest in labeled:
        raw = manifest.guidelines_reviewed
        if not raw:
            continue
        try:
            reviewed = date.fromisoformat(raw)
        except ValueError:
            out.append(
                f"skill '{name}': prumo.guidelines_reviewed inválido ({raw!r}); use ISO YYYY-MM-DD."
            )
            continue
        age = (today - reviewed).days
        if age > max_age_days:
            out.append(
                f"skill '{name}': checklists revisados há {age} dias "
                f"(> {max_age_days}); revalide os reporting guidelines e atualize guidelines_reviewed."
            )
    return out
