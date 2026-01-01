"""Kalshi websocket data feed handling and request signing."""
from __future__ import annotations

import base64
import json
import time
from urllib.parse import urlparse
from typing import Any, AsyncIterator

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import (
    API,
    KALSHI_API_KEY,
    KALSHI_KEY_ID,
    KALSHI_ORDER_URL,
    KALSHI_PRIVATE_KEY_B64,
    KALSHI_PRIVATE_KEY_PATH,
)

_PRIVATE_KEY = None


def _ensure_credentials() -> None:
    if not KALSHI_KEY_ID:
        raise RuntimeError(
            "KALSHI_KEY_ID is not set. This is the API key id shown in the Kalshi UI."
        )


def _api_key_value() -> str:
    return KALSHI_API_KEY or KALSHI_KEY_ID


def _load_private_key() -> Any:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        if KALSHI_PRIVATE_KEY_B64:
            key_bytes = base64.b64decode(KALSHI_PRIVATE_KEY_B64)
        elif KALSHI_PRIVATE_KEY_PATH:
            with open(KALSHI_PRIVATE_KEY_PATH, "rb") as key_file:
                key_bytes = key_file.read()
        else:
            raise RuntimeError(
                "Set KALSHI_PRIVATE_KEY_B64 or KALSHI_PRIVATE_KEY_PATH for Kalshi auth"
            )
        _PRIVATE_KEY = serialization.load_pem_private_key(key_bytes, password=None)
    return _PRIVATE_KEY


def sign_request(message: str) -> str:
    """Sign a payload with RSA-2048, returning base64."""
    private_key = _load_private_key()
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _build_timestamp(unit: str) -> str:
    if unit == "s":
        return str(int(time.time()))
    return str(int(time.time() * 1000))


def build_auth_payload(timestamp: str) -> dict[str, Any]:
    _ensure_credentials()
    api_key = _api_key_value()
    message = f"{timestamp}{api_key}"
    signature = sign_request(message)
    return {
        "id": KALSHI_KEY_ID,
        "timestamp": timestamp,
        "signature": signature,
        "api_key": api_key,
    }


def build_ws_headers(ws_url: str, timestamp: str) -> dict[str, str]:
    """Build websocket auth headers using Kalshi's access signature scheme."""
    _ensure_credentials()
    parsed = urlparse(ws_url)
    message = f"{timestamp}GET{parsed.path}"
    signature = sign_request(message)
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }


async def kalshi_ws_stream(
    session: aiohttp.ClientSession,
) -> AsyncIterator[dict[str, Any]]:
    """Yield messages from the Kalshi websocket."""
    last_error: Exception | None = None
    attempts = [
        ("ms", "ms", True),
        ("s", "s", True),
        ("s", "ms", True),
        ("ms", "s", True),
        ("ms", "ms", False),
        ("s", "s", False),
    ]
    for header_unit, payload_unit, use_headers in attempts:
        header_ts = _build_timestamp(header_unit)
        payload_ts = _build_timestamp(payload_unit)
        headers = build_ws_headers(API.kalshi_ws_url, header_ts) if use_headers else None
        try:
            async with session.ws_connect(
                API.kalshi_ws_url, headers=headers, heartbeat=15
            ) as ws:
                await ws.send_str(
                    json.dumps({"type": "auth", "data": build_auth_payload(payload_ts)})
                )
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        yield json.loads(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
            return
        except aiohttp.WSServerHandshakeError as exc:
            last_error = exc
            if exc.status != 401:
                break
    if last_error is not None:
        raise last_error


async def place_limit_order(
    session: aiohttp.ClientSession,
    ticker: str,
    side: str,
    price: int,
    quantity: int,
) -> dict[str, Any]:
    """Submit a limit order to Kalshi."""
    _ensure_credentials()
    api_key = _api_key_value()
    payload = {
        "ticker": ticker,
        "side": side,
        "type": "limit",
        "price": price,
        "count": quantity,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    async with session.post(KALSHI_ORDER_URL, json=payload, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()
