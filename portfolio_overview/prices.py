"""Fetch current prices via yfinance + EURUSD FX conversion."""

from __future__ import annotations

import sys
from typing import Any

# Yahoo suffixes commonly quoted in EUR
_EUR_SUFFIXES = (
    ".DE",
    ".PA",
    ".AS",
    ".BR",
    ".MI",
    ".MC",
    ".LS",
    ".F",
    ".XETRA",
    ".VI",
    ".HE",
    ".ST",
    ".OL",
    ".CO",
)


def fetch_eurusd() -> float:
    """Return EURUSD (USD per 1 EUR). Raises on failure."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required. Install with: pip install -r requirements.txt"
        ) from exc

    # Prefer EURUSD=X; fall back to EUR=X
    for symbol in ("EURUSD=X", "EUR=X"):
        try:
            t = yf.Ticker(symbol)
            price = None
            try:
                fi = t.fast_info
                price = getattr(fi, "last_price", None) or getattr(
                    fi, "lastPrice", None
                )
            except Exception:
                price = None
            if price is None:
                hist = t.history(period="5d")
                if hist is not None and not hist.empty:
                    price = float(hist["Close"].dropna().iloc[-1])
            if price is not None and float(price) > 0:
                return float(price)
        except Exception as exc:
            print(f"Warning: FX fetch {symbol} failed: {exc}", file=sys.stderr)

    raise RuntimeError("Could not fetch EURUSD rate from yfinance")


def infer_currency(ticker: str, yf_currency: str | None = None) -> str:
    """Best-effort quote currency: EUR or USD (default USD)."""
    if yf_currency:
        c = yf_currency.strip().upper()
        if c in ("EUR", "USD", "GBP", "CHF", "CAD", "JPY"):
            return c
    u = ticker.upper()
    for suf in _EUR_SUFFIXES:
        if u.endswith(suf):
            return "EUR"
    return "USD"


def to_eur(amount: float, currency: str, eurusd: float) -> float:
    """Convert amount in `currency` to EUR using EURUSD (USD per 1 EUR)."""
    c = currency.upper()
    if c == "EUR":
        return amount
    if c == "USD":
        return amount / eurusd
    # Rough fallbacks via USD if ever needed
    if c == "GBP":
        # without GBPUSD, leave as-is with warning path — treat unknown as USD-like
        print(
            f"Warning: no dedicated FX for {c}; treating amount as USD for EUR convert",
            file=sys.stderr,
        )
        return amount / eurusd
    print(
        f"Warning: unsupported currency {c}; treating as USD",
        file=sys.stderr,
    )
    return amount / eurusd


def to_usd(amount: float, currency: str, eurusd: float) -> float:
    """Convert amount in `currency` to USD."""
    c = currency.upper()
    if c == "USD":
        return amount
    if c == "EUR":
        return amount * eurusd
    return amount


def fetch_prices(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch last price, currency, and daily change % for each ticker.

    Returns mapping:
      ticker -> {"price": float|None, "currency": str|None, "day_change_pct": float|None}
    """
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required. Install with: pip install -r requirements.txt"
        ) from exc

    seen: set[str] = set()
    ordered: list[str] = []
    for t in tickers:
        u = t.upper()
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    result: dict[str, dict[str, Any]] = {
        t: {"price": None, "currency": None, "day_change_pct": None} for t in ordered
    }

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
        data = None

    if data is not None and not data.empty:
        if len(ordered) == 1:
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

    # Fill gaps + currency via Ticker
    for t in ordered:
        try:
            tk = yf.Ticker(t)
            yf_cur = None
            try:
                fi = tk.fast_info
                yf_cur = getattr(fi, "currency", None)
                if result[t]["price"] is None:
                    price = getattr(fi, "last_price", None) or getattr(
                        fi, "lastPrice", None
                    )
                    prev = getattr(fi, "previous_close", None) or getattr(
                        fi, "previousClose", None
                    )
                    if price is not None:
                        result[t]["price"] = float(price)
                        if prev not in (None, 0):
                            result[t]["day_change_pct"] = (
                                (float(price) - float(prev)) / float(prev) * 100.0
                            )
            except Exception:
                pass

            if result[t]["price"] is None:
                hist = tk.history(period="5d")
                if hist is not None and not hist.empty:
                    closes = hist["Close"].dropna()
                    if len(closes) >= 1:
                        price = float(closes.iloc[-1])
                        result[t]["price"] = price
                        if len(closes) >= 2:
                            prev = float(closes.iloc[-2])
                            if prev:
                                result[t]["day_change_pct"] = (
                                    (price - prev) / prev * 100.0
                                )

            if yf_cur is None:
                try:
                    info = tk.info or {}
                    yf_cur = info.get("currency")
                except Exception:
                    yf_cur = None

            result[t]["currency"] = infer_currency(t, yf_cur)
            if result[t]["price"] is None:
                print(f"Warning: no price for {t}", file=sys.stderr)
        except Exception as exc:
            result[t]["currency"] = infer_currency(t, None)
            if result[t]["price"] is None:
                print(f"Warning: failed to fetch {t}: {exc}", file=sys.stderr)

    return result


def enrich_holdings(
    holdings: list[dict[str, Any]],
    prices: dict[str, dict[str, Any]],
    eurusd: float,
) -> list[dict[str, Any]]:
    """Attach native + EUR prices/values; drop unpriced rows."""
    rows: list[dict[str, Any]] = []
    for h in holdings:
        t = h["ticker"]
        info = prices.get(t) or {}
        price = info.get("price")
        if price is None:
            print(f"Warning: excluding {t} (no price)", file=sys.stderr)
            continue
        shares = float(h["shares"])
        currency = info.get("currency") or infer_currency(t, None)
        price_n = float(price)
        price_eur = to_eur(price_n, currency, eurusd)
        price_usd = to_usd(price_n, currency, eurusd)
        market_value_eur = shares * price_eur
        market_value_usd = shares * price_usd
        market_value_native = shares * price_n

        row: dict[str, Any] = {
            "ticker": t,
            "shares": shares,
            "currency": currency,
            "price": price_n,
            "price_eur": price_eur,
            "price_usd": price_usd,
            "market_value": market_value_eur,  # weights use EUR
            "market_value_eur": market_value_eur,
            "market_value_usd": market_value_usd,
            "market_value_native": market_value_native,
            "day_change_pct": info.get("day_change_pct"),
        }
        if h.get("avg_cost_eur") is not None:
            row["avg_cost_eur"] = float(h["avg_cost_eur"])
        if h.get("buy_date"):
            row["buy_date"] = h["buy_date"]
        rows.append(row)
    return rows
