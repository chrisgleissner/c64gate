# Security Audit

## 1. Executive Summary

This audit reviews C64 Gate against the architecture in [doc/architecture.md](../architecture.md) and the current implementation on `main`. The architecture is directionally sound for a small Linux gateway, but the current implementation has several material security gaps that would prevent it from safely serving as a containment boundary for an untrusted Commodore 64 Ultimate device.

The highest-risk issues are not subtle. The current runtime renders firewall, DHCP, FTPS, and capture configuration, but does not start or enforce those controls. The container also runs as root with `NET_ADMIN` and `NET_RAW`, uses writable host bind mounts for logs, captures, and Caddy state, publishes management and proxy ports broadly, and pulls the Caddy binary without integrity verification. Those gaps create a realistic path from a compromised device or exposed service to loss of containment, log tampering, or host-impacting network manipulation.

The most important engineering conclusion is this: the project already has the right high-level security objectives, but its current implementation does not yet reliably provide the security boundary it documents. Remediation should focus first on making the gateway fail closed, constraining privilege, fixing management-plane exposure, and hardening the supply chain.

Positive observations:

- The architecture correctly assumes hostile firmware and treats observability as part of the security model.
- The Python upgrade proxy uses certificate validation by default through `httpx` unless explicitly overridden.
- The generated FTPS configuration already constrains TLS to `TLSv1.2` and `TLSv1.3`.
- The Python dependency set is small, which helps patching and review.

## 2. Threat Model

### Trust Boundaries

| Boundary | Less trusted side | More trusted side | Primary risk |
| --- | --- | --- | --- |
| Device-side network | C64 firmware and any attached device-side client | Gateway routing, filtering, logging, and capture | Policy bypass, parser attacks, DoS, log flooding |
| Management boundary | LAN clients and local host users | Dashboard, health, readiness, and logs | Credential theft, information disclosure, unauthorized admin access |
| Upstream network boundary | Internet hosts and services | Gateway egress controls and TLS upgrade logic | MITM, malicious responses, downgrade pressure, resource exhaustion |
| Host/container boundary | Containerized daemons and Python services | Linux host kernel, routing state, mounted files | Host network reconfiguration, packet sniffing, log tampering, container escape impact |
| Build/supply boundary | Package mirrors, GitHub releases, GitHub Actions marketplace | Final production image | Dependency compromise, malicious binary insertion |

### Attacker Capabilities

- Compromised C64 firmware can send arbitrary device-side traffic, malformed protocol input, and intentional high-rate flows.
- A malicious device-side client can abuse DHCP, DNS, FTP, HTTP, Telnet, or raw TCP/UDP paths.
- A malicious LAN client can target published ports, steal basic-auth credentials over cleartext management paths, or enumerate readiness data.
- A malicious Internet host can serve malformed HTTP or TLS responses, hold sockets open, and induce downgrade or cache poisoning behavior.
- A supply-chain attacker can target the Caddy download path, Python dependencies, distro packages, or CI actions.

### Critical Assets

- Effective firewall and routing policy enforcement.
- LAN isolation from the hostile device.
- Caddy local CA private keys and issued certificates.
- Dashboard credentials and authentication policy.
- PCAP files and normalized logs.
- Host network state, routing tables, and packet capture capability.
- Integrity of the production container image.

### Privilege Domains

| Domain | Current effective privilege | Notes |
| --- | --- | --- |
| Container entrypoint and Python runtime | Root inside container | No `USER` directive in [Dockerfile](../../Dockerfile) |
| Network control plane | `CAP_NET_ADMIN`, `CAP_NET_RAW` in [docker-compose.yml](../../docker-compose.yml) | Enough to modify firewall/routing and sniff/inject packets |
| Caddy PKI state | Writable host bind mount under [data/caddy](../../data/caddy) | Includes local CA private keys |
| Logs and captures | Writable host bind mounts under [data/logs](../../data/logs) and [data/pcap](../../data/pcap) | No integrity control or retention enforcement |
| CI/build pipeline | External package registries and GitHub Actions | Not fully integrity-pinned |

### External Interfaces and Data Flows

