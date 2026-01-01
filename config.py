"""Centralized configuration for the Ashburn Sniper Bot."""
from __future__ import annotations
import os
from dataclasses import dataclass

# --- 🏦 MONEY MANAGEMENT ---
BANKROLL = 26.00       # Your starting amount
MAX_RISK_PER_TRADE = 2.00   # Max bet per snipe
MIN_EDGE = 0.02             # Minimum 2% edge required to fire

# --- 🌍 ENVIRONMENT ---
# Set to "PROD" to use real money and real API endpoints
ENV = os.getenv("KALSHI_ENV", "PROD").upper() 

# --- 🔑 API KEYS ---
# PASTE YOUR REAL KEYS HERE IF NOT USING ENV VARIABLES
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "YOUR_KALSHI_KEY_ID_HERE")
KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID", "YOUR_KALSHI_KEY_ID_HERE")
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi.key") 

# Your "oddspapi.io" key
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "YOUR_ODDS_API_KEY_HERE")

# Backwards compatibility map (for gather_data.py)
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
        kalshi_rest_base="https://api.elections.kalshi.com",
        kalshi_ws_url="wss://api.elections.kalshi.com/trade-api/ws/v2",
        odds_ws_url="wss://app.oddsapi.io/ws/v1", 
    ),
}

API = API_CONFIGS.get(ENV, API_CONFIGS["DEMO"])

# --- ⚙️ BETTING SETTINGS ---
BETTING_SETTINGS = {
    # UPDATED: Using the Numeric IDs required by your API provider
    "LEAGUES": [
        "10", # Soccer/Generic (Verify based on your API dashboard)
        "11", # Basketball (NBA usually)
        "14", # Hockey (NHL)
        "15"  # Football (NFL/NCAAF)
    ],
    
    "REGIONS": "us",
    "MARKETS": "h2h",  # Moneyline only for snipes
    "ODDS_FORMAT": "american"
}

# --- 🛡️ FILTERS ---
FILTERS = {
    "TARGET_SPORTSBOOKS": [
        "draftkings", 
        "fanduel", 
        "betmgm", 
        "hardrockbet",
        "caesars"
    ],
    "MIN_LIQUIDITY": 10,       # Lowered for sniping (we only need $2 liquidity)
    "MIN_PROFIT_PCT": 2.0      # Minimum edge to trigger
}
