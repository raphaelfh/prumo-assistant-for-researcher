"""Parser de ``SKILL.md`` (frontmatter rico) + registry de descoberta.

Decisão arquitetural (DRY):
``SKILL.md`` é a **única** fonte de metadata por skill. Não temos ``manifest.yaml``
separado. Tudo que precisa ser declarado vai no frontmatter YAML, sob a chave
``prumo:`` pra não conflitar com convenções universais (``name``, ``description``)
que outros agent-hosts (Cursor, Codex, Gemini) já consomem.

Exemplo mínimo (campos obrigatórios em **bold**):

    ---
    name: paper-extract              # **obrigatório** — id único
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from prumo_assist import ManifestError

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)

VALID_DETERMINISM = frozenset({"agentic", "deterministic", "hybrid"})


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
    inputs: dict[str, str] = field(default_factory=dict)

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

    extra_keys = set(prumo_block) - {
        "version",
        "schema",
        "determinism",
        "agent_compat",
        "cost_estimate",
        "inputs",
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
        inputs=inputs,
        extra=extra,
    )


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
            manifest = parse_skill_file(skill_md)
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

    return SkillRegistry(skills=found), warnings
