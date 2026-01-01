"""Centralized configuration for the sniper bot."""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV = os.getenv("KALSHI_ENV", "DEMO").upper()


@dataclass(frozen=True)
class ApiConfig:
    kalshi_rest_base: str
    kalshi_ws_url: str
    odds_ws_url: str


API_CONFIGS = {
    "DEMO": ApiConfig(
        kalshi_rest_base="https://demo-api.kalshi.co",
        kalshi_ws_url="wss://demo-api.kalshi.co/ws",
        odds_ws_url="wss://api.the-odds-api.com/v4/sports",  # placeholder
    ),
    "PROD": ApiConfig(
        kalshi_rest_base="https://api.kalshi.com",
        kalshi_ws_url="wss://api.kalshi.com/ws",
        odds_ws_url="wss://api.the-odds-api.com/v4/sports",  # placeholder
    ),
}

API = API_CONFIGS.get(ENV, API_CONFIGS["DEMO"])

KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID", "")
KALSHI_PRIVATE_KEY_B64 = os.getenv("KALSHI_PRIVATE_KEY_B64", "")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

BANKROLL = float(os.getenv("BANKROLL", "1000"))
EV_THRESHOLD = float(os.getenv("EV_THRESHOLD", "0.05"))
KELLY_MULTIPLIER = float(os.getenv("KELLY_MULTIPLIER", "0.2"))

KALSHI_MARKETS_URL = f"{API.kalshi_rest_base}/trade-api/v2/markets"
KALSHI_ORDER_URL = f"{API.kalshi_rest_base}/trade-api/v2/portfolio/orders"

SHARP_BOOKS = {"DraftKings", "Pinnacle", "FanDuel"}
