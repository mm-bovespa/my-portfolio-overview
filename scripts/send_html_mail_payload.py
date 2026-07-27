"""Generate compact pretty HTML portfolio email and save payload JSON."""
from __future__ import annotations

import html as H
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portfolio_overview.web_data import build_dashboard_data


def esc(x) -> str:
    return H.escape("" if x is None else str(x))


def m(n, d=0) -> str:
    return "—" if n is None else f"{n:,.{d}f}"


def p(n, d=1, signed=True) -> str:
    if n is None:
        return "—"
    return f"{n:+.{d}f}%" if signed else f"{n:.{d}f}%"


def c(n) -> str:
    if n is None:
        return "#64748b"
    return "#15803d" if n >= 0 else "#b91c1c"


def main() -> None:
    d = build_dashboard_data()
    s = d["summary"]
    positions = sorted(
        d["positions"], key=lambda x: x.get("weight_pct") or 0, reverse=True
    )

    rows = []
    for i, pos in enumerate(positions):
        r = pos.get("returns") or {}
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        day = pos.get("day_change_pct")
        tot = r.get("total_return_pct")
        irr = r.get("irr_annual_pct")
        prof = r.get("profit_eur")
        sh = pos.get("shares") or 0
        sh_d = 0 if abs(sh - round(sh)) < 1e-9 else 2
        rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:8px;font-weight:700'>{esc(pos.get('ticker'))}</td>"
            f"<td style='padding:8px;text-align:right'>{m(sh, sh_d)}</td>"
            f"<td style='padding:8px;text-align:right;font-weight:600'>"
            f"€ {m(pos.get('market_value_eur'), 0)}</td>"
            f"<td style='padding:8px;text-align:right'>"
            f"{p(pos.get('weight_pct'), 1, False)}</td>"
            f"<td style='padding:8px;text-align:right;color:{c(day)}'>{p(day, 1)}</td>"
            f"<td style='padding:8px;text-align:right'>"
            f"€ {m(r.get('cost_basis_eur'), 0)}</td>"
            f"<td style='padding:8px;text-align:right;color:{c(prof)}'>"
            f"€ {m(prof, 0)}</td>"
            f"<td style='padding:8px;text-align:right;color:{c(tot)}'>{p(tot, 0)}</td>"
            f"<td style='padding:8px;text-align:right;color:{c(irr)}'>{p(irr, 1)}</td>"
            f"</tr>"
            f"<tr style='background:{bg}'>"
            f"<td colspan='9' style='padding:0 8px 8px;font-size:11px;color:#64748b;"
            f"border-bottom:1px solid #e2e8f0'>"
            f"Kurs € {m(pos.get('price_eur'), 2)}"
            f" · Div € {m(r.get('dividends_eur_total'), 0)}"
            f" · Wtd Kauf {esc(pos.get('avg_buy_date_weighted') or '—')}"
            f" · Lots {pos.get('lot_count') or 0}"
            f"</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Portfolio Overview</title></head>
