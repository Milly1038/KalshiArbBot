"""Entry point for the Ashburn Sniper Bot (High-Frequency)."""
from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

# --- LOCAL MODULES ---
from config import (
    BANKROLL, 
    MAX_RISK_PER_TRADE, 
    MIN_EDGE, 
    API, 
    KALSHI_API_KEY, 
    KALSHI_KEY_ID
)
from gather_data import odds_ws_feed
from kalshi_data import kalshi_ws_stream, sign_request
from mapping import MarketMapper

# --- SYSTEM OPTIMIZATION ---
import sys
if sys.platform == 'win32':
    try:
        import winloop
        asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
    except ImportError:
        pass

console = Console()

@dataclass
class BotState:
    bankroll: float = BANKROLL
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)
        self.logs[:] = self.logs[-10:] # Keep last 10 logs

# --- 🧮 MATH HELPERS ---
def implied_prob(american_odds: int) -> float:
    """Converts American Odds (-110, +150) to Implied Probability (0.0 to 1.0)."""
    if american_odds < 0:
        return (-american_odds) / (-american_odds + 100)
    else:
        return 100 / (american_odds + 100)

# --- 🔫 EXECUTION ENGINE ---
async def get_kalshi_ask(session: aiohttp.ClientSession, ticker: str) -> float | None:
    """Fetches the current cheapest 'Yes' price (Ask) for a ticker."""
    url = f"{API.kalshi_rest_base}/trade-api/v2/markets/{ticker}/orderbook"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Orderbook structure: {'orderbook': {'yes': [[price, qty], ...], ...}}
                yes_asks = data.get('orderbook', {}).get('yes', [])
                if yes_asks:
                    return yes_asks[0][0] # Return the Price (cents)
    except Exception:
        pass
    return None

async def execute_snipe(session: aiohttp.ClientSession, ticker: str, side: str, count: int, price: int, state: BotState) -> bool:
    """Fires a LIMIT order to Kalshi immediately (Zero Disk I/O)."""
    timestamp = str(int(time.time() * 1000))
    path = "/trade-api/v2/portfolio/orders"
    
    # Sign the request using the in-memory key
    msg = f"{timestamp}POST{path}" 
    signature = sign_request(msg) 
    
    headers = {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }

    # API expects price in cents (e.g., 45)
    payload = {
        "action": "buy",
        "ticker": ticker, 
        "count": count,
        "max_cost": count * price,
        "side": side,
        "type": "limit",
        "yes_price": price,
        "client_order_id": str(int(time.time() * 100000))
    }
    
    url = f"{API.kalshi_rest_base}{path}"

    try:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status in [201, 200]:
                state.log(f"🔫 FIRE SUCCESS: {count}x {ticker} @ {price}¢")
                return True
            else:
                err = await resp.text()
                state.log(f"❌ FIRE FAIL: {err[:50]}")
                return False
    except Exception as e:
        state.log(f"❌ NET ERROR: {e}")
        return False

