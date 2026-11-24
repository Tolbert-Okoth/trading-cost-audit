"""costaudit: rebuild gross edge from fills, stress it under cost scenarios, and watch live spread drift."""
from .core import breakeven_cost, cost_grid, gross_from_fills, speed_limit, spread_drift

__all__ = ["gross_from_fills", "cost_grid", "breakeven_cost", "speed_limit", "spread_drift"]
__version__ = "0.1.0"
