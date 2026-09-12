"""Instalador Claude Code: traduz ``SkillRegistry`` → ``<pj>/.claude/skills/``.

Convenção do Claude Code (espelhada do plugin atual):

    pj_x/
    └── .claude/
        └── skills/
            └── <skill-name>/
                └── SKILL.md

Como a fonte canônica já está nesse formato, "instalar" é essencialmente:

    copy skills/<name>/ → pj_x/.claude/skills/<name>/

A árvore vai inteira: ``modes/``, ``references/``, ``examples/`` e ``templates/``
são lidos pelo agente a partir do ``SKILL.md`` (spec de superfície por domínio).

Os subagents do plugin (``agents/*.md``) vão para ``pj_x/.claude/agents/``, onde o
Claude Code os registra como subagents do projeto (ADR-0033).

Esse adapter é deliberadamente fino. Quando Cursor/Codex/Gemini entrarem,
eles transformam o ``SKILL.md`` no formato deles (TOML, custom rules, ...);
Claude Code é cópia direta porque nascemos no formato dele.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from par import IntegrationError
from par.core.paths import find_resource
from par.core.skills import SkillRegistry
from par.integrations.base import BaseIntegration, InstallReport


class ClaudeCodeIntegration(BaseIntegration):
    name = "claude_code"

    def install(self, target_dir: Path, registry: SkillRegistry) -> InstallReport:
        skills_root = target_dir / ".claude" / "skills"
        try:
            skills_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise IntegrationError(f"Não foi possível criar {skills_root}: {e}") from e

        installed: list[str] = []
        skipped: list[tuple[str, str]] = []

        for name in registry.names():
            manifest = registry.get(name)
            try:
                shutil.copytree(manifest.path.parent, skills_root / name, dirs_exist_ok=True)
                installed.append(name)
            except OSError as e:
                skipped.append((name, f"erro de escrita: {e}"))

        agents_src = find_resource("agents")
        if agents_src is not None:
            agents_root = target_dir / ".claude" / "agents"
            try:
                agents_root.mkdir(parents=True, exist_ok=True)
                for agent in sorted(agents_src.glob("*.md")):
                    shutil.copy2(agent, agents_root / agent.name)
            except OSError as e:
                skipped.append(("agents", f"erro de escrita: {e}"))

        return InstallReport(
            integration=self.name,
            target_dir=target_dir,
            installed=installed,
            skipped=skipped,
        )

    def doctor(self, target_dir: Path) -> list[str]:
        issues: list[str] = []
        skills_root = target_dir / ".claude" / "skills"
        if not skills_root.is_dir():
            issues.append(f"Diretório ausente: {skills_root}")
            return issues
        # Sanidade mínima: cada subdir tem SKILL.md
        for child in skills_root.iterdir():
            if child.is_dir() and not (child / "SKILL.md").is_file():
                issues.append(f"Skill incompleta (sem SKILL.md): {child}")
        return issues
