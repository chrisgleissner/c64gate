#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/lib/c64gate/logs /var/lib/c64gate/pcap /var/lib/c64gate/caddy /run/c64gate/config /tmp
chown -R c64gate:c64gate /var/lib/c64gate/logs /var/lib/c64gate/caddy || true
chmod 0750 /var/lib/c64gate/logs /var/lib/c64gate/pcap || true
chmod 0700 /var/lib/c64gate/caddy || true
exec python3 -m controlplane.runtime
