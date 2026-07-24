"""Tests for table formatting (no network)."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portfolio_overview.display import compute_weights, format_overview  # noqa: E402


class TestDisplay(unittest.TestCase):
    def test_weights_sum_to_100(self) -> None:
        rows = [
            {"ticker": "A", "shares": 1, "price": 50.0, "market_value": 50.0},
            {"ticker": "B", "shares": 1, "price": 150.0, "market_value": 150.0},
        ]
        weighted = compute_weights(rows)
        total_w = sum(r["weight_pct"] for r in weighted)
        self.assertAlmostEqual(total_w, 100.0, places=6)
        self.assertAlmostEqual(weighted[0]["weight_pct"], 25.0, places=6)
        self.assertAlmostEqual(weighted[1]["weight_pct"], 75.0, places=6)

    def test_format_contains_total_and_columns(self) -> None:
        rows = [
            {
                "ticker": "AAPL",
                "shares": 10,
                "price": 100.0,
                "market_value": 1000.0,
                "day_change_pct": 1.5,
            },
            {
                "ticker": "PG",
                "shares": 5,
                "price": 50.0,
                "market_value": 250.0,
                "day_change_pct": -0.5,
            },
        ]
        text = format_overview(rows, source="test.json")
        self.assertIn("Ticker", text)
        self.assertIn("AAPL", text)
        self.assertIn("PG", text)
        self.assertIn("TOTAL", text)
        self.assertIn("1,250.00", text)
        self.assertIn("Source: test.json", text)
        self.assertIn("+1.50", text)

    def test_empty(self) -> None:
        text = format_overview([])
        self.assertIn("No holdings", text)


if __name__ == "__main__":
    unittest.main()
