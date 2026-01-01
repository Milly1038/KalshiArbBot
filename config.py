"""Centralized configuration for the arbitrage bot."""
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
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi.key")

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

BANKROLL = float(os.getenv("BANKROLL", "1000"))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "50"))
MIN_EDGE = float(os.getenv("MIN_EDGE", "0.02"))

KALSHI_MARKETS_URL = f"{API.kalshi_rest_base}/trade-api/v2/markets"
