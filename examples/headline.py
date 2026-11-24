"""Reproduce the README figures (synthetic data only). Run: python examples/headline.py  (needs matplotlib)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import costaudit as ca

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"); os.makedirs(DOCS, exist_ok=True)
rng = np.random.default_rng(7)

# --- a synthetic fill ledger: 2,000 trades, small gross edge, realistic-looking costs -------------------------------
n = 2000
side = rng.choice([1, -1], n); risk = rng.uniform(2.0, 6.0, n)
mid_in = 100 + rng.normal(0, 5, n); move = rng.normal(0.15, 1.2, n) * risk                    # gross edge 0.15 R/trade
sp_in, sp_out = rng.lognormal(np.log(0.25), 0.3, n), rng.lognormal(np.log(0.25), 0.3, n)
trades = pd.DataFrame(dict(side=side, risk=risk, spread_entry=sp_in, spread_exit=sp_out,
                           entry_fill=mid_in + side * sp_in / 2, exit_fill=mid_in + side * move - side * sp_out / 2,
                           commission=np.full(n, 0.07), swap=np.where(rng.random(n) < 0.3, rng.uniform(0, 0.3, n), 0.0)))
g = ca.gross_from_fills(trades)
m = g.mean()
print(f"gross {m.gross_R:+.3f} R/tr | spread {m.spread_R:.3f} | commission {m.commission_R:.3f} | swap {m.swap_R:.3f} | net {m.net_R:+.3f} "
      f"| cost share {m.cost_R / m.gross_R:.0%}")
be = ca.breakeven_cost(g.gross_R, trades.risk); print(f"breakeven round-trip cost {be:.3f} price units")
sl = ca.speed_limit(g.gross_R, g.cost_R, trades_per_year=250); print("speed limit:", {k: round(v, 3) if isinstance(v, float) else v for k, v in sl.items()})

# 1) waterfall
fig, ax = plt.subplots(figsize=(7, 4))
steps = [("gross\n(mid-to-mid)", m.gross_R), ("spread", -m.spread_R), ("commission", -m.commission_R), ("swap", -m.swap_R)]
level = 0.0
for i, (lab, v) in enumerate(steps):
    base = 0.0 if i == 0 else level
    ax.bar(i, v, bottom=base, color="#2b8a3e" if v > 0 else "#d9480f"); level = base + v
    ax.text(i, base + v + (0.004 if v > 0 else -0.004), f"{v:+.3f}", ha="center", va="bottom" if v > 0 else "top", fontsize=9)
ax.bar(len(steps), level, color="#1c7ed6"); ax.text(len(steps), level + 0.004, f"{level:+.3f}", ha="center", va="bottom", fontsize=9)
ax.set_xticks(range(len(steps) + 1), [s[0] for s in steps] + ["net"]); ax.axhline(0, color="#333", lw=0.8)
ax.set_ylim(0, m.gross_R * 1.15); ax.set_ylabel("mean R per trade"); ax.set_title(f"Where the edge goes: costs take {m.cost_R / m.gross_R:.0%} of gross"); ax.grid(axis="y", alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(DOCS, "cost_waterfall.png"), dpi=130); plt.close(fig)

# 2) cost grid
spreads = np.linspace(0, 1.0, 41); grid = ca.cost_grid(g.gross_R, trades.risk, spreads, commissions=(0.0, 0.07, 0.14))
fig, ax = plt.subplots(figsize=(7, 4))
for c in grid.columns:
    ax.plot(grid.index, grid[c], label=f"commission {c:.2f}")
ax.axhline(0, color="#333", lw=0.8); ax.axvline(np.mean(sp_in + sp_out) / 2, color="#888", ls=":", label="spread actually paid")
ax.set_xlabel("round-trip spread (price units)"); ax.set_ylabel("mean net R per trade"); ax.grid(alpha=.3); ax.legend(fontsize=8)
ax.set_title(f"Cost stress: the edge survives up to ~{be:.2f} price units of round-trip cost")
fig.tight_layout(); fig.savefig(os.path.join(DOCS, "cost_grid.png"), dpi=130); plt.close(fig)

# 3) spread drift monitor
idx = pd.date_range("2025-01-01", periods=24 * 90, freq="h")
level = np.where(idx < "2025-02-15", 0.25, 0.34)                                               # spread regime change mid-way
obs = pd.Series(level * rng.lognormal(0, 0.25, len(idx)), index=idx)
d = ca.spread_drift(obs, baseline=0.25, window="5D", watch_mult=1.2, gross_R_per_trade=0.15, risk=4.0)
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(d.index, d.spread, color="#ced4da", lw=0.5, label="observed spread")
ax.plot(d.index, d.rolling_median, color="#1c7ed6", lw=2, label="5-day rolling median")
ax.axhline(0.25, color="#2b8a3e", ls="--", label="research baseline"); ax.axhline(0.30, color="#d9480f", ls=":", label="WATCH (+20 %)")
first = d.index[d.status.eq("WATCH")][0]; ax.axvline(first, color="#d9480f", alpha=.4)
ax.set_ylim(0, 0.8); ax.set_ylabel("spread (price units)"); ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=.3)
ax.set_title(f"Spread drift monitor: WATCH from {first:%d %b}, implied net edge change {d.edge_change.iloc[-1]:+.0%}")
fig.tight_layout(); fig.savefig(os.path.join(DOCS, "spread_drift.png"), dpi=130); plt.close(fig)
print(f"drift: first WATCH {first:%Y-%m-%d}, final edge change {d.edge_change.iloc[-1]:+.1%}")
