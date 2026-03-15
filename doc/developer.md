# Developer Guide

## Principles

- Treat [doc/architecture.md](architecture.md) as normative.
- Route build, lint, test, smoke, HIL, and CI-like workflows through [build](../build).
- Keep changes traceable by updating [doc/traceability-matrix.yaml](traceability-matrix.yaml), [PLANS.md](../PLANS.md), and [WORKLOG.md](../WORKLOG.md).

## Local Setup

```bash
./build venv
source .venv/bin/activate
./build lint
./build test
```

## Build Entry Point

`./build --help` prints all supported workflows. The important commands are:

- `./build fmt`: run formatting
- `./build fmt --check`: check formatting only
- `./build lint`: run Ruff
- `./build test`: run the Python test suite
- `./build smoke`: build the production image and run smoke validation against that image
- `./build hil`: run optional hardware-in-the-loop tests against `c64u`
- `./build image`: build the production Docker image locally
- `./build ci`: run the local CI-equivalent workflow

## Host HTTPS On 443

If you want rootless Docker to publish `443` for a normal `https://127.0.0.1/...` entry point, the host needs one-time preparation:

```bash
sudo ./scripts/setup-host-https.sh
```

That script lowers `net.ipv4.ip_unprivileged_port_start` to `443` and installs `libnss3-tools` so Chrome trust can be updated without making the c64gate container run as root.

After the stack has started once and generated the Caddy local CA, trust it for Chrome and other NSS consumers with:

```bash
./scripts/trust-caddy-local-ca.sh
```

## Linux Runtime Notes

- The runtime is Linux-only by design.
- Full routing and capture flows may require `NET_ADMIN` and `NET_RAW` at container runtime.
- The default automated validation path uses a simulation fixture mode that still runs the exact production image but avoids mutating host networking state.
- Real device-side DHCP and firewall enforcement should be exercised on a disposable Linux host or namespace-backed integration setup.

## Traceability Workflow

Every normative requirement needs:

- one requirement row in [doc/traceability-matrix.yaml](traceability-matrix.yaml)
- at least one implementation reference
- at least one automated test reference
- at least one CI coverage reference

Validate it with:

```bash
python3 tools/check_traceability.py
```

## Artifacts

The local and CI workflows store outputs under `artifacts/`:

- normalized logs
- PCAPs and decoded summaries
- test reports
- traceability coverage reports
