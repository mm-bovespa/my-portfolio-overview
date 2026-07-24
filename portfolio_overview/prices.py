"""Fetch current prices via yfinance."""

from __future__ import annotations

import sys
from typing import Any


def fetch_prices(tickers: list[str]) -> dict[str, dict[str, float | None]]:
    """Fetch last price and daily change % for each ticker.

    Returns mapping:
      ticker -> {"price": float|None, "day_change_pct": float|None}

    Missing/failed symbols get None values and a stderr warning.
    """
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required. Install with: pip install -r requirements.txt"
        ) from exc

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tickers:
        u = t.upper()
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    result: dict[str, dict[str, float | None]] = {
        t: {"price": None, "day_change_pct": None} for t in ordered
    }

    # Prefer batch download of recent history for price + previous close
    try:
        data = yf.download(
            tickers=ordered,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as exc:
        print(f"Error: yfinance download failed: {exc}", file=sys.stderr)
        # Fall back to per-ticker
        data = None

    if data is not None and not data.empty:
        if len(ordered) == 1:
            # Single ticker: columns are simple OHLCV
            t = ordered[0]
            try:
                closes = data["Close"].dropna()
                if len(closes) >= 1:
                    last = float(closes.iloc[-1])
                    result[t]["price"] = last
                    if len(closes) >= 2:
                        prev = float(closes.iloc[-2])
                        if prev:
                            result[t]["day_change_pct"] = (last - prev) / prev * 100.0
            except Exception as exc:
                print(f"Warning: could not parse {t}: {exc}", file=sys.stderr)
        else:
            for t in ordered:
                try:
                    if t not in data.columns.get_level_values(0):
                        # try alternate layout
                        continue
                    sub = data[t]
                    closes = sub["Close"].dropna()
                    if len(closes) < 1:
                        continue
                    last = float(closes.iloc[-1])
                    result[t]["price"] = last
                    if len(closes) >= 2:
                        prev = float(closes.iloc[-2])
                        if prev:
                            result[t]["day_change_pct"] = (last - prev) / prev * 100.0
                except Exception as exc:
                    print(f"Warning: could not parse {t}: {exc}", file=sys.stderr)

    # Fill gaps with Ticker.fast_info / info as fallback
    for t in ordered:
        if result[t]["price"] is not None:
            continue
        try:
            tk = yf.Ticker(t)
            price = None
            day_pct = None
            # fast_info is lighter when available
            try:
                fi = tk.fast_info
                price = getattr(fi, "last_price", None) or getattr(
                    fi, "lastPrice", None
                )
                prev = getattr(fi, "previous_close", None) or getattr(
                    fi, "previousClose", None
                )
                if price is not None:
                    price = float(price)
                if price is not None and prev not in (None, 0):
                    day_pct = (price - float(prev)) / float(prev) * 100.0
            except Exception:
                hist = tk.history(period="5d")
                if hist is not None and not hist.empty:
                    closes = hist["Close"].dropna()
                    if len(closes) >= 1:
                        price = float(closes.iloc[-1])
                        if len(closes) >= 2:
                            prev = float(closes.iloc[-2])
                            if prev:
                                day_pct = (price - prev) / prev * 100.0
            result[t]["price"] = price
            result[t]["day_change_pct"] = day_pct
            if price is None:
                print(f"Warning: no price for {t}", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: failed to fetch {t}: {exc}", file=sys.stderr)

    return result


def enrich_holdings(
    holdings: list[dict[str, Any]],
    prices: dict[str, dict[str, float | None]],
) -> list[dict[str, Any]]:
    """Attach price, market_value, day_change_pct to each holding; drop unpriced."""
    rows: list[dict[str, Any]] = []
    for h in holdings:
        t = h["ticker"]
        info = prices.get(t) or {}
        price = info.get("price")
        if price is None:
            print(f"Warning: excluding {t} (no price)", file=sys.stderr)
            continue
        shares = float(h["shares"])
        market_value = shares * float(price)
        rows.append(
            {
                "ticker": t,
                "shares": shares,
                "price": float(price),
                "market_value": market_value,
                "day_change_pct": info.get("day_change_pct"),
            }
        )
    return rows
