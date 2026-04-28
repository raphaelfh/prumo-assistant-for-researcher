"""``prumo`` — entry point CLI (Typer).

Filosofia: este arquivo é a **fina fachada** que costura os comandos do CLI.
Lógica real fica em ``core/`` (transversal) e ``domains/`` (a entrar nos PR1+).
Aqui só tem: parsing de args, chamada da função certa, formatação de saída.

Comandos disponíveis no PR0 (fundação):

- ``prumo --version`` — mostra a versão
- ``prumo init <project>`` — cria estrutura de ``pj_*`` a partir do template
- ``prumo doctor [path]`` — health-check do projeto e das skills instaladas

Subcomandos por domínio (``prumo paper ...``, ``prumo wiki ...``, ...) entram
nos PR1-2. O ``cli.py`` apenas registra esses sub-apps quando os domínios
forem implementados.
"""

from __future__ import annotations

import importlib.resources as ir
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from prumo_assist import (
    ConfigError,
    IntegrationError,
    ManifestError,
    PrumoError,
    __version__,
)
from prumo_assist.core.output import Console
from prumo_assist.core.skills import load_skill_registry
from prumo_assist.domains.capture.cli import capture_app
from prumo_assist.domains.paper.cli import paper_app
from prumo_assist.domains.wiki.cli import wiki_app
from prumo_assist.domains.write.cli import write_app
from prumo_assist.integrations import REGISTRY as INTEGRATIONS

app = typer.Typer(
    name="prumo",
    help=(
        "Knowledge, bibliography & academic writing assistant for clinical research.\n"
        "Lives between Zotero, Obsidian, and your agent-host."
    ),
    add_completion=False,
    no_args_is_help=True,
)
# Subcomandos por domínio. Cada domínio é uma sub-app independente.
app.add_typer(paper_app)
app.add_typer(wiki_app)
app.add_typer(capture_app)
app.add_typer(write_app)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"prumo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Mostra versão e sai.", callback=_version_callback),
    ] = False,
) -> None:
    """Entry point — flags globais."""


# ---------------------------------------------------------------------------
# prumo init
# ---------------------------------------------------------------------------


def _resolve_template_dir() -> Path:
    """Localiza ``templates/pj_base/`` tanto em modo dev quanto instalado.

    - **Dev (editable)**: pasta ``templates/`` na raiz do worktree.
    - **Instalado**: empacotada em ``prumo_assist/_templates/`` via
      ``[tool.hatch.build.targets.wheel.force-include]``.
    """
    # 1. Tentar pacote instalado
    try:
        package_files = ir.files("prumo_assist") / "_templates" / "pj_base"
        if package_files.is_dir():
            return Path(str(package_files))
    except (ModuleNotFoundError, AttributeError, NotADirectoryError):
        pass

    # 2. Fallback dev: pasta templates/ irmã ao src/
    pkg_root = Path(__file__).resolve().parent
    candidates = [
        pkg_root.parent.parent / "templates" / "pj_base",  # src/prumo_assist/../../templates
        pkg_root.parent / "templates" / "pj_base",  # editable layouts mais rasos
    ]
    for c in candidates:
        if c.is_dir():
            return c

    raise ConfigError("Template 'pj_base' não encontrado. Reinstale o pacote ou rode do worktree.")


