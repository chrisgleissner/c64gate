FROM debian:stable-slim AS caddy-fetch

ARG TARGETARCH
ARG CADDY_VERSION=2.11.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar grep coreutils \
    && rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
    amd64) export CADDY_ARCH="amd64" ;; \
    arm64) export CADDY_ARCH="arm64" ;; \
    *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_checksums.txt" -o /tmp/caddy-checksums.txt \
    && curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${CADDY_ARCH}.tar.gz" -o /tmp/caddy.tgz \
    && grep "caddy_${CADDY_VERSION}_linux_${CADDY_ARCH}.tar.gz" /tmp/caddy-checksums.txt | sha256sum -c - \
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
    iproute2 \
    nftables \
    openssl \
    proftpd-core \
    proftpd-mod-crypto \
    proftpd-mod-proxy \
    python3 \
    python3-pip \
    tshark \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --home-dir /var/lib/c64gate --shell /usr/sbin/nologin c64gate \
    && mkdir -p /var/lib/c64gate/logs /var/lib/c64gate/pcap /var/lib/c64gate/caddy /run/c64gate \
    && chown -R root:root /var/lib/c64gate /run/c64gate \
    && chown -R c64gate:c64gate /var/lib/c64gate/logs /var/lib/c64gate/caddy

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

EXPOSE 8443 2121

ENTRYPOINT ["/opt/c64gate/docker/entrypoint.sh"]
