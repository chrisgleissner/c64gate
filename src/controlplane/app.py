from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI

from common.capture import build_capture_plan
from common.logging import JsonLogger
from common.settings import Settings, get_settings
from controlplane.auth import authenticate


def _load_recent_summary(logger: JsonLogger) -> dict[str, Any]:
    recent = logger.read_recent(limit=200)
    protocol_counts = Counter(item.get("protocol", "unknown") for item in recent)
    decision_counts = Counter(item.get("decision", "unknown") for item in recent)
    return {
        "recent_events": recent[-20:],
        "protocol_counts": dict(protocol_counts),
        "decision_counts": dict(decision_counts),
    }


def create_app(
    settings: Settings | None = None,
    logger: JsonLogger | None = None,
    runtime_state: dict[str, Any] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logger = logger or JsonLogger(Path(settings.log_dir) / "c64gate.jsonl")
    state = (
        runtime_state
        if runtime_state is not None
        else {"ready": True, "metrics": {}, "components": {}}
    )

    app = FastAPI(title="C64 Gate Control Plane", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "component": "controlplane"}

    @app.get("/ready")
    async def ready() -> dict[str, Any]:
        return {
            "status": "ready" if state.get("ready", False) else "not-ready",
            "components": state.get("components", {}),
            "metrics": state.get("metrics", {}),
            "capture": asdict(build_capture_plan(settings)),
        }

    @app.get("/dashboard/summary")
    async def dashboard_summary(_: str = Depends(authenticate(settings))) -> dict[str, Any]:
        summary = _load_recent_summary(logger)
        summary["strict_tls_mode"] = settings.strict_tls_mode
        summary["verbose_logging"] = settings.verbose_logging
        summary["verbose_stream_logging"] = settings.verbose_stream_logging
        return summary

    @app.get("/dashboard/flows/recent")
    async def recent_flows(_: str = Depends(authenticate(settings))) -> dict[str, Any]:
        return {"flows": logger.read_recent(limit=50)}

    @app.get("/dashboard/spec")
    async def spec_status(_: str = Depends(authenticate(settings))) -> dict[str, Any]:
        return {
            "traceability_matrix": "doc/traceability-matrix.yaml",
            "simulation_mode": settings.simulation_mode,
        }

    return app
