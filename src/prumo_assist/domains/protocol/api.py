"""Python API pra ``protocol``."""

from __future__ import annotations

from prumo_assist.domains.protocol.ops import (
    AdrResult,
    InitResult,
    PropagateReport,
    create_picot_adr,
    detect_mode,
    diff_against_last_adr,
    init_picot_spec,
    propagate,
)
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

__all__ = [
    "AdrResult",
    "Hypothesis",
    "InitResult",
    "PicotSpec",
    "PropagateReport",
    "create_picot_adr",
    "detect_mode",
    "diff_against_last_adr",
    "init_picot_spec",
    "picot_hash",
    "picot_path",
    "propagate",
    "read_picot",
    "write_picot",
]
