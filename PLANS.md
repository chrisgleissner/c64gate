# C64 Gate Plan

## Phase Map

### Phase 1 - Specification Intake and Planning
- [x] Read `doc/architecture.md` fully
- [x] Extract every normative requirement
- [x] Create an explicit requirement inventory
- [x] Create the traceability matrix scaffold
- [x] Create `PLANS.md`
- [x] Create `WORKLOG.md`
- [x] Record all assumptions
- [x] Amend `doc/architecture.md` immediately if any ambiguity or inconsistency is discovered

Architecture sections: 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 17

Acceptance criteria:
- Every normative requirement is enumerated in `doc/traceability-matrix.yaml`
- Traceability structure exists and is CI-checkable
- `PLANS.md` and `WORKLOG.md` are populated
- No unresolved architecture ambiguity blocks implementation

Verification:
- `python3 tools/check_traceability.py`

Completion condition:
- Requirement inventory and traceability scaffold are committed in-repo

### Phase 2 - Repository Foundation
- [x] Create repository layout matching the architecture
- [x] Add `README.md`
- [x] Add `doc/developer.md`
- [x] Add GPL-v3 `LICENSE`
- [x] Add `.gitignore`
- [x] Add linting and formatting configuration
- [x] Add traceability matrix location and initial content
- [x] Add documented non-goals and deferred-work sections

Architecture sections: 2, 3.1, 10, 11, 13, 14, 16, 17

Acceptance criteria:
- Repository structure matches the architecture
- Foundation documentation exists and is actionable
- Lint and formatting configuration are runnable from `./build`
- Non-goals and deferred work are explicit

Verification:
- `./build fmt --check`
- `./build lint`

Completion condition:
- A fresh checkout contains enough structure to build, lint, and test

### Phase 3 - Build Wrapper and Local Developer UX
- [x] Implement root `build` Bash script
- [x] Provide idiomatic `./build --help`
- [x] Make `build` the single entry point for build, lint, test, smoke, HIL, and CI-like local workflows
- [x] Add thin wrapper support for local images and GHCR images if required by architecture
- [x] Add Docker Compose orchestration
- [x] Document Linux runtime usage in `README.md`
- [x] Document Linux-focused developer workflow in `doc/developer.md`

Architecture sections: 3.1, 10, 11, 12, 13

Acceptance criteria:
- `./build --help` is complete and idiomatic
- `./build` orchestrates actual workflows correctly
- Documentation reflects real usage

Verification:
- `./build --help`
- `./build ci`

Completion condition:
- All local developer workflows are routed through `./build`

### Phase 4 - Production Image and Runtime Process Model
- [x] Build the single production image on Debian stable slim
- [x] Pin upstream Caddy to 2.11.2 or later
- [x] Install and configure nftables, dnsmasq, ProFTPD modules, and Wireshark CLI capture tools
- [x] Add Python runtime dependencies for FastAPI, Uvicorn, h11, and httpx
- [x] Keep image size and resident footprint under control
- [x] Avoid privileged mode if possible
- [x] Support `linux/amd64` and `linux/arm64`
- [x] Implement health and readiness entry points
- [x] Make startup fail fast for mandatory component failures

Architecture sections: 3.4, 3.5, 3.6, 3.7, 3.8, 3.10, 8.6, 9, 10

Acceptance criteria:
- Production image builds reproducibly
- Mandatory components start deterministically
- Image is lean and hardened
- Architecture-mandated components are present

Verification:
- `./build image`
- `./build smoke`

Completion condition:
- The exact production image passes smoke validation

### Phase 5 - Device-Side Networking and DHCP
- [x] Implement router-mode networking model
- [x] Configure device-side DHCP with dnsmasq
- [x] Support configurable interfaces and subnets
- [x] Support local hostname `c64gate.local`
- [x] Minimize permanent host modifications
- [x] Document any unavoidable Linux host prerequisites

Architecture sections: 3.3, 5, 6, 8.2, 9

Acceptance criteria:
- Device-side DHCP works
- Interfaces and subnets are configurable
- Host impact is minimal and documented

Verification:
- `./build test -k dhcp`

Completion condition:
- DHCP configuration is generated, validated, and exercised by integration tests

