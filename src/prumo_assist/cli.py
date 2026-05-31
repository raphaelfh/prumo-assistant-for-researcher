"""``prumo`` — entry point CLI (Typer).

Filosofia: este arquivo é a **fina fachada** que costura os comandos do CLI.
Lógica real fica em ``core/`` (transversal) e ``domains/`` (a entrar nos PR1+).
Aqui só tem: parsing de args, chamada da função certa, formatação de saída.

Comandos disponíveis no PR0 (fundação):

- ``prumo --version`` — mostra a versão
- ``prumo init [project]`` — cria estrutura de ``pj_*`` a partir do template
  (wizard interativo se ``project`` for omitido)
- ``prumo doctor [path]`` — health-check do projeto e das skills instaladas

Subcomandos por domínio (``prumo paper ...``, ``prumo wiki ...``, ...) entram
nos PR1-2. O ``cli.py`` apenas registra esses sub-apps quando os domínios
forem implementados.
"""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.text import Text

from prumo_assist import (
    IntegrationError,
    ManifestError,
    PrumoError,
    __version__,
)
from prumo_assist.core.deps import check_external_deps
from prumo_assist.core.output import Console
from prumo_assist.core.paths import find_resource, resolve_resource
from prumo_assist.core.scaffold import (
    ModuleInfo,
    discover_modules,
    get_module,
    is_applied,
)
from prumo_assist.core.scaffold import overlay as _overlay
from prumo_assist.core.skills import load_skill_registry
from prumo_assist.domains.capture.cli import capture_command
from prumo_assist.domains.paper.cli import paper_app
from prumo_assist.domains.protocol.cli import protocol_app
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
app.add_typer(protocol_app)
app.add_typer(wiki_app)
app.add_typer(write_app)
app.command(
    "capture", help="Classifica input (URL, DOI, arXiv, PDF, citekey) e sugere próximo passo."
)(capture_command)

# Referência ao stdin capturada na importação. Usada para decidir se um comando
# roda em modo interativo. Capturamos o objeto (em vez de ler ``sys.stdin``
# direto no momento da decisão) porque o ``CliRunner`` dos testes substitui
# ``sys.stdin`` por um wrapper durante o ``invoke`` — ler o objeto vivo nesse
# instante perderia o ``isatty`` injetado pelo teste no stdin original.
_STDIN = sys.stdin


def _stdin_isatty() -> bool:
    """``True`` se a entrada padrão é um terminal interativo.

    Lê do objeto stdin capturado na importação (ver ``_STDIN``), de modo que
    permaneça testável via ``monkeypatch.setattr(cli.sys.stdin, "isatty", ...)``
    mesmo quando o ``CliRunner`` troca ``sys.stdin`` por baixo dos panos.
    """
    try:
        return _STDIN.isatty()
    except (ValueError, OSError):  # stdin fechado/sem fd (ex.: alguns runners)
        return False


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


# Modos de criação do pj_*. Mantém ordem de exibição no wizard.
MODE_NEW = "new"
MODE_MERGE = "merge"
MODE_FORCE = "force"

_VALID_PREFIXES = ("pj_",)
_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def _resolve_template_dir() -> Path:
    """Localiza ``templates/pj_base/`` (instalado ou worktree)."""
    return resolve_resource("templates") / "pj_base"


def _resolve_skills_dir() -> Path | None:
    """Localiza ``skills/`` da fonte (raiz do plugin) ou retorna ``None``."""
    return find_resource("skills")


def _validate_project_name(raw: str) -> tuple[Path, str]:
    """Normaliza e valida o nome do projeto.

    Aceita: ``pj_x``, ``./pj_x``, ``/tmp/pj_x``.
    Rejeita: nomes sem prefixo válido, caracteres inválidos.

    Retorna ``(absolute_path, basename)``.
    """
    target = Path(raw).resolve()
    name = target.name
    if not name.startswith(_VALID_PREFIXES):
        raise typer.BadParameter(
            f"Nome do projeto deve começar com {' ou '.join(_VALID_PREFIXES)} (recebido: {name!r})."
        )
    if not _NAME_RE.match(name):
        raise typer.BadParameter(
            f"Nome do projeto deve usar apenas [a-z0-9_] (recebido: {name!r})."
        )
    return target, name


