"""Servidor MCP local (stdio) do prumo — `prumo-review`.

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

from prumo_assist.domains.write import review

server = FastMCP("prumo-review")

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
def review_events(page: str) -> list[dict[str, Any]]:
    """`events.yaml` completo de `page` — cada evento serializado via
    `model_dump(mode="json")`, na mesma ordem em que `ingest()` os gravou."""
    events_file = _domain_read(review.read_events_file, page)
    return [event.model_dump(mode="json") for event in events_file.events]


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


def run_stdio() -> None:
    """Inicia o transporte stdio do servidor MCP `prumo-review` — bloqueia
    até o cliente encerrar a conexão. Chamado por `prumo mcp serve`
    (`cli.py`, fachada fina)."""
    server.run()
