"""Regras do projeto num bloco gerado do ``AGENTS.md`` (ADR-0046).

Idioma de interação e saídas seguras (dado de paciente, célula mínima) variam por
projeto: o valor mora em ``.claude/pj_config.toml`` e a instrução, já com os valores,
num bloco machine-owned do ``AGENTS.md`` (ADR-0009). O ``AGENTS.md`` é o arquivo que
Claude, Codex e Antigravity leem; ``.claude/rules/`` só o Claude lia.

A checagem determinística de dado fora do git continua em ``core/safe_outputs.py``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from par import ConfigError
from par.core.config import load_project_config

BLOCK_BEGIN = "<!-- prumo:project-rules:begin -->"
BLOCK_END = "<!-- prumo:project-rules:end -->"

_BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END), re.DOTALL)

#: Parágrafo fixo que o ``pj_base`` trazia antes do bloco; o ``update`` o troca pelo bloco.
_LEGACY_LANGUAGE_RE = re.compile(
    r"^Idioma de \*\*interação\*\*: pt-BR\..*?(?=\n\n|\Z)", re.M | re.S
)

#: Rule que o bloco substitui, e o sha256 de cada versão publicada dela: cópia
#: idêntica sai no ``update``; cópia editada é do pesquisador e fica.
LEGACY_RULE_RELPATH = ".claude/rules/safe_outputs.md"
_LEGACY_RULE_SHA256 = frozenset(
    {"11f8f07b1de89924bbe24a4fb50f88690727641f6d9d7e92bd25ad35f3d6b4df"}
)

#: Limiar mais comum em publicação de dado de saúde; abaixo dele o ``doctor`` avisa.
USUAL_MIN_CELL = 5

_INTERACTION_NOTE = {
    "pt-BR": "",
    "en-US": " (responda ao usuário em inglês, mesmo com estas instruções em português)",
}

_MINIMUM = (
    "- **Mínimo necessário.** Nunca copie dado linha-a-linha ou identificável (nome, "
    "prontuário, CPF, data de nascimento, endereço, texto livre de prontuário) para prosa, "
    "notas, findings, wiki ou contexto da conversa além do que a tarefa exige. Para entender "
    "um dataset, leia esquema e agregados, não linhas."
)
_OUT_OF_GIT = (
    "- **Dado fora do git.** `content/` (dado bruto e processado) e `.prumo/` (trace local de "
    "LLM) ficam no `.gitignore` e nunca são rastreados. `prumo doctor` confere."
)


def _safe_outputs_lines(patient_data: bool, min_cell: int) -> list[str]:
    if not patient_data:
        return [
            "Este projeto declarou que não trabalha com dado de paciente "
            "(`[safe_outputs].patient_data = false`). Se isso mudar, avise o usuário e peça "
            "para atualizar a config.",
            "",
            _OUT_OF_GIT,
        ]
    if min_cell == 0:
        cell = (
            "- A supressão de célula pequena está desligada por decisão do projeto "
            "(`[safe_outputs].min_cell = 0`)."
        )
    else:
        faixa = "igual a 1" if min_cell == 2 else f"entre 1 e {min_cell - 1}"
        cell = (
            (
                f"- **Célula mínima = {min_cell}.** Tabela ou texto com contagem de **pacientes** "
                f"{faixa} (e o percentual ou a diferença que a revela) é suprimido ou agregado "
                "com a categoria vizinha. Contagem de não-pacientes (clínicos respondentes, "
                '"1 de 33"; estudos incluídos) não entra na regra.'
            )
            if min_cell > 1
            else (
                "- **Célula mínima = 1.** Nenhuma contagem de pacientes é suprimida "
                "(`[safe_outputs].min_cell = 1`)."
            )
        )
    return [
        "Referência: Five Safes / controle estatístico de divulgação (UK Data Service).",
        "",
        _MINIMUM,
        cell,
        _OUT_OF_GIT,
    ]


def render_project_rules(cfg: dict[str, Any]) -> str:
    """Bloco ``prumo:project-rules`` (com os delimitadores) para a config ``cfg``."""
    interaction = cfg["interaction"]["language"]
    lines = [
        BLOCK_BEGIN,
        "<!-- Gerado de `.claude/pj_config.toml` pelo `prumo update`. "
        "Edite a config, não este bloco. -->",
        f"Idioma de **interação**: {interaction}{_INTERACTION_NOTE[interaction]}. Idioma de "
        f"**escrita científica**: {cfg['writing']['language']} (`[writing].language`); "
        "documento de CEP/CONEP é sempre pt-BR.",
        "",
        "## Saídas seguras (dado de paciente)",
        "",
        *_safe_outputs_lines(cfg["safe_outputs"]["patient_data"], cfg["safe_outputs"]["min_cell"]),
        BLOCK_END,
    ]
    return "\n".join(lines)


def sync_project_rules(
    pj_root: Path, *, write: bool = True
) -> Literal["inserted", "updated"] | None:
    """Põe o bloco do ``AGENTS.md`` em dia com a config; diz o que mudou (ou ``None``).

    Só reescreve dentro do bloco. Sem bloco, ele entra no lugar do parágrafo fixo de
    idioma que o template antigo trazia ou, na falta dele, logo abaixo do título.
    ``write=False`` só responde (é o que o ``doctor`` e o ``update --dry-run`` usam).

    Raises:
        ConfigError: delimitador sem par, ou ``pj_config.toml`` inválido.
    """
    agents = pj_root / "AGENTS.md"
    if not agents.is_file():
        return None
    text = agents.read_text(encoding="utf-8")
    block = render_project_rules(load_project_config(pj_root))

    change: Literal["inserted", "updated"]
    if _BLOCK_RE.search(text):
        new = _BLOCK_RE.sub(lambda _: block, text, count=1)
        change = "updated"
    elif BLOCK_BEGIN in text or BLOCK_END in text:
        raise ConfigError(
            f"{agents}: bloco `prumo:project-rules` com delimitador sem par. Apague o "
            "marcador que sobrou e rode `prumo update`, que reinsere o bloco."
        )
    else:
        change = "inserted"
        if _LEGACY_LANGUAGE_RE.search(text):
            new = _LEGACY_LANGUAGE_RE.sub(lambda _: block, text, count=1)
        else:
            title = re.match(r"\A# .*\n+", text)
            cut = title.end() if title else 0
            new = text[:cut] + block + "\n\n" + text[cut:]
    if new == text:
        return None
    if write:
        agents.write_text(new, encoding="utf-8")
    return change


def retire_legacy_rule(pj_root: Path, *, write: bool = True) -> Literal["removed", "kept"] | None:
    """Aposenta ``.claude/rules/safe_outputs.md``: intacta sai, editada fica (``None`` se não há)."""
    rule = pj_root / LEGACY_RULE_RELPATH
    if not rule.is_file():
        return None
    if hashlib.sha256(rule.read_bytes()).hexdigest() not in _LEGACY_RULE_SHA256:
        return "kept"
    if write:
        rule.unlink()
    return "removed"


def low_min_cell_warning(cfg: dict[str, Any]) -> str | None:
    """Aviso ``[celula_minima_baixa]``: dado de paciente com limiar abaixo do usual."""
    safe = cfg["safe_outputs"]
    if not safe["patient_data"] or safe["min_cell"] >= USUAL_MIN_CELL:
        return None
    return (
        f"[celula_minima_baixa] `[safe_outputs].min_cell = {safe['min_cell']}` com dado de "
        f"paciente: {USUAL_MIN_CELL} é o limiar mais comum em publicação de dado de saúde. Se "
        f"não foi de propósito, ponha `min_cell = {USUAL_MIN_CELL}` em `.claude/pj_config.toml` "
        "e rode `prumo update`."
    )
