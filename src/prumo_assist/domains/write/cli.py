"""Subcomandos ``prumo write *``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from prumo_assist import PrumoError
from prumo_assist.core.cli_io import parse_json_list, read_stdin_text
from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.write import comments, compose, export, review
from prumo_assist.domains.write.schemas.v1 import WriteKind, WriteMode

write_app = typer.Typer(
    name="write",
    help="Escrita: export Pandoc/Typst, composição multi-página, extração de comentários.",
    no_args_is_help=True,
)

_WRITE_KINDS = ("paper", "projeto-cep", "statistics", "scientific")
_WRITE_MODES = ("drafts", "into", "out")

FIRST_USE_DOCX_NOTE = (
    "Primeiro uso no Word: abra o arquivo com o plugin do Zotero instalado e "
    "use Zotero → Refresh para atualizar citações e bibliografia. As "
    "preferências do documento já vão embutidas (ZOTERO_PREF) — o diálogo "
    "'Document Preferences' não deve abrir."
)


def _truncate_detail(detail: str, limit: int = 80) -> str:
    """Trunca ``detail`` em ``limit`` caracteres pro modo lista/checklist do
    comando ``events`` — reticências (``…``) só aparecem quando o corte de
    fato remove conteúdo (Minor do review da Fase 3: ``detail[:80]`` cru
    cortava sem sinalizar, indistinguível de um detail que coubesse
    inteiro)."""
    return detail if len(detail) <= limit else f"{detail[:limit]}…"


review_app = typer.Typer(
    help="Round-trip docx↔CriticMarkup do coautor: ingest da revisão, aplicação de decisões.",
    no_args_is_help=True,
)
write_app.add_typer(review_app, name="review")


@write_app.command("export")
def export_command(
    page: Annotated[Path, typer.Argument(help="Página .md a exportar.")],
    to: Annotated[str, typer.Option("--to", help="docx | typst | pdf | html")] = "docx",
    style: Annotated[str, typer.Option("--style", help="Estilo CSL (default: apa).")] = "apa",
    bib: Annotated[Path | None, typer.Option("--bib")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    template: Annotated[
        Path | None,
        typer.Option("--template", help="Template para typst/pdf (ignorado em docx)."),
    ] = None,
    reference_doc: Annotated[
        Path | None,
        typer.Option(
            "--reference-doc",
            help="Template .docx (estilos/cabeçalho/rodapé) — somente formato docx.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Exporta uma página Markdown via Pandoc + CSL → DOCX/Typst/PDF/HTML."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        page_resolved = page.resolve()

        result = export.export(
            page=page_resolved,
            style=style,
            to=to,
            out_dir=out_dir.resolve() if out_dir else None,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            reference_doc=reference_doc.resolve() if reference_doc else None,
        )
        console.success(f"exportado: {result}")
        if to == "docx":
            console.info(FIRST_USE_DOCX_NOTE)
        console.emit({"page": str(page_resolved), "output": str(result), "format": to})


@write_app.command("compose")
def compose_command(
    index: Annotated[Path, typer.Option("--index", help="Index file com pages: [...]")],
    to: Annotated[str, typer.Option("--to")] = "docx",
    style: Annotated[str | None, typer.Option("--style")] = None,
    bib: Annotated[Path | None, typer.Option("--bib")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    template: Annotated[
        Path | None,
        typer.Option("--template", help="Template para typst/pdf (ignorado em docx)."),
    ] = None,
    reference_doc: Annotated[
        Path | None,
        typer.Option(
            "--reference-doc",
            help="Template .docx (estilos/cabeçalho/rodapé) — somente formato docx.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compõe múltiplas páginas (frontmatter ``pages: [...]``) em um documento único."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        index_resolved = index.resolve()

        result = export.compose(
            index=index_resolved,
            to=to,
            style=style,
            out_dir=out_dir.resolve() if out_dir else None,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            reference_doc=reference_doc.resolve() if reference_doc else None,
        )
        console.success(f"composto: {result}")
        if to == "docx":
            console.info(FIRST_USE_DOCX_NOTE)
        console.emit({"index": str(index_resolved), "output": str(result), "format": to})


@write_app.command("list-styles")
def list_styles_command(
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista CSLs disponíveis em ``~/Zotero/styles/``."""
    with cli_run(json_mode=json_mode) as console:
        styles = export.list_styles()
        if not styles:
            console.warn("Nenhum estilo CSL em ~/Zotero/styles/.")
        console.emit({"styles": styles})


