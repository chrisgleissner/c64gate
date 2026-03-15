from __future__ import annotations

from pathlib import Path

import yaml


def _load_matrix() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "doc/traceability-matrix.yaml").read_text(encoding="utf-8"))


def test_linux_only_scope_documented() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Linux only" in readme or "Linux host" in readme


def test_build_entry_point_declared() -> None:
    root = Path(__file__).resolve().parents[2]
    build_script = (root / "build").read_text(encoding="utf-8")
    assert "Usage: ./build <command>" in build_script


def test_traceability_rows_are_complete() -> None:
    payload = _load_matrix()
    rows = payload["requirements"]
    assert rows
    for row in rows:
        assert row["implementation"]
        assert row["tests"]
        assert row["ci"]
