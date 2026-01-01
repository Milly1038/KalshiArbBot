"""Odds API websocket streaming into an asyncio queue."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import aiohttp

# Ensure these are imported from your config
from config import API, ODDS_API_KEY, SHARP_BOOKS

# Configure local logging for this module
logger = logging.getLogger(__name__)

async def odds_ws_feed(
    session: aiohttp.ClientSession, queue: "asyncio.Queue[dict[str, Any]]"
) -> None:
    """
    Connect to the Odds WebSocket. 
    Includes automatic whitespace stripping and error handling for 401s.
    """
    raw_url = API.odds_ws_url
    
    # FIX: Ensure the key has no invisible whitespace (common copy-paste error)
    clean_key = ODDS_API_KEY.strip() if ODDS_API_KEY else ""

    # Construct the URL safely
    if clean_key and "apiKey=" not in raw_url:
        parsed = urlparse(raw_url)
        query = dict(parse_qsl(parsed.query))
        query["apiKey"] = clean_key
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
    else:
        url = raw_url

    print(f"Attempting to connect to Odds WS...") # Debug print

    while True:
        try:
            async with session.ws_connect(url, heartbeat=15) as ws:
                print("Successfully connected to Odds WS!")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            payload = json.loads(msg.data)
                            book = payload.get("bookmaker") or payload.get("bookmaker_key") or ""
                            if str(book).lower() in SHARP_BOOKS:
                                await queue.put(payload)
                        except json.JSONDecodeError:
                            logger.error("Failed to decode JSON from websocket")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"Websocket connection closed with error: {ws.exception()}")
                        break
        
        except aiohttp.WSServerHandshakeError as e:
            if e.status == 401:
                print("\nCRITICAL ERROR: 401 Unauthorized.")
                print("1. Check config.py: Is the API Key correct?")
                print("2. Check Subscription: Does your plan allow WebSocket (WSS) access?")
                print(f"URL used: {url.replace(clean_key, 'REDACTED')}") # Don't print the actual key to logs
                # Stop the loop, otherwise, we just spam the server and get banned
                return
            else:
                print(f"Handshake error ({e.status}). Retrying in 5 seconds...")
                await asyncio.sleep(5)
        
        except Exception as e:
            print(f"Connection lost: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