def _is_dir_empty(p: Path) -> bool:
    """``True`` se o diretório não existe ou só tem arquivos ``.DS_Store``-like."""
    if not p.exists():
        return True
    if not p.is_dir():
        return False
    for child in p.iterdir():
        if child.name in {".DS_Store", "Thumbs.db"}:
            continue
        return False
    return True


def _render_banner(console: Console) -> None:
    """Banner Rich estilo Speckit para abrir o wizard interativo."""
    if console.json_mode:
        return
    body = Text.assemble(
        ("prumo init  ", "bold cyan"),
        (f"v{__version__}\n", "dim"),
        ("Knowledge, bibliography & writing scaffold\n", ""),
        ("for clinical research projects.", "dim"),
    )
    console._rich.print(Panel(body, border_style="cyan", padding=(0, 2)))


def _render_next_steps(console: Console, target: Path, mode: str) -> None:
    """Mostra passos seguintes — invocado após sucesso, ignorado em JSON."""
    if console.json_mode:
        return
    rel = target.name
    console._rich.print()
    console._rich.print("[bold]Próximos passos:[/bold]")
    console._rich.print(f"  [cyan]cd {rel}[/cyan]")
    if mode == MODE_NEW:
        console._rich.print(
            "  Edite [cyan]docs/project_guide.md[/cyan] e [cyan].claude/rules/project_context.md[/cyan]"
        )
        console._rich.print("  Ative módulos opcionais (clínico, ML): [cyan]prumo add[/cyan]")
        console._rich.print("  No Claude Code, comece por: [cyan]/prumo-assist:start[/cyan]")
    elif mode == MODE_MERGE:
        console._rich.print(
            "  Revise as diferenças no [cyan]git status[/cyan] — arquivos existentes foram preservados."
        )
        console._rich.print(
            "  Ative módulos com [cyan]prumo add[/cyan]; no Claude Code: [cyan]/prumo-assist:start[/cyan]."
        )
    else:  # MODE_FORCE
        console._rich.print(
            "  [yellow]Conteúdo anterior foi substituído.[/yellow] Confira [cyan]git status[/cyan]."
        )


@dataclass(frozen=True)
class WizardAnswers:
    """Respostas coletadas pelo wizard interativo de ``prumo init``."""

    target: Path
    mode: str
    integrations: list[str]
    modules: list[str]
    init_git: bool


