#!/usr/bin/env python3
"""Auto-detecta o modo da skill formulate-picot pelo estado do projeto.

Imprime exatamente uma palavra em stdout:

- ``init``       — ``.claude/picot.toml`` ausente e ``docs/protocol.md`` vazio.
- ``formalize``  — ``.claude/picot.toml`` ausente mas ``docs/protocol.md`` tem prose.
- ``propagate``  — ``picot.toml`` existe mas ainda não há ADR baseline.
- ``diff``       — há baseline; verificar se mudou (delegar a ``prumo protocol diff``).
"""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.protocol.adr import find_last_picot_adr
from prumo_assist.domains.protocol.picot_io import picot_path


def main() -> None:
    pj = Path(".")
    toml = picot_path(pj)
    last_adr = find_last_picot_adr(pj)
    protocol_md = pj / "docs" / "protocol.md"

    if not toml.exists():
        has_prose = protocol_md.exists() and protocol_md.read_text(errors="ignore").strip() != ""
        print("formalize" if has_prose else "init")
    elif last_adr is None:
        print("propagate")
    else:
        print("diff")


if __name__ == "__main__":
    main()
