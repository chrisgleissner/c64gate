from __future__ import annotations

from common.config_renderers import render_proftpd_config


def test_proftpd_configuration_contains_tls_and_proxy(temp_settings) -> None:
    config = render_proftpd_config(temp_settings)
    assert "TLSEngine on" in config
    assert "ProxyEngine on" in config
    assert "ProxyRole reverse" in config
