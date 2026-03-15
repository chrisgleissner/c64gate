from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import h11
import httpx

from common.logging import CanonicalLogEvent, JsonLogger
from common.settings import Settings
from upgrade_proxy.cache import CapabilityCache


@dataclass(slots=True)
class ParsedRequest:
    method: str
    target: str
    headers: dict[str, str]
    body: bytes


class ProxyRequestError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _parse_request(data: bytes) -> ParsedRequest:
    conn = h11.Connection(h11.SERVER)
    conn.receive_data(data)
    event = conn.next_event()
    if not isinstance(event, h11.Request):
        raise ProxyRequestError(400, "expected HTTP request")
    body = bytearray()
    while True:
        next_event = conn.next_event()
        if isinstance(next_event, h11.Data):
            body.extend(next_event.data)
        elif isinstance(next_event, h11.EndOfMessage):
            break
        elif next_event is h11.NEED_DATA:
            break
    headers = {key.decode("ascii").lower(): value.decode("ascii") for key, value in event.headers}
    return ParsedRequest(
        method=event.method.decode("ascii"),
        target=event.target.decode("ascii"),
        headers=headers,
        body=bytes(body),
    )


def _resolve_urls(request: ParsedRequest) -> tuple[str, str, str]:
    if request.target.startswith("http://") or request.target.startswith("https://"):
        split = urlsplit(request.target)
        host = split.netloc
        path = split.path or "/"
        if split.query:
            path = f"{path}?{split.query}"
    else:
        host = request.headers["host"]
        path = request.target
    return host, f"https://{host}{path}", f"http://{host}{path}"


