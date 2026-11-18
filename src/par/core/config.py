"""Carregador de ``pj_*/.claude/pj_config.toml`` com defaults e validação leve.

Transformado de ``monorepo-anterior/.claude/scripts/_project_config.py``. Mudanças:

- ``ValueError`` → ``ConfigError`` (entra na hierarquia ``PrumoError``).
- Função ``load_project_config`` (nome mais descritivo do que ``load_config``).

Regras de cascata (escala futura, não implementada no MVP):
``CLI flags > pj_config.toml > ~/.config/prumo/config.toml > DEFAULTS``.
Por enquanto só cobrimos ``pj_config.toml`` e ``DEFAULTS``. ``~/.config/prumo/`` já é a
pasta do usuário (templates e guias, ADR-0045); o ``config.toml`` ali segue não implementado.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from par import ConfigError

DEFAULTS: dict[str, Any] = {
    "paper_extract": {
        "language": "pt-BR",
        "template": ".claude/paper_extraction.md",
        "batch": {
            "default_limit": 20,
            "subagents_per_wave": 8,
        },
    },
    "writing": {
        "language": "en-US",
    },
    "interaction": {
        "language": "pt-BR",
    },
    "safe_outputs": {
        "patient_data": True,
        "min_cell": 5,
    },
    "wiki": {},
    "citation": {},
}

VALID_LANGUAGES = frozenset({"pt-BR", "en", "es"})

# Vocabulário do idioma de PROSA (skills de escrita, ADR-0021) — deliberadamente
# separado de VALID_LANGUAGES, que é do callout de extração: dois contratos, e
# fundi-los amarraria a evolução de um ao outro.
WRITING_LANGUAGES = frozenset({"pt-BR", "en-US"})

# Idioma em que o agente CONVERSA (ADR-0046). Terceiro contrato: coincide hoje com
# WRITING_LANGUAGES, mas ampliar um não amplia o outro.
INTERACTION_LANGUAGES = frozenset({"pt-BR", "en-US"})


def load_project_config(pj_path: Path) -> dict[str, Any]:
    """Carrega ``pj_*/.claude/pj_config.toml`` mesclado com ``DEFAULTS``.

    Raises:
        ConfigError: se um idioma estiver fora do seu vocabulário ou ``[safe_outputs]``
            tiver tipo errado. A mensagem traz a correção.
    """
    cfg_path = pj_path / ".claude" / "pj_config.toml"
    if not cfg_path.exists():
        return copy.deepcopy(DEFAULTS)
    with cfg_path.open("rb") as f:
        user_cfg = tomllib.load(f)
    merged = _deep_merge(DEFAULTS, user_cfg)
    _validate(merged, cfg_path)
    return merged


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in base.items():
        if isinstance(v, dict):
            overlay_val = overlay.get(k, {})
            out[k] = _deep_merge(v, overlay_val if isinstance(overlay_val, dict) else {})
        else:
            out[k] = v
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            continue
        out[k] = v
    return out


def _validate(cfg: dict[str, Any], source: Path) -> None:
    lang = cfg["paper_extract"]["language"]
    if lang not in VALID_LANGUAGES:
        raise ConfigError(
            f"{source}: paper_extract.language='{lang}' inválido; "
            f"use um de {sorted(VALID_LANGUAGES)}"
        )
    writing_lang = cfg["writing"]["language"]
    if writing_lang not in WRITING_LANGUAGES:
        raise ConfigError(
            f"{source}: writing.language='{writing_lang}' inválido; "
            f"use um de {sorted(WRITING_LANGUAGES)}"
        )
    interaction_lang = cfg["interaction"]["language"]
    if interaction_lang not in INTERACTION_LANGUAGES:
        raise ConfigError(
            f"{source}: interaction.language='{interaction_lang}' inválido; "
            f"use um de {sorted(INTERACTION_LANGUAGES)}"
        )
    patient_data = cfg["safe_outputs"]["patient_data"]
    if not isinstance(patient_data, bool):
        raise ConfigError(
            f"{source}: safe_outputs.patient_data={patient_data!r} inválido; use true ou false"
        )
    min_cell = cfg["safe_outputs"]["min_cell"]
    if isinstance(min_cell, bool) or not isinstance(min_cell, int) or min_cell < 0:
        raise ConfigError(
            f"{source}: safe_outputs.min_cell={min_cell!r} inválido; "
            "use um inteiro >= 0 (0 desliga a supressão)"
        )


def set_config_values(pj_path: Path, values: dict[tuple[str, str], str | bool | int]) -> None:
    """Grava ``(seção, chave) -> valor`` no ``pj_config.toml``, preservando comentários.

    Edição textual de propósito: o arquivo é do pesquisador e vem comentado do
    template; reserializar com ``tomli_w`` apagaria os comentários. Chave existente
    é trocada no lugar; ausente entra logo abaixo do cabeçalho; seção ausente vai
    para o fim. Só seções de primeiro nível e valores escalares.
    """
    cfg_path = pj_path / ".claude" / "pj_config.toml"
    text = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
    for (section, key), value in values.items():
        # bool/int/str escalares: o literal JSON coincide com o TOML
        line = f"{key} = {json.dumps(value, ensure_ascii=False)}"
        header = re.search(rf"^\[{re.escape(section)}\][ \t]*$", text, re.MULTILINE)
        if header is None:
            text = (
                text.rstrip("\n") + f"\n\n[{section}]\n{line}\n"
                if text.strip()
                else (f"[{section}]\n{line}\n")
            )
            continue
        nxt = re.compile(r"^\[", re.MULTILINE).search(text, header.end())
        end = nxt.start() if nxt else len(text)
        body = text[header.end() : end]
        key_re = re.compile(rf"^{re.escape(key)}[ \t]*=.*$", re.MULTILINE)
        body = key_re.sub(line, body, count=1) if key_re.search(body) else f"\n{line}{body}"
        text = text[: header.end()] + body + text[end:]
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(text, encoding="utf-8")
