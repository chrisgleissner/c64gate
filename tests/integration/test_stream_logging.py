from __future__ import annotations

from common.logging import CanonicalLogEvent


def test_stream_logging_modes(temp_settings) -> None:
    event = CanonicalLogEvent(
        protocol="tcp-stream",
        direction="inbound",
        source="c64-device",
        destination="backend",
        action="stream-pass-through",
        decision="granted",
        latency_ms=0.0,
        bytes_transferred=256,
        component="stream-logger",
        payload_summary=None if not temp_settings.verbose_stream_logging else "payload",
    )
    assert event.payload_summary is None


def test_udp_summary_logging_default(temp_settings) -> None:
    assert temp_settings.verbose_stream_logging is False
