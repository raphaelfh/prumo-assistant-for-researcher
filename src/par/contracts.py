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

from typing import Any

from pydantic import BaseModel, ValidationError

from par import PrumoError
from par.domains.paper.schemas.v1 import PaperCallout, SupportReport
from par.domains.write.schemas.v1 import PeerReviewReport

__all__ = ["CONTRACTS", "validate_contract"]

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
        return model.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        erros = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(raiz)'}: {err['msg'].rstrip('.')}"
            for err in exc.errors()[:5]
        )
        raise PrumoError(
            f"JSON não valida contra {name}: {erros}. Corrija esses campos e valide de novo "
            f"com `prumo validate {name}`."
        ) from exc
