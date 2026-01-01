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

from config import API, KALSHI_API_KEY, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, KALSHI_ORDER_URL

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
        if not KALSHI_PRIVATE_KEY_B64:
            raise RuntimeError("KALSHI_PRIVATE_KEY_B64 is not set")
        key_bytes = base64.b64decode(KALSHI_PRIVATE_KEY_B64)
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


def build_auth_payload() -> dict[str, Any]:
    _ensure_credentials()
    timestamp = str(int(time.time() * 1000))
    api_key = _api_key_value()
    message = f"{timestamp}{api_key}"
    signature = sign_request(message)
    return {
        "id": KALSHI_KEY_ID,
        "timestamp": timestamp,
        "signature": signature,
        "api_key": api_key,
    }


def build_ws_headers(ws_url: str) -> dict[str, str]:
    """Build websocket auth headers using Kalshi's access signature scheme."""
    _ensure_credentials()
    parsed = urlparse(ws_url)
    timestamp = str(int(time.time() * 1000))
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
    headers = build_ws_headers(API.kalshi_ws_url)
    async with session.ws_connect(API.kalshi_ws_url, headers=headers, heartbeat=15) as ws:
        await ws.send_str(json.dumps({"type": "auth", "data": build_auth_payload()}))
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                yield json.loads(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break


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
