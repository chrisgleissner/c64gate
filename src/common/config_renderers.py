from __future__ import annotations

import socket
from ipaddress import ip_network
from textwrap import dedent

from common.settings import Settings


def _resolve_entry(entry: str) -> tuple[set[str], set[str]]:
    try:
        network = ip_network(entry, strict=False)
    except ValueError:
        ipv4: set[str] = set()
        ipv6: set[str] = set()
        try:
            for _, _, _, _, sockaddr in socket.getaddrinfo(entry, None):
                address = sockaddr[0]
                if ":" in address:
                    ipv6.add(address)
                else:
                    ipv4.add(address)
        except socket.gaierror:
            return set(), set()
        return ipv4, ipv6
    if network.version == 4:
        return {str(network)}, set()
    return set(), {str(network)}


def _render_elements(elements: set[str]) -> str:
    return ", ".join(sorted(elements)) if elements else ""


def _render_set(name: str, set_type: str, elements: set[str]) -> str:
    rendered_elements = _render_elements(elements)
    elements_clause = f"\n        elements = {{ {rendered_elements} }}" if rendered_elements else ""
    return dedent(
        f"""
        set {name} {{
            type {set_type}
            flags interval{elements_clause}
        }}
        """
    ).strip()


def _collect_allowlist(settings: Settings) -> tuple[set[str], set[str]]:
    ipv4: set[str] = set()
    ipv6: set[str] = set()
    for entry in settings.allowed_local_destinations:
        local_v4, local_v6 = _resolve_entry(entry)
        ipv4.update(local_v4)
        ipv6.update(local_v6)
    for entry in settings.commodore_hostnames:
        commodore_v4, commodore_v6 = _resolve_entry(entry)
        ipv4.update(commodore_v4)
        ipv6.update(commodore_v6)
    return ipv4, ipv6


def render_dnsmasq_config(settings: Settings) -> str:
    subnet = ip_network(settings.device_subnet, strict=False)
    dhcp_start = str(subnet.network_address + 50)
    dhcp_end = str(subnet.network_address + 150)
    return (
        dedent(
            f"""
        domain-needed
        bogus-priv
        no-resolv
        server={settings.dns_upstream}
        interface={settings.device_interface}
        bind-interfaces
        dhcp-authoritative
        dhcp-leasefile=/tmp/dnsmasq.leases
        dhcp-range={dhcp_start},{dhcp_end},255.255.255.0,12h
        dhcp-option=3,{settings.gateway_address}
        dhcp-option=6,{settings.gateway_address}
        address=/{settings.hostname}/{settings.gateway_address}
        local=/local/
        log-dhcp
        log-queries=extra
        """
        ).strip()
        + "\n"
    )


def render_nftables_ruleset(settings: Settings) -> str:
    allowed_ipv4, allowed_ipv6 = _collect_allowlist(settings)
    input_ports = ", ".join(
        [
            "8443",
            "2121",
            f"{settings.ftps_passive_port_start}-{settings.ftps_passive_port_end}",
        ]
    )
    commodore_hosts = " ".join(settings.commodore_hostnames)
    allowed_v4_set = _render_set("allowed_v4", "ipv4_addr", allowed_ipv4)
    allowed_v6_set = _render_set("allowed_v6", "ipv6_addr", allowed_ipv6)
    return (
        dedent(
            f"""
        flush ruleset

        table inet c64gate {{
            define device_if = \"{settings.device_interface}\"
            define uplink_if = \"{settings.uplink_interface}\"

            set rfc1918 {{
                type ipv4_addr
                flags interval
                elements = {{ 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 }}
            }}

            set blocked_v6_local {{
                type ipv6_addr
                flags interval
                elements = {{ ::1/128, fc00::/7, fe80::/10 }}
            }}

            {allowed_v4_set}

            {allowed_v6_set}

            chain input {{
                type filter hook input priority filter; policy drop;
                iifname \"lo\" counter accept
                ct state established,related accept
                tcp dport {{ {input_ports} }} counter log prefix \"c64gate-input-allow \" accept
                iifname \"lo\" tcp dport {settings.controlplane_port} counter accept
                iifname $device_if tcp dport {settings.upgrade_proxy_port} counter accept
                counter log prefix \"c64gate-input-drop \" drop
            }}

            chain forward {{
                type filter hook forward priority filter; policy drop;
                ct state established,related accept
                iifname $device_if oifname $uplink_if ip daddr @rfc1918 \
                    counter log prefix \"c64gate-rfc1918-drop \" drop
                iifname $device_if oifname $uplink_if ip6 daddr @blocked_v6_local \
                    counter log prefix \"c64gate-ipv6-local-drop \" drop
                iifname $device_if oifname $uplink_if ip daddr @allowed_v4 \
                    counter log prefix \"c64gate-allow-forward \" accept
                iifname $device_if oifname $uplink_if ip6 daddr @allowed_v6 \
                    counter log prefix \"c64gate-allow-forward-v6 \" accept
                counter log prefix \"c64gate-forward-drop \" drop
            }}

            chain output {{
                type filter hook output priority filter; policy accept;
            }}
        }}

        table ip c64gate_nat {{
            chain prerouting {{
                type nat hook prerouting priority dstnat; policy accept;
                iifname \"{settings.device_interface}\" tcp dport 80 \
                    redirect to :{settings.upgrade_proxy_port}
            }}
        }}

        # Commodore destinations are documented for allowlist resolution: {commodore_hosts}
        """
        ).strip()
        + "\n"
    )


