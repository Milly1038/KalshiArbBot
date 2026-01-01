"""Kalshi websocket data feed handling and request signing."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, AsyncIterator

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import API, KALSHI_API_KEY, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, KALSHI_ORDER_URL

_PRIVATE_KEY = None


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
    timestamp = str(int(time.time() * 1000))
    message = f"{timestamp}{KALSHI_API_KEY}"
    signature = sign_request(message)
    return {
        "id": KALSHI_KEY_ID,
        "timestamp": timestamp,
        "signature": signature,
        "api_key": KALSHI_API_KEY,
    }


async def kalshi_ws_stream(
    session: aiohttp.ClientSession,
) -> AsyncIterator[dict[str, Any]]:
    """Yield messages from the Kalshi websocket."""
    async with session.ws_connect(API.kalshi_ws_url, heartbeat=15) as ws:
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
    payload = {
        "ticker": ticker,
        "side": side,
        "type": "limit",
        "price": price,
        "count": quantity,
    }
    headers = {"Authorization": f"Bearer {KALSHI_API_KEY}"}
    async with session.post(KALSHI_ORDER_URL, json=payload, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()
