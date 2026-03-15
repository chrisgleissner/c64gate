from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from common.logging import JsonLogger
from controlplane.auth import validate_management_auth
from conftest import BackendServer, build_tls_context, request_via_proxy
from upgrade_proxy.service import UpgradeProxyService


@pytest.mark.asyncio
async def test_upgrade_proxy_https_first_and_cache(
    temp_settings, trustme_ca, tmp_path: Path
) -> None:
    http_server = BackendServer("http-response").start()
    https_server = BackendServer(
        "https-response",
        tls_context=build_tls_context(trustme_ca["cert"], trustme_ca["key"]),
    ).start()
    temp_settings.https_port_map = {http_server.port: https_server.port}
    temp_settings.tls_ca_bundle = trustme_ca["ca"]
    logger = JsonLogger(tmp_path / "upgrade.jsonl")
    runtime_state = {"ready": True, "metrics": {}, "components": {}}
    service = UpgradeProxyService(
        settings=temp_settings, logger=logger, runtime_state=runtime_state
    )
    server = await service.start()
    try:
        payload = await request_via_proxy(
            temp_settings.upgrade_proxy_port, f"http://127.0.0.1:{http_server.port}/hello"
        )
        assert b"https-response" in payload
        assert service.cache.get(f"127.0.0.1:{http_server.port}") is not None
        assert service.cache.get(f"127.0.0.1:{http_server.port}").mode == "https"
    finally:
        server.close()
        await server.wait_closed()
        await service.client.aclose()
        http_server.close()
        https_server.close()


@pytest.mark.asyncio
async def test_upgrade_proxy_http_fallback_when_not_strict(temp_settings, tmp_path: Path) -> None:
    http_server = BackendServer("http-only").start()
    temp_settings.https_port_map = {http_server.port: http_server.port + 1}
    logger = JsonLogger(tmp_path / "fallback.jsonl")
    runtime_state = {"ready": True, "metrics": {}, "components": {}}
    service = UpgradeProxyService(
        settings=temp_settings, logger=logger, runtime_state=runtime_state
    )
    server = await service.start()
    try:
        payload = await request_via_proxy(
            temp_settings.upgrade_proxy_port, f"http://127.0.0.1:{http_server.port}/hello"
        )
        assert b"http-only" in payload
        assert service.cache.get(f"127.0.0.1:{http_server.port}").mode == "http"
        warnings = logger.read_recent(1)[0].get("warnings")
        assert "https-unavailable" in warnings
    finally:
        server.close()
        await server.wait_closed()
        await service.client.aclose()
        http_server.close()


@pytest.mark.asyncio
async def test_upgrade_proxy_strict_mode_blocks_fallback(
    temp_settings, tmp_path: Path, openssl_self_signed
) -> None:
    https_server = BackendServer(
        "invalid-cert",
        tls_context=build_tls_context(openssl_self_signed["cert"], openssl_self_signed["key"]),
    ).start()
    temp_settings.strict_tls_mode = True
    temp_settings.https_port_map = {https_server.port - 1: https_server.port}
    logger = JsonLogger(tmp_path / "strict.jsonl")
    runtime_state = {"ready": True, "metrics": {}, "components": {}}
    service = UpgradeProxyService(
        settings=temp_settings, logger=logger, runtime_state=runtime_state
    )
    server = await service.start()
    try:
        payload = await request_via_proxy(
            temp_settings.upgrade_proxy_port, f"http://127.0.0.1:{https_server.port - 1}/hello"
        )
        assert b"strict TLS mode rejected HTTP fallback" in payload
        assert logger.read_recent(1)[0]["decision"] == "blocked"
    finally:
        server.close()
        await server.wait_closed()
        await service.client.aclose()
        https_server.close()


@pytest.mark.asyncio
async def test_upgrade_proxy_rejects_oversized_headers(temp_settings, tmp_path: Path) -> None:
    logger = JsonLogger(tmp_path / "oversized.jsonl")
    runtime_state = {"ready": True, "metrics": {}, "components": {}}
    service = UpgradeProxyService(
        settings=temp_settings.model_copy(update={"proxy_max_header_bytes": 128}),
        logger=logger,
        runtime_state=runtime_state,
    )
    server = await service.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", temp_settings.upgrade_proxy_port)
        writer.write(
            b"GET http://example.test/ HTTP/1.1\r\nHost: example.test\r\nX-Fill: "
            + (b"a" * 256)
            + b"\r\n\r\n"
        )
        await writer.drain()
        payload = await reader.read()
        assert b"431" in payload or b"request headers too large" in payload
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()
        await service.client.aclose()


@pytest.mark.asyncio
async def test_upgrade_proxy_times_out_slow_headers(temp_settings, tmp_path: Path) -> None:
    logger = JsonLogger(tmp_path / "timeout.jsonl")
    runtime_state = {"ready": True, "metrics": {}, "components": {}}
    service = UpgradeProxyService(
        settings=temp_settings.model_copy(update={"proxy_client_header_timeout_seconds": 0.05}),
        logger=logger,
        runtime_state=runtime_state,
    )
    server = await service.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", temp_settings.upgrade_proxy_port)
        writer.write(b"GET http://example.test/ HTTP/1.1\r\n")
        await writer.drain()
        await asyncio.sleep(0.1)
        payload = await reader.read()
        assert b"408" in payload or b"request header timeout" in payload
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()
        await service.client.aclose()


def test_weak_dashboard_password_rejected_outside_simulation(temp_settings) -> None:
    secured = temp_settings.model_copy(update={"simulation_mode": False, "dashboard_password": "changeme"})
    with pytest.raises(RuntimeError):
        validate_management_auth(secured)
