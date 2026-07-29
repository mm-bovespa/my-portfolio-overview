"""Build portfolio dashboard payload (prices + lot returns)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from portfolio_overview.loader import default_profile_path, load_profile, sample_profile_path
from portfolio_overview.prices import (
    enrich_holdings,
    fetch_eurusd,
    fetch_prices,
    infer_currency,
    to_eur,
)

# Reuse finance-profile return math (stdlib) when available
_SKILL_REF = (
    Path.home() / ".grok" / "skills" / "my-finance-profile" / "references"
)
if str(_SKILL_REF) not in sys.path:
    sys.path.insert(0, str(_SKILL_REF))

try:
    from finance_profile import FinanceProfile  # type: ignore
except ImportError:  # pragma: no cover
    FinanceProfile = None  # type: ignore


def _extract_holdings_full(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Holdings including purchases and stored metrics."""
    raw = profile.get("holdings") or []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qty = item.get("shares", item.get("quantity"))
        if qty is None or qty == "":
            continue
        try:
            shares = float(qty)
        except (TypeError, ValueError):
            continue
        if shares <= 0:
            continue
        h: dict[str, Any] = {"ticker": ticker, "shares": shares}
        for key in (
            "avg_cost_eur",
            "buy_date",
            "notes",
            "purchases",
            "avg_buy_date_weighted",
            "weighted_age_days",
            "dividends_eur_total",
            "cost_basis_eur",
        ):
            if key in item and item[key] not in (None, ""):
                h[key] = item[key]
        # legacy cost field
        if "avg_cost_eur" not in h:
            legacy = item.get("avg_cost_usd", item.get("avg_buy_price"))
            if legacy not in (None, ""):
                try:
                    h["avg_cost_eur"] = float(legacy)
                except (TypeError, ValueError):
                    pass
        out.append(h)
    return out


