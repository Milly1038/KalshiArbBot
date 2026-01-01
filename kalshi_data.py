"""Kalshi websocket data feed handling and request signing."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, AsyncIterator

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import API, KALSHI_API_KEY, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_PATH

_PRIVATE_KEY = None


def _load_private_key() -> Any:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        with open(KALSHI_PRIVATE_KEY_PATH, "rb") as key_file:
            _PRIVATE_KEY = serialization.load_pem_private_key(
                key_file.read(), password=None
            )
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


def build_ws_headers() -> dict[str, str]:
    """Generates the required headers for the WebSocket Handshake."""
    timestamp = str(int(time.time() * 1000))
    # CRITICAL: Signature message must be: timestamp + "GET" + "/trade-api/ws/v2"
    msg = f"{timestamp}GET/trade-api/ws/v2"
    signature = sign_request(msg)
    
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp
    }


async def kalshi_ws_stream(
    session: aiohttp.ClientSession,
) -> AsyncIterator[dict[str, Any]]:
    """Yield messages from the Kalshi websocket."""
    
    # 1. Generate Headers BEFORE connecting
    headers = build_ws_headers()
    
    # 2. Connect WITH Headers (This fixes the 401)
    async with session.ws_connect(API.kalshi_ws_url, headers=headers, heartbeat=15) as ws:
        # Note: We do NOT send the {"type": "auth"} message anymore. 
        # The headers handle it.
        
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                yield json.loads(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
