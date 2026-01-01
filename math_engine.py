"""Probability and sizing math for the sniper bot."""
from __future__ import annotations


def american_to_implied_prob(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def devig_two_way(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Remove vig from a two-outcome market using proportional normalization."""
    p_a = american_to_implied_prob(odds_a)
    p_b = american_to_implied_prob(odds_b)
    total = p_a + p_b
    if total == 0:
        return 0.0, 0.0
    return p_a / total, p_b / total


def kelly_fraction(edge: float, payout: float) -> float:
    """Return Kelly fraction based on edge and payout ratio (b)."""
    if payout <= 0:
        return 0.0
    return max(0.0, edge / payout)


def kelly_bet_size(bankroll: float, edge: float, payout: float, multiplier: float) -> float:
    fraction = kelly_fraction(edge, payout)
    return max(0.0, bankroll * fraction * multiplier)
