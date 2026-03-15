from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


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
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: CanonicalLogEvent) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(event.to_json())
            handle.write("\n")

    def read_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        with self.log_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        return [json.loads(line) for line in lines]
