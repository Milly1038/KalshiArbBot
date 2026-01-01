"""Kalshi websocket data feed handling and request signing."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import API, KALSHI_API_KEY, KALSHI_KEY_ID, KALSHI_ORDER_URL, KALSHI_PRIVATE_KEY_B64

_PRIVATE_KEY = None


def _api_key_value() -> str:
    return KALSHI_API_KEY or KALSHI_KEY_ID


def _load_private_key() -> Any:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        if not KALSHI_PRIVATE_KEY_B64:
            raise RuntimeError(
                "Missing Key: set KALSHI_PRIVATE_KEY_B64 in your .env file"
            )
        key_bytes = base64.b64decode(KALSHI_PRIVATE_KEY_B64)
        _PRIVATE_KEY = serialization.load_pem_private_key(key_bytes, password=None)
    return _PRIVATE_KEY


def sign_request(message: str) -> str:
    """Sign a payload with RSA-2048 (PSS), returning base64."""
    private_key = _load_private_key()
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def build_ws_headers(ws_url: str, timestamp: str) -> dict[str, str]:
    """Build websocket auth headers using Kalshi's access signature scheme."""
    parsed = urlparse(ws_url)
    message = f"{timestamp}GET{parsed.path}"
    signature = sign_request(message)
    return {
        "Content-Type": "application/json",
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }


async def kalshi_ws_stream(
    session: aiohttp.ClientSession,
) -> AsyncIterator[dict[str, Any]]:
    """Yield messages from the Kalshi websocket."""
    if not KALSHI_KEY_ID:
        raise RuntimeError("Missing Key: set KALSHI_KEY_ID in your .env file")
    timestamp = str(int(time.time() * 1000))
    headers = build_ws_headers(API.kalshi_ws_url, timestamp)
    async with session.ws_connect(
        API.kalshi_ws_url, headers=headers, heartbeat=15
    ) as ws:
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
    if not KALSHI_KEY_ID:
        raise RuntimeError("Missing Key: set KALSHI_KEY_ID in your .env file")
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
