from __future__ import annotations

from common.settings import Settings


def test_network_settings_are_configurable() -> None:
    settings = Settings(
        device_interface="ve-c64",
        uplink_interface="ve-up",
        device_subnet="10.20.30.0/24",
        gateway_address="10.20.30.1",
    )
    assert settings.device_interface == "ve-c64"
    assert settings.uplink_interface == "ve-up"
    assert settings.device_subnet == "10.20.30.0/24"
    assert settings.gateway_address == "10.20.30.1"


def test_backend_hosts_follow_rest_backend_by_default() -> None:
    settings = Settings(rest_backend_url="http://192.168.1.167")
    assert settings.ftp_backend_host == "192.168.1.167"
    assert settings.telnet_backend_host == "192.168.1.167"
    assert settings.tcp_stream_backend_host == "192.168.1.167"


def test_explicit_backend_hosts_are_preserved() -> None:
    settings = Settings(
        rest_backend_url="http://192.168.1.167",
        ftp_backend_host="192.168.1.200",
        telnet_backend_host="192.168.1.201",
        tcp_stream_backend_host="192.168.1.202",
    )
    assert settings.ftp_backend_host == "192.168.1.200"
    assert settings.telnet_backend_host == "192.168.1.201"
    assert settings.tcp_stream_backend_host == "192.168.1.202"
