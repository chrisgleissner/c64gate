from __future__ import annotations

from common.config_renderers import render_proftpd_config


def test_proftpd_configuration_contains_tls_and_proxy(temp_settings) -> None:
    config = render_proftpd_config(temp_settings)
    assert "Include /etc/proftpd/modules.conf" in config
    assert "LoadModule mod_tls.c" in config
    assert "LoadModule mod_proxy.c" in config
    assert "TLSEngine on" in config
    assert "DefaultAddress localhost" in config
    assert "SocketBindTight on" in config
    assert "CapabilitiesEngine off" in config
    assert "TLSOptions NoSessionReuseRequired" in config
    assert "TLSRenegotiate required off" in config
    assert "DelayEngine off" in config
    assert "MasqueradeAddress 127.0.0.1" in config
    assert "TLSMasqueradeAddress 127.0.0.1" in config
    assert "PassivePorts 30000 30009" in config
    assert "ProxyEngine on" in config
    assert "ProxyTLSTransferProtectionPolicy clear" in config
    assert "ProxyRole reverse" in config