1. Device-side traffic enters the gateway and is supposed to be filtered, logged, optionally upgraded to HTTPS, and captured.
2. Inbound REST traffic reaches Caddy on `8443`, which proxies to the backend REST service.
3. Inbound dashboard traffic can reach Caddy on `8443` or the FastAPI control plane directly on `8081`.
4. FTPS is expected on `2121` through ProFTPD.
5. Logs and PCAP artifacts are written to host-mounted storage.
6. The image build downloads Caddy from GitHub and Python packages from PyPI.

## 3. Architecture Attack Surface

### Device-Side Attack Surface

- Outbound HTTP interception point implemented by [src/upgrade_proxy/service.py](../../src/upgrade_proxy/service.py).
- Any future nftables forward path rendered by [src/common/config_renderers.py](../../src/common/config_renderers.py).
- Passive DNS through `dnsmasq` and full packet capture tooling.
- Plaintext Telnet and raw TCP stream pass-through required by the architecture.

### LAN Attack Surface

- Published host ports `8443`, `2121`, and `8081` in [docker-compose.yml](../../docker-compose.yml).
- Direct HTTP management plane on `8081`.
- Caddy HTTPS facade and any reverse-proxied dashboard path.
- Host trust helper scripts in [scripts/setup-host-https.sh](../../scripts/setup-host-https.sh) and [scripts/trust-caddy-local-ca.sh](../../scripts/trust-caddy-local-ca.sh).

### Internet-Facing Attack Surface

- Whatever ports the operator publishes or forwards upstream, especially `8443` and `2121`.
- The upgrade proxy's outbound requests to arbitrary external destinations.
- Any plaintext HTTP fallback when strict TLS mode is disabled.

### Host and Build Attack Surface

- Root container with network capabilities.
- Bind-mounted CA, logs, and PCAP storage.
- Unverified Caddy download in [Dockerfile](../../Dockerfile).
- CI actions and package installs in [.github/workflows/ci.yml](../../.github/workflows/ci.yml).

## 4. Component Security Analysis

### nftables

- Hardening status: weak in current state.
- The renderer creates a default-drop ruleset, but the runtime does not apply it. [src/controlplane/runtime.py](../../src/controlplane/runtime.py) renders `nftables.conf` and validates the `nft` binary, but never runs `nft -f`.
- The rendered ruleset allows any non-RFC1918 IPv4 destination instead of enforcing the architecture's stated allowlist intent.
- IPv6 isolation is absent. The ruleset uses `ip daddr` tests only and does not block IPv6 ULA, link-local, or global traffic.
- Logging every decision is valuable, but log volume can be attacker-controlled.

### dnsmasq

- Hardening status: partial.
- The generated config uses `no-resolv`, `domain-needed`, and `bogus-priv`, which is a reasonable baseline.
- The runtime renders the config but does not start `dnsmasq`, so authoritative DHCP and DNS observability are not actually enforced.
- `log-queries=extra` creates high privacy sensitivity and disk-pressure risk.
- No DNS policy enforcement exists in v1, which means DNS is an observability plane, not a control plane.

### Caddy

- Hardening status: mixed.
- Caddy defaults are generally strong for TLS, and `tls internal` with a local CA is appropriate for LAN-first use.
- The dashboard auth configuration is inconsistent. The generated Caddyfile uses a fixed bcrypt hash instead of deriving from `C64GATE_DASHBOARD_PASSWORD`, while FastAPI separately checks the configured plaintext password.
- The API path is reverse proxied without additional authentication. That may be intended for device compatibility, but it should not be exposed beyond trusted management scope.
- Local CA keys persist on a host bind mount, increasing the consequences of host or volume compromise.

### ProFTPD with `mod_tls` and `mod_proxy`

- Hardening status: incomplete.
- The generated config enables TLS and reverse proxy mode and limits protocol versions to TLS 1.2 and 1.3.
- The runtime does not start ProFTPD, so the FTPS facade does not currently exist as an enforced security control.
- Passive data-channel hardening, backend credential handling, data-port scoping, and anti-bounce considerations are not yet visible in the configuration.
- FTPS in a containerized NAT path is operationally fragile and should be tested carefully before exposure.

### Python HTTP Upgrade Proxy (`h11` + `httpx`)

