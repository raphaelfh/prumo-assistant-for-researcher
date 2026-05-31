"""Python API pra ``write``."""

from __future__ import annotations

from prumo_assist.domains.write.comments import extract_to_file as extract_comments
from prumo_assist.domains.write.compose import (
    compose_path,
    extract_missing_refs,
    read_inputs,
    resolve_template,
    write_output,
)
from prumo_assist.domains.write.disclosure import generate_disclosure
from prumo_assist.domains.write.export import compose, export, list_styles
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteOutput,
)

__all__ = [
    "ComposeInputs",
    "FindingSummary",
    "PaperSummary",
    "WriteOutput",
    "compose",
    "compose_path",
    "export",
    "extract_comments",
    "extract_missing_refs",
    "generate_disclosure",
    "list_styles",
    "read_inputs",
    "resolve_template",
    "write_output",
]
