"""Tests for profile loading (no network)."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portfolio_overview.loader import (  # noqa: E402
    extract_holdings,
    load_holdings,
    load_profile,
    sample_profile_path,
)


class TestLoader(unittest.TestCase):
    def test_sample_profile_exists(self) -> None:
        path = sample_profile_path()
        self.assertTrue(path.exists(), f"missing {path}")
        profile = load_profile(path)
        self.assertIn("holdings", profile)

    def test_load_sample_holdings(self) -> None:
        holdings, path = load_holdings(use_sample=True)
        self.assertTrue(path.exists())
        self.assertGreaterEqual(len(holdings), 1)
        for h in holdings:
            self.assertIn("ticker", h)
            self.assertIn("shares", h)
            self.assertGreater(h["shares"], 0)

    def test_skip_missing_shares(self) -> None:
        profile = {
            "holdings": [
                {"ticker": "AAPL", "shares": 10},
                {"ticker": "MSFT"},  # no shares
                {"ticker": "BAD", "shares": 0},
            ]
        }
        usable = extract_holdings(profile)
        self.assertEqual(len(usable), 1)
        self.assertEqual(usable[0]["ticker"], "AAPL")

    def test_quantity_alias(self) -> None:
        profile = {"holdings": [{"ticker": "pg", "quantity": 3}]}
        usable = extract_holdings(profile)
        self.assertEqual(usable[0]["ticker"], "PG")
        self.assertEqual(usable[0]["shares"], 3.0)

    def test_custom_profile_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "p.json"
            path.write_text(
                json.dumps(
                    {
                        "holdings": [
                            {"ticker": "XOM", "shares": 2.5},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            holdings, used = load_holdings(profile_path=path)
            self.assertEqual(used, path)
            self.assertEqual(holdings[0]["ticker"], "XOM")
            self.assertEqual(holdings[0]["shares"], 2.5)


if __name__ == "__main__":
    unittest.main()
