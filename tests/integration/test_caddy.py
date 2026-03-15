from __future__ import annotations

from common.config_renderers import render_caddyfile


def test_caddyfile_contains_https_facade_and_logging(temp_settings) -> None:
    config = render_caddyfile(temp_settings)
    assert "https_port 8443" in config
    assert "default_sni 127.0.0.1" in config
    assert "local_certs" in config
    assert "tls internal" in config
    assert "https://127.0.0.1, https://localhost" in config
    assert "reverse_proxy" in config
    assert "format json" in config
    assert f"output file {temp_settings.log_dir}/caddy-access.jsonl {{" in config
    assert "roll_size 10MiB" in config
    assert "roll_keep 5" in config
    assert "X-C64Gate true" in config
    assert "handle /health" in config
    assert "handle /ready" in config
    assert "handle /api/*" in config
    assert "handle_path /api/*" not in config
    assert "basic_auth" not in config
