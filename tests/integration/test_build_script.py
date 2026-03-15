from __future__ import annotations

import subprocess
from pathlib import Path


def test_build_help() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(root / "build"), "--help"], check=True, capture_output=True, text=True
    )
    assert "Usage: ./build <command>" in result.stdout
    assert "smoke" in result.stdout
    assert "ci" in result.stdout
