"""Build readable HTML portfolio overview for email (mobile-friendly)."""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio_overview.web_data import build_dashboard_data


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def money(n, d=0) -> str:
    if n is None:
        return "—"
    return f"{n:,.{d}f}"


def pct(n, d=1, signed=True) -> str:
    if n is None:
        return "—"
    return f"{n:+.{d}f}%" if signed else f"{n:.{d}f}%"


def col(n) -> str:
    if n is None:
        return "#64748b"
    return "#15803d" if n >= 0 else "#b91c1c"


def build_html() -> str:
    d = build_dashboard_data()
    s = d["summary"]
    positions = sorted(
        d["positions"], key=lambda x: x.get("weight_pct") or 0, reverse=True
    )

    # Summary cards as stacked blocks (email-safe)
    def card(title: str, value: str, sub: str = "") -> str:
        return f"""
        <td width="33%" valign="top" style="padding:6px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;">
            <tr><td style="padding:14px 12px;">
              <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">{esc(title)}</div>
              <div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:6px;">{esc(value)}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:4px;">{esc(sub)}</div>
            </td></tr>
          </table>
        </td>"""

    cards_row1 = "".join(
        [
            card("Marktwert", f"€ {money(s.get('market_value_eur'), 0)}", f"$ {money(s.get('market_value_usd'), 0)}"),
            card("Einstand", f"€ {money(s.get('cost_basis_eur'), 0)}", "mit Kauf-Lots"),
            card("Dividenden", f"€ {money(s.get('dividends_eur'), 0)}", "seit Kauf"),
        ]
    )
    cards_row2 = "".join(
        [
            card("Gewinn gesamt", f"€ {money(s.get('profit_eur'), 0)}", "Kurs + Div."),
            card("Total Return", pct(s.get("total_return_pct"), 1), "Portfolio (Lots)"),
            card("IRR / Jahr", pct(s.get("irr_annual_pct"), 2), "kapitalgewichtet"),
        ]
    )

    # Compact holdings: dense but readable rows (email clients)
    row_bits = []
    for i, p in enumerate(positions):
        r = p.get("returns") or {}
        tot = r.get("total_return_pct")
        irr = r.get("irr_annual_pct")
        prof = r.get("profit_eur")
        day = p.get("day_change_pct")
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        row_bits.append(
            f"""<tr style="background:{bg};">
<td style="padding:9px 8px;border-bottom:1px solid #e2e8f0;font-weight:700;">{esc(p.get("ticker"))}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;">{money(p.get("shares"), 0 if not ((p.get("shares") or 0) % 1) else 2)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:600;">€&nbsp;{money(p.get("market_value_eur"), 0)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;">{pct(p.get("weight_pct"), 1, False)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;color:{col(day)};">{pct(day, 1)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;">€&nbsp;{money(r.get("cost_basis_eur"), 0)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;color:{col(prof)};">€&nbsp;{money(prof, 0)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;color:{col(tot)};">{pct(tot, 0)}</td>
<td style="padding:9px 6px;border-bottom:1px solid #e2e8f0;text-align:right;color:{col(irr)};">{pct(irr, 1)}</td>
</tr>
<tr style="background:{bg};">
<td colspan="9" style="padding:0 8px 10px;border-bottom:1px solid #e2e8f0;font-size:11px;color:#64748b;">
Kurs € {money(p.get("price_eur"), 2)}
 · Div € {money(r.get("dividends_eur_total"), 0)}
 · Wtd Kauf {esc(p.get("avg_buy_date_weighted") or "—")}
 · Lots {p.get("lot_count") or 0}
</td>
</tr>"""
        )
    blocks = [
        f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
<tr style="background:#0f172a;color:#e2e8f0;font-size:11px;text-transform:uppercase;">
<th align="left" style="padding:10px 8px;">Ticker</th>
<th align="right" style="padding:10px 6px;">Qty</th>
<th align="right" style="padding:10px 6px;">MW €</th>
<th align="right" style="padding:10px 6px;">Wt%</th>
<th align="right" style="padding:10px 6px;">Tag</th>
<th align="right" style="padding:10px 6px;">Cost</th>
<th align="right" style="padding:10px 6px;">Gewinn</th>
<th align="right" style="padding:10px 6px;">Tot%</th>
<th align="right" style="padding:10px 6px;">IRR</th>
</tr>
{"".join(row_bits)}
</table>"""
    ]

    body = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Portfolio Overview {esc(d["as_of"])}</title>
</head>
<body style="margin:0;padding:0;background:#e2e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;padding:20px 10px;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #cbd5e1;">

<tr><td style="background:#0f172a;padding:24px 22px;">
  <div style="font-size:11px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#93c5fd;">my-portfolio-overview</div>
  <div style="font-size:24px;font-weight:700;color:#ffffff;margin-top:6px;">Portfolio Dashboard</div>
  <div style="font-size:13px;color:#cbd5e1;margin-top:8px;">
    Stand <strong style="color:#fff;">{esc(d["as_of"])}</strong>
    · EURUSD <strong style="color:#fff;">{d["eurusd"]:.4f}</strong>
    · {s.get("position_count") or 0} Positionen
  </div>
</td></tr>

<tr><td style="padding:16px 14px 4px;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>{cards_row1}</tr></table>
  <table width="100%" cellpadding="0" cellspacing="0"><tr>{cards_row2}</tr></table>
</td></tr>

<tr><td style="padding:12px 18px 6px;">
  <div style="font-size:15px;font-weight:700;color:#0f172a;">Holdings nach Gewichtung</div>
  <div style="font-size:12px;color:#64748b;margin-top:2px;">Tot %% und IRR inkl. Dividenden (wo Lots vorhanden)</div>
</td></tr>

<tr><td style="padding:8px 14px 18px;">
{blocks[0]}
</td></tr>

<tr><td style="padding:0 18px 22px;">
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.5;color:#64748b;">
    <div>Preise via yfinance · EUR-Umrechnung mit EURUSD · Kein Finanzrat.</div>
    <div style="margin-top:4px;">Dashboard: http://127.0.0.1:8765/</div>
    <div style="margin-top:4px;">From: bovespamm@gmail.com · To: matthias.mueller@gmx.de</div>
  </div>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""
    # fix accidental double percent in template
    body = body.replace("Tot %% und", "Tot % und")
    out = Path.home() / "Downloads" / "portfolio-dashboard-email.html"
    out.write_text(body, encoding="utf-8")
    print(out, len(body))
    return body


if __name__ == "__main__":
    build_html()
