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
