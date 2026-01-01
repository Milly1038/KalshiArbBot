"""Fuzzy market mapping for Kalshi teams and contracts."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable

import aiohttp
import orjson
from rapidfuzz import process, fuzz

from config import KALSHI_MARKETS_URL


@dataclass(frozen=True)
class MarketEntry:
    ticker: str
    title: str
    teams: tuple[str, ...]


class MarketMapper:
    def __init__(self) -> None:
        self._entries: list[MarketEntry] = []
        self._team_index: list[str] = []
        self._lock = asyncio.Lock()

    async def preload(self, session: aiohttp.ClientSession) -> None:
        """Load all active markets into memory once at startup."""
        async with self._lock:
            if self._entries:
                return
            params = {"status": "open", "limit": 200}
            entries: list[MarketEntry] = []
            async with session.get(KALSHI_MARKETS_URL, params=params) as resp:
                resp.raise_for_status()
                payload = orjson.loads(await resp.read())
            for market in payload.get("markets", []):
                title = market.get("title", "")
                ticker = market.get("ticker", "")
                teams = tuple(self._extract_teams(title))
                entries.append(MarketEntry(ticker=ticker, title=title, teams=teams))
            self._entries = entries
            self._team_index = [team for entry in entries for team in entry.teams]

    def _extract_teams(self, title: str) -> Iterable[str]:
        parts = [part.strip() for part in title.replace("@", "vs").split("vs")]
        return [part for part in parts if part]

    def match_team(self, name: str) -> str | None:
        """Return the closest team string from loaded markets."""
        if not self._team_index:
            return None
        match = process.extractOne(name, self._team_index, scorer=fuzz.WRatio)
        return match[0] if match else None

    def find_market(self, team_name: str) -> MarketEntry | None:
        """Return a market entry for a matching team name."""
        match = self.match_team(team_name)
        if not match:
            return None
        for entry in self._entries:
            if match in entry.teams:
                return entry
        return None