### Phase 6 - Firewall and Policy Enforcement
- [x] Implement nftables ruleset generation
- [x] Enforce default deny
- [x] Allow `commodore.net`
- [x] Block RFC1918 ranges by default and log them
- [x] Block direct host access except required gateway services
- [x] Make LAN isolation configurable
- [x] Log every allow and deny decision
- [x] Use atomic ruleset loading
- [x] Verify behavior through tests

Architecture sections: 3.2, 6, 8.1, 8.8, 9

Acceptance criteria:
- Firewall behavior matches the architecture exactly
- Rule updates are deterministic
- Logs include required decision data

Verification:
- `./build test -k firewall`

Completion condition:
- Ruleset generation and normalization are covered by tests and traceability

### Phase 7 - Inbound HTTPS REST Façade
- [x] Configure Caddy as HTTPS reverse proxy for the backend REST API
- [x] Use pinned upstream Caddy version
- [x] Configure local-LAN-friendly certificate handling
- [x] Configure JSON access logging
- [x] Rewrite headers as required for device compatibility
- [x] Record latency and bytes transferred
- [x] Integrate Caddy logs into the project JSON pipeline

Architecture sections: 3.4, 8.3, 8.8, 9

Acceptance criteria:
- HTTPS façade works end to end
- Access logs are present and structured
- Header rewriting is correct

Verification:
- `./build test -k caddy`

Completion condition:
- HTTPS façade behavior is validated in automated tests

### Phase 8 - Inbound FTPS Façade
- [x] Configure ProFTPD with `mod_tls`
- [x] Configure ProFTPD `mod_proxy` reverse-proxying to the backend C64 FTP server
- [x] Ensure passive and control/data behavior are handled correctly
- [x] Record connection metadata, latency, and bytes transferred
- [x] Normalize ProFTPD logs into project JSON

Architecture sections: 3.5, 8.3, 8.8, 9

Acceptance criteria:
- FTPS façade works end to end
- Backend FTP remains plain behind the façade
- Logs are normalized into project JSON

Verification:
- `./build test -k ftps`

Completion condition:
- FTPS façade config and normalization are covered by tests

### Phase 9 - Outbound HTTP→HTTPS Upgrade Proxy
- [x] Implement custom Python transparent HTTP interception service
- [x] Parse client HTTP/1.1 requests with `h11`
- [x] Forward upgraded requests with `httpx`
- [x] Always try HTTPS first
- [x] Maintain destination capability cache
- [x] Fall back to HTTP only in non-strict mode
- [x] Reject fallback in strict TLS mode
- [x] Enforce strict TLS validation on upgraded HTTPS
- [x] Log warnings for fallback and certificate-name anomalies
- [x] Support identification of HTTP traffic regardless of port
- [x] Expose metrics and health state to the dashboard/health plane

Architecture sections: 3.6, 7.2, 8.4, 8.8, 9

Acceptance criteria:
- Success path works
- Fallback path works
- Strict mode rejection works
- Cache behavior works
- Logs contain all required fields

Verification:
- `./build test -k upgrade_proxy`

Completion condition:
- Upgrade proxy behavior is covered by integration tests and health endpoints

### Phase 10 - Passive Protocol Logging
- [x] Log inbound Telnet without altering it
- [x] Log inbound TCP streaming traffic without altering it
- [x] Log outbound UDP stream traffic in summary mode by default
- [x] Implement optional verbose stream logging
- [x] Keep defaults lightweight

Architecture sections: 7.1, 7.2, 8.8

Acceptance criteria:
- Protocol behavior remains unmodified
- Default logging stays lightweight
- Verbose mode is separately controllable

Verification:
- `./build test -k stream_logging`

Completion condition:
- Stream log controls are implemented and validated

### Phase 11 - DNS Observability and Packet Capture
- [x] Implement passive DNS observability only
- [x] Do not implement DNS policy enforcement
- [x] Capture rolling PCAPs with `dumpcap`
- [x] Rotate captures by both size and time
- [x] Use `tshark` and `capinfos` for decoding and assertions
- [x] Correlate DNS observations with later flows where practical

Architecture sections: 3.3, 3.7, 8.5, 8.6, 8.8, 16

Acceptance criteria:
- DNS observability works
- Rolling capture works
- Tests verify packet contents, not only file existence

Verification:
- `./build test -k capture`

Completion condition:
- Packet capture pipeline is covered with content-based assertions

