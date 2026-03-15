from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from common.capture import CapturePlan
from common.settings import Settings
from controlplane import runtime


class FakeProcess:
    def __init__(self, poll_result: int | None = None, timeout_on_wait: bool = False) -> None:
        self._poll_result = poll_result
        self.timeout_on_wait = timeout_on_wait
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._poll_result

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int) -> None:
        if self.timeout_on_wait and not self.killed:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)

    def kill(self) -> None:
        self.killed = True


def _runtime_settings(tmp_path: Path, **overrides: object) -> Settings:
    payload: dict[str, object] = {
        "log_dir": tmp_path / "logs",
        "pcap_dir": tmp_path / "pcap",
        "caddy_data_dir": tmp_path / "caddy",
        "runtime_dir": tmp_path / "run",
        "config_output_dir": tmp_path / "run/config",
        "controlplane_port": 18081,
        "upgrade_proxy_port": 18080,
        "simulation_mode": True,
    }
    payload.update(overrides)
    return Settings(
        **payload,
    )


def test_start_managed_process_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[dict[str, object]] = []

    class PopenStub(FakeProcess):
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            super().__init__(poll_result=None)
            created.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(runtime.subprocess, "Popen", PopenStub)
    process = runtime.start_managed_process(["echo", "ok"], name="echo", extra_env={"X": "1"})
    assert isinstance(process, FakeProcess)
    assert created[0]["kwargs"]["env"]["X"] == "1"

    class FailedPopen(FakeProcess):
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            super().__init__(poll_result=1)

    monkeypatch.setattr(runtime.subprocess, "Popen", FailedPopen)
    with pytest.raises(RuntimeError):
        runtime.start_managed_process(["false"], name="broken")


def test_stop_managed_process_handles_timeout() -> None:
    process = FakeProcess(poll_result=None, timeout_on_wait=True)
    runtime.stop_managed_process(process)
    assert process.terminated is True
    assert process.killed is True


def test_ensure_runtime_layout_and_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path)
    chowned: list[Path] = []
    monkeypatch.setattr(runtime.os, "geteuid", lambda: 0)
    monkeypatch.setattr(runtime.os, "chown", lambda path, uid, gid: chowned.append(Path(path)))
    monkeypatch.setattr("pwd.getpwnam", lambda _: SimpleNamespace(pw_uid=123, pw_gid=456))
    runtime.ensure_runtime_layout(settings)
    runtime.ensure_runtime_credentials(settings)
    assert settings.log_dir.exists()
    assert settings.caddy_data_dir.exists()
    assert (settings.runtime_dir / "tls").exists()
    assert (settings.runtime_dir / "proxy").exists()
    assert settings.log_dir in chowned
    assert settings.caddy_data_dir in chowned
    assert (settings.runtime_dir / "proftpd.passwd").exists()


def test_prepare_simulation_network_updates_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path, device_interface="eth9", capture_interface="any")
    calls: list[list[str]] = []

    def fake_interface_exists(name: str) -> bool:
        return name == "c64gate-sim0"

    monkeypatch.setattr(runtime, "interface_exists", fake_interface_exists)
    monkeypatch.setattr(runtime, "run_command", lambda command, name: calls.append(command))
    runtime.prepare_simulation_network(settings)
    assert settings.device_interface == "c64gate-sim0"
    assert settings.capture_interface == "c64gate-sim0"
    assert calls[0][:3] == ["ip", "addr", "replace"]
    assert calls[1] == ["ip", "link", "set", "c64gate-sim0", "up"]


def test_prepare_simulation_network_creates_dummy_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path, device_interface="eth9")
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime, "interface_exists", lambda name: False)
    monkeypatch.setattr(runtime, "run_command", lambda command, name: calls.append(command))
    runtime.prepare_simulation_network(settings)
    assert calls[0] == ["ip", "link", "add", "c64gate-sim0", "type", "dummy"]


def test_ensure_runtime_tls_material_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _runtime_settings(tmp_path)
    (settings.runtime_dir / "tls").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: None)
    runtime.ensure_runtime_tls_material(settings)
    cert = (settings.runtime_dir / "tls/test-cert.pem").read_text(encoding="utf-8")
    assert cert == "simulation-cert\n"

    secured = _runtime_settings(tmp_path / "strict", simulation_mode=False)
    (secured.runtime_dir / "tls").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError):
        runtime.ensure_runtime_tls_material(secured)


def test_ensure_runtime_tls_material_uses_openssl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path)
    (settings.runtime_dir / "tls").mkdir(parents=True, exist_ok=True)
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        check: bool,
        env: dict[str, str],
        stdout: int,
        stderr: int,
    ) -> None:
        calls.append(command)
        cert_path = Path(command[command.index("-out") + 1])
        key_path = Path(command[command.index("-keyout") + 1])
        cert_path.write_text("cert\n", encoding="utf-8")
        key_path.write_text("key\n", encoding="utf-8")

    monkeypatch.setattr(runtime.shutil, "which", lambda _: "/usr/bin/openssl")
    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    runtime.ensure_runtime_tls_material(settings)
    assert calls
    assert (settings.runtime_dir / "tls/openssl-san.cnf").exists()


def test_render_runtime_configs_and_validate_binaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: None)
    outputs = runtime.render_runtime_configs(settings)
    assert set(outputs) == {"dnsmasq.conf", "nftables.conf", "Caddyfile", "proftpd.conf"}
    assert (settings.config_output_dir / "dnsmasq.conf").exists()

    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    components = runtime.validate_binaries(simulation_mode=False)
    assert components["nft"]["present"] is True

    monkeypatch.setattr(
        runtime.shutil,
        "which",
        lambda binary: None if binary == "nft" else f"/usr/bin/{binary}",
    )
    with pytest.raises(RuntimeError):
        runtime.validate_binaries(simulation_mode=False)
    simulated = runtime.validate_binaries(simulation_mode=True)
    assert simulated["nft"]["present"] is False


