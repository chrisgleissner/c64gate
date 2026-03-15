# AGENTS.md

This file is the canonical startup brief for LLM agents working in this repository.

## Mission

Implement and maintain C64 Gate as a Linux-only, spec-driven gateway for Commodore 64 Ultimate devices.

Before making design choices, read [doc/architecture.md](doc/architecture.md). That document is the normative source for architecture, locked technology choices, and scope.

## First Steps

On a new task, do this before editing:

1. Read [doc/architecture.md](doc/architecture.md) when the task touches runtime behavior, packaging, networking, security, or observability.
2. Read [README.md](README.md) for the user-facing workflow and [doc/developer.md](doc/developer.md) for local development conventions.
3. Inspect the current implementation and tests before proposing changes.
4. Keep changes small, traceable, and aligned with the locked stack.

## Locked Constraints

Do not replace core technologies unless the architecture is amended first.

- Base image: Debian stable slim
- Firewall and routing: nftables
- DHCP and local naming: dnsmasq
- HTTPS facade: upstream Caddy, pinned to 2.11.2 or later
- FTPS facade: ProFTPD with mod_tls and mod_proxy
- Outbound HTTP upgrade path: custom Python service using h11 and httpx
- Packet capture and inspection: dumpcap, tshark, capinfos
- Control plane: FastAPI and Uvicorn
- Build entry point: root [build](build) script
- Runtime packaging: one production Docker image plus Docker Compose

## Working Rules

- Treat [doc/architecture.md](doc/architecture.md) as the source of truth.
- Route standard validation through [build](build) whenever practical.
- Prefer fixing root causes over adding narrow patches.
- Preserve Linux-only scope for v1.
- Avoid introducing new infrastructure or services that the architecture does not call for.
- Keep runtime behavior observable through existing JSON logs, health endpoints, and traceability artifacts.
- Do not silently change public behavior, ports, environment variables, or image composition without updating documentation and tests.

## Files To Keep In Sync

When relevant, update these alongside code changes:

- [README.md](README.md) for user-facing behavior and quick start
- [doc/developer.md](doc/developer.md) for engineering workflow changes
- [doc/traceability-matrix.yaml](doc/traceability-matrix.yaml) for requirement coverage
- [PLANS.md](PLANS.md) when execution phases or acceptance criteria change
- [WORKLOG.md](WORKLOG.md) for notable implementation work

## Validation Expectations

Use the narrowest useful validation first, then broader checks as needed.

Common commands:

```bash
./build lint
./build test
./build image
./build smoke
./build ci
python3 tools/check_traceability.py
```

Notes:

- `./build test` is the main Python test path.
- `./build smoke` validates the production image.
- `./build ci` is the local CI-equivalent workflow.
- Some capture assertions depend on host tools such as `tshark` and `capinfos`.
- Compose defaults run in simulation mode unless configured otherwise.

## Runtime Notes

- The default documented Compose path is for local exploration, not proof of real device routing.
- Real DHCP, firewall enforcement, and packet capture should be exercised on an isolated Linux host or lab network.
- The real C64 Ultimate may be reachable as `c64u`; do not hardcode that assumption into product defaults unless the architecture or docs explicitly require it.

## Agent Output Style

- Be concise, factual, and implementation-focused.
- Explain decisions in terms of architecture, operational safety, and verification.
- Prefer repository-relative file references in documentation.
- Avoid hype, vague claims, and speculative promises.
