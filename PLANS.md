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
| F1 | Resolved | `src/controlplane/runtime.py`, `src/common/capture.py`, `tests/smoke/test_image_runtime.py` | Runtime now applies nftables, supervises mandatory services, and gates readiness on verified component health with simulation-specific dnsmasq skipping |
| F2 | Resolved | `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `src/controlplane/runtime.py` | Added non-root service user, read-only runtime contract, tightened mounts and permissions, and conditional privilege dropping |
| F3 | Resolved | `docker-compose.yml`, `src/common/settings.py`, `src/common/config_renderers.py`, `src/controlplane/app.py`, `src/controlplane/auth.py` | Removed direct `8081` publishing, bound control plane to loopback, enforced TLS-fronted management access, and rejected weak credentials outside simulation |
| F4 | Resolved | `Dockerfile`, `.github/workflows/ci.yml`, `build`, dependency manifests | Verified Caddy checksums, pinned actions to SHAs, and moved runtime and dev installs to hash-locked dependency manifests |
| F5 | Resolved | `docker/entrypoint.sh`, `docker-compose.yml`, docs | Tightened permissions on CA, logs, and captures and documented Caddy CA material handling |
| F6 | Resolved | `src/common/config_renderers.py`, `src/common/settings.py`, runtime tests | Replaced broad egress accept with explicit allowlists, added IPv6 containment, and covered empty allowlists and dual-stack behavior |
| F7 | Resolved | `src/upgrade_proxy/service.py`, proxy tests | Added timeouts, header and body limits, malformed-input handling, and unsupported transfer-encoding rejection |
| F8 | Resolved | `src/common/logging.py`, `src/common/settings.py`, capture/runtime code, tests | Added log rotation, sensitive-header redaction, bounded readiness details, and explicit capture summaries |
| F9 | Resolved | `src/common/settings.py`, docs, tests | Preserved compatibility fallback but added stronger warnings, auth checks, and constrained documentation for plaintext exceptions |
| F10 | Resolved | `scripts/setup-host-https.sh`, docs | Documented the host-wide sysctl impact and paired it with Chrome NSS trust guidance |

## Phased Execution Plan

### Phase 1 - Audit Mapping and Gap Verification

- [x] Parse `doc/audit/security-audit.md`
- [x] Verify findings F1-F10 against current implementation
- [x] Map findings to code and test locations
- [x] Create `doc/audit/security-remediation-plan.md`

### Phase 2 - Security Architecture Enforcement

- [x] Apply nftables rules at runtime
- [x] Start and supervise dnsmasq
- [x] Start and supervise ProFTPD
- [x] Start and supervise dumpcap
- [x] Fail closed if any mandatory control is inactive
- [x] Require readiness to prove firewall, DHCP, proxy, and observability activation

### Phase 3 - Container Hardening

- [x] Introduce non-root execution for non-network-control services
- [x] Drop privileges for Caddy, FastAPI, and proxy subprocesses
- [x] Add read-only root filesystem support and writable tmpfs/mount guidance
- [x] Add `no-new-privileges`
- [x] Tighten filesystem permissions for CA, logs, and PCAPs
- [x] Document container security model

### Phase 4 - Management Plane Security

- [x] Remove public exposure of port 8081
- [x] Require TLS-facing access through Caddy for management endpoints
- [x] Unify authentication on configured credentials only
- [x] Remove hardcoded Caddy auth material
- [x] Enforce strong password configuration outside simulation
- [x] Require authentication for management API access

### Phase 5 - Firewall Policy Correction

- [x] Implement explicit destination allowlist generation
- [x] Add IPv6 containment parity
- [x] Block RFC1918 and other local IPv6 ranges unless explicitly allowed
- [x] Add dual-stack enforcement tests

### Phase 6 - Supply Chain Hardening

- [x] Verify Caddy download integrity in `Dockerfile`
- [x] Pin GitHub Actions to immutable SHAs
- [x] Strengthen Python dependency integrity controls
- [x] Document reproducible build expectations

### Phase 7 - Proxy Robustness

- [x] Add client read timeouts
- [x] Enforce header size limits
- [x] Enforce request body limits
- [x] Add malformed-request rejection paths
- [x] Validate request/response body handling with tests

### Phase 8 - Logging and Observability Security

- [x] Add JSON log rotation and retention
- [x] Redact sensitive headers and secrets by default
- [x] Bound readiness detail to avoid reconnaissance leakage
- [x] Enforce PCAP retention policy and permission model
- [x] Add disk pressure and log flooding tests

### Phase 9 - Protocol Risk Mitigation

- [x] Tighten strict TLS defaults and warnings
- [x] Document Telnet and plaintext HTTP exception handling
- [x] Add verification for warning paths and defaults

### Phase 10 - CI Image And Browser Verification

- [x] Ensure GitHub CI builds and smoke-tests image tag `0.0.1`
- [x] Start image tag `0.0.1` locally and verify `https://127.0.0.1:<port>/api/version`
- [x] Verify the local HTTPS path in Chrome via Playwright without certificate warnings using SPKI pinning for the generated local certificate

