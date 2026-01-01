"""Configuration settings for the sniper bot."""
import os

# --- 1. AUTO-LOAD .ENV FILE ---
# This manually reads your .env file so you don't need 'python-dotenv'
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Split on the first "=" to handle the long B64 key safely
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip('\'"')
                os.environ[key] = value

# --- 2. AUTHENTICATION ---
# These now come directly from your .env file
KALSHI_KEY_ID = os.environ.get("KALSHI_KEY_ID")
KALSHI_PRIVATE_KEY_B64 = os.environ.get("KALSHI_PRIVATE_KEY_B64")
KALSHI_PRIVATE_KEY_PATH = None  # Disabled (we are using B64)
KALSHI_API_KEY = None           # Not used for V2

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

# --- 3. STRATEGY SETTINGS ---
SHARP_BOOKS = ["betmgm", "kalshi", "fanduel", "draftkings", "hardrockbet"]
BANKROLL = float(os.environ.get("BANKROLL", "500.0"))
KELLY_MULTIPLIER = float(os.environ.get("KELLY_MULTIPLIER", "0.1"))
EV_THRESHOLD = 0.02

# --- 4. API ENDPOINTS ---
class API:
    # Kalshi V2 Production (Correct "elections" subdomain)
    kalshi_ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"
    kalshi_api_url = "https://api.elections.kalshi.com/trade-api/v2"
    
    # OddsPapi
    odds_ws_url = "wss://api.oddspapi.io/v4/ws"

# Derived URLs
KALSHI_ORDER_URL = f"{API.kalshi_api_url}/portfolio/orders"
KALSHI_MARKETS_URL = f"{API.kalshi_api_url}/markets"
