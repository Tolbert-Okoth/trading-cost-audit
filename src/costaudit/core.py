"""Trading cost audit: rebuild gross edge from fills, stress it under cost scenarios, and watch live spreads.

Conventions
-----------
side      +1 long, -1 short
prices    fill prices as executed (longs buy the ask, sell the bid)
spread    quoted spread at the fill, in price units
risk      the trade's 1R distance in price units (e.g. stop distance); results are expressed in R
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADE_COLUMNS = ("side", "entry_fill", "exit_fill", "spread_entry", "spread_exit", "risk")


def gross_from_fills(trades: pd.DataFrame, commission_col: str | None = "commission", swap_col: str | None = "swap") -> pd.DataFrame:
    """Rebuild mid-to-mid gross R and itemised costs from a fill-based ledger.

    entry_mid = entry_fill - side * spread_entry / 2 ;  exit_mid = exit_fill + side * spread_exit / 2
    gross_R   = side * (exit_mid - entry_mid) / risk
    spread_R  = (spread_entry + spread_exit) / 2 / risk
    commission/swap columns (optional) are in price units per unit size, positive = cost.
    """
    missing = [c for c in TRADE_COLUMNS if c not in trades]
    if missing:
        raise KeyError(f"missing columns: {missing}")
    t = trades
    s = t["side"].to_numpy(float)
    entry_mid = t["entry_fill"] - s * t["spread_entry"] / 2
    exit_mid = t["exit_fill"] + s * t["spread_exit"] / 2
    out = pd.DataFrame(index=t.index)
    out["gross_R"] = s * (exit_mid - entry_mid) / t["risk"]
    out["spread_R"] = (t["spread_entry"] + t["spread_exit"]) / 2 / t["risk"]
    out["commission_R"] = t[commission_col] / t["risk"] if commission_col and commission_col in t else 0.0
    out["swap_R"] = t[swap_col] / t["risk"] if swap_col and swap_col in t else 0.0
    out["cost_R"] = out[["spread_R", "commission_R", "swap_R"]].sum(axis=1)
    out["net_R"] = out["gross_R"] - out["cost_R"]
    return out


def cost_grid(gross_R, risk, spreads, commissions=(0.0,)) -> pd.DataFrame:
    """Mean net R per trade if every trade paid `spread + commission` (price units, round trip) instead of its actual cost."""
    g, r = np.asarray(gross_R, float), np.asarray(risk, float)
    rows = {c: [float(np.mean(g - (s + c) / r)) for s in spreads] for c in commissions}
    return pd.DataFrame(rows, index=pd.Index(spreads, name="spread")).rename_axis(columns="commission")


def breakeven_cost(gross_R, risk) -> float:
    """Round-trip cost (price units, same for every trade) at which mean net R is zero."""
    g, r = np.asarray(gross_R, float), np.asarray(risk, float)
    return float(np.mean(g) / np.mean(1.0 / r))


def speed_limit(gross_R, cost_R, trades_per_year: float, limit: float = 1 / 3) -> dict:
    """Carver's speed limit: annual cost Sharpe should be <= `limit` x annual gross Sharpe.

    Both Sharpes use the gross per-trade standard deviation, so the test is size-free."""
    g, c = np.asarray(gross_R, float), np.asarray(cost_R, float)
    sd = g.std(ddof=1); k = np.sqrt(trades_per_year)
    gross_sr, cost_sr = g.mean() / sd * k, c.mean() / sd * k
    ratio = cost_sr / gross_sr if gross_sr > 0 else np.inf
    return dict(gross_sr=float(gross_sr), cost_sr=float(cost_sr), cost_share=float(c.mean() / g.mean()) if g.mean() > 0 else np.inf,
                ratio=float(ratio), passes=bool(0 <= ratio <= limit))


def spread_drift(spreads: pd.Series, baseline: float, window: str = "5D", watch_mult: float = 1.2,
                 gross_R_per_trade: float | None = None, risk: float | None = None) -> pd.DataFrame:
    """Rolling median of observed spreads vs the spread your research assumed.

    status = WATCH when the rolling median exceeds baseline x watch_mult. If gross_R_per_trade and risk are given,
    `edge_change` is the % change in net R/trade implied by the drift (round-trip spread paid once per trade)."""
    s = spreads.sort_index()
    med = s.rolling(window).median()
    out = pd.DataFrame({"spread": s, "rolling_median": med, "baseline": baseline})
    out["status"] = np.where(med > baseline * watch_mult, "WATCH", "OK")
    if gross_R_per_trade is not None and risk:
        net_base = gross_R_per_trade - baseline / risk
        out["edge_change"] = ((gross_R_per_trade - med / risk) - net_base) / abs(net_base)
    return out
