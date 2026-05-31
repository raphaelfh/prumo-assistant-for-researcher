"""Read/write canônico de ``.claude/picot.toml``.

Usa ``tomllib`` (stdlib) pra leitura e ``tomli_w`` pra escrita. Validação via
Pydantic (``PicotSpec/v1``) acontece no read; write pré-condiciona spec válido.

Hash sha256[:8] do conteúdo serve pra detectar drift nos blocos delimitados
dos destinos (``protocol.md``, ``project_guide.md``).
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec


def picot_path(pj_path: Path) -> Path:
    """Retorna ``<pj>/.claude/picot.toml``."""
    return pj_path / ".claude" / "picot.toml"


def read_picot(pj_path: Path) -> PicotSpec:
    """Lê e valida ``.claude/picot.toml``. Levanta ``FileNotFoundError`` se ausente."""
    path = picot_path(pj_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} não encontrado. Rode `/prumo-assist:formulate-picot init` primeiro."
        )
    with path.open("rb") as f:
        raw = tomllib.load(f)
    picot_block = raw.get("picot")
    if not isinstance(picot_block, dict):
        raise ValueError(f"{path}: bloco [picot] ausente ou inválido.")
    return PicotSpec.model_validate(picot_block)


def write_picot(pj_path: Path, spec: PicotSpec) -> Path:
    """Escreve ``.claude/picot.toml`` a partir de ``spec`` (já validado).

    Campos ``None`` são omitidos do TOML (TOML não tem null nativo).
    Preserva ordem dos campos do schema.
    """
    path = picot_path(pj_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = spec_to_toml_payload(spec)
    text = tomli_w.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def picot_hash(pj_path: Path) -> str:
    """sha256[:8] do conteúdo do TOML — usado em ``<!-- picot:begin hash=...-->``."""
    path = picot_path(pj_path)
    if not path.exists():
        raise FileNotFoundError(f"{path} não encontrado.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:8]


def spec_to_toml_payload(spec: PicotSpec) -> dict[str, Any]:
    """Converte ``PicotSpec`` em dict TOML-friendly omitindo ``None``s.

    Função pública (sem prefixo ``_``) porque ``adr.py`` reusa para gerar
    snapshots dentro dos ADRs.
    """
    dumped = spec.model_dump(mode="python", exclude={"schema_version"})
    hypothesis = dumped.pop("hypothesis")
    base = {k: v for k, v in dumped.items() if v is not None}
    return {"picot": {**base, "hypothesis": hypothesis}}
