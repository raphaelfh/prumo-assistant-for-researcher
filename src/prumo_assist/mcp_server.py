"""Servidor MCP local (stdio) do prumo — `prumo`.

Task 1 da Fase 3 da ponte docx↔CriticMarkup
(`docs/superpowers/plans/2026-07-24-ponte-fase3-mcp-reconciliador.md`):
expõe o ciclo de revisão (`reviews/<slug>/{review.md,events.yaml,
review-comments.yaml}`, produzidos por `domains.write.review.ingest`) para
agentes (Claude Code/Desktop) via `mcp` (SDK oficial, FastMCP —
`mcp==1.28.1`, ADR-0017 a registrar na Task 5).

Vive no TOPO do pacote (não em `domains/`) porque é a própria fachada do
protocolo — importa domínios livremente (`domains/write/review.py`, os
leitores read-side e a proposta de edição), nunca o contrário; `core/`
permanece intocado (regra deste plano — "Global Constraints").

Fachada fina sobre o domínio: nenhuma lógica de revisão mora aqui. Cada
tool delega ao leitor de domínio correspondente (`review.status`/
`read_events_file`/`read_worklist` — resolução de caminho, validação de
schema, agregação de contagens e mensagens pt-BR moram lá, fonte única;
consolidação do achado do /simplify 2026-07-25, que encontrou a fachada
re-implementando essas leituras com wording divergente) e devolve dado
plano (`dict`/`list[dict]`/`str`) — nunca um objeto de domínio. A única
adaptação local é de contrato de erro: FastMCP serializa qualquer exceção
do corpo da tool como erro de protocolo (nunca um traceback cru chega ao
agent-host), mas só `ValueError` com mensagem pt-BR + comando dá ao agente
algo acionável — então `_domain_read` re-levanta o `FileNotFoundError`
pt-BR do domínio (sidecar ausente ou raiz de projeto não localizada) como
`ValueError`, unificando o contrato de erro das tools; `ValueError` de
sidecar corrompido já sai pronto do domínio.

Desde 2026-08-23 o servidor cobre também o domínio `paper` (7 tools, uma
delas mutante — ver `MUTATING_TOOLS`), e por isso deixou de se chamar
`prumo-review`: o nome é o prefixo das tools no agent-host
(`mcp__prumo__paper_find`). ADR emendando a 0017.

Task 1 entrega as 3 tools READ-ONLY (`review_status`, `review_events`,
`review_worklist`) + `run_stdio()` (chamado por `prumo mcp serve`,
`cli.py`). Task 2 acrescenta a única tool de ESCRITA (`propose_prose_edit`)
— fachada fina sobre `domains.write.review.propose_prose_edit` (lógica e
guardas I1/I3b moram no domínio; ver docstring de lá). A tradução de
`pydantic.ValidationError` pra `ValueError` pt-BR+comando (sidecar
corrompido/fora do schema — achado da review da Task 1) mora hoje nos
leitores de domínio, não mais aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypeVar

from mcp.server.fastmcp import FastMCP

from prumo_assist import PrumoError
from prumo_assist._version import __version__
from prumo_assist.domains.paper import api as paper_api
from prumo_assist.domains.write import review

server = FastMCP("prumo")

# `serverInfo.version` do handshake identifica o PRUMO, não o SDK.
# O FastMCP não aceita versão no construtor — a ADR-0017 registrou isso como
# dívida — mas o `Server` de baixo nível lê `self.version` em
# `create_initialization_options()` (`server_version=self.version if
# self.version else pkg_version("mcp")`), e `version` é atributo público dele.
# O acoplamento restante é ao NOME `_mcp_server`; se o SDK mudar,
# `test_server_reports_the_prumo_version_not_the_sdk_version` falha alto.
server._mcp_server.version = __version__

_ReadT = TypeVar("_ReadT")


def _domain_read(reader: Callable[[Path], _ReadT], page: str) -> _ReadT:
    """Chama um leitor read-side do domínio (`review.status`/
    `read_events_file`/`read_worklist`) traduzindo só o tipo do erro:
    `FileNotFoundError` pt-BR (sidecar ausente ou raiz de projeto não
    localizada) vira `ValueError` com a MESMA mensagem — ver docstring do
    módulo. `ValueError` de sidecar corrompido já sai pronto do domínio."""
    try:
        return reader(Path(page).resolve())
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc


@server.tool()
def review_status(page: str) -> dict[str, Any]:
    """Contagens do ciclo de revisão de `page`: marcas pendentes em
    `review.md`, eventos por `kind`, comentários extraídos do docx revisado
    e drops de citação (`kind == "citation-drop"`) ainda pendentes de
    confirmação no `apply` — fachada fina sobre `review.status`."""
    return _domain_read(review.status, page)


@server.tool()
def review_events(page: str) -> dict[str, Any]:
    """`events.yaml` completo de `page`, no envelope versionado
    `ReviewEventsFile/v1` (`schema_version`, `page`, `events`) — o MESMO que o
    `--json` do CLI emite. Os eventos vêm na ordem em que `ingest()` os
    gravou."""
    events_file = _domain_read(review.read_events_file, page)
    return events_file.model_dump(mode="json")


@server.tool()
def review_worklist(page: str) -> str:
    """Conteúdo cru de `review.md` de `page` — o worklist vivo do ciclo de
    revisão (frontmatter + corpo com as marcas CriticMarkup ainda
    pendentes)."""
    return _domain_read(review.read_worklist, page)


@server.tool()
def propose_prose_edit(
    page: str,
    *,
    anchor_excerpt: str,
    position: Literal["before", "after", "replace"],
    kind: Literal["ins", "del", "sub"],
    a: str = "",
    b: str = "",
    author: str = "agente",
) -> dict[str, Any]:
    """Insere uma marca CriticMarkup PENDENTE no worklist (`review.md`) de
    `page`, proposta por um agente — a ÚNICA tool de ESCRITA deste servidor.

    Fachada fina sobre `domains.write.review.propose_prose_edit`: zero
    lógica de revisão aqui, só tradução `str` (protocolo MCP) -> `Path`
    (domínio) e de volta a dado plano. A proposta NUNCA aplica nada
    sozinha — vira marca pendente que um humano decide via `prumo write
    review apply --by-author agente` (ou `apply_review(by_author="agente",
    ...)`); as guardas I1/I3b (payload de citação, âncora que toca
    citação (`[@key]` ou `@key`)) e a validação de `anchor_excerpt`/`position` moram no
    domínio e chegam aqui como `ValueError` pt-BR já pronto — esta tool só
    traduz `FileNotFoundError` (raiz do projeto ou worklist ausente, mesmo
    padrão das 3 tools read-only acima) para o mesmo tipo.

    Devolve `{"review_md": <caminho>, "inserted_mark_index": <índice>}` —
    dado plano (nunca o `ProposalResult` de domínio), mesma disciplina das
    outras tools deste módulo."""
    try:
        result = review.propose_prose_edit(
            Path(page),
            anchor_excerpt=anchor_excerpt,
            position=position,
            kind=kind,
            a=a,
            b=b,
            author=author,
        )
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc

    return {"review_md": str(result.review_md), "inserted_mark_index": result.inserted_mark_index}


# ---------------------------------------------------------------------------
# Domínio `paper` — mesmas fachadas finas, mesmo contrato de erro
# ---------------------------------------------------------------------------

#: Tools que mudam estado FORA do processo. `paper_connect` chama
#: `autoexport.add` no Zotero do usuário (ADR-0020: "a primeira e única
#: chamada MUTANTE"); `propose_prose_edit` grava marca pendente no worklist.
#: Guarda de desenho coberta por teste — tool nova que mute algo tem de
#: entrar aqui conscientemente.
MUTATING_TOOLS = {"propose_prose_edit", "paper_connect"}


def _paper_call(op: Callable[..., _ReadT], *args: Any, **kwargs: Any) -> _ReadT:
    """Chama uma operação de ``domains.paper`` unificando o contrato de erro.

    Mesma disciplina de :func:`_domain_read`: o agente só recebe
    ``ValueError`` com a mensagem pt-BR do domínio (que já embute o comando
    de correção), nunca traceback. ``PaperError`` e demais ``PrumoError`` já
    saem prontos do domínio; ``FileNotFoundError`` (bib ou pj ausente) também.
    """
    try:
        return op(*args, **kwargs)
    except (FileNotFoundError, PrumoError) as exc:
        raise ValueError(str(exc)) from exc


@server.tool()
def paper_sync(pj_path: str) -> dict[str, Any]:
    """``.bib`` → ``docs/references/papers/<citekey>/_meta.md`` (layout α).

    Fachada fina sobre ``domains.paper.sync``. Idempotente: relê o ``.bib``
    exportado pelo Better BibTeX e reconcilia as notas."""
    return _paper_call(paper_api.sync, Path(pj_path).resolve())


@server.tool()
def paper_find(pj_path: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """Busca fuzzy sobre ``.bib`` + notas (autor, título, ano, tldr).

    Mesmo shape do ``--json`` do CLI (``query`` + ``results``)."""
    results = _paper_call(paper_api.find, Path(pj_path).resolve(), query, top_k=top_k)
    return {"query": query, "results": results}


@server.tool()
def paper_lint(pj_path: str) -> dict[str, Any]:
    """Auditoria do acervo: bib↔notas↔pdfs, citekeys quebradas, symlink de PDF
    pendurado, mais de um ``role: primary``."""
    return _paper_call(paper_api.lint, Path(pj_path).resolve())


@server.tool()
def paper_graph(pj_path: str) -> dict[str, Any]:
    """Grafo passivo de citação: lê ``[@key]``/``@key`` no corpo das notas e
    popula ``cites:`` no YAML."""
    return _paper_call(paper_api.update_graph, Path(pj_path).resolve())


@server.tool()
def paper_verify_refs(pj_path: str, page: str | None = None) -> dict[str, Any]:
    """Verifica as referências do bib: existência (Crossref), retração
    (Crossref/PubMed) e título.

    ``page`` restringe às citekeys de uma página ``.md`` — recomendado, porque
    o acervo inteiro é lento. A verificação profunda (``--deep``, que dispara
    ``uvx``) fica fora desta tool de propósito: subprocess externo não é
    fachada fina."""
    return _paper_call(
        paper_api.verify_refs,
        Path(pj_path).resolve(),
        page=Path(page).resolve() if page is not None else None,
    )


@server.tool()
def paper_sync_all(pj_path: str) -> dict[str, Any]:
    """``sync`` + ``sync-pdfs`` + ``sync-annotations`` + ``sync-notes`` numa
    passada. Anotações e notas degradam para warning se o Zotero estiver
    fechado ou com a API local desligada; o resto segue."""
    return _paper_call(paper_api.sync_all, Path(pj_path).resolve())


@server.tool()
def paper_connect(pj_path: str, collection: str, library: str | None = None) -> dict[str, Any]:
    """Liga ``docs/references/_references.bib`` a uma coleção do Zotero via
    ``autoexport.add`` do Better BibTeX.

    MUTA O ZOTERO DO USUÁRIO — ver :data:`MUTATING_TOOLS`. A guarda contra
    coleção-fantasma mora no domínio (ADR-0020): ``autoexport.add`` CRIA a
    coleção se o caminho não existir, então ``find_collection`` confirma a
    existência antes, e a mensagem de erro afirma "NADA foi criado". Nome
    ambíguo entre bibliotecas exige ``library``."""
    result = _paper_call(
        paper_api.connect_collection,
        Path(pj_path).resolve(),
        collection,
        library=library,
    )
    return {
        "collection": result.collection.path,
        "library": result.collection.library,
        "bib_path": str(result.bib_path),
        "exported": result.exported,
    }


def run_stdio() -> None:
    """Inicia o transporte stdio do servidor MCP `prumo` — bloqueia
    até o cliente encerrar a conexão. Chamado por `prumo mcp serve`
    (`cli.py`, fachada fina)."""
    server.run()
