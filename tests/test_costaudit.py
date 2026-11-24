import unittest

import numpy as np
import pandas as pd

import costaudit as ca


def ledger():
    # one long, one short; mid moves +2 and -3 respectively; spread 0.2 at both ends; risk 1
    return pd.DataFrame(dict(side=[1, -1], entry_fill=[100.1, 99.9], exit_fill=[101.9, 97.1], spread_entry=[0.2, 0.2],
                             spread_exit=[0.2, 0.2], risk=[1.0, 1.0], commission=[0.05, 0.05]))


class Gross(unittest.TestCase):
    def test_mid_to_mid_rebuild(self):
        g = ca.gross_from_fills(ledger())
        self.assertTrue(np.allclose(g["gross_R"], [2.0, 3.0]))
        self.assertTrue(np.allclose(g["spread_R"], [0.2, 0.2]))
        self.assertTrue(np.allclose(g["net_R"], [2.0 - 0.25, 3.0 - 0.25]))

    def test_net_equals_fill_pnl_minus_commission(self):
        t = ledger(); g = ca.gross_from_fills(t)
        fill_pnl = t["side"] * (t["exit_fill"] - t["entry_fill"]) / t["risk"]
        self.assertTrue(np.allclose(g["net_R"], fill_pnl - t["commission"]))

    def test_missing_column(self):
        with self.assertRaises(KeyError):
            ca.gross_from_fills(ledger().drop(columns="risk"))


class Stress(unittest.TestCase):
    def test_breakeven_zeroes_mean(self):
        rng = np.random.default_rng(0); g = rng.normal(0.1, 1, 500); r = rng.uniform(1, 3, 500)
        be = ca.breakeven_cost(g, r); self.assertAlmostEqual(float(np.mean(g - be / r)), 0.0, places=9)

    def test_cost_grid_monotone(self):
        grid = ca.cost_grid([0.2] * 10, [1.0] * 10, spreads=[0.0, 0.1, 0.2], commissions=[0.0, 0.05])
        self.assertAlmostEqual(grid.loc[0.2, 0.0], 0.0); self.assertTrue((grid.diff().dropna() < 0).all().all())

    def test_speed_limit(self):
        rng = np.random.default_rng(1); g = rng.normal(0, 1, 1000); g = g - g.mean() + 0.2
        self.assertTrue(ca.speed_limit(g, np.full(1000, 0.05), 100)["passes"])
        self.assertFalse(ca.speed_limit(g, np.full(1000, 0.10), 100)["passes"])


class Drift(unittest.TestCase):
    def test_watch_flag_and_edge(self):
        idx = pd.date_range("2024-01-01", periods=20, freq="D")
        s = pd.Series([0.2] * 10 + [0.3] * 10, index=idx)
        d = ca.spread_drift(s, baseline=0.2, window="3D", gross_R_per_trade=0.3, risk=1.0)
        self.assertEqual(d["status"].iloc[0], "OK"); self.assertEqual(d["status"].iloc[-1], "WATCH")
        self.assertAlmostEqual(d["edge_change"].iloc[-1], -1.0)


if __name__ == "__main__":
    unittest.main()