@app.command("init")
def init_command(
    project: Annotated[str, typer.Argument(help="Nome do diretório do pj_* a criar.")],
    integration: Annotated[
        list[str],
        typer.Option(
            "--integration",
            "-i",
            help="Adapter de agent-host a configurar. Pode repetir. Default: claude_code.",
        ),
    ] = ["claude_code"],
    json_mode: Annotated[
        bool, typer.Option("--json", help="Saída em JSON pra scripts/notebooks.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Sobrescreve diretório existente (cuidado)."),
    ] = False,
) -> None:
    """Cria um novo projeto ``pj_*`` a partir do template e instala skills."""
    console = Console(json_mode=json_mode)
    target = Path(project).resolve()

    if target.exists() and not force:
        console.error(f"{target} já existe. Use --force pra sobrescrever.")
        raise typer.Exit(code=1)

    try:
        template = _resolve_template_dir()
        if target.exists() and force:
            shutil.rmtree(target)
        shutil.copytree(template, target)

        # Instala skills via integrations escolhidas (modo tolerante:
        # uma skill com YAML quebrado não bloqueia init do projeto).
        skills_dir = _resolve_skills_dir()
        registry = None
        if skills_dir is not None:
            registry, skill_warnings = load_skill_registry(skills_dir, strict=False)
            for w in skill_warnings:
                console.warn(f"skill ignorada: {w}")

        installed_summary: list[dict[str, object]] = []
        for key in integration:
            cls = INTEGRATIONS.get(key)
            if cls is None:
                console.warn(f"Integration '{key}' desconhecida; ignorada.")
                continue
            adapter = cls()
            if registry is not None:
                report = adapter.install(target, registry)
                installed_summary.append(
                    {
                        "integration": report.integration,
                        "installed": report.installed,
                        "skipped": [{"skill": s, "reason": r} for s, r in report.skipped],
                    }
                )
            else:
                installed_summary.append(
                    {"integration": adapter.name, "installed": [], "skipped": []}
                )

        payload = {
            "project": str(target),
            "template": str(template),
            "integrations": installed_summary,
            "version": __version__,
        }
        console.success(f"Projeto criado em {target}")
        console.emit(payload)
    except PrumoError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e


def _resolve_skills_dir() -> Path | None:
    """Localiza ``skills/`` da fonte (raiz do plugin) ou retorna ``None``."""
    pkg_root = Path(__file__).resolve().parent
    candidates = [
        pkg_root.parent.parent / "skills",  # dev / worktree
        pkg_root / "_skills",  # se um dia empacotarmos
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


# ---------------------------------------------------------------------------
# prumo doctor
# ---------------------------------------------------------------------------


@app.command("doctor")
def doctor_command(
    path: Annotated[
        Path,
        typer.Argument(help="Diretório do pj_* a auditar (default: cwd).", exists=False),
    ] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json", help="Saída JSON.")] = False,
) -> None:
    """Health-check do projeto: estrutura, skills instaladas, integrations OK?"""
    console = Console(json_mode=json_mode)
    target = path.resolve()
    issues: list[str] = []

    expected = [".claude", "docs", "references"]
    for name in expected:
        if not (target / name).is_dir():
            issues.append(f"Diretório esperado ausente: {name}/")

    for adapter_cls in INTEGRATIONS.values():
        adapter = adapter_cls()
        issues.extend(adapter.doctor(target))

    payload = {
        "project": str(target),
        "ok": not issues,
        "issues": issues,
        "version": __version__,
    }
    if issues:
        console.warn(f"{len(issues)} problema(s) encontrado(s).")
        for i in issues:
            console.info(f"  • {i}")
    else:
        console.success("Tudo certo.")
    console.emit(payload)
    if issues:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# prumo skills (descoberta)
# ---------------------------------------------------------------------------


@app.command("skills")
def skills_command(
    json_mode: Annotated[bool, typer.Option("--json", help="Saída JSON.")] = False,
) -> None:
    """Lista skills disponíveis no plugin (descoberta, não instalação)."""
    console = Console(json_mode=json_mode)
    skills_dir = _resolve_skills_dir()
    if skills_dir is None:
        console.warn("Diretório de skills não encontrado.")
        console.emit({"skills": []})
        return
    try:
        registry, warnings = load_skill_registry(skills_dir, strict=False)
    except ManifestError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    for w in warnings:
        console.warn(f"skill ignorada: {w}")
    payload = {
        "skills": [
            {
                "name": s.name,
                "version": s.version,
                "schema": s.schema,
                "determinism": s.determinism,
                "description": s.description,
            }
            for s in (registry.get(n) for n in registry.names())
        ]
    }
    console.emit(payload)


def _entry() -> None:
    """Entry point usado pelo ``project.scripts``."""
    try:
        app()
    except IntegrationError as e:
        print(f"prumo: integration error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _entry()