class UpgradeProxyService:
    def __init__(
        self, settings: Settings, logger: JsonLogger, runtime_state: dict[str, Any]
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.runtime_state = runtime_state
        self.cache = CapabilityCache()
        verify: bool | ssl.SSLContext = True
        if self.settings.tls_ca_bundle is not None:
            verify = ssl.create_default_context(cafile=str(Path(self.settings.tls_ca_bundle)))
        self.client = httpx.AsyncClient(follow_redirects=False, timeout=10.0, verify=verify)

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(
            self.handle_client,
            host=self.settings.upgrade_proxy_host,
            port=self.settings.upgrade_proxy_port,
        )

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        started = perf_counter()
        response: httpx.Response | None = None
        decision = "granted"
        action = "https-upgrade"
        warnings: list[str] = []
        try:
            request = await self._read_request(reader)
        except ProxyRequestError as exc:
            await self._write_error(writer, exc.status_code, exc.message)
            return
        host, https_url, http_url = self._resolve_urls(request)
        cache_key = host
        cached = self.cache.get(cache_key)
        try:
            if cached is None or cached.mode == "https":
                response = await self._send_upstream(request, https_url)
                self.cache.set(cache_key, "https")
            else:
                response = await self._send_upstream(request, http_url)
        except (
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            httpx.ReadError,
            ssl.SSLError,
            httpx.ConnectTimeout,
        ) as exc:
            warnings.append(type(exc).__name__)
            if self.settings.strict_tls_mode:
                decision = "blocked"
                action = "strict-tls-block"
            else:
                response = await self._send_upstream(request, http_url)
                self.cache.set(cache_key, "http")
                action = "http-fallback"
                warnings.append("https-unavailable")

        latency_ms = (perf_counter() - started) * 1000
        self.runtime_state.setdefault("metrics", {}).setdefault("upgrade_proxy_requests", 0)
        self.runtime_state["metrics"]["upgrade_proxy_requests"] += 1
        self.logger.emit(
            CanonicalLogEvent(
                protocol="http",
                direction="outbound",
                source="c64-device",
                destination=host,
                action=action,
                decision=decision,
                latency_ms=latency_ms,
                bytes_transferred=len(response.content) if response is not None else 0,
                component="upgrade_proxy",
                headers=request.headers if self.settings.verbose_logging else None,
                warnings=warnings or None,
                metadata={
                    "cache_mode": self.cache.get(cache_key).mode
                    if self.cache.get(cache_key)
                    else None
                },
            )
        )

        await self._write_response(writer, response, decision)

    async def _read_request(self, reader: asyncio.StreamReader) -> ParsedRequest:
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            if len(buffer) >= self.settings.proxy_max_header_bytes:
                raise ProxyRequestError(431, "request headers too large")
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=self.settings.proxy_client_header_timeout_seconds)
            except TimeoutError as exc:
                raise ProxyRequestError(408, "request header timeout") from exc
            if not chunk:
                raise ProxyRequestError(400, "incomplete request headers")
            buffer.extend(chunk)
            if len(buffer) > self.settings.proxy_max_header_bytes:
                raise ProxyRequestError(431, "request headers too large")
        header_bytes, body_remainder = buffer.split(b"\r\n\r\n", 1)
        request = _parse_request(header_bytes + b"\r\n\r\n")
        transfer_encoding = request.headers.get("transfer-encoding")
        if transfer_encoding is not None:
            raise ProxyRequestError(501, "transfer-encoding is not supported")
        content_length_header = request.headers.get("content-length", "0")
        try:
            content_length = int(content_length_header)
        except ValueError as exc:
            raise ProxyRequestError(400, "invalid content-length") from exc
        if content_length > self.settings.proxy_max_body_bytes:
            raise ProxyRequestError(413, "request body too large")
        body = bytearray(body_remainder)
        while len(body) < content_length:
            try:
                chunk = await asyncio.wait_for(
                    reader.read(min(65536, content_length - len(body))),
                    timeout=self.settings.proxy_client_body_timeout_seconds,
                )
            except TimeoutError as exc:
                raise ProxyRequestError(408, "request body timeout") from exc
            if not chunk:
                raise ProxyRequestError(400, "incomplete request body")
            body.extend(chunk)
        request.body = bytes(body[:content_length])
        return request

    async def _send_upstream(self, request: ParsedRequest, url: str) -> httpx.Response:
        headers = {key: value for key, value in request.headers.items() if key != "host"}
        return await self.client.request(
            request.method,
            url,
            content=request.body or None,
            headers=headers,
        )

    def _resolve_urls(self, request: ParsedRequest) -> tuple[str, str, str]:
        host, _, http_url = _resolve_urls(request)
        split = urlsplit(http_url)
        hostname = split.hostname or request.headers["host"]
        http_port = split.port or 80
        https_port = self.settings.https_port_map.get(
            http_port, 443 if http_port == 80 else http_port
        )
        netloc = hostname if https_port == 443 else f"{hostname}:{https_port}"
        https_url = f"https://{netloc}{split.path or '/'}"
        if split.query:
            https_url = f"{https_url}?{split.query}"
        return host, https_url, http_url

    async def _write_response(
        self,
        writer: asyncio.StreamWriter,
        response: httpx.Response | None,
        decision: str,
    ) -> None:
        conn = h11.Connection(h11.SERVER)
        if decision == "blocked" or response is None:
            payload = b"HTTPS upgrade failed and strict TLS mode rejected HTTP fallback."
            headers = [
                (b"content-length", str(len(payload)).encode("ascii")),
                (b"content-type", b"text/plain"),
            ]
            data = b"".join(
                [
                    conn.send(h11.Response(status_code=502, headers=headers)),
                    conn.send(h11.Data(data=payload)),
                    conn.send(h11.EndOfMessage()),
                ]
            )
        else:
            headers = [
                (key.encode("ascii"), value.encode("ascii"))
                for key, value in response.headers.items()
            ]
            data = b"".join(
                [
                    conn.send(h11.Response(status_code=response.status_code, headers=headers)),
                    conn.send(h11.Data(data=response.content)),
                    conn.send(h11.EndOfMessage()),
                ]
            )
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _write_error(
        self, writer: asyncio.StreamWriter, status_code: int, message: str
    ) -> None:
        conn = h11.Connection(h11.SERVER)
        payload = message.encode("utf-8")
        data = b"".join(
            [
                conn.send(
                    h11.Response(
                        status_code=status_code,
                        headers=[
                            (b"content-length", str(len(payload)).encode("ascii")),
                            (b"content-type", b"text/plain"),
                        ],
                    )
                ),
                conn.send(h11.Data(data=payload)),
                conn.send(h11.EndOfMessage()),
            ]
        )
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
