#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_PATH="${ROOT_DIR}/data/caddy/pki/authorities/local/root.crt"
NSS_DB="sql:${HOME}/.pki/nssdb"
CERT_NAME="C64 Gate Local CA"

if [[ ! -f "${CA_PATH}" ]]; then
  echo "missing CA certificate at ${CA_PATH}; start c64gate once before trusting it" >&2
  exit 1
fi

if ! command -v certutil >/dev/null 2>&1; then
  echo "certutil not found; install libnss3-tools first" >&2
  exit 1
fi

mkdir -p "${HOME}/.pki/nssdb"

if [[ ! -f "${HOME}/.pki/nssdb/cert9.db" ]]; then
  certutil -N --empty-password -d "${NSS_DB}"
fi

certutil -D -d "${NSS_DB}" -n "${CERT_NAME}" >/dev/null 2>&1 || true
certutil -A -d "${NSS_DB}" -n "${CERT_NAME}" -t "C,," -i "${CA_PATH}"

echo "trusted ${CA_PATH} in ${NSS_DB}"
