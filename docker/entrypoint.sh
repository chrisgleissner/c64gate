#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/lib/c64gate/logs /var/lib/c64gate/pcap /run/c64gate/config
exec python3 -m controlplane.runtime
