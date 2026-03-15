FROM debian:stable-slim AS caddy-fetch

ARG TARGETARCH
ARG CADDY_VERSION=2.11.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar \
    && rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
    amd64) export CADDY_ARCH="amd64" ;; \
    arm64) export CADDY_ARCH="arm64" ;; \
    *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${CADDY_ARCH}.tar.gz" -o /tmp/caddy.tgz \
    && tar -xzf /tmp/caddy.tgz -C /tmp \
    && install -m 0755 /tmp/caddy /usr/local/bin/caddy

FROM debian:stable-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/c64gate/src \
    C64GATE_SIMULATION_MODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    dnsmasq \
    nftables \
    openssl \
    proftpd-core \
    proftpd-mod-crypto \
    proftpd-mod-proxy \
    python3 \
    python3-pip \
    tshark \
    && rm -rf /var/lib/apt/lists/*

COPY --from=caddy-fetch /usr/local/bin/caddy /usr/local/bin/caddy

WORKDIR /opt/c64gate

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY src ./src
COPY config ./config
COPY docker ./docker
COPY build ./build
COPY README.md LICENSE ./

RUN chmod +x ./docker/entrypoint.sh ./build

EXPOSE 8443 2121 8081 18080

ENTRYPOINT ["/opt/c64gate/docker/entrypoint.sh"]
