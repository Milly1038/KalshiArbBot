"""Entry point for the high-frequency sniper bot."""
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

from config import BANKROLL, EV_THRESHOLD, KELLY_MULTIPLIER
from gather_data import odds_ws_feed
from kalshi_data import kalshi_ws_stream, place_limit_order
from mapping import MarketMapper
from math_engine import devig_two_way, kelly_bet_size

console = Console()


@dataclass
class BotState:
    bankroll: float = BANKROLL
    signals: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    kalshi_prices: dict[str, int] = field(default_factory=dict)

    def log(self, message: str) -> None:
        self.logs.append(message)
        self.logs[:] = self.logs[-10:]


def build_dashboard(state: BotState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=10),
        Layout(name="bottom"),
    )
    layout["top"].split_row(Layout(name="signals"), Layout(name="bankroll", size=30))

    signals_table = Table(title="Live EV Signals", box=box.SIMPLE)
    signals_table.add_column("Market")
    signals_table.add_column("Edge")
    signals_table.add_column("Bet")
    for signal in state.signals[-5:]:
        signals_table.add_row(
            signal.get("market", "-"),
            f"{signal.get('edge', 0):.2%}",
            f"${signal.get('size', 0):.2f}",
        )

    bankroll_panel = Panel(
        f"${state.bankroll:,.2f}\nKelly x {KELLY_MULTIPLIER:.2f}",
        title="Bankroll",
        box=box.ROUNDED,
    )

    logs_table = Table(title="Sniper Log", box=box.SIMPLE)
    logs_table.add_column("Message")
    for line in state.logs[-10:]:
        logs_table.add_row(line)

    layout["signals"].update(signals_table)
    layout["bankroll"].update(bankroll_panel)
    layout["bottom"].update(logs_table)
    return layout


async def process_kalshi_feed(state: BotState) -> None:
    async for message in kalshi_ws_stream(state.session):  # type: ignore[attr-defined]
        if message.get("type") == "price":
            ticker = message.get("ticker")
            price = message.get("price")
            if ticker and price is not None:
                state.kalshi_prices[ticker] = int(price)
        state.log(f"Kalshi update: {message.get('type', 'unknown')}")
        await asyncio.sleep(0)


async def process_odds_feed(
    state: BotState, mapper: MarketMapper, queue: asyncio.Queue[dict[str, Any]]
) -> None:
    while True:
        payload = await queue.get()
        team_a = payload.get("team_a")
        team_b = payload.get("team_b")
        odds_a = payload.get("odds_a")
        odds_b = payload.get("odds_b")
        if not all([team_a, team_b, odds_a, odds_b]):
            queue.task_done()
            continue

        fair_a, _ = devig_two_way(int(odds_a), int(odds_b))
        market = mapper.find_market(team_a)
        if not market:
            state.log(f"No Kalshi market for {team_a}")
            queue.task_done()
            continue

        kalshi_price = state.kalshi_prices.get(market.ticker)
        if kalshi_price is None:
            queue.task_done()
            continue

        kalshi_prob = kalshi_price / 100
        edge = fair_a - kalshi_prob
        if edge >= EV_THRESHOLD:
            payout = (1 - kalshi_prob) / kalshi_prob if kalshi_prob > 0 else 0
            size = kelly_bet_size(state.bankroll, edge, payout, KELLY_MULTIPLIER)
            if size > 0:
                contracts = int(size)
                await place_limit_order(
                    state.session, market.ticker, "buy", int(kalshi_price), contracts
                )
                state.bankroll -= contracts
                state.signals.append(
                    {"market": market.ticker, "edge": edge, "size": size}
                )
                state.log(
                    f"Sniped {market.ticker} @ {kalshi_price} for {contracts}"
                )

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
            asyncio.create_task(process_odds_feed(state, mapper, queue)),
            asyncio.create_task(dashboard_loop(state)),
            asyncio.create_task(process_kalshi_feed(state)),
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
