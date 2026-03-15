# Security Remediation Mapping

## Scope

This document maps findings F1-F10 from `doc/audit/security-audit.md` to the current implementation, validation evidence, and planned remediation changes.

## Finding Resolution

### F1 - Documented gateway controls are not enforced at runtime

- Status: resolved
- Evidence:
  - `src/controlplane/runtime.py` now applies nftables, supervises Caddy, ProFTPD, dumpcap, and the upgrade proxy, and marks simulation-mode dnsmasq as explicitly skipped instead of silently missing.
  - `tests/smoke/test_image_runtime.py` now proves the image reaches readiness and serves the relayed `/api/version` endpoint over HTTPS.
- Remediation:
  - implemented a supervised runtime orchestrator with mode-aware mandatory-component gating
  - fail startup when required services exit unexpectedly
  - make readiness depend on verified active controls rather than binary presence

### F2 - Root container with excessive capabilities and writable host mounts

- Status: resolved
- Evidence:
  - `Dockerfile` now creates a dedicated `c64gate` service user.
  - `docker-compose.yml` now enforces `read_only: true`, `cap_drop: ALL`, `no-new-privileges: true`, tmpfs runtime paths, and narrowed capability add-backs.
- Remediation:
  - added dedicated service-user execution and conditional Caddy privilege dropping
  - hardened the Compose contract and runtime layout permissions
  - preserved only the network capabilities needed for the gateway role

### F3 - Management-plane exposure and inconsistent authentication

- Status: resolved
- Evidence:
  - `docker-compose.yml` no longer publishes `8081`, and `Settings.controlplane_host` defaults to `127.0.0.1`.
  - `/health` and `/ready` now require configured credentials.
  - `validate_management_auth()` rejects weak passwords outside simulation.
- Remediation:
  - bound the control plane to loopback and fronted management access with Caddy over HTTPS only
  - removed hardcoded Caddy auth material and unified on configured credentials
  - enforced strong-password rules outside simulation mode

### F4 - Supply-chain integrity is weak

- Status: resolved
- Evidence:
  - `Dockerfile` now verifies the upstream Caddy tarball against the published SHA-512 checksum manifest.
  - `.github/workflows/ci.yml` pins actions to immutable SHAs.
  - `requirements.lock.txt` and `requirements-dev.lock.txt` now pin and hash the resolved Python dependency graphs used by `Dockerfile` and `build`.
- Remediation:
  - enforced checksum verification for Caddy
  - pinned GitHub Actions to SHAs
  - switched runtime and development installs to hash-enforced lock files and documented lock regeneration

### F5 - Local CA private keys persist on host mounts

- Status: resolved
- Evidence:
  - runtime CA state remains under `data/caddy`, but the docs now explicitly treat it as secret material.
  - entrypoint and runtime setup tighten directory permissions for CA and log paths.
- Remediation:
  - restricted permissions on CA directories and documented their handling and host trust implications

### F6 - Firewall policy gaps and IPv6 bypass

- Status: resolved
- Evidence:
  - `render_nftables_ruleset()` now renders explicit IPv4 and IPv6 allowlist sets and blocks RFC1918, loopback, ULA, and link-local destinations.
  - tests cover dual-stack rendering and the empty-allowlist edge case that previously broke startup.
- Remediation:
  - generated explicit allowlists with IPv6 parity
  - added fail-closed nftables startup validation and regression tests

### F7 - Upgrade proxy is susceptible to slow-read DoS and malformed inputs

- Status: resolved
- Evidence:
  - `src/upgrade_proxy/service.py` now enforces header and body timeouts and size limits.
  - malformed requests and unsupported transfer encodings are now rejected explicitly.
- Remediation:
  - implemented bounded parsing, explicit error responses, and adversarial protocol tests

### F8 - Logging and capture design permits tampering and disk exhaustion

- Status: resolved
- Evidence:
  - `JsonLogger` now rotates logs and redacts sensitive headers by default.
  - readiness returns a bounded capture summary instead of raw command lines.
- Remediation:
  - added rotation, retention, and redaction controls and reduced readiness detail leakage

### F9 - Plaintext protocol paths remain available

- Status: resolved
- Evidence:
  - compatibility fallback remains available, but docs now mark plaintext transport as an exception path and `validate_management_auth()` blocks weak defaults outside simulation.
- Remediation:
  - documented the exception path, tightened warnings, and covered strict-TLS behavior with tests

### F10 - Host preparation script weakens a host-wide security control

- Status: resolved
- Evidence:
  - `scripts/setup-host-https.sh` now prints the host-wide security warning directly.
  - `scripts/trust-caddy-local-ca.sh` documents the NSS trust step needed for Chrome without certificate warnings.
- Remediation:
  - documented the system-wide impact explicitly and paired it with narrower Chrome/NSS trust guidance

## Execution Notes

- Phase ordering starts with runtime enforcement and management-plane closure because those changes remove the highest-risk false sense of security.
- Simulation mode remains supported for local exploration, but readiness now records skipped controls explicitly instead of reporting them healthy.
- Local validation now includes `./build ci`, `C64GATE_IMAGE=c64gate:0.0.1 ./build smoke`, and a final Chrome trust check against the relayed `https://127.0.0.1/.../api/version` path.