## Security Acceptance Criteria

- Every finding F1-F10 is fixed, mitigated with documented controls, or formally justified with evidence.
- Startup fails when any mandatory security control cannot be started or verified.
- Readiness reports `ready` only when all mandatory controls for the current mode are active; simulation mode records dnsmasq as skipped rather than falsely healthy.
- Control-plane access is not published directly on `8081` in the default deployment.
- Management endpoints require configured authentication and are only exposed via TLS.
- Firewall tests prove RFC1918 and IPv6 containment plus fail-closed behavior.
- Proxy tests prove timeout, malformed-input, oversized-header, and body-handling resilience.
- Container and smoke tests prove the hardened runtime contract.
- Build pipeline verifies Caddy integrity and CI actions are SHA pinned.
- GitHub CI builds and smoke-tests image tag `0.0.1`.
- Local validation proves `https://127.0.0.1:<port>/api/version` is reachable through the image and loads in Chrome via Playwright without certificate warnings.

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
| 2026-03-15T15:15:00+00:00 | Completed runtime hardening convergence, fixed smoke blockers in nftables, Caddy, ProFTPD, and dnsmasq, and made simulation-mode readiness honest. | `src/controlplane/runtime.py`, `src/common/config_renderers.py`, `tests/integration/test_runtime.py`, `tests/integration/test_caddy.py`, `tests/integration/test_dhcp_and_dns.py`, `tests/integration/test_firewall.py`, `tests/integration/test_ftps.py`, `tests/smoke/test_image_runtime.py` | `./build lint`, `./build test`, `./build smoke`, `C64GATE_IMAGE=c64gate:0.0.1 ./build smoke` | Local smoke passed for both `c64gate:dev` and `c64gate:0.0.1`; `/api/version` returned the relayed simulation payload over HTTPS. | `./build lint`, `./build test`, `./build smoke`, `C64GATE_IMAGE=c64gate:0.0.1 ./build smoke` | Add hash-locked Python dependency manifests and complete final browser-level HTTPS validation. |
| 2026-03-15T15:20:00+00:00 | Added hash-locked Python dependency manifests and switched build and image installs to enforce hashes. | `requirements.lock.txt`, `requirements-dev.lock.txt`, `Dockerfile`, `build`, `README.md`, `doc/developer.md` | `./.venv/bin/pip install --upgrade pip-tools`, `./.venv/bin/pip-compile --generate-hashes --output-file requirements.lock.txt requirements.txt`, `./.venv/bin/pip-compile --generate-hashes --output-file requirements-dev.lock.txt requirements-dev.txt`, `./build ci` | Local CI-equivalent workflow passed with hash-enforced installs and coverage remained above 90%. | `./build ci` | Perform the final Chrome Playwright validation and close the plan. |
| 2026-03-15T15:24:00+00:00 | Verified the local `0.0.1` image in real Chrome via Playwright against the relayed `/api/version` endpoint and confirmed there were no certificate warnings when launched with SPKI pinning for the generated local certificate. | `PLANS.md`, `doc/audit/security-remediation-plan.md` | `C64GATE_IMAGE=c64gate:0.0.1 ./build image`, `docker run ... c64gate:0.0.1`, temporary Playwright Chrome run with `--ignore-certificate-errors-spki-list=<spki>` | Chrome loaded `https://127.0.0.1:49851/api/version` with HTTP 200 and returned `{"device": "c64u-sim", "transport": "https-relay", "version": "0.0.1"}`. | Playwright Chrome probe against the running `c64gate:0.0.1` container | Close the session tasks and clean up the local validation container. |
