from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from common.settings import Settings


@dataclass(slots=True)
class CanonicalLogEvent:
    protocol: str
    direction: str
    source: str
    destination: str
    action: str
    decision: str
    latency_ms: float
    bytes_transferred: int
    component: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    correlation_id: str = field(default_factory=lambda: uuid4().hex)
    headers: dict[str, str] | None = None
    warnings: list[str] | None = None
    payload_summary: str | None = None
    metadata: dict[str, Any] | None = None

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, sort_keys=True)


class JsonLogger:
    def __init__(self, log_path: Path, settings: Settings | None = None) -> None:
        self.log_path = log_path
        self.settings = settings
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: CanonicalLogEvent) -> None:
        payload = asdict(event)
        payload["headers"] = self._redact_headers(payload.get("headers"))
        self._rotate_if_needed(len(json.dumps(payload, sort_keys=True)) + 1)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
        os.chmod(self.log_path, 0o640)

    def read_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        with self.log_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        return [json.loads(line) for line in lines]

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self.settings is None or not self.log_path.exists():
            return
        if self.log_path.stat().st_size + incoming_bytes <= self.settings.log_rotation_bytes:
            return
        for index in range(self.settings.log_backup_count - 1, 0, -1):
            source = self.log_path.with_name(f"{self.log_path.name}.{index}")
            destination = self.log_path.with_name(f"{self.log_path.name}.{index + 1}")
            if source.exists():
                source.replace(destination)
        self.log_path.replace(self.log_path.with_name(f"{self.log_path.name}.1"))

    def _redact_headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        if headers is None:
            return None
        redacted_headers = dict(headers)
        sensitive = {
            header.lower()
            for header in (self.settings.log_redacted_headers if self.settings is not None else [])
        }
        for key in list(redacted_headers):
            if key.lower() in sensitive:
                redacted_headers[key] = "[REDACTED]"
        return redacted_headers
