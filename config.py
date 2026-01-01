"""Centralized configuration for the Ashburn Sniper Bot."""
from __future__ import annotations
import os
from dataclasses import dataclass

# --- 🏦 MONEY MANAGEMENT ---
BANKROLL = 26.00
MAX_RISK_PER_TRADE = 2.00
MIN_EDGE = 0.02

# --- 🌍 ENVIRONMENT ---
ENV = os.getenv("KALSHI_ENV", "PROD").upper() 

# --- 🔑 API KEYS ---
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY")
KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID")
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi.key") 
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

API_KEYS = {
    "THE_ODDS_API": ODDS_API_KEY,
    "KALSHI_ID": KALSHI_KEY_ID
}

# --- 🔌 ENDPOINTS ---
@dataclass(frozen=True)
class ApiConfig:
    kalshi_rest_base: str
    kalshi_ws_url: str
    odds_ws_url: str

API_CONFIGS = {
    "DEMO": ApiConfig(
        kalshi_rest_base="https://demo-api.kalshi.co",
        kalshi_ws_url="wss://demo-api.kalshi.co/trade-api/ws/v2",
        odds_ws_url="wss://app.oddsapi.io/ws/v1", 
    ),
    "PROD": ApiConfig(
        # WE KNOW THIS DOMAIN RESOLVES:
        kalshi_rest_base="https://api.elections.kalshi.com",
        kalshi_ws_url="wss://api.elections.kalshi.com/trade-api/ws/v2",
        odds_ws_url="wss://app.oddsapi.io/ws/v1", 
    ),
}

API = API_CONFIGS.get(ENV, API_CONFIGS["PROD"])

# --- ⚙️ BETTING SETTINGS ---
BETTING_SETTINGS = {
    "LEAGUES": ["10", "11", "14", "15"],
    "REGIONS": "us",
    "MARKETS": "h2h",
    "ODDS_FORMAT": "american"
}

# --- 🛡️ FILTERS ---
FILTERS = {
    "TARGET_SPORTSBOOKS": ["draftkings", "fanduel", "betmgm", "hardrockbet", "caesars"],
    "MIN_LIQUIDITY": 10,
    "MIN_PROFIT_PCT": 2.0
}

# REQUIRED MARKET MAPPER URL
KALSHI_MARKETS_URL = f"{API.kalshi_rest_base}/trade-api/v2/markets"
