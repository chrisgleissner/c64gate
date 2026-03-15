# Security Remediation Plan

## Executive Remediation Strategy

This plan is the execution source of truth for remediating findings F1-F10 from `doc/audit/security-audit.md` and bringing the implementation back into conformance with `doc/architecture.md`.

Strategy:

- make mandatory gateway controls real runtime prerequisites and fail closed when they are not active
- reduce blast radius by hardening container execution, permissions, and process privilege boundaries
- remove management bypass paths and require TLS plus a single configured authentication model
- correct firewall policy semantics to explicit allowlists with IPv4 and IPv6 parity
- harden build integrity for Caddy, Python dependencies, and CI actions
- make the upgrade proxy resilient against slowloris, malformed input, and oversized requests
- constrain observability storage growth and redact sensitive material by default
- document any residual plaintext protocol risk as an explicit, bounded exception path

## Findings To Fix Mapping

| Finding | Status | Primary code/docs targets | Planned remediation |
| --- | --- | --- | --- |
| F1 | In progress | `src/controlplane/runtime.py`, `src/common/capture.py`, `tests/smoke/test_image_runtime.py` | Supervise nftables, dnsmasq, ProFTPD, dumpcap; fail closed on startup and readiness |
| F2 | In progress | `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `src/controlplane/runtime.py` | Add non-root service user for app processes, tighten mounts, permissions, read-only runtime, no-new-privileges, capability minimization by process |
| F3 | In progress | `docker-compose.yml`, `src/common/settings.py`, `src/common/config_renderers.py`, `src/controlplane/app.py`, `src/controlplane/auth.py` | Remove direct `8081` publish, bind control plane to loopback, require TLS-facing access through Caddy, unify auth on configured credentials, reject weak defaults |
| F4 | In progress | `Dockerfile`, `.github/workflows/ci.yml`, `build`, dependency manifests | Verify Caddy checksum, pin actions to SHAs, move build install path toward stronger dependency integrity and document reproducibility |
| F5 | In progress | `docker/entrypoint.sh`, `docker-compose.yml`, docs | Tighten filesystem permissions on CA state, logs, and captures; document secret handling and rotation |
| F6 | In progress | `src/common/config_renderers.py`, `src/common/settings.py`, runtime tests | Replace broad egress accept with explicit allowlist generation, add IPv6 controls and dual-stack tests |
| F7 | In progress | `src/upgrade_proxy/service.py`, proxy tests | Add read timeouts, header/body limits, malformed-input handling, and streaming-safe forwarding |
| F8 | In progress | `src/common/logging.py`, `src/common/settings.py`, capture/runtime code, tests | Add log rotation, redaction, disk limits, and bounded readiness detail |
| F9 | In progress | `src/common/settings.py`, docs, tests | Make strict TLS safer by default where feasible, add warnings and constrained exposure guidance for plaintext paths |
| F10 | In progress | `scripts/setup-host-https.sh`, docs | Document host-wide sysctl impact clearly and prefer narrower guidance where possible |

## Phased Execution Plan

### Phase 1 - Audit Mapping and Gap Verification

- [x] Parse `doc/audit/security-audit.md`
- [x] Verify findings F1-F10 against current implementation
- [x] Map findings to code and test locations
- [x] Create `doc/audit/security-remediation-plan.md`

### Phase 2 - Security Architecture Enforcement

- [ ] Apply nftables rules at runtime
- [ ] Start and supervise dnsmasq
- [ ] Start and supervise ProFTPD
- [ ] Start and supervise dumpcap
- [ ] Fail closed if any mandatory control is inactive
- [ ] Require readiness to prove firewall, DHCP, proxy, and observability activation

### Phase 3 - Container Hardening

- [ ] Introduce non-root execution for non-network-control services
- [ ] Drop privileges for Caddy, FastAPI, and proxy subprocesses
- [ ] Add read-only root filesystem support and writable tmpfs/mount guidance
- [ ] Add `no-new-privileges`
- [ ] Tighten filesystem permissions for CA, logs, and PCAPs
- [ ] Document container security model

### Phase 4 - Management Plane Security

- [ ] Remove public exposure of port 8081
- [ ] Require TLS-facing access through Caddy for management endpoints
- [ ] Unify authentication on configured credentials only
- [ ] Remove hardcoded Caddy auth material
- [ ] Enforce strong password configuration outside simulation
- [ ] Require authentication for management API access

### Phase 5 - Firewall Policy Correction

- [ ] Implement explicit destination allowlist generation
- [ ] Add IPv6 containment parity
- [ ] Block RFC1918 and other local IPv6 ranges unless explicitly allowed
- [ ] Add dual-stack enforcement tests

### Phase 6 - Supply Chain Hardening

- [ ] Verify Caddy download integrity in `Dockerfile`
- [ ] Pin GitHub Actions to immutable SHAs
- [ ] Strengthen Python dependency integrity controls
- [ ] Document reproducible build expectations

### Phase 7 - Proxy Robustness

- [ ] Add client read timeouts
- [ ] Enforce header size limits
- [ ] Enforce request body limits
- [ ] Add malformed-request rejection paths
- [ ] Validate request/response body handling with tests

### Phase 8 - Logging and Observability Security

- [ ] Add JSON log rotation and retention
- [ ] Redact sensitive headers and secrets by default
- [ ] Bound readiness detail to avoid reconnaissance leakage
- [ ] Enforce PCAP retention policy and permission model
- [ ] Add disk pressure and log flooding tests

### Phase 9 - Protocol Risk Mitigation

- [ ] Tighten strict TLS defaults and warnings
- [ ] Document Telnet and plaintext HTTP exception handling
- [ ] Add verification for warning paths and defaults

## Security Acceptance Criteria

- Every finding F1-F10 is fixed, mitigated with documented controls, or formally justified with evidence.
- Startup fails when any mandatory security control cannot be started or verified.
- Readiness reports `ready` only when firewall, DHCP, FTPS, proxy, and capture controls are active.
- Control-plane access is not published directly on `8081` in the default deployment.
- Management endpoints require configured authentication and are only exposed via TLS.
- Firewall tests prove RFC1918 and IPv6 containment plus fail-closed behavior.
- Proxy tests prove timeout, malformed-input, oversized-header, and body-handling resilience.
- Container and smoke tests prove the hardened runtime contract.
- Build pipeline verifies Caddy integrity and CI actions are SHA pinned.

## Test Plan

- `./build lint`
- `./build test`
- `./build smoke`
- `python3 tools/check_traceability.py`
- focused pytest runs for firewall, control-plane, upgrade proxy, logging, and smoke security cases during implementation

## Risk Register

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Starting real networking daemons in simulation can behave differently from lab routing | Medium | Keep simulation-specific safe interface selection while requiring full enforcement outside simulation | Open |
| R2 | Read-only rootfs can break daemon PID, socket, or cache paths | Medium | Explicitly provide writable runtime paths and tmpfs guidance | Open |
| R3 | Python dependency hash locking may require a generated lock file larger than the current manifests | Medium | Introduce dedicated locked install artifact rather than weakening verification | Open |
| R4 | FTPS supervision inside tests may be environment-sensitive | Medium | Use narrow unit/integration verification plus smoke coverage in container | Open |

## Work Log

| Timestamp | Action performed | Files modified | Commands executed | Results observed | Tests executed | Next step |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-03-15T14:30:57+00:00 | Verified audit findings against architecture, runtime, config, container, and test surfaces; created the remediation execution artifacts. | `PLANS.md`, `doc/audit/security-remediation-plan.md` | `date -Iseconds`, read-only code inspection | Confirmed F1, F3, F6, and F7 directly in implementation; confirmed F4 and CI mutability; identified current smoke path assumptions around `8081`. | None | Implement runtime enforcement and management-plane hardening first because they unblock multiple findings and tests. |