### Phase 12 - Dashboard, Health, and Unified Logging
- [x] Implement authenticated FastAPI dashboard
- [x] Run it with Uvicorn
- [x] Expose health and readiness endpoints
- [x] Implement canonical project JSON schema
- [x] Normalize Caddy, ProFTPD, firewall, and Python service events into canonical JSON
- [x] Implement default and verbose logging modes
- [x] Implement separate verbose stream logging toggle
- [x] Expose recent flow summaries derived from JSON logs

Architecture sections: 3.8, 3.9, 7, 8.7, 8.8, 12

Acceptance criteria:
- Dashboard is authenticated and reachable
- Health/readiness are correct
- JSON logs are unified and valid
- Verbosity controls work

Verification:
- `./build test -k controlplane`

Completion condition:
- Control plane features are validated and wired into logging

### Phase 13 - Test Harness and Fixtures
- [x] Build Python integration harness
- [x] Create mock C64 service fixtures
- [x] Create external fixtures for HTTP-only
- [x] Create external fixtures for HTTPS-only
- [x] Create external fixtures for dual-protocol HTTP+HTTPS
- [x] Create external fixtures for invalid certificate
- [x] Create external fixtures for failure/error cases
- [x] Create Linux network-namespace or veth-based simulation where practical
- [x] Add smoke tests against the exact production image
- [x] Add packet-content assertions using tshark/capinfos
- [x] Add JSON-log assertions
- [x] Add traceability/spec-coverage assertions
- [x] Add optional local HIL tests against `c64u` using non-destructive operations only

Architecture sections: 10, 11, 12, 17

Acceptance criteria:
- Integration tests cover all normative behaviors
- Smoke tests hit the exact production image
- HIL tests are separated and optional

Verification:
- `./build test`
- `./build smoke`
- `./build hil`

Completion condition:
- Test harness validates the image, logs, PCAPs, and spec coverage

### Phase 14 - CI and Release Workflows
- [x] Implement GitHub Actions workflows
- [x] Use sensible job separation without fragmentation
- [x] Validate the exact production image in CI
- [x] Cover `linux/amd64` and `linux/arm64`
- [x] Upload logs, PCAPs, reports, and spec-coverage outputs as artifacts
- [x] Enforce traceability/spec coverage in CI
- [x] Document or implement GHCR image publishing workflow as required

Architecture sections: 10, 11, 12, 17

Acceptance criteria:
- CI is authoritative and green
- Artifacts are uploaded
- Spec coverage is enforced
- Architecture requirements are demonstrably covered

Verification:
- `./build ci`

Completion condition:
- Local CI-equivalent workflow passes and GitHub Actions definitions are present

### Phase 15 - Final Hardening and Documentation Pass
- [x] Review the repository for simplicity and maintainability
- [x] Remove unnecessary complexity
- [x] Confirm comments remain essential only
- [x] Confirm documentation matches implementation
- [x] Confirm non-goals and deferred work are documented
- [x] Confirm fresh-checkout build path works
- [x] Confirm CI passes cleanly

Architecture sections: 2, 10, 11, 12, 13, 16, 17

Acceptance criteria:
- Repository is coherent and production-grade
- Documentation is accurate
- No major phase remains incomplete without explicit architecture-backed deferral

Verification:
- `./build ci`

Completion condition:
- Final local validation passes and remaining deferrals are explicit

## Requirement Inventory

Normative requirements are enumerated in `doc/traceability-matrix.yaml`. The inventory is authoritative for implementation, tests, and CI coverage checks.

## Assumptions

- CI can validate the production image in a simulation fixture mode that still uses the exact production image but avoids requiring a physical C64 or unrestricted host network control.
- Docker Buildx is available in CI for multi-arch builds.
- Network capability tests that require `NET_ADMIN` are limited to integration contexts and do not require privileged mode.
- Real-device HIL tests remain optional and local-only.

## Non-Goals

- macOS and Windows host support in v1
- Bridge mode in v1
- DNS policy enforcement, sinkholing, or filtering in v1
- Heavy analytics platforms or cloud-hosted observability dependencies

## Deferred Work

- Real-device performance tuning on Raspberry Pi Zero 2 W beyond automated footprint-conscious defaults
- Remote observation of GitHub Actions status requires pushing the authored workflow to GitHub; local CI-equivalent validation is green in this workspace
- Remote publication workflow to GHCR beyond documented usage unless release credentials are configured