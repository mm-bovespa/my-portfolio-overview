"""Format portfolio overview table for the terminal."""

from __future__ import annotations

from typing import Any


def compute_weights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add weight_pct based on market_value / total."""
    total = sum(r["market_value"] for r in rows)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        if total > 0:
            row["weight_pct"] = r["market_value"] / total * 100.0
        else:
            row["weight_pct"] = 0.0
        out.append(row)
    return out


def format_overview(
    rows: list[dict[str, Any]],
    *,
    source: str | None = None,
) -> str:
    """Return a plain-text table + total portfolio value."""
    if not rows:
        lines = ["No holdings with both quantity and price to display."]
        if source:
            lines.append(f"Source: {source}")
        return "\n".join(lines)

    weighted = compute_weights(rows)
    # Sort by market value descending for readability
    weighted.sort(key=lambda r: r["market_value"], reverse=True)
    total = sum(r["market_value"] for r in weighted)

    headers = (
        f"{'Ticker':<8} {'Qty':>12} {'Price':>12} "
        f"{'Market Value':>14} {'Day %':>10} {'Weight %':>10}"
    )
    sep = (
        f"{'-' * 8} {'-' * 12} {'-' * 12} "
        f"{'-' * 14} {'-' * 10} {'-' * 10}"
    )
    lines = []
    if source:
        lines.append(f"Source: {source}")
        lines.append("")
    lines.extend([headers, sep])

    for r in weighted:
        day = r.get("day_change_pct")
        if day is None:
            day_s = "n/a"
        else:
            day_s = f"{day:+.2f}"
        lines.append(
            f"{r['ticker']:<8} "
            f"{_fmt_qty(r['shares']):>12} "
            f"{_fmt_money(r['price']):>12} "
            f"{_fmt_money(r['market_value']):>14} "
            f"{day_s:>10} "
            f"{r['weight_pct']:>9.1f}%"
        )

    lines.append(sep)
    lines.append(
        f"{'TOTAL':<8} {'':>12} {'':>12} {_fmt_money(total):>14} {'':>10} {'100.0%':>10}"
    )
    return "\n".join(lines)


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_qty(value: float) -> str:
    # Trim trailing zeros for fractional shares
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:.4f}".rstrip("0").rstrip(".")
