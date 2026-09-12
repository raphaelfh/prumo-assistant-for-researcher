"""Tests para o drift determinístico manuscrito × protocolo/PICOT."""

from __future__ import annotations

import shutil
from pathlib import Path

from prumo_assist.domains.protocol.drift import (
    SourceText,
    find_drift,
    named_tests,
    prespec_polarity,
    windows,
)
from prumo_assist.domains.protocol.ops import manuscript_drift

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "protocol_drift"


def _src(name: str, text: str) -> SourceText:
    return SourceText(label=name, lines=tuple(text.splitlines()))


def test_windows_bilingual() -> None:
    assert windows("coleta entre março e agosto de 2023") == [("03", "08", "2023")]
    assert windows("Janela: **março a agosto de 2023**.") == [("03", "08", "2023")]
    assert windows("between March and July 2023") == [("03", "07", "2023")]


def test_named_tests_closed_vocabulary() -> None:
    line = "qui-quadrado ou exato de Fisher; Cochran–Armitage; Mann–Whitney"
    assert named_tests(line) == {"chi-square", "fisher", "cochran-armitage", "mann-whitney"}
    assert named_tests("Fisher exact and Mann-Whitney tests") == {"fisher", "mann-whitney"}


def test_prespec_polarity() -> None:
    assert prespec_polarity("**Estratificações exploratórias pré-declaradas**") is True
    assert prespec_polarity("by age group were exploratory and were not prespecified") is False
    assert prespec_polarity("Ajuste por família pré-declarada") is None


def test_fixture_detects_three_contradictions() -> None:
    protocol = _src("protocol.md", (FIXTURES / "protocol.md").read_text(encoding="utf-8"))
    picot = _src("picot.toml", (FIXTURES / "picot.toml").read_text(encoding="utf-8"))
    draft = _src("draft.md", (FIXTURES / "draft.md").read_text(encoding="utf-8"))
    drifts = find_drift([protocol, picot], draft)
    kinds = sorted(d.kind for d in drifts)
    assert kinds == ["prespecification", "test", "test", "window"]
    window = next(d for d in drifts if d.kind == "window")
    assert window.protocol_loc == "protocol.md:3"
    assert window.draft_loc == "draft.md:3"
    assert "03–08/2023" in window.protocol_value and "03–07/2023" in window.draft_value
    missing = {d.protocol_value for d in drifts if d.kind == "test"}
    assert missing == {"chi-square", "cochran-armitage"}
    prespec = next(d for d in drifts if d.kind == "prespecification")
    assert prespec.protocol_loc == "protocol.md:16"
    assert prespec.draft_loc == "draft.md:5"
    assert all(d.hint for d in drifts)


def test_agreeing_texts_report_no_drift() -> None:
    protocol = _src(
        "protocol.md",
        "Coleta entre março e agosto de 2023, n=35.\n"
        "Qualitativas: exato de Fisher; quantitativas: Mann–Whitney.\n"
        "Estratificações exploratórias pré-declaradas.\n",
    )
    draft = _src(
        "draft.md",
        "Between March and August 2023, 31 respondents.\n"
        "We used the Fisher exact and Mann-Whitney tests.\n"
        "Subgroup comparisons were prespecified.\n",
    )
    assert find_drift([protocol], draft) == []


def test_sample_size_absent_in_draft() -> None:
    protocol = _src("protocol.md", "n=48 no módulo sociodemográfico\n")
    draft = _src("draft.md", "Of 51 records, 0.53 were complete.\n")
    drifts = find_drift([protocol], draft)
    assert [(d.kind, d.protocol_value, d.protocol_loc) for d in drifts] == [
        ("sample_size", "n=48", "protocol.md:1")
    ]


def test_manuscript_drift_scans_writing_drafts(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    shutil.copy(FIXTURES / "picot.toml", pj / ".claude" / "picot.toml")
    writing = pj / "docs" / "studies" / "principal" / "writing"
    writing.mkdir(parents=True)
    shutil.copy(FIXTURES / "protocol.md", writing / "protocol.md")
    shutil.copy(FIXTURES / "draft.md", writing / "paper.md")
    scope = writing.parent

    drifts = manuscript_drift(scope)
    assert len(drifts) == 4
    assert drifts[0].draft_loc.startswith("docs/studies/principal/writing/paper.md:")
    assert manuscript_drift(scope, draft=writing / "protocol.md") == []
