from __future__ import annotations

from common.config_renderers import render_nftables_ruleset


def test_nftables_ruleset_contains_required_policy(temp_settings) -> None:
    ruleset = render_nftables_ruleset(temp_settings)
    assert "policy drop" in ruleset
    assert "c64gate-rfc1918-drop" in ruleset
    assert "c64gate-ipv6-local-drop" in ruleset
    assert "c64gate-input-allow" in ruleset
    assert f"redirect to :{temp_settings.upgrade_proxy_port}" in ruleset
    assert "allowed_v6" in ruleset
    assert "ip daddr != @rfc1918" not in ruleset
    assert "commodore.net" in ruleset


def test_nftables_ruleset_handles_empty_allowlists(temp_settings) -> None:
    ruleset = render_nftables_ruleset(
        temp_settings.model_copy(
            update={"allowed_local_destinations": [], "commodore_hostnames": []}
        )
    )
    assert "elements = {  }" not in ruleset
    assert "set allowed_v4" in ruleset
    assert "set allowed_v6" in ruleset
