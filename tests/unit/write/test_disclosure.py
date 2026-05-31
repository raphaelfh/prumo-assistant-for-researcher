"""Testes do gerador de declaração de uso de IA."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.schemas.v1 import AIDisclosure, AIToolUse


def test_aitooluse_defaults() -> None:
    u = AIToolUse(tool="prumo-assist:paper-extract", task="t")
    assert u.count == 1
    assert u.human_reviewed is False
    assert u.model is None


def test_aidisclosure_schema_version() -> None:
    d = AIDisclosure(generated_at="t", statement_pt="p", statement_en="e")
    assert d.schema_version == "AIDisclosure/v1"
    assert d.tools == []


def test_record_from_paper_meta() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    rec = _record_from_fm({"extracted_model": "claude-opus-4", "extracted_at": "2026-05-01"})
    assert rec is not None
    assert rec.skill == "paper-extract"
    assert rec.model == "claude-opus-4"


def test_record_from_finding_generator() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    rec = _record_from_fm({"type": "finding", "generator": "wiki-query", "added": "2026-05-02"})
    assert rec is not None
    assert rec.skill == "wiki-query"
    assert rec.model is None


def test_record_from_plain_frontmatter_is_none() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    assert _record_from_fm({"title": "just a note"}) is None


def test_collect_records_walks_and_skips_dotdirs(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import collect_records

    (tmp_path / "references" / "notes" / "a").mkdir(parents=True)
    (tmp_path / "references" / "notes" / "a" / "_meta.md").write_text(
        "---\nextracted_model: m1\nextracted_at: 2026-05-01\n---\n", encoding="utf-8"
    )
    (tmp_path / ".prumo").mkdir()
    (tmp_path / ".prumo" / "leak.md").write_text(
        "---\nextracted_model: leak\n---\n", encoding="utf-8"
    )
    recs = collect_records(tmp_path)
    assert [r.model for r in recs] == ["m1"]


def _paper(p: Path, model: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nextracted_model: {model}\nextracted_at: 2026-05-01\n---\n", encoding="utf-8")


def test_generate_disclosure_names_tool_and_model(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import generate_disclosure

    _paper(tmp_path / "references/notes/a/_meta.md", "claude-opus-4")
    _paper(tmp_path / "references/notes/b/_meta.md", "claude-opus-4")
    disc = generate_disclosure(root=tmp_path)
    assert len(disc.tools) == 1
    assert disc.tools[0].count == 2
    assert disc.tools[0].tool == "prumo-assist:paper-extract"
    assert "claude-opus-4" in disc.statement_en
    assert "responsibility" in disc.statement_en
    assert "responsabilidade" in disc.statement_pt


def test_generate_disclosure_empty(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import generate_disclosure

    disc = generate_disclosure(root=tmp_path)
    assert disc.tools == []
    assert "No generative AI" in disc.statement_en


def test_generate_disclosure_missing_root_raises() -> None:
    import pytest

    from prumo_assist import PrumoError
    from prumo_assist.domains.write.disclosure import generate_disclosure

    with pytest.raises(PrumoError):
        generate_disclosure(root=Path("/no/such/dir/xyz123"))


def test_reexported() -> None:
    from prumo_assist.domains.write.api import generate_disclosure

    assert callable(generate_disclosure)


def test_cli_disclosure_json(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from prumo_assist.domains.write.cli import write_app

    (tmp_path / "references" / "notes" / "a").mkdir(parents=True)
    (tmp_path / "references" / "notes" / "a" / "_meta.md").write_text(
        "---\nextracted_model: claude-opus-4\nextracted_at: 2026-05-01\n---\n", encoding="utf-8"
    )
    result = CliRunner().invoke(write_app, ["disclosure", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert "AIDisclosure/v1" in result.stdout


def test_record_from_canonical_meta_block() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    rec = _record_from_fm(
        {
            "_meta": {
                "skill": "peer-review",
                "model": "claude-opus-4",
                "timestamp_utc": "2026-05-03T00:00:00Z",
                "human_reviewed": True,
            }
        }
    )
    assert rec is not None
    assert rec.skill == "peer-review"
    assert rec.model == "claude-opus-4"
    assert rec.date == "2026-05-03T00:00:00Z"
    assert rec.human_reviewed is True


def test_aggregate_human_reviewed_is_and_across_group(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import generate_disclosure

    base = tmp_path / "references" / "notes"
    # Two paper-extract artifacts, same model → one aggregated tool group.
    # One reviewed, one not → the group must NOT be marked human_reviewed.
    (base / "a").mkdir(parents=True)
    (base / "a" / "_meta.md").write_text(
        "---\nextracted_model: m\nextracted_at: 2026-05-01\nhuman_reviewed: true\n---\n",
        encoding="utf-8",
    )
    (base / "b").mkdir(parents=True)
    (base / "b" / "_meta.md").write_text(
        "---\nextracted_model: m\nextracted_at: 2026-05-02\nhuman_reviewed: false\n---\n",
        encoding="utf-8",
    )
    disc = generate_disclosure(root=tmp_path)
    assert len(disc.tools) == 1
    assert disc.tools[0].count == 2
    assert disc.tools[0].human_reviewed is False
