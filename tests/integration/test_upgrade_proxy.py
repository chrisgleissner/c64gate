from __future__ import annotations

from pathlib import Path

import pytest

from common.logging import JsonLogger
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
