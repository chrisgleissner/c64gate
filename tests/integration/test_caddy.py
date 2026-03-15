from __future__ import annotations

from common.config_renderers import render_caddyfile


def test_caddyfile_contains_https_facade_and_logging(temp_settings) -> None:
    config = render_caddyfile(temp_settings)
    assert "tls /run/c64gate/tls/test-cert.pem /run/c64gate/tls/test-key.pem" in config
    assert "reverse_proxy" in config
    assert "format json" in config
    assert "X-C64Gate true" in config
