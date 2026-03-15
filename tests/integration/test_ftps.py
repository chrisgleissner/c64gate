from __future__ import annotations

from common.config_renderers import render_proftpd_config


def test_proftpd_configuration_contains_tls_and_proxy(temp_settings) -> None:
    config = render_proftpd_config(temp_settings)
    assert "Include /etc/proftpd/modules.conf" in config
    assert "LoadModule mod_tls.c" in config
    assert "LoadModule mod_proxy.c" in config
    assert "TLSEngine on" in config
    assert "DelayEngine off" in config
    assert "ProxyEngine on" in config
    assert "ProxyRole reverse" in config