def _wizard(console: Console, default_target: str | None = None) -> WizardAnswers:
    """Wizard interativo Speckit-style. Retorna respostas do usuário."""
    _render_banner(console)
    # 1. Nome do projeto
    name = typer.prompt(
        "Nome do projeto (ex.: pj_my_study)",
        default=default_target or "pj_",
    )
    target, _ = _validate_project_name(name)

    # 2. Modo
    if target.exists() and not _is_dir_empty(target):
        console._rich.print(
            f"\n[yellow]⚠[/yellow]  [bold]{target}[/bold] já existe e tem conteúdo."
        )
        console._rich.print("Como prosseguir?\n")
        console._rich.print(
            "  [bold cyan]1)[/bold cyan] Merge — preserva seus arquivos, adiciona só o que falta [dim](recomendado)[/dim]"
        )
        console._rich.print(
            "  [bold cyan]2)[/bold cyan] Force — apaga tudo e recria do zero [red](destrutivo)[/red]"
        )
        console._rich.print("  [bold cyan]3)[/bold cyan] Cancelar\n")
        choice = typer.prompt("Escolha [1/2/3]", default="1")
        if choice.strip() == "3":
            raise typer.Abort()
        mode = MODE_MERGE if choice.strip() == "1" else MODE_FORCE
        if mode == MODE_FORCE:
            confirm = typer.confirm(f"Confirma DELETAR tudo em {target}?", default=False)
            if not confirm:
                raise typer.Abort()
    else:
        mode = MODE_NEW

    # 3. Integrações (multi-select simplificado)
    available = list(INTEGRATIONS.keys())
    console._rich.print()
    if len(available) <= 1:
        integrations = available
    else:
        console._rich.print("[bold]Integrações disponíveis:[/bold]")
        for i, key in enumerate(available, 1):
            console._rich.print(f"  [cyan]{i})[/cyan] {key}")
        raw = typer.prompt(
            "Quais instalar? (números separados por vírgula, ou 'all')",
            default="1" if len(available) >= 1 else "",
        )
        if raw.strip().lower() == "all":
            integrations = available
        else:
            try:
                idxs = [int(x.strip()) - 1 for x in raw.split(",") if x.strip()]
                integrations = [available[i] for i in idxs if 0 <= i < len(available)]
            except ValueError:
                integrations = ["claude_code"] if "claude_code" in available else available[:1]

    # Módulos opcionais (à la carte, todos desmarcados).
    _modules = discover_modules()
    selected_modules: list[str] = []
    if _modules:
        console._rich.print("\n[bold]Módulos opcionais (Enter para nenhum):[/bold]")
        for _i, _m in enumerate(_modules, 1):
            console._rich.print(f"  [cyan]{_i})[/cyan] {_m.name} — {_m.description}")
        _raw = typer.prompt("Quais ativar? (números separados por vírgula)", default="")
        for _tok in _raw.split(","):
            _tok = _tok.strip()
            if not _tok:
                continue
            try:
                _idx = int(_tok) - 1
            except ValueError:
                continue
            if 0 <= _idx < len(_modules):
                selected_modules.append(_modules[_idx].name)

    # 4. git init (apenas se MODE_NEW)
    init_git = False
    if mode == MODE_NEW:
        init_git = typer.confirm("Inicializar repositório git?", default=True)

    return WizardAnswers(
        target=target,
        mode=mode,
        integrations=integrations,
        modules=selected_modules,
        init_git=init_git,
    )


