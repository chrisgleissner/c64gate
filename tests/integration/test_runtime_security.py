from __future__ import annotations

from pathlib import Path


def test_compose_hardening_defaults() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'read_only: true' in compose
    assert 'no-new-privileges:true' in compose
    assert 'cap_drop:' in compose
    assert '8081:8081' not in compose
    assert '127.0.0.1' in compose