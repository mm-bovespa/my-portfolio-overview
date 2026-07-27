"""Portfolio analysis: sectors, regions, and performance vs major indexes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from portfolio_overview.loader import default_profile_path, load_profile, sample_profile_path
from portfolio_overview.prices import enrich_holdings, fetch_eurusd, fetch_prices, infer_currency
from portfolio_overview.web_data import _extract_holdings_full

# Normalize yfinance sector strings → display buckets
SECTOR_ALIASES = {
    "technology": "Technology",
    "consumer defensive": "Consumer Defensive",
    "consumer cyclical": "Consumer Cyclical",
    "consumer staples": "Consumer Defensive",
    "consumer discretionary": "Consumer Cyclical",
    "financial services": "Financials",
    "financials": "Financials",
    "healthcare": "Healthcare",
    "health care": "Healthcare",
    "energy": "Energy",
    "industrials": "Industrials",
    "basic materials": "Basic Materials",
    "materials": "Basic Materials",
    "communication services": "Communication Services",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "unknown": "Unknown / Other",
}

COUNTRY_TO_REGION = {
    "united states": "United States",
    "usa": "United States",
    "canada": "Canada",
    "germany": "Europe",
    "france": "Europe",
    "netherlands": "Europe",
    "united kingdom": "Europe",
    "switzerland": "Europe",
    "italy": "Europe",
    "spain": "Europe",
    "belgium": "Europe",
    "ireland": "Europe",
    "sweden": "Europe",
    "denmark": "Europe",
    "norway": "Europe",
    "finland": "Europe",
    "austria": "Europe",
    "portugal": "Europe",
    "luxembourg": "Europe",
    "brazil": "Latin America",
    "mexico": "Latin America",
    "chile": "Latin America",
    "argentina": "Latin America",
    "japan": "Asia Pacific",
    "china": "Asia Pacific",
    "hong kong": "Asia Pacific",
    "taiwan": "Asia Pacific",
    "south korea": "Asia Pacific",
    "korea": "Asia Pacific",
    "australia": "Asia Pacific",
    "singapore": "Asia Pacific",
    "india": "Asia Pacific",
    "israel": "Middle East / Africa",
    "south africa": "Middle East / Africa",
}

# Liquid ETFs as index proxies (total return via adjusted close)
PERFORMANCE_INDEXES = [
    {"id": "sp500", "name": "S&P 500", "symbol": "SPY", "note": "SPY ETF"},
    {"id": "dji", "name": "Dow Jones", "symbol": "DIA", "note": "DIA ETF"},
    {"id": "sx5e", "name": "Euro Stoxx 50", "symbol": "FEZ", "note": "FEZ ETF"},
    {"id": "world", "name": "World (VT)", "symbol": "VT", "note": "Vanguard Total World"},
]

HORIZONS = [
    {"id": "1y", "label": "1 year", "years": 1.0},
    {"id": "5y", "label": "5 years", "years": 5.0},
    {"id": "10y", "label": "10 years", "years": 10.0},
    {"id": "full", "label": "Full period", "years": None},
]


def _norm_sector(raw: str | None) -> str:
    if not raw:
        return "Unknown / Other"
    key = str(raw).strip().lower()
    return SECTOR_ALIASES.get(key, raw.strip().title())


def _norm_region(country: str | None, ticker: str) -> str:
    if country:
        reg = COUNTRY_TO_REGION.get(country.strip().lower())
        if reg:
            return reg
        return f"Other ({country.strip()})"
    t = ticker.upper()
    if t.endswith(
        (".DE", ".PA", ".AS", ".BR", ".MI", ".MC", ".LS", ".F", ".VI", ".HE", ".ST")
    ):
        return "Europe"
    if t.endswith((".L", ".LON")):
        return "Europe"
    if t.endswith((".T", ".HK", ".SS", ".SZ", ".KS", ".AX")):
        return "Asia Pacific"
    if t.endswith(".SA"):
        return "Latin America"
    return "United States"


def _fetch_meta(ticker: str) -> dict[str, str]:
    try:
        import yfinance as yf
    except ImportError:
        return {
            "sector": "Unknown / Other",
            "country": "",
            "region": _norm_region(None, ticker),
        }

    sector = None
    country = None
    try:
        info = yf.Ticker(ticker).info or {}
        sector = info.get("sector")
        country = info.get("country")
    except Exception:
        pass
    return {
        "sector": _norm_sector(sector),
        "country": country or "",
        "region": _norm_region(country, ticker),
    }


def _pct_map(weights: dict[str, float], total: float) -> list[dict[str, Any]]:
    if total <= 0:
        return []
    rows = [
        {"name": k, "weight_pct": v / total * 100.0, "value_eur": v}
        for k, v in weights.items()
        if v > 0
    ]
    rows.sort(key=lambda r: r["weight_pct"], reverse=True)
    return rows


def _as_date(d: Any) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def _history_close(symbol: str, start: date, end: date):
    """Return series of adjusted closes (or None)."""
    import yfinance as yf
    import pandas as pd

    # pad start for weekends/holidays
    s = start - timedelta(days=7)
    e = end + timedelta(days=3)
    hist = yf.Ticker(symbol).history(start=s.isoformat(), end=e.isoformat(), auto_adjust=True)
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    # Normalize index to dates
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    return closes


def _price_on_or_before(closes, d: date) -> float | None:
    if closes is None or closes.empty:
        return None
    import pandas as pd

    ts = pd.Timestamp(d)
    # last close on or before d
    eligible = closes[closes.index <= ts]
    if eligible.empty:
        # first available after
        after = closes[closes.index >= ts]
        if after.empty:
            return None
        return float(after.iloc[0])
    return float(eligible.iloc[-1])


def _price_on_or_after(closes, d: date) -> float | None:
    if closes is None or closes.empty:
        return None
    import pandas as pd

    ts = pd.Timestamp(d)
    after = closes[closes.index >= ts]
    if after.empty:
        eligible = closes[closes.index <= ts]
        if eligible.empty:
            return None
        return float(eligible.iloc[-1])
    return float(after.iloc[0])


def _cagr(total_return: float, years: float) -> float | None:
    if years is None or years <= 0:
        return None
    mult = 1.0 + total_return
    if mult <= 0:
        return None
    return mult ** (1.0 / years) - 1.0


def _xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """Newton-Raphson XIRR. cashflows: (date, amount), negative = invest."""
    if len(cashflows) < 2:
        return None
    cashflows = sorted(cashflows, key=lambda x: x[0])
    t0 = cashflows[0][0]
    times = [(d - t0).days / 365.25 for d, _ in cashflows]
    amounts = [a for _, a in cashflows]
    if not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        return None

    def npv(r: float) -> float:
        return sum(a / ((1.0 + r) ** t) for a, t in zip(amounts, times))

    def dnpv(r: float) -> float:
        return sum(-t * a / ((1.0 + r) ** (t + 1.0)) for a, t in zip(amounts, times))

    r = guess
    for _ in range(80):
        y = npv(r)
        dy = dnpv(r)
        if abs(dy) < 1e-12:
            break
        r_next = r - y / dy
        if r_next <= -0.9999:
            r_next = -0.9999
        if abs(r_next - r) < 1e-8:
            return r_next
        r = r_next
    if abs(npv(r)) < 1e-3:
        return r
    return None


def _index_period_return(symbol: str, start: date, end: date) -> dict[str, Any]:
    closes = _history_close(symbol, start, end)
    p0 = _price_on_or_after(closes, start)
    p1 = _price_on_or_before(closes, end)
    if p0 is None or p1 is None or p0 <= 0:
        return {
            "symbol": symbol,
            "total_return_pct": None,
            "irr_annual_pct": None,
            "years": None,
            "error": "no price history",
        }
    years = max((end - start).days / 365.25, 1e-6)
    total_ret = p1 / p0 - 1.0
    irr = _cagr(total_ret, years)
    return {
        "symbol": symbol,
        "total_return_pct": total_ret * 100.0,
        "irr_annual_pct": (irr * 100.0) if irr is not None else None,
        "years": years,
        "start_price": p0,
        "end_price": p1,
        "error": None,
    }


def _portfolio_period_return(
    holdings: list[dict[str, Any]],
    live_by: dict[str, dict[str, Any]],
    hist_cache: dict[str, Any],
    eurusd_hist,
    eurusd_now: float,
    start: date,
    end: date,
    *,
    full_xirr: bool = False,
) -> dict[str, Any]:
    """Portfolio return over [start, end].

    Value-path method: for each lot, start value at max(buy_date, start) and
    end value at end. Dividends pro-rated by ownership days in window / life.
    Full period also computes money-weighted XIRR on purchase cash flows.
    """
    start_val = 0.0
    end_val = 0.0
    div_in_period = 0.0
    lots_used = 0
    cashflows: list[tuple[date, float]] = []

    for h in holdings:
        t = h["ticker"]
        live = live_by.get(t)
        if not live:
            continue
        price_now_native = float(live["price"])
        ccy = live.get("currency") or infer_currency(t, None)
        price_now_eur = float(live["price_eur"])

        purchases = h.get("purchases") or []
        if not purchases:
            # No lots: use current shares only if we treat as held whole period
            # Skip for period math without cost basis
            continue

        if t not in hist_cache:
            hist_cache[t] = _history_close(t, start - timedelta(days=14), end)

        closes = hist_cache[t]

        for lot in purchases:
            bd = _as_date(lot["buy_date"])
            if bd > end:
                continue
            qty = float(lot["shares"])
            buy_px_eur = float(lot["price_eur"])
            div_total = float(lot.get("dividends_eur") or 0.0)
            days_held_life = max((end - bd).days, 1)

            if full_xirr:
                cashflows.append((bd, -qty * buy_px_eur))

            eff_start = start if bd <= start else bd
            if bd <= start:
                # Need historical native price at start → EUR
                p_nat = _price_on_or_before(closes, start)
                if p_nat is None:
                    # fallback: buy price EUR (understates if appreciated before start)
                    start_px_eur = buy_px_eur
                else:
                    fx0 = _price_on_or_before(eurusd_hist, start) or eurusd_now
                    if ccy == "EUR":
                        start_px_eur = p_nat
                    else:
                        start_px_eur = p_nat / float(fx0)
            else:
                start_px_eur = buy_px_eur

            start_val += qty * start_px_eur
            end_val += qty * price_now_eur

            # Pro-rate stored lifetime dividends into this window
            days_in_window = max((end - eff_start).days, 0)
            if div_total and days_held_life > 0:
                div_in_period += div_total * (days_in_window / days_held_life)

            lots_used += 1

    if start_val <= 0 or lots_used == 0:
        return {
            "total_return_pct": None,
            "irr_annual_pct": None,
            "years": None,
            "start_value_eur": start_val,
            "end_value_eur": end_val,
            "dividends_eur": div_in_period,
            "lots_used": lots_used,
            "method": "xirr" if full_xirr else "value_path",
            "error": "insufficient lot data for period",
        }

    years = max((end - start).days / 365.25, 1e-6)
    proceeds = end_val + div_in_period
    total_ret = proceeds / start_val - 1.0
    irr = _cagr(total_ret, years)

    xirr_val = None
    if full_xirr and cashflows:
        cashflows.append((end, end_val + div_in_period))
        xirr_val = _xirr(cashflows)

    return {
        "total_return_pct": total_ret * 100.0,
        "irr_annual_pct": (
            (xirr_val * 100.0)
            if xirr_val is not None
            else ((irr * 100.0) if irr is not None else None)
        ),
        "cagr_pct": (irr * 100.0) if irr is not None else None,
        "xirr_pct": (xirr_val * 100.0) if xirr_val is not None else None,
        "years": years,
        "start_value_eur": start_val,
        "end_value_eur": end_val,
        "dividends_eur": div_in_period,
        "lots_used": lots_used,
        "method": "xirr" if full_xirr and xirr_val is not None else "value_path",
        "error": None,
    }


def build_performance_comparison(
    holdings: list[dict[str, Any]],
    live_by: dict[str, dict[str, Any]],
    eurusd_now: float,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Portfolio vs index performance for 1y / 5y / 10y / full."""
    end = as_of or date.today()
    # earliest purchase
    earliest = end
    for h in holdings:
        for lot in h.get("purchases") or []:
            bd = _as_date(lot["buy_date"])
            if bd < earliest:
                earliest = bd

    eurusd_hist = _history_close("EURUSD=X", earliest - timedelta(days=30), end)
    hist_cache: dict[str, Any] = {}

    rows: list[dict[str, Any]] = []
    for hdef in HORIZONS:
        if hdef["years"] is None:
            start = earliest
            full = True
        else:
            start = end - timedelta(days=int(hdef["years"] * 365.25))
            if start < earliest:
                # still compute but note shorter span for some lots
                pass
            full = False

        port = _portfolio_period_return(
            holdings,
            live_by,
            hist_cache,
            eurusd_hist,
            eurusd_now,
            start,
            end,
            full_xirr=full,
        )

        indexes: dict[str, Any] = {}
        for idx in PERFORMANCE_INDEXES:
            indexes[idx["id"]] = {
                "name": idx["name"],
                **_index_period_return(idx["symbol"], start, end),
            }

        # Active return vs each index (portfolio IRR - index IRR)
        vs: dict[str, Any] = {}
        p_irr = port.get("irr_annual_pct")
        for iid, idata in indexes.items():
            i_irr = idata.get("irr_annual_pct")
            if p_irr is not None and i_irr is not None:
                vs[iid] = round(p_irr - i_irr, 2)
            else:
                vs[iid] = None

        rows.append(
            {
                "id": hdef["id"],
                "label": hdef["label"],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "years": port.get("years"),
                "portfolio": port,
                "indexes": indexes,
                "vs_index_irr_pp": vs,  # percentage points
            }
        )

    return {
        "as_of": end.isoformat(),
        "earliest_purchase": earliest.isoformat(),
        "indexes": PERFORMANCE_INDEXES,
        "horizons": rows,
        "notes": [
            "Portfolio: value-path return on lots (start MV of held lots → end MV + pro-rated dividends).",
            "Full period portfolio IRR uses money-weighted XIRR when possible (purchases as cash outflows).",
            "Indexes: total return via ETF adjusted close (SPY, DIA, FEZ, VT).",
            "1y / 5y / 10y annualized = CAGR of period total return.",
        ],
    }


