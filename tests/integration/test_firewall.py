from __future__ import annotations

from common.config_renderers import render_nftables_ruleset


def test_nftables_ruleset_contains_required_policy(temp_settings) -> None:
    ruleset = render_nftables_ruleset(temp_settings)
    assert "policy drop" in ruleset
    assert "c64gate-rfc1918-drop" in ruleset
    assert "c64gate-input-allow" in ruleset
    assert "commodore.net" in ruleset
