#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run with sudo: sudo ./scripts/setup-host-https.sh" >&2
  exit 1
fi

cat >/etc/sysctl.d/50-c64gate-rootless-ports.conf <<'EOF'
net.ipv4.ip_unprivileged_port_start=443
EOF

sysctl --system >/dev/null

apt-get update
apt-get install -y libnss3-tools

echo "host prepared for rootless Docker HTTPS on port 443"
