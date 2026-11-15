"""Read/write canônico de ``.claude/question.toml`` (``QuestionSpec/v1``, ADR-0041).

Sem ``question.toml``, lê o ``.claude/picot.toml`` antigo e converte sem perda.
A primeira escrita grava ``question.toml`` e remove ``picot.toml``: o snapshot
no ADR e o git guardam o formato antigo.

Hash sha256[:8] do arquivo vigente marca os blocos delimitados dos destinos.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from par.domains.protocol.picot_io import picot_path, read_picot
from par.domains.protocol.schemas.v1 import QuestionSpec, question_from_picot


def question_path(pj_path: Path) -> Path:
    """Retorna ``<pj>/.claude/question.toml``."""
    return pj_path / ".claude" / "question.toml"


def current_question_file(pj_path: Path) -> Path | None:
    """Arquivo vigente: ``question.toml``, senão o ``picot.toml`` antigo, senão ``None``."""
    for path in (question_path(pj_path), picot_path(pj_path)):
        if path.exists():
            return path
    return None


def read_question(pj_path: Path) -> QuestionSpec:
    """Lê e valida a pergunta do estudo; converte o ``picot.toml`` antigo se for o caso.

    Levanta ``FileNotFoundError`` se nenhum dos dois existir.
    """
    path = question_path(pj_path)
    if not path.exists():
        if picot_path(pj_path).exists():
            return question_from_picot(read_picot(pj_path))
        raise FileNotFoundError(
            f"{path} não encontrado. Rode `/par:protocol question` para fechar a pergunta "
            "do estudo."
        )
    with path.open("rb") as f:
        raw = tomllib.load(f)
    block = raw.get("question")
    if not isinstance(block, dict):
        raise ValueError(
            f"{path}: tabela [question] ausente ou inválida. Confira com "
            "`git diff .claude/question.toml`."
        )
    return QuestionSpec.model_validate(block)


def write_question(pj_path: Path, spec: QuestionSpec) -> Path:
    """Escreve ``.claude/question.toml`` e remove o ``picot.toml`` antigo, se houver."""
    path = question_path(pj_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(spec_to_toml_payload(spec)), encoding="utf-8")
    picot_path(pj_path).unlink(missing_ok=True)
    return path


def question_hash(pj_path: Path) -> str:
    """sha256[:8] do arquivo vigente — usado em ``<!-- question:begin hash=... -->``."""
    path = current_question_file(pj_path)
    if path is None:
        raise FileNotFoundError(f"{question_path(pj_path)} não encontrado.")
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def spec_to_toml_payload(spec: QuestionSpec) -> dict[str, Any]:
    """``QuestionSpec`` → dict TOML-friendly sem ``None``s (TOML não tem null).

    Tabelas (``elements``, ``hypothesis``) vão por último, depois dos escalares.
    """
    dumped = spec.model_dump(mode="python", exclude={"schema_version"})
    tables = {k: dumped.pop(k) for k in ("elements", "hypothesis")}
    base = {k: v for k, v in dumped.items() if v is not None}
    base.update({k: v for k, v in tables.items() if v is not None})
    return {"question": base}
