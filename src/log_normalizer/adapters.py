from __future__ import annotations

import json
from typing import Any

from common.logging import CanonicalLogEvent


def normalize_caddy_log(record: dict[str, Any]) -> CanonicalLogEvent:
    request = record.get("request", {})
    return CanonicalLogEvent(
        protocol="https",
        direction="inbound",
        source=request.get("remote_ip", "unknown"),
        destination=request.get("host", "unknown"),
        action=request.get("uri", "/"),
        decision="granted",
        latency_ms=float(record.get("duration", 0.0)) * 1000,
        bytes_transferred=int(record.get("size", 0)),
        component="caddy",
        headers=request.get("headers"),
        metadata={"status": record.get("status")},
    )


def normalize_proftpd_log(line: str) -> CanonicalLogEvent:
    tokens = line.split()
    source = tokens[0] if tokens else "unknown"
    action = tokens[-1] if tokens else "unknown"
    return CanonicalLogEvent(
        protocol="ftps",
        direction="inbound",
        source=source,
        destination="c64-backend",
        action=action,
        decision="granted",
        latency_ms=0.0,
        bytes_transferred=0,
        component="proftpd",
        metadata={"raw": line},
    )


def normalize_nftables_log(line: str) -> CanonicalLogEvent:
    decision = "blocked" if "drop" in line.lower() else "granted"
    return CanonicalLogEvent(
        protocol="firewall",
        direction="bidirectional",
        source="kernel",
        destination="firewall",
        action="nftables-decision",
        decision=decision,
        latency_ms=0.0,
        bytes_transferred=0,
        component="nftables",
        metadata={"raw": line},
    )


def normalize_json_line(payload: str) -> dict[str, Any]:
    return json.loads(payload)