def build_allocation_analysis(
    *,
    profile_path: Path | None = None,
    use_sample: bool = False,
) -> dict[str, Any]:
    """Sectors, regions, and performance vs major indexes."""
    if use_sample:
        path = sample_profile_path()
    elif profile_path is not None:
        path = profile_path
    else:
        path = default_profile_path()

    profile = load_profile(path)
    holdings = _extract_holdings_full(profile)
    eurusd = fetch_eurusd()
    tickers = [h["ticker"] for h in holdings]
    prices = fetch_prices(tickers) if tickers else {}
    live = enrich_holdings(
        [{"ticker": h["ticker"], "shares": h["shares"]} for h in holdings],
        prices,
        eurusd,
    )
    live_by = {r["ticker"]: r for r in live}

    sector_w: dict[str, float] = defaultdict(float)
    region_w: dict[str, float] = defaultdict(float)
    positions_meta: list[dict[str, Any]] = []
    total_mv = 0.0

    for h in holdings:
        t = h["ticker"]
        row = live_by.get(t)
        if not row:
            continue
        mv = float(row["market_value_eur"])
        total_mv += mv
        meta = _fetch_meta(t)
        sector_w[meta["sector"]] += mv
        region_w[meta["region"]] += mv
        positions_meta.append(
            {
                "ticker": t,
                "market_value_eur": mv,
                "weight_pct": 0.0,
                "sector": meta["sector"],
                "country": meta["country"],
                "region": meta["region"],
            }
        )

    for p in positions_meta:
        p["weight_pct"] = (p["market_value_eur"] / total_mv * 100.0) if total_mv else 0.0
    positions_meta.sort(key=lambda x: x["market_value_eur"], reverse=True)

    portfolio_sectors = _pct_map(dict(sector_w), total_mv)
    portfolio_regions = _pct_map(dict(region_w), total_mv)

    performance = build_performance_comparison(holdings, live_by, eurusd)

    return {
        "source": str(path),
        "eurusd": eurusd,
        "total_market_value_eur": total_mv,
        "position_count": len(positions_meta),
        "positions": positions_meta,
        "sectors": portfolio_sectors,
        "regions": portfolio_regions,
        "performance": performance,
        "notes": [
            "Portfolio sector/region weights by current market value (EUR).",
            "Sector/country from yfinance (best effort).",
            "Index comparison is performance (total return / annualized IRR), not sector mix.",
        ],
    }
