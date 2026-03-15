#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/lib/c64gate/logs /var/lib/c64gate/pcap /var/lib/c64gate/caddy /run/c64gate/config /tmp
exec python3 -m controlplane.runtime
