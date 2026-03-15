from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.smoke


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_image_metadata_and_smoke_runtime(image_name: str, tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    port = _free_port()
    container_name = f"c64gate-smoke-{port}"
    caddy_dir = tmp_path / "caddy"
    logs_dir = tmp_path / "logs"
    pcap_dir = tmp_path / "pcap"
    caddy_dir.mkdir()
    logs_dir.mkdir()
    pcap_dir.mkdir()
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--cap-drop",
            "ALL",
            "--cap-add",
            "NET_ADMIN",
            "--cap-add",
            "NET_RAW",
            "--read-only",
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/tmp",
            "-e",
            "C64GATE_SIMULATION_MODE=1",
            "-e",
            "C64GATE_DASHBOARD_PASSWORD=changeme",
            "-p",
            f"127.0.0.1:{port}:8443",
            "-v",
            f"{caddy_dir}:/var/lib/c64gate/caddy",
            "-v",
            f"{logs_dir}:/var/lib/c64gate/logs",
            "-v",
            f"{pcap_dir}:/var/lib/c64gate/pcap",
            image_name,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        for _ in range(30):
            try:
                response = httpx.get(
                    f"https://127.0.0.1:{port}/health",
                    timeout=1.0,
                    verify=False,
                    auth=("admin", "changeme"),
                )
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(1)
        else:
            raise AssertionError("control plane did not become healthy")
        ready = httpx.get(
            f"https://127.0.0.1:{port}/ready",
            timeout=2.0,
            verify=False,
            auth=("admin", "changeme"),
        ).json()
        version = httpx.get(
            f"https://127.0.0.1:{port}/v1/version",
            timeout=2.0,
            verify=False,
        ).json()
        assert ready["status"] == "ready"
        assert ready["components"]["caddy"]["healthy"] is True
        assert ready["components"]["proftpd"]["healthy"] is True
        assert ready["components"]["dumpcap"]["healthy"] is True
        assert "privilege_dropped" in ready["components"]["caddy"]
        assert version["device"] == "c64u-sim"
        assert version["version"] == "0.0.1"
        versions = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "sh",
                "-lc",
                "caddy version && proftpd -v && dumpcap --version | head -n 1",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "v2.11.2" in versions.stdout or "2.11.2" in versions.stdout
        (Path("artifacts")).mkdir(exist_ok=True)
        Path("artifacts/smoke-ready.json").write_text(json.dumps(ready, indent=2), encoding="utf-8")
        Path("artifacts/smoke-version.json").write_text(
            json.dumps(version, indent=2), encoding="utf-8"
        )
        Path("artifacts/smoke-versions.txt").write_text(versions.stdout, encoding="utf-8")
    finally:
        logs = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/smoke-container.log").write_text(
            logs.stdout + logs.stderr, encoding="utf-8"
        )
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True)