def build_dashboard_data(
    *,
    profile_path: Path | None = None,
    use_sample: bool = False,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Assemble full dashboard JSON for the webpage."""
    today = as_of or date.today()
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
    live_rows = enrich_holdings(
        [{"ticker": h["ticker"], "shares": h["shares"]} for h in holdings],
        prices,
        eurusd,
    )
    live_by_t = {r["ticker"]: r for r in live_rows}

    positions: list[dict[str, Any]] = []
    sum_mv = 0.0
    # Return aggregates only over positions that have cost / lot data
    sum_cost = 0.0
    sum_div = 0.0
    sum_profit = 0.0
    sum_tv = 0.0  # for portfolio IRR age
    sum_mv_with_cost = 0.0

    for h in holdings:
        t = h["ticker"]
        live = live_by_t.get(t)
        if not live:
            positions.append(
                {
                    "ticker": t,
                    "shares": h["shares"],
                    "error": "no price",
                    "purchases": h.get("purchases") or [],
                }
            )
            continue

        price_eur = float(live["price_eur"])
        currency = live.get("currency") or "USD"
        mv = float(live["market_value_eur"])
        day_pct = live.get("day_change_pct")
        # Day P&L in EUR ≈ current market value × day %
        day_eur = None
        if day_pct is not None:
            try:
                day_eur = mv * float(day_pct) / 100.0
            except (TypeError, ValueError):
                day_eur = None

        purchases = h.get("purchases") or []
        lot_rows: list[dict[str, Any]] = []
        ret_summary: dict[str, Any] | None = None

        if purchases and FinanceProfile is not None:
            ret = FinanceProfile.compute_returns(
                purchases, price_eur, as_of=today
            )
            w = FinanceProfile.compute_cost_weighted_buy_date(
                purchases, as_of=today
            )
            if ret:
                ret_summary = {
                    "cost_basis_eur": ret["cost_basis_eur"],
                    "market_value_eur": ret["market_value_eur"],
                    "dividends_eur_total": ret["dividends_eur_total"],
                    "profit_eur": ret["profit_eur"],
                    "price_gain_eur": ret["price_gain_eur"],
                    "total_return_pct": ret["total_return_pct"],
                    "irr_annual_pct": ret["irr_annual_pct"],
                    "weighted_age_days": ret["weighted_age_days"],
                    "weighted_age_years": ret["weighted_age_years"],
                    "avg_buy_date_weighted": (w or {}).get(
                        "avg_buy_date_weighted"
                    ),
                }
                lot_rows = ret["lots"]
                sum_cost += ret["cost_basis_eur"]
                sum_div += ret["dividends_eur_total"]
                sum_profit += ret["profit_eur"]
                sum_tv += ret["cost_basis_eur"] * ret["weighted_age_days"]
                sum_mv_with_cost += ret["market_value_eur"]
            elif w:
                ret_summary = {
                    "avg_buy_date_weighted": w.get("avg_buy_date_weighted"),
                    "weighted_age_days": w.get("weighted_age_days"),
                    "cost_basis_eur": w.get("cost_basis_eur"),
                }
        else:
            # No lots: estimate cost from avg_cost_eur if present
            cost = None
            if h.get("avg_cost_eur") is not None:
                cost = float(h["shares"]) * float(h["avg_cost_eur"])
                sum_cost += cost
                sum_mv_with_cost += mv
            if cost is not None:
                profit = mv - cost
                sum_profit += profit
                ret_summary = {
                    "cost_basis_eur": cost,
                    "market_value_eur": mv,
                    "dividends_eur_total": 0.0,
                    "profit_eur": profit,
                    "price_gain_eur": profit,
                    "total_return_pct": (mv / cost - 1.0) * 100.0 if cost else None,
                    "irr_annual_pct": None,
                    "avg_buy_date_weighted": h.get("avg_buy_date_weighted"),
                    "weighted_age_days": h.get("weighted_age_days"),
                }

        sum_mv += mv

        positions.append(
            {
                "ticker": t,
                "shares": h["shares"],
                "currency": currency,
                "price": live["price"],
                "price_eur": price_eur,
                "market_value_eur": mv,
                "day_change_pct": day_pct,
                "day_change_eur": day_eur,
                "avg_cost_eur": h.get("avg_cost_eur"),
                "buy_date_first": h.get("buy_date"),
                "avg_buy_date_weighted": (ret_summary or {}).get(
                    "avg_buy_date_weighted"
                )
                or h.get("avg_buy_date_weighted"),
                "weighted_age_days": (ret_summary or {}).get("weighted_age_days")
                or h.get("weighted_age_days"),
                "returns": ret_summary,
                "lots": lot_rows,
                "lot_count": len(purchases) if purchases else 0,
            }
        )

    # Weights + portfolio totals
    for p in positions:
        mv = p.get("market_value_eur") or 0.0
        p["weight_pct"] = (mv / sum_mv * 100.0) if sum_mv > 0 else 0.0

    portfolio_irr = None
    portfolio_return = None
    if sum_cost > 0:
        # Return/IRR only on positions that have cost (not whole book MV)
        proceeds = sum_mv_with_cost + sum_div
        portfolio_return = (proceeds / sum_cost - 1.0) * 100.0
        wtd_days = sum_tv / sum_cost if sum_tv > 0 else 0.0
        years = wtd_days / 365.25 if wtd_days > 0 else 0.0
        mult = proceeds / sum_cost
        if years > 0 and mult > 0:
            portfolio_irr = (mult ** (1.0 / years) - 1.0) * 100.0

    # Sort by market value desc
    positions.sort(key=lambda x: x.get("market_value_eur") or 0.0, reverse=True)

    return {
        "as_of": today.isoformat(),
        "source": str(path),
        "eurusd": eurusd,
        "profile": {
            "risk_tolerance": profile.get("risk_tolerance"),
            "investment_horizon": profile.get("investment_horizon"),
            "investment_strategy": profile.get("investment_strategy"),
            "watchlist": profile.get("watchlist") or [],
        },
        "summary": {
            "position_count": len(positions),
            "market_value_eur": sum_mv,
            "market_value_usd": sum_mv * eurusd,
            "cost_basis_eur": sum_cost if sum_cost else None,
            "dividends_eur": sum_div if sum_div else None,
            "profit_eur": sum_profit if sum_cost else None,
            "total_return_pct": portfolio_return,
            "irr_annual_pct": portfolio_irr,
        },
        "positions": positions,
    }


def build_dashboard_json(**kwargs: Any) -> str:
    return json.dumps(build_dashboard_data(**kwargs), indent=2, default=str)
