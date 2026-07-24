"""Format portfolio overview table for the terminal (EUR-centric)."""

from __future__ import annotations

from typing import Any


def compute_weights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add weight_pct based on market_value_eur / total EUR."""
    total = sum(
        r.get("market_value_eur", r.get("market_value", 0.0)) for r in rows
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        mv = r.get("market_value_eur", r.get("market_value", 0.0))
        if total > 0:
            row["weight_pct"] = mv / total * 100.0
        else:
            row["weight_pct"] = 0.0
        out.append(row)
    return out


def format_overview(
    rows: list[dict[str, Any]],
    *,
    source: str | None = None,
    eurusd: float | None = None,
) -> str:
    """Return a plain-text table with native + EUR prices and EUR totals."""
    if not rows:
        lines = ["No holdings with both quantity and price to display."]
        if source:
            lines.append(f"Source: {source}")
        return "\n".join(lines)

    weighted = compute_weights(rows)
    weighted.sort(
        key=lambda r: r.get("market_value_eur", r.get("market_value", 0.0)),
        reverse=True,
    )
    total_eur = sum(
        r.get("market_value_eur", r.get("market_value", 0.0)) for r in weighted
    )
    total_usd = sum(r.get("market_value_usd", 0.0) for r in weighted)

    # Columns: Ticker Qty Ccy Price Price€ Value€ Day% Weight%
    headers = (
        f"{'Ticker':<8} {'Qty':>8} {'Ccy':>4} "
        f"{'Price':>10} {'Price €':>10} "
        f"{'Value €':>12} {'Day %':>8} {'Wt %':>7}"
    )
    sep = (
        f"{'-' * 8} {'-' * 8} {'-' * 4} "
        f"{'-' * 10} {'-' * 10} "
        f"{'-' * 12} {'-' * 8} {'-' * 7}"
    )
    lines: list[str] = []
    if source:
        lines.append(f"Source: {source}")
    if eurusd is not None:
        lines.append(f"FX: EURUSD = {eurusd:.4f}  (USD per 1 EUR)")
        lines.append(
            f"    → 1 USD = {1.0 / eurusd:.4f} EUR"
        )
    if lines:
        lines.append("")
    lines.extend([headers, sep])

    for r in weighted:
        day = r.get("day_change_pct")
        day_s = "n/a" if day is None else f"{day:+.2f}"
        ccy = r.get("currency") or "?"
        price_eur = r.get("price_eur", r.get("price", 0.0))
        value_eur = r.get("market_value_eur", r.get("market_value", 0.0))
        lines.append(
            f"{r['ticker']:<8} "
            f"{_fmt_qty(r['shares']):>8} "
            f"{ccy:>4} "
            f"{_fmt_money(r['price']):>10} "
            f"{_fmt_money(price_eur):>10} "
            f"{_fmt_money(value_eur):>12} "
            f"{day_s:>8} "
            f"{r['weight_pct']:>6.1f}%"
        )

    lines.append(sep)
    lines.append(
        f"{'TOTAL':<8} {'':>8} {'':>4} "
        f"{'':>10} {'':>10} "
        f"{_fmt_money(total_eur):>12} "
        f"{'':>8} {'100.0%':>7}"
    )
    lines.append("")
    lines.append(f"Total portfolio value:  € {_fmt_money(total_eur)}")
    if eurusd is not None:
        lines.append(f"                        $ {_fmt_money(total_usd)}  (at FX)")
    return "\n".join(lines)


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_qty(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:.4f}".rstrip("0").rstrip(".")
