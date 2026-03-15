from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
import subprocess
from contextlib import suppress
from ipaddress import ip_network
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn

from common.capture import build_capture_plan
from common.config_renderers import (
    render_caddyfile,
    render_dnsmasq_config,
    render_nftables_ruleset,
    render_proftpd_config,
)
from common.logging import JsonLogger
from common.settings import Settings, get_settings
from controlplane.app import create_app
from controlplane.auth import validate_management_auth
from upgrade_proxy.service import UpgradeProxyService

MANDATORY_BINARIES = [
    "nft",
    "dnsmasq",
    "caddy",
    "proftpd",
    "dumpcap",
    "tshark",
    "capinfos",
    "ip",
]
MANDATORY_COMPONENTS = ["nftables", "dnsmasq", "proftpd", "dumpcap", "upgrade_proxy", "caddy"]


def should_start_simulated_rest_backend(settings: Settings) -> bool:
    if not settings.simulation_mode:
        return False
    split = urlsplit(settings.rest_backend_url)
    return split.scheme == "http" and (split.hostname in {"127.0.0.1", "localhost"})


async def handle_simulated_rest_backend(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    payload = {"device": "c64u-sim", "version": "0.0.1", "transport": "https-relay"}
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    status = b"200 OK"
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2.0)
        request_line = request.splitlines()[0].decode("ascii", errors="replace")
        method, path, _ = request_line.split(" ", 2)
        if method != "GET" or path not in {"/api/version", "/api/v1/info"}:
            status = b"404 Not Found"
            body = json.dumps({"detail": "not found"}).encode("utf-8")
    except (TimeoutError, asyncio.IncompleteReadError, ValueError):
        status = b"400 Bad Request"
        body = json.dumps({"detail": "bad request"}).encode("utf-8")
    response = b"".join(
        [
            b"HTTP/1.1 ",
            status,
            b"\r\nContent-Type: application/json\r\n",
            f"Content-Length: {len(body)}".encode("ascii"),
            b"\r\nConnection: close\r\n\r\n",
            body,
        ]
    )
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def start_simulated_rest_backend(settings: Settings) -> asyncio.AbstractServer:
    split = urlsplit(settings.rest_backend_url)
    host = split.hostname or "127.0.0.1"
    port = split.port or 80
    return await asyncio.start_server(handle_simulated_rest_backend, host=host, port=port)


def _drop_privileges_preexec() -> None:
    import pwd

    account = pwd.getpwnam("c64gate")
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)


def _service_account_ids() -> tuple[int, int]:
    import pwd

    account = pwd.getpwnam("c64gate")
    return account.pw_uid, account.pw_gid


def start_managed_process(
    command: list[str],
    name: str,
    drop_privileges: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        text=True,
        env={**os.environ, **(extra_env or {})},
        preexec_fn=_drop_privileges_preexec if drop_privileges and os.geteuid() == 0 else None,
    )
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
    secure_paths = [settings.log_dir, settings.pcap_dir, settings.caddy_data_dir]
    runtime_paths = [settings.runtime_dir, settings.config_output_dir]
    for path in secure_paths + runtime_paths:
        Path(path).mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        service_uid, service_gid = _service_account_ids()
        for path in [settings.log_dir, settings.caddy_data_dir]:
            try:
                os.chown(path, service_uid, service_gid)
            except PermissionError:
                pass
    os.chmod(settings.log_dir, 0o750)
    os.chmod(settings.pcap_dir, 0o750)
    os.chmod(settings.caddy_data_dir, 0o700)
    (Path(settings.runtime_dir) / "tls").mkdir(parents=True, exist_ok=True)
    (Path(settings.runtime_dir) / "proxy").mkdir(parents=True, exist_ok=True)


def can_drop_privileges_to_service_user(*paths: Path) -> bool:
    if os.geteuid() != 0:
        return False
    service_uid, service_gid = _service_account_ids()
    for path in paths:
        metadata = path.stat()
        mode = metadata.st_mode
        if metadata.st_uid == service_uid and mode & stat.S_IWUSR and mode & stat.S_IXUSR:
            continue
        if metadata.st_gid == service_gid and mode & stat.S_IWGRP and mode & stat.S_IXGRP:
            continue
        if mode & stat.S_IWOTH and mode & stat.S_IXOTH:
            continue
        return False
    return True


def ensure_runtime_credentials(settings: Settings) -> None:
    passwd_path = Path(settings.runtime_dir) / "proftpd.passwd"
    if not passwd_path.exists():
        passwd_path.write_text(
            "proxy:$1$4m5/Bd1B$YG1n9LkB2tVx1lGzJh8qz/:1000:1000::/tmp:/usr/sbin/nologin\n",
            encoding="utf-8",
        )
        os.chmod(passwd_path, 0o640)


def run_command(command: list[str], name: str) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def interface_exists(interface_name: str) -> bool:
    return Path(f"/sys/class/net/{interface_name}").exists()


