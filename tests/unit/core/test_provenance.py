"""Tests pra provenance: bloco _meta."""

from __future__ import annotations

from par.core.provenance import (
    build_meta,
    hash_input,
    new_run_id,
    now_utc,
)


def test_now_utc_format() -> None:
    ts = now_utc()
    # YYYY-MM-DDTHH:MM:SSZ
    assert len(ts) == 20
    assert ts.endswith("Z")
    assert ts[4] == "-" and ts[10] == "T"


def test_run_id_is_8_hex_chars() -> None:
    rid = new_run_id()
    assert len(rid) == 8
    int(rid, 16)  # raises if not hex


def test_hash_input_is_deterministic() -> None:
    a = hash_input("paper PDF bytes")
    b = hash_input("paper PDF bytes")
    assert a == b
    assert len(a) == 16
    assert hash_input("different") != a


def test_hash_input_accepts_bytes() -> None:
    assert hash_input(b"raw") == hash_input("raw")


def test_build_meta_omits_none_in_dict() -> None:
    m = build_meta(schema="X/v1", skill="paper-extract", model="claude-opus-4-7")
    d = m.to_dict()
    assert d["schema"] == "X/v1"
    assert d["skill"] == "paper-extract"
    assert d["model"] == "claude-opus-4-7"
    assert "cost_usd" not in d
    assert "input_hash" not in d


def test_build_meta_carries_extra() -> None:
    m = build_meta(schema="X/v1", extra={"venue": "Nature Medicine"})
    assert m.to_dict()["extra"] == {"venue": "Nature Medicine"}


def test_build_meta_human_reviewed_unset_is_omitted() -> None:
    m = build_meta(schema="X/v1")
    assert m.human_reviewed is None
    assert "human_reviewed" not in m.to_dict()


def test_build_meta_keeps_explicit_human_reviewed_false() -> None:
    assert build_meta(schema="X/v1", human_reviewed=False).to_dict()["human_reviewed"] is False


def test_build_meta_records_human_reviewed() -> None:
    m = build_meta(schema="X/v1", human_reviewed=True)
    assert m.to_dict()["human_reviewed"] is True