- Hardening status: moderate but incomplete.
- `httpx` certificate validation is enabled by default, which is correct.
- The service reads only until the end of headers and does not robustly stream or bound request bodies. That creates correctness and DoS risks.
- There is no per-connection timeout on incoming client reads, making slowloris-style starvation realistic.
- The default mode allows plaintext HTTP fallback, which weakens integrity and confidentiality guarantees.
- Capability caching is destination-based and unauthenticated. It is helpful for performance but susceptible to adversarial influence if not bounded carefully.

### FastAPI Dashboard and Control Plane

- Hardening status: weak for exposure control.
- Authentication is only applied to dashboard endpoints, not to `/health` or `/ready`.
- The service binds `0.0.0.0` by default and `docker-compose.yml` publishes `8081` directly.
- Direct `8081` access bypasses the Caddy HTTPS facade, so dashboard credentials can traverse cleartext if users connect directly.
- The readiness response leaks component inventory and capture command details that assist reconnaissance.

### `dumpcap` / `tshark` / `capinfos`

- Hardening status: not operationalized.
- The runtime validates the binaries and exposes capture commands in readiness, but does not start `dumpcap`.
- Packet capture typically requires elevated privilege or carefully delegated file capabilities. Running capture inside a root `NET_RAW` container increases blast radius.
- PCAP files are high-value forensic artifacts and should be treated as sensitive data.

### Docker Container Runtime

- Hardening status: weak.
- The image runs as root, no read-only root filesystem is configured, and no `no-new-privileges`-style confinement is declared.
- Compose grants `NET_ADMIN` and `NET_RAW`, and writable host mounts are present.
- Real router-mode deployment will likely require at least `CAP_NET_ADMIN`, `CAP_NET_RAW`, and direct interface attachment. That is workable, but it sharply raises the importance of process minimization and port exposure control.

## 5. Container Security Review

### Likely Required Privileges

- `CAP_NET_ADMIN`: required for nftables, routing, and DHCP-related interface control.
- `CAP_NET_RAW`: likely required for packet capture and some low-level network diagnostics.
- Privileged mode: not obviously required and should be avoided.
- Host networking: not required by the current Compose file, but real router-mode deployments may need host networking, macvlan, or direct namespace/interface wiring to reach physical uplink and device interfaces.

### Implications

- A compromise in Caddy, ProFTPD, FastAPI, or the Python upgrade proxy would land inside a container that can reprogram firewall state, observe traffic, and tamper with evidence.
- Bind-mounted host storage provides persistence and tamper opportunity even if the container is later replaced.
- If host networking is introduced for production realism, all exposed listeners become more directly host-reachable and the impact of parser bugs rises.

### Container Escape and Host Impact Assessment

- The present configuration does not by itself prove a container escape, but it materially increases the value of any daemon or kernel exploit.
- The combination of root, network capabilities, packet capture tooling, and host-mounted sensitive state makes post-compromise containment weak.

## 6. Network Security Review

- Router mode is the right topology for containment, but its security depends entirely on actual routing and firewall enforcement.
- The current runtime does not enforce nftables or start DHCP, so the intended device-side security perimeter is not live.
- The rendered firewall policy blocks IPv4 RFC1918 by default but does not address IPv6, which creates a plausible bypass path on dual-stack hosts.
- The current rendered ruleset accepts all non-RFC1918 IPv4 destinations rather than a strict destination allowlist.
- Published ports are not bound to `127.0.0.1`, so they are reachable on all host interfaces unless external firewalling limits them.
- DNS visibility exists as logging intent, but no DNS policy control exists, so domain-based exfiltration detection remains retrospective only.

Ways a compromised device could abuse the model:

- Use unrestricted public IPv4 destinations if the rendered ruleset is applied as written.
- Use IPv6 to bypass the RFC1918-only containment logic on dual-stack networks.
- Generate high-volume traffic to flood logs, captures, or proxy sockets.
- Use plaintext HTTP fallback as an exfiltration channel.

## 7. Protocol Security Review

### Incoming

- HTTP via HTTPS facade: directionally sound, but depends on not exposing the backend or control plane directly.
- FTP via FTPS facade: protocol-aware proxying is appropriate, but FTPS reverse proxying needs stricter passive-port and auth hardening before exposure.
- Telnet: passed through unchanged by design, which means plaintext credentials and session data remain exposed to any observer on permitted paths.
- TCP streaming endpoint: logged only at summary level by default, so deep inspection and abuse detection are limited.

### Outgoing

