"""CLI entry for portfolio overview."""

from __future__ import annotations

import argparse
import pathlib
import sys

from portfolio_overview import __version__
from portfolio_overview.display import format_overview
from portfolio_overview.loader import load_holdings
from portfolio_overview.prices import enrich_holdings, fetch_eurusd, fetch_prices


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="portfolio-overview",
        description=(
            "Terminal overview of share holdings: live prices (native + EUR via "
            "EURUSD), market values in EUR, daily change %, and portfolio weights."
        ),
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    p.add_argument(
        "--profile",
        type=pathlib.Path,
        default=None,
        help=(
            "Path to profile JSON (default: "
            "~/.grokbuild/skills/my-finance-profile/profile.json "
            "or $PORTFOLIO_PROFILE_PATH)"
        ),
    )
    p.add_argument(
        "--sample",
        action="store_true",
        help="Use bundled samples/sample_profile.json (demo, no personal data)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        holdings, path = load_holdings(
            profile_path=args.profile,
            use_sample=args.sample,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not holdings:
        print(
            "No holdings with a valid quantity found.\n"
            f"Source: {path}\n"
            "Add shares via my-finance-profile add-holding, or use --sample.",
            file=sys.stderr,
        )
        return 1

    tickers = [h["ticker"] for h in holdings]
    try:
        eurusd = fetch_eurusd()
        prices = fetch_prices(tickers)
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    rows = enrich_holdings(holdings, prices, eurusd)
    if not rows:
        print(
            "Could not price any holdings. Check tickers / network / yfinance.",
            file=sys.stderr,
        )
        return 1

    print(format_overview(rows, source=str(path), eurusd=eurusd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