def _init_git_repo(target: Path) -> bool:
    """Roda ``git init`` no target. Retorna True se sucesso."""
    if (target / ".git").exists():
        return False
    import subprocess

    try:
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=target,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@app.command("init")
def init_command(
    project: Annotated[
        str | None,
        typer.Argument(
            help="Nome do diretório do pj_* a criar. Omita para wizard interativo.",
        ),
    ] = None,
    integration: Annotated[
        list[str] | None,
        typer.Option(
            "--integration",
            "-i",
            help="Adapter de agent-host a configurar. Pode repetir. Default: claude_code.",
        ),
    ] = None,
    with_modules: Annotated[
        str | None,
        typer.Option(
            "--with",
            help="Módulos a ativar na criação, separados por vírgula (ex.: clinical,ml).",
        ),
    ] = None,
    json_mode: Annotated[
        bool, typer.Option("--json", help="Saída em JSON pra scripts/notebooks.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Apaga o destino e recria do zero (DESTRUTIVO).",
        ),
    ] = False,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            "-m",
            help="Mescla scaffold em diretório existente sem sobrescrever arquivos.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Não-interativo: aceita defaults e pula wizard (útil em CI).",
        ),
    ] = False,
    init_git: Annotated[
        bool,
        typer.Option(
            "--git/--no-git",
            help="Inicializa git no novo projeto (modo não-interativo; default: True).",
        ),
    ] = True,
) -> None:
    """Cria um novo projeto ``pj_*`` a partir do template e instala skills.

    Modos:

    \b
    - ``prumo init`` (sem args, TTY) → wizard interativo (Speckit-style)
    - ``prumo init pj_x`` → cria do zero (erro se já existir)
    - ``prumo init pj_x --merge`` → mescla sem sobrescrever existentes
    - ``prumo init pj_x --force`` → apaga e recria (DESTRUTIVO)
    - ``prumo init pj_x --yes`` → não-interativo (CI)
    """
    console = Console(json_mode=json_mode)

    if force and merge:
        console.error("--force e --merge são mutuamente exclusivos.")
        raise typer.Exit(code=2)

    # Decide se vai pro wizard ou modo direto.
    interactive = project is None and not yes and not json_mode and sys.stdin.isatty()

    if interactive:
        try:
            answers = _wizard(console)
        except typer.Abort:
            console.warn("Cancelado.")
            raise typer.Exit(code=130) from None  # 130 = SIGINT convention
        target = answers.target
        mode = answers.mode
        integration_list = list(answers.integrations)
        init_git_flag = answers.init_git
    else:
        if project is None:
            console.error("Informe o nome do projeto ou rode em terminal interativo (TTY).")
            raise typer.Exit(code=2)
        target, _ = _validate_project_name(project)
        integration_list = integration or ["claude_code"]
        init_git_flag = init_git
        if merge:
            mode = MODE_MERGE
        elif force:
            mode = MODE_FORCE
        else:
            mode = MODE_NEW

    # Validações de existência conforme modo.
    if mode == MODE_NEW and target.exists() and not _is_dir_empty(target):
        console.error(
            f"{target} já existe e tem conteúdo. Use --merge (preservar) ou --force (apagar)."
        )
        raise typer.Exit(code=1)

    try:
        template = _resolve_template_dir()
        copied: list[str] = []
        skipped: list[str] = []

        if mode == MODE_FORCE and target.exists():
            shutil.rmtree(target)

        if mode == MODE_MERGE:
            target.mkdir(parents=True, exist_ok=True)
            copied, skipped = _overlay(template, target)
        else:  # MODE_NEW or MODE_FORCE
            shutil.copytree(template, target)
            copied = [str(p.relative_to(template)) for p in template.rglob("*") if p.is_file()]

        # git init (somente em MODE_NEW por default; merge não toca git existente).
        git_initialized = False
        if mode == MODE_NEW and init_git_flag:
            git_initialized = _init_git_repo(target)

        # Instala skills via integrations escolhidas (modo tolerante).
        skills_dir = _resolve_skills_dir()
        registry = None
        if skills_dir is not None:
            registry, skill_warnings = load_skill_registry(skills_dir, strict=False)
            for w in skill_warnings:
                console.warn(f"skill ignorada: {w}")

        installed_summary: list[dict[str, object]] = []
        for key in integration_list:
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

        # Módulos a ativar (wizard no modo interativo; --with no modo direto).
        if interactive:
            module_names = list(answers.modules)
        else:
            module_names = (
                [m.strip() for m in with_modules.split(",") if m.strip()] if with_modules else []
            )
        modules_applied: list[str] = []
        for _name in module_names:
            _info = get_module(_name)
            if _info is None:
                console.warn(f"Módulo '{_name}' desconhecido; ignorado.")
                continue
            _overlay(_info.path, target)
            modules_applied.append(_name)

        payload = {
            "project": str(target),
            "template": str(template),
            "mode": mode,
            "files_copied": len(copied),
            "files_skipped": len(skipped),
            "git_initialized": git_initialized,
            "integrations": installed_summary,
            "modules_applied": modules_applied,
            "version": __version__,
        }

        verb = {MODE_NEW: "criado", MODE_MERGE: "mesclado", MODE_FORCE: "recriado"}[mode]
        console.success(f"Projeto {verb} em {target}")
        if mode == MODE_MERGE and not json_mode:
            console.info(
                f"  [dim]{len(copied)} arquivo(s) novo(s), {len(skipped)} já existiam (preservados).[/dim]"
            )
        console.emit(payload)
        _render_next_steps(console, target, mode)
    except PrumoError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e


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
    """Health-check do projeto: estrutura, skills instaladas, integrations OK?

    Também reporta dependências externas (qmd, Zotero). Dependência externa
    ausente é informativa — não muda o exit code; só problemas estruturais
    (diretórios/skills faltando) retornam 1.
    """
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

    deps = check_external_deps()

    payload = {
        "project": str(target),
        "ok": not issues,
        "issues": issues,
        "external_deps": [d.as_dict() for d in deps],
        "version": __version__,
    }
    if issues:
        console.warn(f"{len(issues)} problema(s) estrutural(is) encontrado(s).")
        for i in issues:
            console.info(f"  • {i}")
    else:
        console.success("Estrutura do projeto OK.")

    console.info("")
    console.info("Dependências externas:")
    for d in deps:
        mark = "✓" if d.present else "○"
        console.info(f"  {mark} {d.name} — {d.detail}")
        if not d.present:
            console.info(f"      ↳ {d.hint}")

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


