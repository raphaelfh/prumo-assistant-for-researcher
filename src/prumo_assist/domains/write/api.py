"""Python API pra ``write``."""

from __future__ import annotations

from prumo_assist.domains.write.comments import extract_to_file as extract_comments
from prumo_assist.domains.write.compose import (
    WritePrep,
    compose_path,
    extract_missing_refs,
    prep,
    read_inputs,
    resolve_template,
    write_output,
)
from prumo_assist.domains.write.disclosure import generate_disclosure
from prumo_assist.domains.write.errors import WriteError
from prumo_assist.domains.write.export import compose, export, list_styles
from prumo_assist.domains.write.review import ApplyResult, IngestResult, apply_review, ingest
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteOutput,
)
from prumo_assist.domains.write.zettlr import generate_profile as generate_zettlr_profile
from prumo_assist.domains.write.zettlr import profile_issues as zettlr_profile_issues

__all__ = [
    "ApplyResult",
    "ComposeInputs",
    "FindingSummary",
    "IngestResult",
    "PaperSummary",
    "WriteError",
    "WriteOutput",
    "WritePrep",
    "apply_review",
    "compose",
    "compose_path",
    "export",
    "extract_comments",
    "extract_missing_refs",
    "generate_disclosure",
    "generate_zettlr_profile",
    "ingest",
    "list_styles",
    "prep",
    "read_inputs",
    "resolve_template",
    "write_output",
    "zettlr_profile_issues",
]
