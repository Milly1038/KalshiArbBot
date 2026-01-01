"""Entry point for the high-frequency arbitrage bot."""
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from config import BANKROLL, MAX_RISK_PER_TRADE, MIN_EDGE
from gather_data import odds_ws_feed
from kalshi_data import kalshi_ws_stream
from mapping import MarketMapper

console = Console()


@dataclass
class BotState:
    bankroll: float = BANKROLL
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)
        self.logs[:] = self.logs[-10:]


def american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1 + (odds / 100)
    return 1 + (100 / abs(odds))


def hedge_size(kalshi_contracts: float, sportsbook_american_odds: int) -> float:
    decimal_odds = american_to_decimal(sportsbook_american_odds)
    return (kalshi_contracts * 1.0) / decimal_odds


def build_dashboard(state: BotState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=8),
        Layout(name="bottom"),
    )
    layout["top"].split_row(Layout(name="opps"), Layout(name="bankroll", size=30))

    opps_table = Table(title="Live Opportunities", box=box.SIMPLE)
    opps_table.add_column("Market")
    opps_table.add_column("Edge")
    opps_table.add_column("Hedge")
    for opp in state.opportunities[-5:]:
        opps_table.add_row(
            opp.get("market", "-"),
            f"{opp.get('edge', 0):.2%}",
            f"{opp.get('hedge', 0):.2f}",
        )

    bankroll_panel = Panel(
        f"${state.bankroll:,.2f}\nMax Risk: ${MAX_RISK_PER_TRADE:,.2f}",
        title="Bankroll",
        box=box.ROUNDED,
    )

    logs_table = Table(title="Logs", box=box.SIMPLE)
    logs_table.add_column("Message")
    for line in state.logs[-10:]:
        logs_table.add_row(line)

    layout["opps"].update(opps_table)
    layout["bankroll"].update(bankroll_panel)
    layout["bottom"].update(logs_table)
    return layout


async def process_kalshi_feed(state: BotState, mapper: MarketMapper) -> None:
    async for message in kalshi_ws_stream(state.session):  # type: ignore[attr-defined]
        state.log(f"Kalshi update: {message.get('type', 'unknown')}")
        await asyncio.sleep(0)


async def process_odds_feed(state: BotState, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        payload = await queue.get()
        market = payload.get("market", "unknown")
        odds = int(payload.get("odds", 100))
        kalshi_contracts = float(payload.get("kalshi_contracts", 1))
        hedge = hedge_size(kalshi_contracts, odds)
        edge = float(payload.get("edge", 0.0))
        if edge >= MIN_EDGE:
            state.opportunities.append(
                {"market": market, "edge": edge, "hedge": hedge}
            )
            state.log(f"Opportunity: {market} edge {edge:.2%}")
        queue.task_done()


async def dashboard_loop(state: BotState) -> None:
    with Live(build_dashboard(state), console=console, refresh_per_second=4) as live:
        while True:
            live.update(build_dashboard(state))
            await asyncio.sleep(0.25)


async def main() -> None:
    mapper = MarketMapper()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    state = BotState()

    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        await mapper.preload(session)
        state.session = session  # type: ignore[attr-defined]
        state.log("Loaded Kalshi markets into RAM")

        tasks = [
            asyncio.create_task(odds_ws_feed(session, queue)),
            asyncio.create_task(process_odds_feed(state, queue)),
            asyncio.create_task(dashboard_loop(state)),
            asyncio.create_task(process_kalshi_feed(state, mapper)),
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass

    asyncio.run(main())