<body style="margin:0;padding:0;background:#e2e8f0;font-family:Segoe UI,Roboto,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;padding:16px">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:#fff;border-radius:12px;border:1px solid #cbd5e1;overflow:hidden">
<tr><td style="background:#0f172a;padding:22px 20px">
<div style="color:#93c5fd;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase">my-portfolio-overview</div>
<div style="color:#fff;font-size:22px;font-weight:700;margin-top:6px">Portfolio Dashboard</div>
<div style="color:#cbd5e1;font-size:13px;margin-top:8px">
Stand <b style="color:#fff">{esc(d['as_of'])}</b>
· EURUSD <b style="color:#fff">{d['eurusd']:.4f}</b>
· {s.get('position_count')} Positionen
</div></td></tr>
<tr><td style="padding:16px 12px 4px">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">MARKTWERT</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">€ {m(s.get('market_value_eur'), 0)}</div>
<div style="font-size:11px;color:#94a3b8">$ {m(s.get('market_value_usd'), 0)}</div>
</div></td>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">EINSTAND</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">€ {m(s.get('cost_basis_eur'), 0)}</div>
<div style="font-size:11px;color:#94a3b8">mit Lots</div>
</div></td>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">DIVIDENDEN</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">€ {m(s.get('dividends_eur'), 0)}</div>
<div style="font-size:11px;color:#94a3b8">seit Kauf</div>
</div></td>
</tr><tr>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">GEWINN</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">€ {m(s.get('profit_eur'), 0)}</div>
<div style="font-size:11px;color:#94a3b8">Kurs + Div.</div>
</div></td>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">TOTAL RETURN</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">{p(s.get('total_return_pct'), 1)}</div>
<div style="font-size:11px;color:#94a3b8">Portfolio</div>
</div></td>
<td width="33%" style="padding:4px"><div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:12px">
<div style="font-size:11px;color:#64748b">IRR / JAHR</div>
<div style="font-size:18px;font-weight:700;margin-top:4px">{p(s.get('irr_annual_pct'), 2)}</div>
<div style="font-size:11px;color:#94a3b8">kapitalgewichtet</div>
</div></td>
</tr></table>
</td></tr>
<tr><td style="padding:8px 16px">
<div style="font-size:15px;font-weight:700">Holdings nach Gewichtung (Wt %)</div>
<div style="font-size:12px;color:#64748b">Tot% und IRR inkl. Dividenden (wo Lots vorhanden)</div>
</td></tr>
<tr><td style="padding:0 12px 16px">
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:10px;font-size:12px">
<tr style="background:#0f172a;color:#e2e8f0;font-size:10px;text-transform:uppercase">
<th align="left" style="padding:9px 8px">Ticker</th>
<th align="right" style="padding:9px 6px">Qty</th>
<th align="right" style="padding:9px 6px">MW €</th>
<th align="right" style="padding:9px 6px">Wt%</th>
<th align="right" style="padding:9px 6px">Tag</th>
<th align="right" style="padding:9px 6px">Cost</th>
<th align="right" style="padding:9px 6px">Gewinn</th>
<th align="right" style="padding:9px 6px">Tot%</th>
<th align="right" style="padding:9px 6px">IRR</th>
</tr>
{''.join(rows)}
</table>
</td></tr>
<tr><td style="padding:0 16px 20px">
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;font-size:12px;color:#64748b;line-height:1.5">
Preise via yfinance · EUR-Umrechnung mit EURUSD · Kein Finanzrat.<br/>
Dashboard: http://127.0.0.1:8765/<br/>
From: bovespamm@gmail.com · To: matthias.mueller@gmx.de
</div></td></tr>
</table></td></tr></table>
</body></html>"""

    out = Path.home() / "Downloads" / "portfolio-email-pretty.html"
    out.write_text(html, encoding="utf-8")
    plain = (
        "Portfolio Overview (HTML-Version – bitte HTML-Ansicht öffnen).\n\n"
        f"Stand: {d['as_of']}\n"
        f"Marktwert EUR: {m(s.get('market_value_eur'), 2)}\n"
        f"Einstand EUR: {m(s.get('cost_basis_eur'), 2)}\n"
        f"Gewinn EUR: {m(s.get('profit_eur'), 2)}\n"
        f"Total Return: {p(s.get('total_return_pct'), 1)}\n"
        f"IRR/Jahr: {p(s.get('irr_annual_pct'), 2)}\n"
        "\nFrom: bovespamm@gmail.com · To: matthias.mueller@gmx.de\n"
    )
    payload = {
        "to": ["matthias.mueller@gmx.de"],
        "subject": f"Portfolio Overview (Dashboard) — {d['as_of']} · HTML",
        "body": plain,
        "body_html": html,
    }
    Path.home().joinpath("Downloads", "gmail_html_send.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(out)
    print("html_len", len(html))
    print("json_bytes", (Path.home() / "Downloads" / "gmail_html_send.json").stat().st_size)


if __name__ == "__main__":
    main()
