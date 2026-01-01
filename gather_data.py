"""Odds API websocket streaming into an asyncio queue."""
from __future__ import annotations

import json
from typing import Any

import aiohttp

from config import API, ODDS_API_KEY, SHARP_BOOKS


async def odds_ws_feed(
    session: aiohttp.ClientSession, queue: "asyncio.Queue[dict[str, Any]]"
) -> None:
    headers = {"x-api-key": ODDS_API_KEY} if ODDS_API_KEY else {}
    async with session.ws_connect(API.odds_ws_url, heartbeat=15, headers=headers) as ws:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                payload = json.loads(msg.data)
                book = payload.get("bookmaker") or payload.get("bookmaker_key") or ""
                if str(book).lower() in SHARP_BOOKS:
                    await queue.put(payload)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
