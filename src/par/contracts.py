"""Registry dos contratos que o CLI valida (spec 2026-09-12, D3).

Subagents devolvem JSON; quem o persiste valida no próprio comando (``prumo paper
extract`` valida ``PaperCallout/v1``). Os contratos que ninguém persiste —
veredito de suporte e relatório de revisão — precisam de um consumidor
determinístico para que "JSON inválido → 1 retry com o erro" seja verificável
(Princípio II). É este módulo, exposto como ``prumo validate <schema>``.

Vive no topo do pacote, como ``mcp_server.py`` e ``status.py`` (ADR-0017): lê
schemas de mais de um domínio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from par import PrumoError
from par.domains.paper.schemas.v1 import PaperCallout, SupportReport
from par.domains.write.schemas.v1 import PeerReviewReport

__all__ = ["CONTRACTS", "validate_contract"]

_QUOTE_MAX_WORDS = 25

CONTRACTS: dict[str, type[BaseModel]] = {
    "PaperCallout/v1": PaperCallout,
    "SupportReport/v1": SupportReport,
    "PeerReviewReport/v1": PeerReviewReport,
}


def validate_contract(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Valida ``payload`` contra o contrato ``name`` e devolve a forma normalizada.

    Raises:
        PrumoError: contrato desconhecido, ou payload que não valida — a mensagem
            lista até cinco campos com erro e o comando para validar de novo.
    """
    model = CONTRACTS.get(name)
    if model is None:
        raise PrumoError(
            f"contrato '{name}' desconhecido. Conhecidos: {', '.join(sorted(CONTRACTS))}."
        )
    try:
        obj = model.model_validate(payload)
    except ValidationError as exc:
        erros = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(raiz)'}: {err['msg'].rstrip('.')}"
            for err in exc.errors()[:5]
        )
        raise PrumoError(
            f"JSON não valida contra {name}: {erros}. Corrija esses campos e valide de novo "
            f"com `prumo validate {name}`."
        ) from exc
    if isinstance(obj, PeerReviewReport):
        _check_quotes(obj)
    return obj.model_dump(mode="json")


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _check_quotes(report: PeerReviewReport) -> None:
    """Confere cada ``quote`` e cada ``citekey`` contra o texto de ``draft_path`` (Princípio II).

    Regras: ``quote`` com no máximo ``_QUOTE_MAX_WORDS`` palavras e substring literal
    do draft, com espaços normalizados; ``citekey`` de ``citation_checks`` presente
    no draft como ``@citekey``. Sem ``quote`` nem ``citation_checks``, o draft nem é lido.
    """
    items: list[tuple[str, str, str]] = [
        (f"{field}.{i}", item.section, item.quote)
        for field in (
            "critical_weaknesses",
            "minor_weaknesses",
            "claims_without_evidence",
            "citation_checks",
        )
        for i, item in enumerate(getattr(report, field))
        if item.quote is not None
    ]
    if not items and not report.citation_checks:
        return
    fix = "Corrija e valide de novo com `prumo validate PeerReviewReport/v1`."
    path = Path(report.draft_path).expanduser()
    try:
        draft = _normalize(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise PrumoError(
            f"não consegui ler draft_path '{report.draft_path}' para conferir os quotes "
            f"({exc.__class__.__name__}). Passe o caminho absoluto do draft. {fix}"
        ) from exc
    erros: list[str] = []
    for loc, section, quote in items:
        norm = _normalize(quote)
        if len(norm.split()) > _QUOTE_MAX_WORDS:
            erros.append(f"{loc} (seção '{section}'): quote passa de {_QUOTE_MAX_WORDS} palavras")
        elif norm not in draft:
            erros.append(f"{loc} (seção '{section}'): quote não é literal do draft: \"{quote}\"")
    for i, check in enumerate(report.citation_checks):
        if f"@{check.citekey}" not in draft:
            erros.append(
                f"citation_checks.{i}: citekey '{check.citekey}' não aparece no draft como "
                f"[@{check.citekey}]"
            )
    if erros:
        raise PrumoError(f"quotes inválidos em PeerReviewReport/v1: {'; '.join(erros)}. {fix}")
