"""Odds API websocket streaming into an asyncio queue."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import aiohttp

from config import API, ODDS_API_KEY, SHARP_BOOKS


async def odds_ws_feed(
    session: aiohttp.ClientSession, queue: "asyncio.Queue[dict[str, Any]]"
) -> None:
    url = API.odds_ws_url
    if ODDS_API_KEY and "apiKey=" not in url:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        query["apiKey"] = ODDS_API_KEY
        url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query),
                parsed.fragment,
            )
        )
    async with session.ws_connect(url, heartbeat=15) as ws:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                payload = json.loads(msg.data)
                book = payload.get("bookmaker") or payload.get("bookmaker_key") or ""
                if str(book).lower() in SHARP_BOOKS:
                    await queue.put(payload)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