def render_caddyfile(settings: Settings) -> str:
    rest_backend = settings.rest_backend_url.removeprefix("http://").removeprefix("https://")
    addresses = ", ".join(
        f"https://{address}"
        for address in dict.fromkeys(["127.0.0.1", "localhost", settings.hostname])
    )
    return (
        dedent(
            f"""
        {{
            admin off
            https_port 8443
            default_sni 127.0.0.1
            log {{
                    output file {settings.log_dir}/caddy-access.jsonl {{
                        roll_size 10MiB
                        roll_keep 5
                    }}
                format json
            }}
            local_certs
            skip_install_trust
        }}

        {addresses} {{
            tls internal

            handle_path /api/* {{
                reverse_proxy {rest_backend} {{
                    header_up X-Forwarded-Proto https
                    header_up X-C64Gate true
                    header_up X-C64Gate-Device {settings.hostname}
                }}
            }}

            handle /v1/* {{
                reverse_proxy {rest_backend} {{
                    header_up X-Forwarded-Proto https
                    header_up X-C64Gate true
                    header_up X-C64Gate-Device {settings.hostname}
                }}
            }}

            handle /dashboard* {{
                reverse_proxy 127.0.0.1:{settings.controlplane_port}
            }}

            handle /health {{
                reverse_proxy 127.0.0.1:{settings.controlplane_port}
            }}

            handle /ready {{
                reverse_proxy 127.0.0.1:{settings.controlplane_port}
            }}
        }}
        """
        ).strip()
        + "\n"
    )


def render_proftpd_config(settings: Settings) -> str:
    return (
        dedent(
            f"""
        Include /etc/proftpd/modules.conf
        LoadModule mod_tls.c
        LoadModule mod_proxy.c

        ServerName "C64 Gate FTPS"
        ServerType standalone
        Port 2121
        UseIPv6 off
        DefaultServer on
        DefaultAddress localhost
        SocketBindTight on
        CapabilitiesEngine off
        RequireValidShell off
        TimeoutIdle 600

        <IfModule mod_delay.c>
            DelayEngine off
        </IfModule>

        TLSEngine on
        TLSProtocol TLSv1.2 TLSv1.3
        TLSRequired on
        TLSOptions NoSessionReuseRequired
        TLSRenegotiate required off
        TLSRSACertificateFile /run/c64gate/tls/test-cert.pem
        TLSRSACertificateKeyFile /run/c64gate/tls/test-key.pem
        MasqueradeAddress {settings.ftps_public_host}
        TLSMasqueradeAddress {settings.ftps_public_host}
        PassivePorts {settings.ftps_passive_port_start} {settings.ftps_passive_port_end}
        TransferLog /var/lib/c64gate/logs/proftpd-transfer.log
        ExtendedLog /var/lib/c64gate/logs/proftpd-access.log ALL default

        <IfModule mod_proxy.c>
            ProxyEngine on
            ProxyLog /var/lib/c64gate/logs/proftpd-proxy.log
            ProxyRole reverse
            ProxyTLSTransferProtectionPolicy clear
            ProxyTables /run/c64gate/proxy
            ProxyReverseServers ftp://{settings.ftp_backend_host}:{settings.ftp_backend_port}
        </IfModule>
        """
        ).strip()
        + "\n"
    )