- HTTP to HTTPS upgrade: useful for raising baseline security, but the default HTTP fallback preserves plaintext risk.
- UDP streams: passed unchanged and logged in summary mode, which is resource-aware but weak for forensic depth under active abuse.

Primary protocol risks:

- Header spoofing and malformed request handling in the upgrade proxy.
- Cleartext Telnet exposure if routed beyond a trusted administrative enclave.
- HTTP downgrade or forced fallback behavior for hostile or misconfigured endpoints.
- FTP control/data-channel complexity in NAT or reverse-proxy deployment.

## 8. Cryptographic Security Review

- Caddy's internal CA is a practical fit for LAN-first deployment, but local CA trust changes the blast radius of any CA private-key compromise.
- The helper script in [scripts/trust-caddy-local-ca.sh](../../scripts/trust-caddy-local-ca.sh) imports that CA into the user's NSS trust store, making key protection important.
- The Docker build downloads the Caddy binary over TLS but does not verify checksum or signature.
- The FTPS configuration explicitly limits TLS to 1.2 and 1.3, which is good.
- The upgrade proxy uses strict certificate validation by default through `httpx`, which is also good.
- Strict TLS mode exists but is off by default, so plaintext fallback remains normal behavior.

## 9. Logging and Observability Risks

- JSON logs are useful for automation, but there is no visible signing, sealing, or append-only protection.
- Log and PCAP directories are writable host mounts, so a compromised container can delete or alter evidence.
- The current logger performs no size-based rotation or retention enforcement.
- Verbose logging can capture request headers and potentially credentials or session tokens.
- `dnsmasq` query logging and PCAP capture create privacy-sensitive records of device behavior.
- Readiness and dashboard responses expose recent events and component metadata that may aid reconnaissance.

## 10. Supply Chain Security

- The Caddy binary is fetched directly from GitHub releases in [Dockerfile](../../Dockerfile) without checksum or signature verification.
- Debian packages are not version-pinned, so rebuilds can drift over time.
- Python dependencies are version-pinned, which is good, but there are no install-time hashes for tamper resistance.
- GitHub Actions use major-version tags rather than immutable commit SHAs in [.github/workflows/ci.yml](../../.github/workflows/ci.yml).
- The repository includes persistent runtime state under [data/caddy](../../data/caddy), including local CA keys, which should not be treated as low-risk disposable data.

## 11. Prioritized Findings Table

| ID | Finding | Severity | Exploitability | Remediation Complexity | Priority |
| --- | --- | --- | --- | --- | --- |
| F1 | Documented gateway controls are not enforced at runtime | CRITICAL | High | Medium | P1 |
| F2 | Root container with `NET_ADMIN`/`NET_RAW` and writable host mounts creates high host-impact blast radius | HIGH | High | Medium | P1 |
| F3 | Management-plane exposure and inconsistent dashboard authentication weaken admin security | HIGH | High | Low | P1 |
| F4 | Supply-chain integrity is weak for Caddy, packages, and CI actions | HIGH | Medium | Medium | P1 |
| F5 | Local CA private keys persist on host mounts and are promoted into host trust stores | HIGH | Medium | Low | P2 |
| F6 | Firewall policy gaps allow broader egress than intended and do not cover IPv6 | HIGH | Medium | Medium | P2 |
| F7 | Upgrade proxy is susceptible to slow-read DoS and HTTP correctness edge cases | MEDIUM | High | Medium | P2 |
| F8 | Logging and capture design permits sensitive-data exposure, tampering, and disk exhaustion | MEDIUM | High | Low | P2 |
| F9 | Plaintext protocol paths remain available for Telnet and default HTTP fallback | MEDIUM | Medium | Low | P3 |
| F10 | Host preparation script weakens a global host security control | LOW | Medium | Low | P3 |

## 12. Detailed Findings

### F1. Documented gateway controls are not enforced at runtime

- Affected component: runtime orchestration, nftables, dnsmasq, ProFTPD, packet capture
- Description: [src/controlplane/runtime.py](../../src/controlplane/runtime.py) renders runtime configs and validates binaries, but only starts Caddy, the FastAPI control plane, and the Python upgrade proxy. It does not apply nftables rules, start `dnsmasq`, launch ProFTPD, or start `dumpcap`. This leaves the implemented security boundary materially weaker than the documented architecture.
- Exploitation scenario: an operator deploys C64 Gate believing firewall containment, DHCP control, FTPS facade, and full capture are active. A compromised device then communicates in ways the operator expects to be blocked or observed, but the controls are not running.
- Severity rating: CRITICAL
- Priority level: P1
- Remediation recommendation: make mandatory security controls explicit runtime prerequisites, start them under supervision, and fail closed when they do not start successfully.