# ---------------------------------------------------------------------------
# prumo add (módulos opcionais via overlay não-destrutivo)
# ---------------------------------------------------------------------------


@app.command("add")
def add_command(
    module: Annotated[
        str | None,
        typer.Argument(help="Módulo a ativar (ex.: clinical, ml). Omita para listar/escolher."),
    ] = None,
    target: Annotated[
        Path, typer.Option("--target", "-t", help="Projeto alvo (default: cwd).")
    ] = Path("."),
    list_only: Annotated[
        bool, typer.Option("--list", help="Só lista módulos disponíveis.")
    ] = False,
    json_mode: Annotated[bool, typer.Option("--json", help="Saída JSON.")] = False,
) -> None:
    """Ativa um módulo no projeto (overlay não-destrutivo)."""
    console = Console(json_mode=json_mode)
    target = target.resolve()
    modules = discover_modules()

    if list_only or (module is None and (json_mode or not _stdin_isatty())):
        _emit_module_list(console, modules, target)
        return

    if module is None:
        module = _pick_module_interactive(console, modules, target)
        if module is None:
            console.warn("Nenhum módulo selecionado.")
            raise typer.Exit(code=130)

    info = get_module(module)
    if info is None:
        console.error(f"Módulo '{module}' não encontrado. Use `prumo add --list`.")
        raise typer.Exit(code=1)

    copied, skipped = _overlay(info.path, target)
    payload = {
        "module": module,
        "target": str(target),
        "files_copied": len(copied),
        "files_skipped": len(skipped),
    }
    console.success(f"Módulo '{module}' aplicado em {target}")
    if not json_mode and skipped:
        console.info(f"  [dim]{len(skipped)} arquivo(s) já existiam (preservados).[/dim]")
    console.emit(payload)


def _emit_module_list(console: Console, modules: list[ModuleInfo], target: Path) -> None:
    payload = {
        "modules": [
            {
                "name": m.name,
                "description": m.description,
                "when_to_use": m.when_to_use,
                "applied": is_applied(target, m),
            }
            for m in modules
        ]
    }
    if not console.json_mode:
        for m in modules:
            mark = " [green][aplicado][/green]" if is_applied(target, m) else ""
            console._rich.print(f"  [cyan]{m.name}[/cyan]{mark} — {m.description}")
    console.emit(payload)


def _pick_module_interactive(
    console: Console, modules: list[ModuleInfo], target: Path
) -> str | None:
    if not modules:
        console.warn("Nenhum módulo disponível.")
        return None
    console._rich.print("[bold]Módulos disponíveis:[/bold]")
    for i, m in enumerate(modules, 1):
        mark = " [green][aplicado][/green]" if is_applied(target, m) else ""
        console._rich.print(f"  [cyan]{i})[/cyan] {m.name}{mark} — {m.description}")
    raw = typer.prompt("Número do módulo (vazio para cancelar)", default="")
    raw = raw.strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
    except ValueError:
        return None
    if 0 <= idx < len(modules):
        return modules[idx].name
    return None


def _entry() -> None:
    """Entry point usado pelo ``project.scripts``."""
    try:
        app()
    except IntegrationError as e:
        print(f"prumo: integration error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _entry()
