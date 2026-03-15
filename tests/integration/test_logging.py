from __future__ import annotations

from pathlib import Path

from common.logging import CanonicalLogEvent, JsonLogger
from common.settings import Settings
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


def test_logger_redacts_sensitive_headers_and_rotates(tmp_path: Path) -> None:
    settings = Settings(
        log_dir=tmp_path,
        pcap_dir=tmp_path / "pcap",
        runtime_dir=tmp_path / "run",
        config_output_dir=tmp_path / "run/config",
        log_rotation_bytes=200,
        log_backup_count=2,
        simulation_mode=True,
    )
    logger = JsonLogger(tmp_path / "log.jsonl", settings=settings)
    for index in range(4):
        logger.emit(
            CanonicalLogEvent(
                protocol="https",
                direction="inbound",
                source="127.0.0.1",
                destination="c64gate.local",
                action=f"event-{index}",
                decision="granted",
                latency_ms=1.0,
                bytes_transferred=32,
                component="caddy",
                headers={"authorization": "secret", "x-test": "visible"},
            )
        )
    assert logger.read_recent(1)[0]["headers"]["authorization"] == "[REDACTED]"
    assert (tmp_path / "log.jsonl.1").exists()
