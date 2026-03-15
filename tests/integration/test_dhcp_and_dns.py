from __future__ import annotations

from common.config_renderers import render_dnsmasq_config


def test_dnsmasq_configuration_contains_dhcp_and_local_name(temp_settings) -> None:
    config = render_dnsmasq_config(temp_settings)
    assert "dhcp-range" in config
    assert f"dhcp-leasefile={temp_settings.runtime_dir}/dnsmasq.leases" in config
    assert f"address=/{temp_settings.hostname}/{temp_settings.gateway_address}" in config
    assert "log-queries=extra" in config
