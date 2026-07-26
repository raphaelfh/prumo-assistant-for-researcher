"""Servidor MCP local (stdio) do prumo — `prumo-review`.

Task 1 da Fase 3 da ponte docx↔CriticMarkup
(`docs/superpowers/plans/2026-07-24-ponte-fase3-mcp-reconciliador.md`):
expõe o ciclo de revisão (`reviews/<slug>/{review.md,events.yaml,
review-comments.yaml}`, produzidos por `domains.write.review.ingest`) para
agentes (Claude Code/Desktop) via `mcp` (SDK oficial, FastMCP —
`mcp==1.28.1`, ADR-0017 a registrar na Task 5).

Vive no TOPO do pacote (não em `domains/`) porque é a própria fachada do
protocolo — importa domínios livremente (`domains/write/export.py` para
resolução de caminho, `domains/write/schemas/v1.py` para os schemas), nunca
o contrário; `core/` permanece intocado (regra deste plano — "Global
Constraints").

Fachada fina sobre o domínio: nenhuma lógica de revisão mora aqui. Cada
tool resolve o caminho (`export.detect_project_root` + `export.slugify`,
MESMO padrão de path resolution de `review.ingest()`), lê o(s) artefato(s)
certo(s) de `reviews/<slug>/` e devolve dado plano (`dict`/`list[dict]`/
`str`) — nunca um objeto de domínio. Falha de resolução ou leitura (sidecars
de review ainda não gerados — a página nunca foi ingerida — ou raiz de
projeto não localizada) vira sempre `ValueError` pt-BR com o comando de
correção embutido: FastMCP serializa qualquer exceção do corpo da tool como
erro de protocolo (nunca um traceback cru chega ao agent-host), mas só
`ValueError` com mensagem pt-BR + comando dá ao agente algo acionável —
mesma disciplina de mensagem de `review._read_sidecars`, adaptada aqui para
sempre re-levantar como `ValueError` (nunca `FileNotFoundError` cru), pra
unificar o contrato de erro das 3 tools de leitura.

Task 1 entrega as 3 tools READ-ONLY (`review_status`, `review_events`,
`review_worklist`) + `run_stdio()` (chamado por `prumo mcp serve`,
`cli.py`). Task 2 acrescenta a única tool de ESCRITA (`propose_prose_edit`)
— fachada fina sobre `domains.write.review.propose_prose_edit` (lógica e
guardas I1/I3b moram no domínio; ver docstring de lá) — e traduz
`pydantic.ValidationError` (sidecar corrompido/fora do schema — achado da
review da Task 1) para o MESMO `ValueError` pt-BR+comando das demais
falhas, em vez de deixar vazar a mensagem crua do pydantic.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Literal

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from prumo_assist.core import criticmarkup
from prumo_assist.domains.write import review
from prumo_assist.domains.write.export import detect_project_root, slugify
from prumo_assist.domains.write.schemas.v1 import ReviewCommentsFile, ReviewEventsFile

server = FastMCP("prumo-review")

# Comando de correção embutido em toda mensagem de artefato de review
# ausente — mesma disciplina de `.claude/rules/code.md` ("comando de
# correção embutido na mensagem de erro").
_INGEST_HINT = "prumo write review ingest <reviewed.docx> --page <page>"


def _resolve_review_dir(page: str) -> Path:
    """`reviews/<slug>/` a partir de `page` — MESMO padrão de path
    resolution de `review.ingest()`: resolve o caminho absoluto, sobe até a
    raiz do projeto (`export.detect_project_root`) e computa o slug
    (`export.slugify`). Propaga o `FileNotFoundError` pt-BR de
    `detect_project_root` (sem raiz encontrada) — cada tool traduz para
    `ValueError` no `except` do próprio corpo."""
    page_path = Path(page).resolve()
    project_root = detect_project_root(page_path)
    slug = slugify(page_path, project_root)
    return project_root / "reviews" / slug


def _require_review_artifact(review_dir: Path, name: str) -> Path:
    """Caminho de `review_dir / name`, ou `FileNotFoundError` pt-BR (com o
    comando de ingest embutido) se o artefato ainda não existir — a página
    nunca foi ingerida, ou os artefatos de `reviews/` foram apagados."""
    artifact = review_dir / name
    if not artifact.is_file():
        raise FileNotFoundError(
            f"Artefato de review ausente: {artifact}. A página ainda não foi "
            "ingerida (ou os artefatos de `reviews/` foram apagados) — rode "
            f"`{_INGEST_HINT}` primeiro."
        )
    return artifact


def _read_review_md(review_dir: Path) -> str:
    return _require_review_artifact(review_dir, "review.md").read_text(encoding="utf-8")


def _corrupt_sidecar_message(path: Path) -> str:
    """Mensagem pt-BR única para sidecar (events.yaml/review-comments.yaml)
    corrompido ou fora do schema — traduz `pydantic.ValidationError` (achado
    da review da Task 1: o traceback cru do pydantic vazava pelas tools de
    leitura, sem o comando de correção embutido que toda outra falha deste
    módulo garante)."""
    return f"sidecar corrompido ({path}): re-rode `{_INGEST_HINT}` para regenerá-lo."


def _read_events(page: str) -> ReviewEventsFile:
    """Wrapper fino sobre `review.read_events_file` (achado Important #3 do
    review da Fase 3: esta função duplicava — DIVERGENTE de `cli.py` — a
    leitura+validação de `events.yaml`; consolidada no domínio). Só traduz
    `FileNotFoundError` (sidecar ausente ou raiz de projeto não localizada)
    para `ValueError`, mesma disciplina de toda tool deste módulo;
    `ValueError` de sidecar corrompido já sai pronto do domínio."""
    try:
        return review.read_events_file(Path(page).resolve())
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc


def _read_comments(review_dir: Path) -> ReviewCommentsFile:
    path = _require_review_artifact(review_dir, "review-comments.yaml")
    try:
        return ReviewCommentsFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValidationError as exc:
        raise ValueError(_corrupt_sidecar_message(path)) from exc


@server.tool()
def review_status(page: str) -> dict[str, Any]:
    """Contagens do ciclo de revisão de `page`: marcas pendentes em
    `review.md` (`criticmarkup.parse`), eventos por `kind`, comentários
    extraídos do docx revisado e drops de citação (`kind ==
    "citation-drop"`) ainda pendentes de confirmação no `apply`."""
    try:
        review_dir = _resolve_review_dir(page)
        review_md_text = _read_review_md(review_dir)
        events_file = _read_events(page)
        comments_file = _read_comments(review_dir)
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc

    events_by_kind = dict(Counter(event.kind for event in events_file.events))
    pending_drops = sum(
        1 for event in events_file.events if event.kind == review.EVENT_KIND_CITATION_DROP
    )

    return {
        "page": events_file.page,
        "pending_marks": len(criticmarkup.parse(review_md_text)),
        "events_by_kind": events_by_kind,
        "comments": len(comments_file.comments),
        "pending_drops": pending_drops,
    }


@server.tool()
def review_events(page: str) -> list[dict[str, Any]]:
    """`events.yaml` completo de `page` — cada evento serializado via
    `model_dump(mode="json")`, na mesma ordem em que `ingest()` os gravou."""
    events_file = _read_events(page)
    return [event.model_dump(mode="json") for event in events_file.events]


@server.tool()
def review_worklist(page: str) -> str:
    """Conteúdo cru de `review.md` de `page` — o worklist vivo do ciclo de
    revisão (frontmatter + corpo com as marcas CriticMarkup ainda
    pendentes)."""
    try:
        review_dir = _resolve_review_dir(page)
        return _read_review_md(review_dir)
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc


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
    `[[@key]]`) e a validação de `anchor_excerpt`/`position` moram no
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
