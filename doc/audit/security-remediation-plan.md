# Security Remediation Mapping

## Scope

This document maps findings F1-F10 from `doc/audit/security-audit.md` to the current implementation, validation evidence, and planned remediation changes.

## Finding Verification

### F1 - Documented gateway controls are not enforced at runtime

- Status: confirmed
- Evidence:
  - `src/controlplane/runtime.py` renders configs and validates binaries but only starts Caddy, Uvicorn, and the upgrade proxy.
  - No `nft -f`, `dnsmasq`, `proftpd`, or `dumpcap` process startup exists.
- Remediation:
  - add a supervised runtime orchestrator that applies nftables and starts dnsmasq, ProFTPD, dumpcap, Caddy, FastAPI, and the upgrade proxy
  - fail startup if a mandatory service cannot be verified as active
  - make readiness depend on active control verification instead of static binary presence

### F2 - Root container with excessive capabilities and writable host mounts

- Status: confirmed
- Evidence:
  - `Dockerfile` has no non-root runtime user.
  - `docker-compose.yml` grants `NET_ADMIN` and `NET_RAW` and mounts writable CA, log, and PCAP directories.
- Remediation:
  - create a dedicated service user for non-network-control processes
  - drop privileges per subprocess where possible
  - add read-only rootfs and `no-new-privileges` support in Compose
  - tighten directory ownership and permissions in entrypoint/runtime setup

### F3 - Management-plane exposure and inconsistent authentication

- Status: confirmed
- Evidence:
  - `docker-compose.yml` publishes `8081:8081`.
  - `Settings.controlplane_host` defaults to `0.0.0.0`.
  - `render_caddyfile` contains a hardcoded bcrypt hash unrelated to `dashboard_password`.
  - `/health` and `/ready` are unauthenticated in `src/controlplane/app.py`.
- Remediation:
  - bind the control plane to loopback
  - remove public `8081` publishing
  - terminate all management access at Caddy over TLS only
  - unify on a single configured auth secret and reject weak defaults outside simulation

### F4 - Supply-chain integrity is weak

- Status: confirmed
- Evidence:
  - `Dockerfile` downloads Caddy without checksum verification.
  - `.github/workflows/ci.yml` uses mutable action tags.
  - Python dependencies are version pinned but not locked with integrity metadata.
- Remediation:
  - verify Caddy tarball against the official checksum manifest in the image build
  - pin actions to immutable SHAs
  - strengthen Python dependency installation integrity and document reproducibility constraints

### F5 - Local CA private keys persist on host mounts

- Status: confirmed
- Evidence:
  - runtime CA state is mounted from `data/caddy` and includes PKI material
  - helper scripts encourage trusting the local CA on the host
- Remediation:
  - restrict permissions on CA directories
  - document CA handling, rotation, and sharing constraints
  - reduce exposure of Caddy state in the default runtime contract where possible

### F6 - Firewall policy gaps and IPv6 bypass

- Status: confirmed
- Evidence:
  - `render_nftables_ruleset` accepts any non-RFC1918 IPv4 destination.
  - No IPv6 allowlist or deny model is rendered.
- Remediation:
  - generate explicit IPv4 and IPv6 allowlists
  - block RFC1918, loopback, link-local, and ULA destinations unless explicitly allowed
  - add dual-stack tests and fail-closed enforcement checks

### F7 - Upgrade proxy is susceptible to slow-read DoS and malformed inputs

- Status: confirmed
- Evidence:
  - `reader.readuntil(b"\r\n\r\n")` has no timeout.
  - request bodies are not bounded beyond what arrives with the initial read.
  - malformed or unsupported transfer patterns are not explicitly rejected.
- Remediation:
  - implement bounded request parsing with read deadlines and size limits
  - reject malformed headers and unsupported transfer encodings clearly
  - add adversarial protocol tests, including slow headers and oversized input

### F8 - Logging and capture design permits tampering and disk exhaustion

- Status: confirmed
- Evidence:
  - `JsonLogger` appends indefinitely without rotation.
  - verbose header capture can record sensitive material.
  - readiness exposes capture command detail.
- Remediation:
  - add log rotation and retention controls
  - redact sensitive headers
  - reduce readiness detail to bounded security status summaries
  - enforce directory permissions and retention behavior

### F9 - Plaintext protocol paths remain available

- Status: confirmed
- Evidence:
  - `strict_tls_mode` defaults to `False`.
  - architecture permits Telnet pass-through and fallback HTTP.
- Remediation:
  - tighten defaults and warnings
  - make plaintext behavior explicit and testable
  - document exposure constraints clearly

### F10 - Host preparation script weakens a host-wide security control

- Status: confirmed
- Evidence:
  - `scripts/setup-host-https.sh` lowers `net.ipv4.ip_unprivileged_port_start` system-wide.
- Remediation:
  - document the system-wide impact more explicitly and prefer narrow alternatives in docs

## Execution Notes

- Phase ordering starts with runtime enforcement and management-plane closure because those changes remove the highest-risk false sense of security.
- Simulation mode remains supported for local exploration, but it must no longer imply that real enforcement controls are active when they are not.
- Any residual exception path will require explicit documentation and evidence in tests before the finding can be downgraded.
