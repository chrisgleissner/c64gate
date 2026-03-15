from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

import uvicorn

from common.config_renderers import (
    render_caddyfile,
    render_dnsmasq_config,
    render_nftables_ruleset,
    render_proftpd_config,
)
from common.logging import JsonLogger
from common.settings import Settings, get_settings
from controlplane.app import create_app
from upgrade_proxy.service import UpgradeProxyService

MANDATORY_BINARIES = ["nft", "dnsmasq", "caddy", "proftpd", "dumpcap", "tshark", "capinfos"]


def start_managed_process(command: list[str], name: str) -> subprocess.Popen[str]:
    process = subprocess.Popen(command, text=True)
    if process.poll() is not None:
        raise RuntimeError(f"failed to start {name}")
    return process


def start_managed_process_with_env(
    command: list[str], name: str, extra_env: dict[str, str]
) -> subprocess.Popen[str]:
    process = subprocess.Popen(command, text=True, env={**os.environ, **extra_env})
    if process.poll() is not None:
        raise RuntimeError(f"failed to start {name}")
    return process


def stop_managed_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def ensure_runtime_layout(settings: Settings) -> None:
    for path in [
        settings.log_dir,
        settings.pcap_dir,
        settings.caddy_data_dir,
        settings.runtime_dir,
        settings.config_output_dir,
    ]:
        Path(path).mkdir(parents=True, exist_ok=True)
    (Path(settings.runtime_dir) / "tls").mkdir(parents=True, exist_ok=True)
    (Path(settings.runtime_dir) / "proxy").mkdir(parents=True, exist_ok=True)


def ensure_runtime_tls_material(settings: Settings) -> None:
    tls_dir = Path(settings.runtime_dir) / "tls"
    cert_path = tls_dir / "test-cert.pem"
    key_path = tls_dir / "test-key.pem"
    openssl_config_path = tls_dir / "openssl-san.cnf"
    if cert_path.exists() and key_path.exists():
        return
    openssl_path = shutil.which("openssl")
    if openssl_path is None:
        if settings.simulation_mode:
            cert_path.write_text("simulation-cert\n", encoding="utf-8")
            key_path.write_text("simulation-key\n", encoding="utf-8")
            return
        raise RuntimeError("missing openssl for runtime TLS material generation")
    openssl_config_path.write_text(
        """
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
CN = c64gate.local

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = c64gate.local
DNS.2 = localhost
IP.1 = 127.0.0.1
""".strip()
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            openssl_path,
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-days",
            "365",
            "-config",
            str(openssl_config_path),
            "-extensions",
            "v3_req",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
        ],
        check=True,
        env={**os.environ, "RANDFILE": str(tls_dir / ".rnd")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def render_runtime_configs(settings: Settings) -> dict[str, str]:
    ensure_runtime_layout(settings)
    ensure_runtime_tls_material(settings)
    outputs = {
        "dnsmasq.conf": render_dnsmasq_config(settings),
        "nftables.conf": render_nftables_ruleset(settings),
        "Caddyfile": render_caddyfile(settings),
        "proftpd.conf": render_proftpd_config(settings),
    }
    for filename, content in outputs.items():
        (Path(settings.config_output_dir) / filename).write_text(content, encoding="utf-8")
    return outputs


def validate_binaries(simulation_mode: bool) -> dict[str, dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for binary in MANDATORY_BINARIES:
        resolved = shutil.which(binary)
        components[binary] = {"present": bool(resolved), "path": resolved, "required": True}
        if not simulation_mode and not resolved:
            raise RuntimeError(f"missing mandatory binary: {binary}")
    return components


async def serve() -> None:
    settings = get_settings()
    render_runtime_configs(settings)
    components = validate_binaries(settings.simulation_mode)
    logger = JsonLogger(Path(settings.log_dir) / "c64gate.jsonl")
    runtime_state = {
        "ready": True,
        "metrics": {"upgrade_proxy_requests": 0},
        "components": components,
    }
    app = create_app(settings=settings, logger=logger, runtime_state=runtime_state)
    upgrade_proxy = UpgradeProxyService(
        settings=settings, logger=logger, runtime_state=runtime_state
    )
    proxy_server = await upgrade_proxy.start()
    caddy_process = start_managed_process_with_env(
        [
            "caddy",
            "run",
            "--config",
            str(Path(settings.config_output_dir) / "Caddyfile"),
            "--adapter",
            "caddyfile",
        ],
        name="caddy",
        extra_env={"XDG_DATA_HOME": str(settings.caddy_data_dir.parent)},
    )
    runtime_state["components"].setdefault("caddy", {}).update({"running": True})

    uvicorn_config = uvicorn.Config(
        app,
        host=settings.controlplane_host,
        port=settings.controlplane_port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    try:
        await server.serve()
    finally:
        runtime_state["components"].setdefault("caddy", {}).update({"running": False})
        stop_managed_process(caddy_process)
        proxy_server.close()
        await proxy_server.wait_closed()
        await upgrade_proxy.client.aclose()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(serve())


if __name__ == "__main__":
    main()
