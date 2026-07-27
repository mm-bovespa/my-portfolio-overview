"""Build plain-text portfolio overview for email."""
from __future__ import annotations

from pathlib import Path

from portfolio_overview.web_data import build_dashboard_data


def main() -> str:
    d = build_dashboard_data()
    s = d["summary"]
    lines: list[str] = []
    lines.append("PORTFOLIO OVERVIEW (wie Dashboard)")
    lines.append(f"As of: {d['as_of']}")
    lines.append(f"EURUSD: {d['eurusd']:.4f}")
    lines.append(f"Source: {d['source']}")
    lines.append("")
    lines.append("=== SUMMARY ===")
    lines.append(f"Market value EUR: {s.get('market_value_eur') or 0:,.2f}")
    lines.append(f"Market value USD: {s.get('market_value_usd') or 0:,.2f}")
    if s.get("cost_basis_eur") is not None:
        lines.append(f"Cost basis EUR:   {s['cost_basis_eur']:,.2f}")
    if s.get("dividends_eur") is not None:
        lines.append(f"Dividends EUR:    {s['dividends_eur']:,.2f}")
    if s.get("profit_eur") is not None:
        lines.append(f"Total profit EUR: {s['profit_eur']:,.2f}")
    if s.get("total_return_pct") is not None:
        lines.append(f"Total return %:   {s['total_return_pct']:+.1f}%")
    if s.get("irr_annual_pct") is not None:
        lines.append(f"IRR / year %:     {s['irr_annual_pct']:+.2f}%")
    lines.append(f"Positions:        {s.get('position_count')}")
    lines.append("")
    lines.append("=== HOLDINGS (sorted by weight %) ===")
    hdr = (
        f"{'Ticker':<10} {'Qty':>10} {'Price EUR':>12} {'MV EUR':>14} "
        f"{'Day%':>8} {'Wt%':>7} {'Cost EUR':>12} {'Div EUR':>10} "
        f"{'Profit EUR':>12} {'Tot%':>8} {'IRR%/y':>8} {'Wtd buy':<12} {'Lots':>5}"
    )
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for p in sorted(
        d["positions"], key=lambda x: x.get("weight_pct") or 0, reverse=True
    ):
        r = p.get("returns") or {}
        day = p.get("day_change_pct")
        day_s = f"{day:+.2f}" if day is not None else "n/a"
        tot = r.get("total_return_pct")
        tot_s = f"{tot:+.1f}" if tot is not None else "n/a"
        irr = r.get("irr_annual_pct")
        irr_s = f"{irr:+.2f}" if irr is not None else "n/a"
        cost = r.get("cost_basis_eur")
        cost_s = f"{cost:,.0f}" if cost is not None else "-"
        div = r.get("dividends_eur_total")
        div_s = f"{div:,.0f}" if div is not None else "-"
        prof = r.get("profit_eur")
        prof_s = f"{prof:,.0f}" if prof is not None else "-"
        mv = p.get("market_value_eur")
        mv_s = f"{mv:,.0f}" if mv is not None else "-"
        pe = p.get("price_eur")
        pe_s = f"{pe:,.2f}" if pe is not None else "-"
        wt = p.get("weight_pct")
        wt_s = f"{wt:.1f}" if wt is not None else "-"
        wtd = p.get("avg_buy_date_weighted") or "-"
        lines.append(
            f"{p.get('ticker', '?'):<10} {p.get('shares', 0):>10.2f} "
            f"{pe_s:>12} {mv_s:>14} {day_s:>8} {wt_s:>7} "
            f"{cost_s:>12} {div_s:>10} {prof_s:>12} {tot_s:>8} {irr_s:>8} "
            f"{wtd:<12} {p.get('lot_count', 0):>5}"
        )

    lines.append("")
    lines.append(
        "Hinweis: Tot% und IRR beinhalten Dividenden (wo Lots vorhanden). "
        "Preise via yfinance, EUR-Umrechnung mit EURUSD."
    )
    lines.append("Kein Finanzrat. Lokales Dashboard: http://127.0.0.1:8765/")
    lines.append("")
    lines.append(
        "REGEL (gemerkt): E-Mails standardmäßig an matthias.mueller@gmx.de, "
        "sofern kein anderer Empfänger explizit genannt wird."
    )
    text = "\n".join(lines)
    out = Path.home() / "Downloads" / "portfolio-dashboard-email-body.txt"
    out.write_text(text, encoding="utf-8")
    print(out)
    print("chars", len(text))
    return text


if __name__ == "__main__":
    main()
