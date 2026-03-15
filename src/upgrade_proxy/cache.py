from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class CapabilityEntry:
    mode: str
    updated_at: float


class CapabilityCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, CapabilityEntry] = {}

    def get(self, key: str) -> CapabilityEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if monotonic() - entry.updated_at > self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return entry

    def set(self, key: str, mode: str) -> None:
        self._entries[key] = CapabilityEntry(mode=mode, updated_at=monotonic())
