from __future__ import annotations

from ipaddress import ip_network
from textwrap import dedent

from common.settings import Settings


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
    allowed_destinations = "\n".join(
        f'                ip daddr {entry} counter log prefix "c64gate-allow-local " accept'
        for entry in settings.allowed_local_destinations
    )
    input_ports = ", ".join(
        ["8443", "2121", str(settings.controlplane_port), str(settings.upgrade_proxy_port)]
    )
    commodore_hosts = " ".join(settings.commodore_hostnames)
    lan_guard = "drop" if settings.lan_isolation else "accept"
    return (
        dedent(
            f"""
        flush ruleset

        table inet c64gate {{
            set rfc1918 {{
                type ipv4_addr
                elements = {{ 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 }}
            }}

            chain input {{
                type filter hook input priority filter; policy drop;
                ct state established,related accept
                tcp dport {{ {input_ports} }} \
                    counter log prefix "c64gate-input-allow " accept
                counter log prefix "c64gate-input-drop " drop
            }}

            chain forward {{
                type filter hook forward priority filter; policy drop;
                ct state established,related accept
                ip daddr @rfc1918 counter log prefix "c64gate-rfc1918-drop " drop
                {allowed_destinations}
                ip daddr != @rfc1918 meta mark set 0x1 \
                    counter log prefix "c64gate-allow-forward " accept
                counter log prefix "c64gate-forward-drop " {lan_guard}
            }}

            chain output {{
                type filter hook output priority filter; policy accept;
            }}
        }}

        # Commodore destinations are documented for allowlist resolution: {commodore_hosts}
        """
        ).strip()
        + "\n"
    )


def render_caddyfile(settings: Settings) -> str:
    rest_backend = settings.rest_backend_url.removeprefix("http://").removeprefix("https://")
    dashboard_hash = "$2a$14$WoPzc0w1YbG5ChT1YVn/4e7lQnUnxE27XGr0C.csMEY0S8NxVkg4m"
    return (
        dedent(
            f"""
        {{
            admin off
            log {{
                output file {settings.log_dir}/caddy-access.jsonl
                format json
            }}
        }}

        :8443 {{
            tls /run/c64gate/tls/test-cert.pem /run/c64gate/tls/test-key.pem
            handle_path /api/* {{
                reverse_proxy {rest_backend} {{
                    header_up X-Forwarded-Proto https
                    header_up X-C64Gate true
                    header_up X-C64Gate-Device {settings.hostname}
                }}
            }}

            handle /dashboard* {{
                basic_auth * {{
                    {settings.dashboard_user} {dashboard_hash}
                }}
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
        ServerName "C64 Gate FTPS"
        ServerType standalone
        Port 2121
        UseIPv6 off
        DefaultServer on
        AuthOrder mod_auth_file.c
        AuthUserFile /run/c64gate/proftpd.passwd
        RequireValidShell off
        TimeoutIdle 600
        TLSEngine on
        TLSProtocol TLSv1.2 TLSv1.3
        TLSRequired on
        TLSRSACertificateFile /run/c64gate/tls/test-cert.pem
        TLSRSACertificateKeyFile /run/c64gate/tls/test-key.pem
        TransferLog /var/lib/c64gate/logs/proftpd-transfer.log
        ExtendedLog /var/lib/c64gate/logs/proftpd-access.log ALL default

        <IfModule mod_proxy.c>
            ProxyEngine on
            ProxyLog /var/lib/c64gate/logs/proftpd-proxy.log
            ProxyRole reverse
            ProxyTables /run/c64gate/proxy
            ProxyReverseServers ftp://{settings.ftp_backend_host}:{settings.ftp_backend_port}
        </IfModule>
        """
        ).strip()
        + "\n"
    )
