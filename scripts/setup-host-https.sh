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

cat <<'EOF'
host prepared for rootless Docker HTTPS on port 443

warning: net.ipv4.ip_unprivileged_port_start=443 is a host-wide change.
Only use this on a trusted host where allowing unprivileged local processes to bind port 443 is acceptable.
EOF
