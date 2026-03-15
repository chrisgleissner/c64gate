# C64 Gate Architecture

## Overview

C64 Gate is a containerized firewall and secure gateway for Commodore 64
Ultimate devices.\
It provides:

-   Network firewall containment
-   Secure HTTPS façade for device services
-   Transparent HTTP → HTTPS upgrade attempts for outbound traffic
-   Full packet monitoring and logging
-   Visual traffic analysis
-   Turnkey Docker deployment

The system runs on Linux hosts (including Raspberry Pi) and requires
only Docker to deploy.

------------------------------------------------------------------------

## High‑Level Architecture

``` mermaid
flowchart LR
    C64["Commodore 64 Ultimate"]
    Host["Linux Host (Docker)"]
    Gate["C64 Gate Container"]
    LAN["LAN / Internet"]

    C64 --> Host
    Host --> Gate
    Gate --> LAN
```

C64 Gate sits between the C64 device and the surrounding network and
ensures all communication flows through the gateway.

------------------------------------------------------------------------

## Network Topology

``` mermaid
flowchart LR
    C64["C64 Ultimate"]
    ETH1["eth1 (Device Network)"]
    GATE["C64 Gate"]
    ETH0["eth0 / wlan0 (LAN)"]
    INTERNET["LAN / Internet"]

    C64 --> ETH1 --> GATE --> ETH0 --> INTERNET
```

Example addressing:

  Component    Example IP
  ------------ ----------------------
  C64          192.168.50.2
  Gateway      192.168.50.1
  LAN Router   Standard LAN gateway

------------------------------------------------------------------------

## Component Architecture

``` mermaid
flowchart TB
    subgraph C64 Gate Container
        FW["Firewall Engine"]
        PROXY["HTTPS Reverse Proxy"]
        UPGRADE["HTTP → HTTPS Upgrade Proxy"]
        CAPTURE["Packet Capture"]
        ANALYSIS["Traffic Analysis"]
        LOGS["Logging System"]
    end

    C64["C64 Device"]
    NET["LAN / Internet"]

    C64 --> FW
    FW --> PROXY
    FW --> UPGRADE
    FW --> CAPTURE

    PROXY --> NET
    UPGRADE --> NET

    CAPTURE --> ANALYSIS
    CAPTURE --> LOGS
```

Each subsystem contributes to security, observability, or encrypted
communication.

------------------------------------------------------------------------

## Inbound Secure Access Flow

``` mermaid
sequenceDiagram
    participant Client
    participant Gate as C64 Gate (TLS Proxy)
    participant C64

    Client->>Gate: HTTPS request
    Gate->>C64: HTTP request
    C64-->>Gate: HTTP response
    Gate-->>Client: HTTPS response
```

The proxy terminates TLS and forwards requests to the device's HTTP
interface.

------------------------------------------------------------------------

## Outbound HTTP → HTTPS Upgrade Flow

``` mermaid
sequenceDiagram
    participant C64
    participant Gate
    participant Server

    C64->>Gate: HTTP request
    Gate->>Server: Attempt HTTPS request
    alt HTTPS available
        Server-->>Gate: HTTPS response
        Gate-->>C64: HTTP response
    else HTTPS unavailable
        Gate->>Server: HTTP request
        Server-->>Gate: HTTP response
        Gate-->>C64: HTTP response
    end
```

The gateway attempts to transparently upgrade device HTTP calls to HTTPS
when supported by the remote server.

------------------------------------------------------------------------

## Traffic Monitoring Pipeline

``` mermaid
flowchart LR
    C64["C64 Network Traffic"]
    CAP["Packet Capture (tcpdump/tshark)"]
    FLOW["Flow Analysis"]
    DASH["Dashboard (ntopng)"]
    PCAP["PCAP Files"]
    LOG["Gateway Logs"]

    C64 --> CAP
    CAP --> FLOW
    CAP --> PCAP
    CAP --> LOG
    FLOW --> DASH
```

This pipeline provides both real‑time and offline inspection of device
behavior.

------------------------------------------------------------------------

## Container Deployment Model

``` mermaid
flowchart TB
    USER["User"]
    DOCKER["Docker Host"]
    CONTAINER["C64 Gate Container"]
    NETWORK["Host Networking"]
    C64["C64 Device"]
    INTERNET["LAN / Internet"]

    USER --> DOCKER
    DOCKER --> CONTAINER
    CONTAINER --> NETWORK
    NETWORK --> C64
    NETWORK --> INTERNET
```

The container runs with:

-   host networking
-   NET_ADMIN capability
-   NET_RAW capability

This allows firewall control and packet capture on real interfaces.

------------------------------------------------------------------------

## Repository Structure

    c64gate/
    ├─ docker/
    ├─ compose/
    ├─ config/
    │  ├─ proxy/
    │  └─ firewall/
    ├─ scripts/
    ├─ data/
    │  ├─ logs/
    │  └─ pcap/
    └─ docs/
       └─ architecture.md

------------------------------------------------------------------------

## Security Model

C64 Gate assumes the device firmware may be untrusted.

Protections include:

-   mandatory traffic gateway
-   firewall containment
-   outbound HTTPS upgrade attempts
-   encrypted access endpoints
-   DNS visibility
-   packet logging

If the gateway stops running, the device loses network connectivity,
preventing bypass.

------------------------------------------------------------------------

## Future Extensions

Possible future enhancements:

-   intrusion detection integration
-   DNS telemetry alerts
-   firmware behavior profiling
-   remote VPN access
-   multi‑device support