### F2. Root container with `NET_ADMIN`/`NET_RAW` and writable host mounts creates high host-impact blast radius

- Affected component: Docker runtime, host/container boundary
- Description: [Dockerfile](../../Dockerfile) does not set a non-root user, and [docker-compose.yml](../../docker-compose.yml) grants `NET_ADMIN` and `NET_RAW` while bind-mounting persistent host directories for CA material, logs, and PCAPs. Any remote code execution in an exposed service would land in a process that can alter routing policy, observe traffic, and tamper with evidence.
- Exploitation scenario: an attacker exploits Caddy, ProFTPD, FastAPI, or the upgrade proxy and uses the container's capabilities to disable filtering, sniff packets, rewrite logs, or interfere with host networking.
- Severity rating: HIGH
- Priority level: P1
- Remediation recommendation: reduce privilege to the minimum workable set, split duties where possible, use a non-root user for non-network-control processes, and apply container hardening such as read-only rootfs and `no-new-privileges` where compatible.

### F3. Management-plane exposure and inconsistent dashboard authentication weaken admin security

- Affected component: Caddy, FastAPI control plane, Compose exposure
- Description: [docker-compose.yml](../../docker-compose.yml) publishes `8081` directly, the control plane binds `0.0.0.0` by default in [src/common/settings.py](../../src/common/settings.py), and [src/common/config_renderers.py](../../src/common/config_renderers.py) hardcodes a Caddy `basic_auth` hash instead of using the configured dashboard password. FastAPI separately uses `C64GATE_DASHBOARD_PASSWORD`, which defaults to `changeme`.
- Exploitation scenario: a LAN client connects directly to `http://host:8081/dashboard/...` and captures basic-auth credentials over cleartext, or an operator believes a rotated password protects the Caddy dashboard while Caddy still accepts a fixed credential set.
- Severity rating: HIGH
- Priority level: P1
- Remediation recommendation: stop publishing `8081` externally by default, require TLS for management access, remove static auth material from generated configs, and refuse weak default credentials in non-simulation deployments.

### F4. Supply-chain integrity is weak for Caddy, packages, and CI actions

- Affected component: image build and CI pipeline
- Description: [Dockerfile](../../Dockerfile) downloads the Caddy tarball with `curl` but does not verify checksum or signature. Debian packages are not version-pinned. Python packages are pinned by version but not by hash. [.github/workflows/ci.yml](../../.github/workflows/ci.yml) uses tagged GitHub Actions rather than immutable SHAs.
- Exploitation scenario: a compromised release artifact, package mirror, or malicious action update inserts a backdoored binary into the production image or CI workflow.
- Severity rating: HIGH
- Priority level: P1
- Remediation recommendation: verify upstream binaries cryptographically, pin CI actions to SHAs, and use reproducibility-oriented package controls where practical.

### F5. Local CA private keys persist on host mounts and are promoted into host trust stores

- Affected component: Caddy PKI state and host trust model
- Description: the mounted Caddy PKI directory under [data/caddy/pki/authorities/local](../../data/caddy/pki/authorities/local) contains `root.key` and `intermediate.key`. [scripts/trust-caddy-local-ca.sh](../../scripts/trust-caddy-local-ca.sh) imports the generated root CA into the user's NSS trust store. This makes the local CA a high-value secret rather than routine application state.
- Exploitation scenario: a local attacker, backup compromise, or mistakenly shared runtime directory exposes the CA private key. The attacker can then mint trusted certificates for names and endpoints that the operator has configured to trust.
- Severity rating: HIGH
- Priority level: P2
- Remediation recommendation: treat PKI material as secret data, lock down filesystem permissions, avoid committing or broadly sharing the directory, and document rotation and revocation procedures.

### F6. Firewall policy gaps allow broader egress than intended and do not cover IPv6

