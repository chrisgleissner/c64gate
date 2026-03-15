from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="C64GATE_", case_sensitive=False)

    device_interface: str = "eth1"
    uplink_interface: str = "eth0"
    device_subnet: str = "192.168.50.0/24"
    gateway_address: str = "192.168.50.1"
    hostname: str = "c64gate.local"
    dns_upstream: str = "1.1.1.1"
    allowed_local_destinations: list[str] = Field(default_factory=list)
    commodore_hostnames: list[str] = Field(default_factory=lambda: ["commodore.net"])
    lan_isolation: bool = True

    rest_backend_url: str = "http://127.0.0.1:8080"
    ftp_backend_host: str = "127.0.0.1"
    ftp_backend_port: int = 21
    telnet_backend_host: str = "127.0.0.1"
    telnet_backend_port: int = 23
    tcp_stream_backend_host: str = "127.0.0.1"
    tcp_stream_backend_port: int = 1541

    caddy_version: str = "2.11.2"
    dashboard_user: str = "admin"
    dashboard_password: str = "changeme"
    controlplane_host: str = "127.0.0.1"
    controlplane_port: int = 8081
    upgrade_proxy_host: str = "0.0.0.0"
    upgrade_proxy_port: int = 18080
    https_port_map: dict[int, int] = Field(default_factory=lambda: {80: 443})
    tls_ca_bundle: Path | None = None

    strict_tls_mode: bool = False
    verbose_logging: bool = False
    verbose_stream_logging: bool = False
    simulation_mode: bool = False

    log_dir: Path = Path("/var/lib/c64gate/logs")
    pcap_dir: Path = Path("/var/lib/c64gate/pcap")
    caddy_data_dir: Path = Path("/var/lib/c64gate/caddy")
    runtime_dir: Path = Path("/run/c64gate")
    config_output_dir: Path = Path("/run/c64gate/config")
    capture_interface: str = "any"
    capture_rotation_seconds: int = 300
    capture_rotation_megabytes: int = 10
    capture_ring_files: int = 5
    proxy_client_header_timeout_seconds: float = 5.0
    proxy_client_body_timeout_seconds: float = 5.0
    proxy_max_header_bytes: int = 16384
    proxy_max_body_bytes: int = 1048576
    log_rotation_bytes: int = 1048576
    log_backup_count: int = 5
    log_redacted_headers: list[str] = Field(
        default_factory=lambda: ["authorization", "cookie", "proxy-authorization", "set-cookie"]
    )

    def dashboard_password_is_weak(self) -> bool:
        return (
            self.dashboard_password in {"", "changeme", "password", "admin"}
            or len(self.dashboard_password) < 12
        )

    def device_subnet_prefixlen(self) -> int:
        return int(ip_network(self.device_subnet, strict=False).prefixlen)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