def prepare_simulation_network(settings: Settings) -> None:
    if not settings.simulation_mode or interface_exists(settings.device_interface):
        return
    simulation_interface = "c64gate-sim0"
    if not interface_exists(simulation_interface):
        run_command(["ip", "link", "add", simulation_interface, "type", "dummy"], "dummy interface")
    subnet = ip_network(settings.device_subnet, strict=False)
    run_command(
        [
            "ip",
            "addr",
            "replace",
            f"{settings.gateway_address}/{subnet.prefixlen}",
            "dev",
            simulation_interface,
        ],
        "simulation interface address",
    )
    run_command(["ip", "link", "set", simulation_interface, "up"], "simulation interface up")
    settings.device_interface = simulation_interface
    if settings.capture_interface == "any":
        settings.capture_interface = simulation_interface


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
    ensure_runtime_credentials(settings)
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


def update_component_state(
    runtime_state: dict[str, Any], component: str, **fields: Any
) -> None:
    runtime_state.setdefault("components", {}).setdefault(component, {}).update(fields)
    runtime_state["ready"] = all(
        runtime_state.get("components", {}).get(name, {}).get("healthy", False)
        for name in MANDATORY_COMPONENTS
    )


def apply_nftables(settings: Settings, runtime_state: dict[str, Any]) -> None:
    run_command(["nft", "-f", str(Path(settings.config_output_dir) / "nftables.conf")], "nftables")
    run_command(["nft", "list", "table", "inet", "c64gate"], "nftables verify")
    update_component_state(runtime_state, "nftables", running=True, healthy=True, required=True)


async def monitor_processes(
    managed_processes: dict[str, subprocess.Popen[str]],
    runtime_state: dict[str, Any],
    server: uvicorn.Server,
) -> None:
    while True:
        for name, process in managed_processes.items():
            healthy = process.poll() is None
            update_component_state(
                runtime_state,
                name,
                running=healthy,
                healthy=healthy,
                required=True,
            )
            if not healthy:
                server.should_exit = True
                return
        await asyncio.sleep(1)


async def serve() -> None:
    settings = get_settings()
    validate_management_auth(settings)
    components = validate_binaries(settings.simulation_mode)
    prepare_simulation_network(settings)
    render_runtime_configs(settings)
    logger = JsonLogger(Path(settings.log_dir) / "c64gate.jsonl", settings=settings)
    runtime_state = {
        "ready": False,
        "metrics": {"upgrade_proxy_requests": 0},
        "components": components,
    }
    apply_nftables(settings, runtime_state)
    app = create_app(settings=settings, logger=logger, runtime_state=runtime_state)
    upgrade_proxy = UpgradeProxyService(
        settings=settings, logger=logger, runtime_state=runtime_state
    )
    simulated_backend_server: asyncio.AbstractServer | None = None
    if should_start_simulated_rest_backend(settings):
        simulated_backend_server = await start_simulated_rest_backend(settings)
        update_component_state(
            runtime_state,
            "rest_backend_simulation",
            running=True,
            healthy=True,
            required=False,
        )
    proxy_server = await upgrade_proxy.start()
    update_component_state(
        runtime_state,
        "upgrade_proxy",
        running=True,
        healthy=True,
        required=True,
    )

    dnsmasq_process = start_managed_process(
        [
            "dnsmasq",
            "--keep-in-foreground",
            f"--conf-file={Path(settings.config_output_dir) / 'dnsmasq.conf'}",
        ],
        name="dnsmasq",
    )
    proftpd_process = start_managed_process(
        ["proftpd", "-n", "-c", str(Path(settings.config_output_dir) / "proftpd.conf")],
        name="proftpd",
    )
    dumpcap_process = start_managed_process(
        build_capture_plan(settings).dumpcap_command,
        name="dumpcap",
    )
    drop_caddy_privileges = can_drop_privileges_to_service_user(
        settings.log_dir,
        settings.caddy_data_dir,
    )
    caddy_process = start_managed_process(
        [
            "caddy",
            "run",
            "--config",
            str(Path(settings.config_output_dir) / "Caddyfile"),
            "--adapter",
            "caddyfile",
        ],
        name="caddy",
        drop_privileges=drop_caddy_privileges,
        extra_env={"XDG_DATA_HOME": str(settings.caddy_data_dir.parent)},
    )
    managed_processes = {
        "dnsmasq": dnsmasq_process,
        "proftpd": proftpd_process,
        "dumpcap": dumpcap_process,
        "caddy": caddy_process,
    }
    for component_name in managed_processes:
        update_component_state(
            runtime_state,
            component_name,
            running=True,
            healthy=True,
            required=True,
        )
    update_component_state(
        runtime_state,
        "caddy",
        privilege_dropped=drop_caddy_privileges,
    )

    uvicorn_config = uvicorn.Config(
        app,
        host=settings.controlplane_host,
        port=settings.controlplane_port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    monitor_task = asyncio.create_task(monitor_processes(managed_processes, runtime_state, server))
    try:
        await server.serve()
    finally:
        monitor_task.cancel()
        for process in managed_processes.values():
            stop_managed_process(process)
        update_component_state(
            runtime_state,
            "upgrade_proxy",
            running=False,
            healthy=False,
            required=True,
        )
        if simulated_backend_server is not None:
            simulated_backend_server.close()
            await simulated_backend_server.wait_closed()
        proxy_server.close()
        await proxy_server.wait_closed()
        await upgrade_proxy.client.aclose()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(serve())


if __name__ == "__main__":
    main()
