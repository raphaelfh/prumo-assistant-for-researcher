"""Python API pra ``protocol``."""

from __future__ import annotations

from par.domains.protocol.drift import Drift
from par.domains.protocol.ops import (
    AdrResult,
    InitResult,
    PropagateReport,
    create_question_adr,
    detect_mode,
    diff_against_last_adr,
    init_question_spec,
    manuscript_drift,
    propagate,
)
from par.domains.protocol.picot_io import read_picot
from par.domains.protocol.question_io import (
    current_question_file,
    question_hash,
    question_path,
    read_question,
    write_question,
)
from par.domains.protocol.schemas.v1 import (
    Hypothesis,
    PicotSpec,
    QuestionSpec,
    question_from_picot,
)

__all__ = [
    "AdrResult",
    "Drift",
    "Hypothesis",
    "InitResult",
    "PicotSpec",
    "PropagateReport",
    "QuestionSpec",
    "create_question_adr",
    "current_question_file",
    "detect_mode",
    "diff_against_last_adr",
    "init_question_spec",
    "manuscript_drift",
    "propagate",
    "question_from_picot",
    "question_hash",
    "question_path",
    "read_picot",
    "read_question",
    "write_question",
]
