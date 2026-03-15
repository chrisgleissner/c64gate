![Logo](./doc/img/logo.png)

# C64 Gate

C64 Gate is a Linux gateway for Commodore 64 Ultimate devices, packaged as a single Docker image. It sits between the device and the rest of the network, tightens inbound and outbound traffic handling, and gives you packet capture, structured logs, and a small control plane without requiring a pile of separate services.

The implementation follows [doc/architecture.md](doc/architecture.md). If you want the full system contract, read that file. If you want to get the container running and see what it does, start here.

> [!NOTE]
> This project is under active development. Some documented features may not yet be fully functional.

## What You Get

- One container image for the complete gateway runtime
- Linux-native firewalling with nftables
- DHCP and local naming for the device-side network
- HTTPS and FTPS front ends for inbound access
- Automatic outbound HTTP to HTTPS upgrade when possible
- Packet capture with Wireshark tooling behind the scenes
- Canonical JSON logs for traffic and daemon events
- A small FastAPI control plane for health, readiness, and dashboard views

## Good First Outcome

If you only want a quick proof that the project works, the shortest useful path is:

1. Install Docker on a Linux machine.
2. Run `docker compose up --build` in this repository.
3. Open `http://127.0.0.1:8081/health` and confirm the service answers.
4. Open `http://127.0.0.1:8081/ready` and inspect the runtime status.

That path uses the same production image the tests validate. By default, the Compose setup runs in simulation mode so you can explore the system without attaching a real device or changing host networking more than necessary.

If Docker is new to you, use the official installation guides rather than learning that from this README:

- [Docker Engine install guide](https://docs.docker.com/engine/install/)
- [Docker Compose guide](https://docs.docker.com/compose/)

## Quick Start

Minimum requirements:

- Linux host
- Docker with the Compose plugin

Start the stack:

```bash
docker compose up --build
```

To proxy a real C64 REST API instead of the default local simulation target, set `C64GATE_REST_BACKEND_URL` to the device's plain HTTP endpoint before starting Compose. Example:

```bash
C64GATE_REST_BACKEND_URL=http://192.168.1.167 docker compose up --build
```

Useful endpoints after startup:

- `http://127.0.0.1:8081/health`
- `http://127.0.0.1:8081/ready`
- `https://127.0.0.1:8443/api/v1/info` for the HTTPS REST facade

If you want host port `443` instead of `8443`, set `C64GATE_HTTPS_HOST_PORT=443` before starting Compose. On rootless Docker hosts, publishing `443` may require lowering `net.ipv4.ip_unprivileged_port_start` or using a rootful Docker daemon.

Stop the stack:

```bash
docker compose down
```

The default Compose file mounts logs and packet captures into `data/logs` and `data/pcap` so you can inspect outputs from the host.

## When You Want More Than A Demo

Use the root build script for the standard workflows:

```bash
./build help
./build test
./build image
./build smoke
./build ci
```

You only need Python if you want to run the local lint and test workflow outside the containerized smoke path.

The most useful follow-on documents are:

- [doc/developer.md](doc/developer.md) for local developer workflows
- [doc/architecture.md](doc/architecture.md) for the system design and locked technology choices
- [doc/traceability-matrix.yaml](doc/traceability-matrix.yaml) for requirement-to-code-to-test coverage
- [PLANS.md](PLANS.md) for delivery phases and acceptance criteria
- [WORKLOG.md](WORKLOG.md) for the implementation record

## Operating Notes

- v1 is Linux only.
- The project is designed as a router-mode gateway, not a generic cross-platform desktop app.
- Real firewall enforcement, DHCP service, and device traffic capture are best exercised on a disposable Linux host or an isolated lab network.
- The runtime depends on Linux networking capabilities such as `NET_ADMIN` and `NET_RAW`.

## Non-Goals In V1

- macOS or Windows runtime support
- bridge mode
- DNS policy enforcement
- cloud-hosted control plane services
- large analytics platforms