# --- 🧠 CORE LOGIC LOOP ---
async def process_odds_feed(state: BotState, queue: asyncio.Queue[dict[str, Any]], mapper: MarketMapper) -> None:
    """
    The Sniper Loop:
    1. Reads Sportsbook feed.
    2. Maps Team -> Kalshi Ticker.
    3. Checks Implied Probability vs Kalshi Price.
    4. Fires if Edge > MIN_EDGE.
    """
    TARGET_BOOKS = ["draftkings", "fanduel", "pinnacle"] # Sharps only
    
    while True:
        payload = await queue.get()
        
        # 1. Parse Odds API Payload
        # Structure: {'home_team': 'Chiefs', 'bookmakers': [...]}
        home_team = payload.get("home_team")
        if not home_team:
            queue.task_done(); continue

        # 2. Map to Kalshi Ticker (Fuzzy Match)
        market_entry = mapper.find_market(home_team)
        if not market_entry:
            queue.task_done(); continue

        ticker = market_entry.ticker

        # 3. Analyze Bookmakers
        bookmakers = payload.get("bookmakers", [])
        for bookie in bookmakers:
            if bookie["key"] not in TARGET_BOOKS: continue
            
            for market in bookie.get("markets", []):
                if market["key"] != "h2h": continue # Only doing Moneyline for now
                
                for outcome in market["outcomes"]:
                    if outcome["name"] == home_team:
                        
                        # A. Calculate "True" Probability (Sportsbook)
                        sb_odds = outcome["price"]
                        true_prob = implied_prob(sb_odds)

                        # B. Get Live Kalshi Price (Network Call)
                        k_price_cents = await get_kalshi_ask(state.session, ticker)
                        if not k_price_cents: continue
                        
                        k_prob = k_price_cents / 100.0

                        # C. Calculate Edge (Sniper Logic)
                        # Example: Sportsbook says 60% (0.60), Kalshi sells for 50 cents (0.50)
                        # Edge = 0.10 (10%)
                        edge = true_prob - k_prob
                        
                        if edge >= MIN_EDGE:
                            # D. EXECUTE SNIPE
                            # Calculate max contracts based on $2 limit
                            # price is in cents (e.g. 50), Max Risk is dollars (2.00)
                            
                            price_dollars = k_price_cents / 100.0
                            count = int(MAX_RISK_PER_TRADE / price_dollars)
                            
                            if count > 0:
                                # Log the signal
                                state.log(f"⚡ SIGNAL: {ticker} | Edge: {edge:.2%} | SB: {true_prob:.2f} vs K: {k_prob:.2f}")
                                
                                # FIRE!
                                asyncio.create_task(
                                    execute_snipe(state.session, ticker, "yes", count, k_price_cents, state)
                                )
                                
                                # Add to Dashboard
                                state.opportunities.append({
                                    "market": ticker,
                                    "edge": edge,
                                    "hedge": 0.0 # Naked Snipe
                                })

        queue.task_done()

# --- 🖥️ DASHBOARD ---
def build_dashboard(state: BotState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=8),
        Layout(name="bottom"),
    )
    layout["top"].split_row(Layout(name="opps"), Layout(name="bankroll", size=30))

    opps_table = Table(title="Live Sniper Signals", box=box.SIMPLE)
    opps_table.add_column("Market", style="cyan")
    opps_table.add_column("Edge", style="green")
    opps_table.add_column("Status")
    
    # Show last 5 opps
    for opp in state.opportunities[-5:]:
        opps_table.add_row(
            opp.get("market", "-"),
            f"{opp.get('edge', 0):.2%}",
            "FIRED 🔫",
        )

    bankroll_panel = Panel(
        f"${state.bankroll:,.2f}\nRisk/Trade: ${MAX_RISK_PER_TRADE:,.2f}",
        title="Ashburn Sniper 🎯",
        box=box.ROUNDED,
        style="bold white on blue"
    )

    logs_table = Table(title="Execution Logs", box=box.SIMPLE)
    logs_table.add_column("Message")
    for line in state.logs[-10:]:
        logs_table.add_row(line)

    layout["opps"].update(opps_table)
    layout["bankroll"].update(bankroll_panel)
    layout["bottom"].update(logs_table)
    return layout

async def dashboard_loop(state: BotState) -> None:
    with Live(build_dashboard(state), console=console, refresh_per_second=4) as live:
        while True:
            live.update(build_dashboard(state))
            await asyncio.sleep(0.25)

async def process_kalshi_feed(state: BotState) -> None:
    """Monitors Kalshi Fill messages (Confirmations)."""
    async for message in kalshi_ws_stream(state.session):
        if message.get("type") == "fill":
            state.log(f"💰 FILL CONFIRMED: {message.get('ticker')}")
        await asyncio.sleep(0)

# --- 🚀 ENTRY POINT ---
async def main() -> None:
    mapper = MarketMapper()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    state = BotState()

    # Optimized Connector for High Frequency
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. Warmup: Load Mappings
        state.log("🗺️ Loading Market Mappings...")
        await mapper.preload(session)
        state.session = session # Bind session to state
        state.log(f"✅ Mappings Loaded. Connecting to Feeds ({API.kalshi_rest_base})...")

        tasks = [
            asyncio.create_task(odds_ws_feed(session, queue)),        # Listen to Sportsbooks
            asyncio.create_task(process_odds_feed(state, queue, mapper)), # Calculate & Snipe
            asyncio.create_task(dashboard_loop(state)),               # UI
            asyncio.create_task(process_kalshi_feed(state)),          # Listen for Fills
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks: task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    import uvloop
    uvloop.install() # Linux Optimization
    asyncio.run(main())
