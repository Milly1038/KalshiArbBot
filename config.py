"""Centralized configuration for the sniper bot."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

KALSHI_REST_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
ODDS_WS_URL = "wss://api.oddspapi.io/v4/ws"


@dataclass(frozen=True)
class ApiConfig:
    kalshi_rest_base: str
    kalshi_ws_url: str
    odds_ws_url: str


API = ApiConfig(
    kalshi_rest_base=KALSHI_REST_BASE,
    kalshi_ws_url=KALSHI_WS_URL,
    odds_ws_url=ODDS_WS_URL,
)

KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID", "")
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
KALSHI_PRIVATE_KEY_B64 = os.getenv("KALSHI_PRIVATE_KEY_B64", "")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

BANKROLL = float(os.getenv("BANKROLL", "1000"))
EV_THRESHOLD = float(os.getenv("EV_THRESHOLD", "0.05"))
KELLY_MULTIPLIER = float(os.getenv("KELLY_MULTIPLIER", "0.2"))

KALSHI_MARKETS_URL = f"{KALSHI_REST_BASE}/markets"
KALSHI_ORDER_URL = f"{KALSHI_REST_BASE}/portfolio/orders"

SHARP_BOOKS = {
    "draftkings",
    "pinnacle",
    "fanduel",
    "betmgm",
    "hardrockbet",
}
