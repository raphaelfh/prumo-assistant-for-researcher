"""Motor único dos backends de ferramenta PINADA rodados via ``uvx``.

A escada de tradução de erro em 4 degraus (uvx ausente → erro de domínio
com hint; timeout → idem; exit ≠ 0 → idem com cauda do stderr; payload
hostil → decidido pelo CHAMADOR) vivia duplicada em
``domains/write/review._run_adeu_extract`` (adeu, backend de prosa) e
``domains/paper/verify._run_refchecker`` (refchecker, verificação profunda)
— achado do passe /simplify de 2026-07-25. Este módulo possui só o que é
comum: subprocess + os 3 primeiros degraus. Extração/validação do payload
(JSON de stdout, report em arquivo) fica em cada wrapper, porque o contrato
de saída difere por ferramenta.

Nível-core puro: NUNCA importa de ``domains/`` — a classe de erro de
domínio chega por parâmetro (``PinnedTool.error_cls``). O wording pt-BR de
cada degrau é composto dos rótulos do :class:`PinnedTool`, byte-idêntico ao
que os wrappers emitiam antes da extração (travado pelos testes deles).
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PinnedTool:
    """Identidade de erro de uma ferramenta pinada rodada via ``uvx``.

    Os três rótulos existem porque o wording histórico de cada ferramenta
    difere POR DEGRAU (ex.: o refchecker usa ``"refchecker"`` no timeout mas
    ``"refchecker (`uvx <pin>`)"`` no exit ≠ 0) — parametrizar menos que
    isso quebraria mensagens byte a byte.
    """

    error_cls: type[Exception]
    hint: str  # comando de correção pt-BR, fecha toda mensagem
    missing_label: str  # "uv/uvx não encontrado no PATH — {missing_label} não pode ser invocado."
    timeout_label: str  # "{timeout_label} excedeu {timeout}s — {timeout_detail}"
    timeout_detail: str
    exit_label: str  # "{exit_label} terminou com exit {rc}. stderr:..."


def run_pinned(
    tool: PinnedTool, argv: Sequence[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Roda ``argv`` (ferramenta pinada via uvx) traduzindo falhas de invocação.

    ``FileNotFoundError`` (uvx fora do PATH), ``TimeoutExpired`` e
    exit ≠ 0 viram ``tool.error_cls`` com mensagem pt-BR + ``tool.hint``.
    Exit 0 retorna o ``CompletedProcess`` intacto — o wrapper decide o que
    fazer com stdout/arquivos (ferramenta que "sai 0 mesmo com erro", como o
    refchecker, é problema do contrato de saída, não da invocação).
    """
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise tool.error_cls(
            f"uv/uvx não encontrado no PATH — {tool.missing_label} não pode ser "
            f"invocado. {tool.hint}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise tool.error_cls(
            f"{tool.timeout_label} excedeu {timeout:.0f}s — {tool.timeout_detail} {tool.hint}"
        ) from exc
    if proc.returncode != 0:
        raise tool.error_cls(
            f"{tool.exit_label} terminou com exit {proc.returncode}. "
            f"stderr:\n{proc.stderr.strip()[-2000:]}\n{tool.hint}"
        )
    return proc