- Affected component: nftables policy model
- Description: [src/common/config_renderers.py](../../src/common/config_renderers.py) renders a forward policy that drops IPv4 RFC1918 destinations but accepts any non-RFC1918 IPv4 destination. It also lacks explicit IPv6 policy. That does not match the architecture's stated allowlist posture and leaves a dual-stack bypass path.
- Exploitation scenario: a compromised device sends traffic to arbitrary public endpoints or uses IPv6 to reach internal or external destinations that the operator expects the gateway to restrict.
- Severity rating: HIGH
- Priority level: P2
- Remediation recommendation: enforce an explicit destination model, add IPv6 policy parity, and test containment on dual-stack hosts.

### F7. Upgrade proxy is susceptible to slow-read DoS and HTTP correctness edge cases

- Affected component: Python upgrade proxy
- Description: [src/upgrade_proxy/service.py](../../src/upgrade_proxy/service.py) reads until `\r\n\r\n` without a client read timeout, does not stream request bodies, and handles only a narrow set of request forms. This is sufficient for happy-path tests but weak against hostile clients.
- Exploitation scenario: a malicious client opens many connections and slowly drips headers to exhaust the event loop, or sends a body-bearing request that is truncated or mishandled, producing undefined backend behavior.
- Severity rating: MEDIUM
- Priority level: P2
- Remediation recommendation: add connection timeouts, header and body limits, robust request streaming, and adversarial protocol tests.

### F8. Logging and capture design permits sensitive-data exposure, tampering, and disk exhaustion

- Affected component: JSON logging, PCAP storage, observability pipeline
- Description: [src/common/logging.py](../../src/common/logging.py) appends JSON logs without rotation or integrity protection. Verbose logging can include request headers, and host bind mounts allow modification or deletion of logs and captures. `dnsmasq` query logging and packet capture amplify privacy sensitivity.
- Exploitation scenario: a compromised device floods logs until disk pressure affects availability, or a compromised service deletes or alters PCAPs and JSON logs to frustrate investigation.
- Severity rating: MEDIUM
- Priority level: P2
- Remediation recommendation: enforce retention and size limits, minimize sensitive field capture, and separate operational logging from forensic-grade evidence storage.

### F9. Plaintext protocol paths remain available for Telnet and default HTTP fallback

- Affected component: protocol handling model
- Description: the architecture explicitly allows Telnet pass-through and HTTP fallback when strict TLS mode is disabled. Those paths preserve plaintext credentials, commands, or content and are incompatible with strong confidentiality or integrity guarantees.
- Exploitation scenario: a LAN or upstream attacker intercepts Telnet sessions or tampers with HTTP fallback traffic, using the hostile or vulnerable device as a foothold.
- Severity rating: MEDIUM
- Priority level: P3
- Remediation recommendation: scope these protocols to trusted networks only, warn clearly when plaintext paths are enabled, and prefer strict TLS mode for hostile environments.

### F10. Host preparation script weakens a global host security control

- Affected component: host operational tooling
- Description: [scripts/setup-host-https.sh](../../scripts/setup-host-https.sh) lowers `net.ipv4.ip_unprivileged_port_start` to `443` system-wide. That is convenient for rootless Docker on port 443, but it also allows any unprivileged local process on the host to bind ports `443` and above.
- Exploitation scenario: on a multi-user or less-trusted host, another unprivileged process binds a sensitive low port and impersonates a service or intercepts traffic.
- Severity rating: LOW
- Priority level: P3
- Remediation recommendation: document the host-wide impact clearly and prefer narrower alternatives where operationally feasible.

## 13. Recommended Remediation Order

1. Make the gateway fail closed by actually applying nftables and supervising all mandatory security controls, or refusing to declare readiness without them.
2. Reduce blast radius by constraining container privilege, narrowing mounts, and isolating high-risk functions from general application code where practical.
3. Lock down the management plane: remove direct `8081` exposure, require TLS, eliminate static auth material, and reject default credentials outside simulation.
4. Harden the build chain: verify Caddy downloads, pin CI actions immutably, and add stronger package integrity controls.
5. Correct firewall policy semantics, especially allowlist enforcement and IPv6 parity.
6. Protect Caddy CA keys and formalize key rotation, trust, and storage guidance.
7. Add resource controls and adversarial parsing tests for the upgrade proxy, logging pipeline, and capture workflow.
8. Treat plaintext protocol support as an exception path with explicit warnings and constrained exposure.