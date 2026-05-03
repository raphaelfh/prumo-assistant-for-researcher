"""Tests pra provenance: _meta block e trace JSONL."""

from __future__ import annotations

import json
from pathlib import Path

from prumo_assist.core.provenance import (
    TraceWriter,
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


def test_trace_writer_appends_jsonl(tmp_path: Path) -> None:
    tw = TraceWriter(project_dir=tmp_path)
    tw.emit("paper.extract.start", run_id="abc12345", payload={"citekey": "smith2024"})
    tw.emit("paper.extract.end", run_id="abc12345", payload={"ok": True})

    files = list((tmp_path / ".prumo" / "traces").glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    rec1 = json.loads(lines[0])
    assert rec1["event"] == "paper.extract.start"
    assert rec1["run_id"] == "abc12345"
    assert rec1["citekey"] == "smith2024"

    rec2 = json.loads(lines[1])
    assert rec2["event"] == "paper.extract.end"
    assert rec2["ok"] is True


def test_trace_writer_handles_unwriteable_dir(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    # Aponta pra um arquivo (não dir) — mkdir vai falhar e o escritor deve tolerar.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    tw = TraceWriter(project_dir=blocker)
    # Não deve lançar:
    tw.emit("evt", run_id="x", payload={"k": 1})