@write_app.command("zettlr-profile")
def zettlr_profile_command(
    path: Annotated[Path, typer.Option("--path", help="Raiz do pj_*.")] = Path("."),
    style: Annotated[str, typer.Option("--style", help="Estilo CSL (default: apa).")] = "apa",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """(Re)gera o perfil de export docx do Zettlr (defaults file) do projeto."""
    with cli_run(json_mode=json_mode, catches=(OSError,)) as console:
        from prumo_assist.domains.write.zettlr import generate_profile

        out = generate_profile(path.resolve(), style=style)
        console.success(
            f"Perfil Zettlr gerado: {out}. Importe uma vez no Zettlr "
            "(Assets Manager → defaults files); re-rode este comando se o prumo for reinstalado."
        )
        console.emit({"profile": str(out)})


@write_app.command("extract-comments")
def extract_comments_command(
    docx: Annotated[Path, typer.Argument(help="Caminho do .docx revisado.")],
    out_dir: Annotated[
        Path, typer.Option("--out-dir", help="Diretório do checklist (default: docs/comments).")
    ] = Path("docs/comments"),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Extrai comentários + track changes do ``.docx`` em checklist Markdown."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        out = comments.extract_to_file(docx.resolve(), out_dir.resolve())
        console.success(f"checklist: {out}")
        console.emit({"docx": str(docx.resolve()), "output": str(out)})


@write_app.command("disclosure")
def disclosure_command(
    path: Annotated[Path, typer.Argument(help="Raiz do pj_* a escanear.")] = Path("."),
    lang: Annotated[str, typer.Option("--lang", help="Idioma da declaração: en | pt.")] = "en",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Gera a declaração de uso de IA a partir da proveniência dos artefatos."""
    with cli_run(json_mode=json_mode) as console:
        from prumo_assist.domains.write.disclosure import generate_disclosure

        disc = generate_disclosure(root=path.resolve())
        if json_mode:
            console.emit(disc.model_dump())
        else:
            console.emit(disc.statement_pt if lang == "pt" else disc.statement_en)


@write_app.command("list-templates")
def list_templates_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista templates resolvíveis (project overrides + plugin defaults)."""
    with cli_run(json_mode=json_mode) as console:
        result: dict[str, dict[str, str | None]] = {}
        for kind in _WRITE_KINDS:
            candidates = compose.template_candidates(
                pj_path=path.resolve(), kind=cast(WriteKind, kind)
            )
            result[kind] = {
                label: str(p) if p is not None and p.exists() else None
                for label, p in candidates.items()
            }
        console.emit(result)


@write_app.command("prep")
def prep_command(
    kind: Annotated[
        str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")
    ] = "paper",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    lang: Annotated[
        str | None, typer.Option("--lang", help="pt-BR|en-US. Omitido resolve pela cascata.")
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lê inputs do projeto + resolve template e idioma (contexto pra escrita) num só passo."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        result = compose.prep(path.resolve(), kind=cast(WriteKind, kind), lang=lang)
        console.success(
            f"Contexto pronto (template {result.template_path.name}, idioma {result.language})."
        )
        console.emit(
            {
                "inputs": result.inputs.model_dump(mode="json"),
                "template_path": str(result.template_path),
                "language": result.language,
                "language_source": result.language_source,
            }
        )


@write_app.command("draft")
def draft_command(
    kind: Annotated[str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    slug: Annotated[str, typer.Option("--slug", help="Slug do output.")],
    mode: Annotated[str, typer.Option("--mode", help="drafts|into|out.")] = "drafts",
    section: Annotated[
        str, typer.Option("--section", help="Nome da seção alvo (obrigatório no modo into).")
    ] = "",
    sections: Annotated[
        str, typer.Option("--sections", help="Array JSON de seções preenchidas.")
    ] = "[]",
    into: Annotated[str, typer.Option("--into", help="Caminho destino (modo into).")] = "",
    out: Annotated[str, typer.Option("--out", help="Caminho destino (modo out).")] = "",
    force: Annotated[bool, typer.Option("--force", help="Sobrescreve no modo out.")] = False,
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Grava o draft (markdown via stdin) conforme o modo; reporta o WriteOutput."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, FileExistsError)
    ) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        if mode not in _WRITE_MODES:
            raise PrumoError(f"--mode deve ser um de {list(_WRITE_MODES)}.")
        content = read_stdin_text()
        sections_list = parse_json_list(sections, "--sections")
        result = compose.write_output(
            content=content,
            pj_path=path.resolve(),
            kind=cast(WriteKind, kind),
            mode=cast(WriteMode, mode),
            section=section or None,
            date=date,
            slug=slug,
            into=Path(into) if into else None,
            out=Path(out) if out else None,
            force=force,
            sections_filled=sections_list,
        )
        console.success(
            f"Draft gravado em {result.output_path} ({result.words_generated} palavras)."
        )
        console.emit(result.model_dump(mode="json"))


@review_app.command("ingest")
def review_ingest_command(
    reviewed_docx: Annotated[Path, typer.Argument(help="Caminho do .docx revisado pelo coautor.")],
    page: Annotated[
        Path, typer.Option("--page", help="Página .md original — a mesma que gerou o docx.")
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Re-ingere mesmo com marcas pendentes no worklist (DESCARTA as pendências).",
        ),
    ] = False,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Ingere um docx revisado: guardas + transplante determinístico → ``reviews/<slug>/review.md``."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        page_resolved = page.resolve()
        reviewed_docx_resolved = reviewed_docx.resolve()
        result = review.ingest(reviewed_docx_resolved, page_resolved, force=force)
        pending_drops = review.count_pending_drops(result.events.events)

        console.success(f"ingerido: {result.review_md}")
        console.info(
            f"{result.marks_applied} marca(s) aplicada(s), {len(result.events.events)} "
            f"evento(s), {len(result.comments.comments)} comentário(s), {pending_drops} "
            "drop(s) de citação pendente(s) de confirmação."
        )
        console.info(
            f"Próximo passo: revise {result.review_md} e rode `prumo write review apply "
            f"--page {page_resolved} ...` com o modo de decisão desejado."
        )
        console.emit(
            {
                "page": str(page_resolved),
                "reviewed_docx": str(reviewed_docx_resolved),
                "review_md": str(result.review_md),
                "marks_applied": result.marks_applied,
                "events": len(result.events.events),
                "comments": len(result.comments.comments),
                "pending_drops": pending_drops,
            }
        )


@review_app.command("events")
def review_events_command(
    page: Annotated[
        Path, typer.Option("--page", help="Página .md original — a mesma passada ao ingest.")
    ],
    checklist: Annotated[
        bool, typer.Option("--checklist", help="Formato checklist numerado.")
    ] = False,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista eventos de revisão de ``reviews/<slug>/events.yaml`` (modo degradado sem agente).

    Sem flags: lista simples (kind, detail resumido).
    --checklist: checklist numerado pt-BR com AÇÃO por kind.
    --json: estrutura completa em JSON.
    """
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        page_resolved = page.resolve()
        events_file = review.read_events_file(page_resolved)

        if json_mode:
            console.emit(events_file.model_dump(mode="json"))
        elif checklist:
            # Checklist numerado pt-BR com AÇÃO por kind — as constantes
            # EVENT_KIND_* de `review.py` são a fonte única do vocabulário
            # (o mapeamento hardcoded antigo shipou comparando kinds que
            # nunca são gravados — Fix pós-review da Fase 3, Crítico #1).
            lines = []
            for i, event in enumerate(events_file.events, start=1):
                lines.append(f"{i}. {event.kind}: {_truncate_detail(event.detail)}")
                if event.kind == review.EVENT_KIND_CITATION_DROP:
                    action = f"   AÇÃO: confirme com --confirm-citation-drops {event.occ_id}"
                elif event.kind in (
                    review.EVENT_KIND_UNANCHORED_MARK,
                    review.EVENT_KIND_AMBIGUOUS_ANCHOR,
                    review.EVENT_KIND_NON_IDENTITY_SPAN,
                ):
                    action = (
                        "   AÇÃO: edite review.md inserindo a mudança manualmente "
                        "no ponto certo, ou rode a skill /prumo-assist:review-reconcile; "
                        "após resolver (manualmente ou por proposta da skill), remova "
                        "o evento de events.yaml"
                    )
                elif event.kind == review.EVENT_KIND_CITATION_TOUCHED_PROSE:
                    action = "   AÇÃO: decisão humana: rejeite no Word ou edite a fonte"
                elif event.kind == review.EVENT_KIND_APPLIED:
                    action = "   AÇÃO: nenhuma ação — histórico"
                else:
                    action = f"   AÇÃO: revise este evento (kind desconhecido: {event.kind})"
                lines.append(action)
            console.emit("\n".join(lines))
        else:
            # Lista simples: kind, detail resumido
            for event in events_file.events:
                console.emit(f"{event.kind}: {_truncate_detail(event.detail)}")


@review_app.command("apply")
def review_apply_command(
    page: Annotated[
        Path, typer.Option("--page", help="Página .md original — a mesma passada ao ingest.")
    ],
    accept_all: Annotated[
        bool, typer.Option("--accept-all", help="Aceita todas as marcas pendentes.")
    ] = False,
    reject_all: Annotated[
        bool, typer.Option("--reject-all", help="Rejeita todas as marcas pendentes.")
    ] = False,
    by_author: Annotated[
        str | None, typer.Option("--by-author", help="Decide só as marcas deste autor.")
    ] = None,
    mark: Annotated[
        int | None, typer.Option("--mark", help="Decide só a marca deste índice (0-based).")
    ] = None,
    accept: Annotated[
        bool, typer.Option("--accept", help="Junto de --by-author/--mark: aceita a(s) marca(s).")
    ] = False,
    reject: Annotated[
        bool,
        typer.Option("--reject", help="Junto de --by-author/--mark: rejeita a(s) marca(s)."),
    ] = False,
    confirm_citation_drops: Annotated[
        str | None,
        typer.Option(
            "--confirm-citation-drops",
            help="occ_id(s) de citação deletada a confirmar, separados por vírgula.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Aplica as decisões de ``reviews/<slug>/review.md`` de volta na página original."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        from datetime import UTC, datetime

        if accept and reject:
            raise PrumoError("--accept e --reject são mutuamente exclusivos — escolha um.")

        decision: bool | None = True if accept else (False if reject else None)

        marks: dict[int, bool] | None = None
        if mark is not None:
            if decision is None:
                raise PrumoError("--mark exige --accept ou --reject junto.")
            marks = {mark: decision}

        drops = (
            [item.strip() for item in confirm_citation_drops.split(",") if item.strip()]
            if confirm_citation_drops
            else None
        )

        result = review.apply_review(
            page.resolve(),
            accept_all=accept_all,
            reject_all=reject_all,
            by_author=by_author,
            author_decision=decision if by_author is not None else None,
            marks=marks,
            confirm_citation_drops=drops,
            today=datetime.now(UTC).date().isoformat(),
        )
        console.success(
            f"aplicado: {result.applied} marca(s) aceita(s), {result.rejected} marca(s) "
            f"rejeitada(s), {len(result.drops_confirmed)} drop(s) de citação confirmado(s)."
        )
        console.emit(
            {
                "page": str(result.page),
                "applied": result.applied,
                "rejected": result.rejected,
                "drops_confirmed": result.drops_confirmed,
            }
        )


def zettlr_export_entry() -> None:
    """Console-script pro custom command do Zettlr: `prumo-zettlr-export <arquivo.md>`.

    O Zettlr invoca o comando com o caminho absoluto do arquivo
    selecionado como único argumento e mostra a saída ao usuário.
    Caminho canônico: mesmas guardas do ``prumo write export --to docx``.
    """
    import sys

    try:
        with cli_run(json_mode=False, catches=(FileNotFoundError, ValueError)) as console:
            if len(sys.argv) != 2:
                raise PrumoError("uso: prumo-zettlr-export <arquivo.md>")
            page = Path(sys.argv[1]).resolve()
            result = export.export(page=page, to="docx")
            console.success(f"exportado: {result}")
    except typer.Exit as e:
        # Entrypoint fora do dispatch do Click (é um `[project.scripts]` cru,
        # não um app Typer/Click): sem isso, o `typer.Exit` levantado por
        # `cli_run` em erro escaparia como traceback cru no painel do Zettlr,
        # mesmo após a mensagem pt-BR já ter sido impressa por `console.error`.
        raise SystemExit(e.exit_code) from None
