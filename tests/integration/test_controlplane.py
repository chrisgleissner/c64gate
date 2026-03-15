from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from common.logging import CanonicalLogEvent, JsonLogger
from controlplane.app import create_app


def test_dashboard_requires_basic_auth(temp_settings, tmp_path: Path) -> None:
    logger = JsonLogger(tmp_path / "c64gate.jsonl")
    logger.emit(
        CanonicalLogEvent(
            protocol="https",
            direction="inbound",
            source="127.0.0.1",
            destination="c64gate.local",
            action="summary",
            decision="granted",
            latency_ms=1.0,
            bytes_transferred=12,
            component="controlplane",
        )
    )
    app = create_app(settings=temp_settings, logger=logger)
    client = TestClient(app)
    assert client.get("/dashboard/summary").status_code == 401
    ok = client.get(
        "/dashboard/summary",
        auth=(temp_settings.dashboard_user, temp_settings.dashboard_password),
    )
    assert ok.status_code == 200
    assert ok.json()["protocol_counts"]["https"] == 1


def test_health_and_readiness(temp_settings) -> None:
    app = create_app(
        settings=temp_settings,
        runtime_state={"ready": True, "components": {"caddy": {"present": True}}, "metrics": {}},
    )
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready").json()
    assert ready["status"] == "ready"
    assert "capture" in ready
