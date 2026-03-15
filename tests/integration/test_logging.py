from __future__ import annotations

from pathlib import Path

from common.logging import CanonicalLogEvent, JsonLogger
from log_normalizer.adapters import (
    normalize_caddy_log,
    normalize_nftables_log,
    normalize_proftpd_log,
)


def test_canonical_log_event_shape(tmp_path: Path) -> None:
    logger = JsonLogger(tmp_path / "log.jsonl")
    event = CanonicalLogEvent(
        protocol="https",
        direction="inbound",
        source="127.0.0.1",
        destination="c64gate.local",
        action="rest-api",
        decision="granted",
        latency_ms=12.5,
        bytes_transferred=128,
        component="caddy",
    )
    logger.emit(event)
    recent = logger.read_recent(1)[0]
    assert recent["protocol"] == "https"
    assert recent["correlation_id"]
    assert recent["bytes_transferred"] == 128


def test_daemon_logs_are_normalized() -> None:
    caddy_event = normalize_caddy_log(
        {
            "duration": 0.1,
            "size": 42,
            "status": 200,
            "request": {
                "remote_ip": "127.0.0.1",
                "host": "c64gate.local",
                "uri": "/api/ping",
                "headers": {},
            },
        }
    )
    proftpd_event = normalize_proftpd_log("127.0.0.1 - RETR disk.d64")
    nft_event = normalize_nftables_log("c64gate-forward-drop")
    assert caddy_event.component == "caddy"
    assert proftpd_event.protocol == "ftps"
    assert nft_event.decision == "blocked"