def test_update_component_state_and_apply_nftables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"components": {}, "ready": False}
    for component in runtime.MANDATORY_COMPONENTS[:-1]:
        runtime.update_component_state(state, component, healthy=True)
    assert state["ready"] is False
    calls: list[list[str]] = []
    settings = _runtime_settings(tmp_path)
    monkeypatch.setattr(runtime, "run_command", lambda command, name: calls.append(command))
    runtime.apply_nftables(settings, state)
    assert calls[0][0] == "nft"
    assert state["components"]["nftables"]["healthy"] is True


def test_should_start_simulated_rest_backend(tmp_path: Path) -> None:
    settings = _runtime_settings(tmp_path)
    assert runtime.should_start_simulated_rest_backend(settings) is True
    external = _runtime_settings(
        tmp_path / "external",
        rest_backend_url="http://192.168.1.10:8080",
    )
    assert runtime.should_start_simulated_rest_backend(external) is False


def test_mandatory_components_for_simulation(tmp_path: Path) -> None:
    simulated = _runtime_settings(tmp_path)
    assert "dnsmasq" not in runtime.mandatory_components_for(simulated)

    secured = _runtime_settings(tmp_path / "real", simulation_mode=False)
    assert "dnsmasq" in runtime.mandatory_components_for(secured)


def test_can_drop_privileges_to_service_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writable = tmp_path / "writable"
    writable.mkdir()
    writable.chmod(0o700)
    monkeypatch.setattr(runtime.os, "geteuid", lambda: 0)
    monkeypatch.setattr(runtime, "_service_account_ids", lambda: (writable.stat().st_uid, 1000))
    assert runtime.can_drop_privileges_to_service_user(writable) is True
    monkeypatch.setattr(runtime, "_service_account_ids", lambda: (999999, 999999))
    assert runtime.can_drop_privileges_to_service_user(writable) is False


@pytest.mark.asyncio
async def test_simulated_rest_backend_serves_version(tmp_path: Path) -> None:
    settings = _runtime_settings(tmp_path, rest_backend_url="http://127.0.0.1:18082")
    server = await runtime.start_simulated_rest_backend(settings)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 18082)
        writer.write(b"GET /v1/version HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        await writer.drain()
        payload = await reader.read()
        assert b"200 OK" in payload
        assert b'"version": "0.0.1"' in payload
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_monitor_processes_updates_exit_flag() -> None:
    state = {"components": {}, "ready": False}
    server = SimpleNamespace(should_exit=False)
    managed = {"dnsmasq": FakeProcess(poll_result=1)}
    await runtime.monitor_processes(managed, state, server)
    assert server.should_exit is True
    assert state["components"]["dnsmasq"]["healthy"] is False


@pytest.mark.asyncio
async def test_serve_orchestrates_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _runtime_settings(tmp_path)
    calls: list[str] = []

    class FakeProxyServer:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            return None

    class FakeUpgradeProxyService:
        def __init__(
            self,
            settings: Settings,
            logger: object,
            runtime_state: dict[str, object],
        ) -> None:
            self.client = SimpleNamespace(aclose=self._aclose)
            self.server = FakeProxyServer()

        async def _aclose(self) -> None:
            return None

        async def start(self) -> FakeProxyServer:
            return self.server

    class FakeServer:
        def __init__(self, config: object) -> None:
            self.should_exit = False

        async def serve(self) -> None:
            return None

    class FakeTask:
        def __init__(self, coro: object) -> None:
            self.coro = coro
            self.cancelled = False
            self.coro.close()

        def cancel(self) -> None:
            self.cancelled = True

    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runtime,
        "validate_management_auth",
        lambda current: calls.append("validate_auth"),
    )
    monkeypatch.setattr(
        runtime,
        "validate_binaries",
        lambda simulation_mode: {"caddy": {"present": True}},
    )
    monkeypatch.setattr(
        runtime,
        "prepare_simulation_network",
        lambda current: calls.append("prepare_network"),
    )
    monkeypatch.setattr(runtime, "render_runtime_configs", lambda current: {"Caddyfile": "ok"})
    monkeypatch.setattr(runtime, "apply_nftables", lambda current, state: calls.append("apply_nft"))
    monkeypatch.setattr(runtime, "create_app", lambda settings, logger, runtime_state: object())
    monkeypatch.setattr(runtime, "UpgradeProxyService", FakeUpgradeProxyService)
    monkeypatch.setattr(
        runtime,
        "build_capture_plan",
        lambda current: CapturePlan(["dumpcap"], ["tshark"], ["capinfos"]),
    )
    monkeypatch.setattr(
        runtime,
        "start_managed_process",
        lambda command, name, drop_privileges=False, extra_env=None: FakeProcess(),
    )
    monkeypatch.setattr(
        runtime,
        "stop_managed_process",
        lambda process: calls.append("stop_process"),
    )
    monkeypatch.setattr(runtime.asyncio, "create_task", lambda coro: FakeTask(coro))
    monkeypatch.setattr(runtime.uvicorn, "Config", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(runtime.uvicorn, "Server", FakeServer)

    await runtime.serve()
    assert "validate_auth" in calls
    assert "prepare_network" in calls
    assert "apply_nft" in calls
    assert calls.count("stop_process") == 3
