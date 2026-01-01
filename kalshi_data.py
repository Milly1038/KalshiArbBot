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


def _load_private_key() -> Any:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        if KALSHI_PRIVATE_KEY_B64:
            # Load from .env (Base64 string)
            key_bytes = base64.b64decode(KALSHI_PRIVATE_KEY_B64)
        elif KALSHI_PRIVATE_KEY_PATH:
            # Load from file
            with open(KALSHI_PRIVATE_KEY_PATH, "rb") as key_file:
                key_bytes = key_file.read()
        else:
            raise RuntimeError(
                "Set KALSHI_PRIVATE_KEY_B64 or KALSHI_PRIVATE_KEY_PATH for Kalshi auth"
            )
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


def _build_timestamp() -> str:
    """Return current timestamp in milliseconds (required by Kalshi)."""
    return str(int(time.time() * 1000))


def build_headers(method: str, url: str) -> dict[str, str]:
    """Generic header builder for both REST and WebSocket."""
    _ensure_credentials()
    timestamp = _build_timestamp()
    
    # Extract the path (e.g., /trade-api/v2/portfolio/orders) without query params
    parsed = urlparse(url)
    path = parsed.path 
    
    # Signature format: timestamp + method + path
    message = f"{timestamp}{method}{path}"
    
    # DEBUG: Print what we are signing to help troubleshoot 401s
    print(f"DEBUG SIGNING: {message}")

    signature = sign_request(message)
    
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json",
    }


async def kalshi_ws_stream(
    session: aiohttp.ClientSession,
) -> AsyncIterator[dict[str, Any]]:
    """Yield messages from the Kalshi websocket."""
    # Build headers for the WebSocket Handshake (GET request upgrade)
    headers = build_headers("GET", API.kalshi_ws_url)
    
    # Remove Content-Type for WS handshake as it can confuse some servers
    headers.pop("Content-Type", None)

    try:
        async with session.ws_connect(
            API.kalshi_ws_url, headers=headers, heartbeat=15
        ) as ws:
            print(f"Connected to Kalshi WS at {API.kalshi_ws_url}")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    yield json.loads(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"Kalshi WS Error: {msg.data}")
                    break
    except aiohttp.WSServerHandshakeError as e:
        if e.status == 401:
            print("\nCRITICAL: 401 UNAUTHORIZED")
            print("Most likely cause: System Clock is out of sync.")
            print("Run this command in terminal: sudo date -s \"$(wget -qSO- --max-redirect=0 google.com 2>&1 | grep Date: | cut -d' ' -f5-8)Z\"")
        raise e


async def place_limit_order(
    session: aiohttp.ClientSession,
    ticker: str,
    side: str,
    price: int,
    quantity: int,
) -> dict[str, Any]:
    """Submit a limit order to Kalshi using RSA-PSS signatures."""
    payload = {
        "ticker": ticker,
        "side": side,
        "type": "limit",
        "price": price,
        "count": quantity,
    }
    
    # FIX: Use RSA headers instead of Bearer token
    headers = build_headers("POST", KALSHI_ORDER_URL)

    async with session.post(KALSHI_ORDER_URL, json=payload, headers=headers) as resp:
        # Print error details if it fails
        if resp.status != 201:
            text = await resp.text()
            print(f"Order Failed ({resp.status}): {text}")
        resp.raise_for_status()
        return await resp.json()
