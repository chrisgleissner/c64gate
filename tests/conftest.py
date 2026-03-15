from __future__ import annotations

import asyncio
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from typing import Any

import pytest
import trustme

from common.settings import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--image", action="store", default="c64gate:dev")


@pytest.fixture
def image_name(request: pytest.FixtureRequest) -> str:
    return str(request.config.getoption("--image"))


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def temp_settings(tmp_path: Path) -> Settings:
    return Settings(
        log_dir=tmp_path / "logs",
        pcap_dir=tmp_path / "pcap",
        runtime_dir=tmp_path / "run",
        config_output_dir=tmp_path / "run/config",
        controlplane_port=get_free_port(),
        upgrade_proxy_port=get_free_port(),
        simulation_mode=True,
    )


class _StaticHandler(BaseHTTPRequestHandler):
    response_text = "ok"

    def do_GET(self) -> None:  # noqa: N802
        body = self.response_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


class BackendServer:
    def __init__(self, response_text: str, tls_context: SSLContext | None = None) -> None:
        self.port = get_free_port()
        handler = type("StaticHandler", (_StaticHandler,), {"response_text": response_text})
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        if tls_context is not None:
            self.server.socket = tls_context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> BackendServer:
        self.thread.start()
        return self

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def trustme_ca(tmp_path: Path) -> dict[str, Path]:
    ca = trustme.CA()
    cert = ca.issue_cert("localhost", "127.0.0.1")
    cert_path = tmp_path / "server.pem"
    key_path = tmp_path / "server.key"
    ca_path = tmp_path / "ca.pem"
    cert.private_key_pem.write_to_path(key_path)
    cert.cert_chain_pems[0].write_to_path(cert_path)
    ca.cert_pem.write_to_path(ca_path)
    return {"cert": cert_path, "key": key_path, "ca": ca_path}


@pytest.fixture
def openssl_self_signed(tmp_path: Path) -> dict[str, Path]:
    cert_path = tmp_path / "selfsigned.pem"
    key_path = tmp_path / "selfsigned.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"cert": cert_path, "key": key_path}


def build_tls_context(cert_path: Path, key_path: Path) -> SSLContext:
    context = SSLContext(PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


async def request_via_proxy(proxy_port: int, target: str) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
    request = (
        f"GET {target} HTTP/1.1\r\n"
        f"Host: {target.removeprefix('http://').removeprefix('https://').split('/', 1)[0]}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    writer.write(request)
    await writer.drain()
    payload = await reader.read()
    writer.close()
    await writer.wait_closed()
    return payload
