"""Build a short, pretty HTML email under 12k and print path."""
from __future__ import annotations

import html as H
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from portfolio_overview.web_data import build_dashboard_data


def esc(x):
    return H.escape("" if x is None else str(x))


def m(n, d=0):
    return "—" if n is None else f"{n:,.{d}f}"


def p(n, d=1, signed=True):
    if n is None:
        return "—"
    return f"{n:+.{d}f}%" if signed else f"{n:.{d}f}%"


def c(n):
    if n is None:
        return "#64748b"
    return "#15803d" if n >= 0 else "#b91c1c"


def main():
    d = build_dashboard_data()
    s = d["summary"]
    positions = sorted(
        d["positions"], key=lambda x: x.get("weight_pct") or 0, reverse=True
    )

    rows = []
    for i, pos in enumerate(positions):
        r = pos.get("returns") or {}
        bg = "#f8fafc" if i % 2 == 0 else "#fff"
        day, tot, irr, prof = (
            pos.get("day_change_pct"),
            r.get("total_return_pct"),
            r.get("irr_annual_pct"),
            r.get("profit_eur"),
        )
        rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:7px 6px;font-weight:700;border-bottom:1px solid #e2e8f0'>{esc(pos.get('ticker'))}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0'>{m(pos.get('shares'),0)}</td>"
            f"<td style='padding:7px 4px;text-align:right;font-weight:600;border-bottom:1px solid #e2e8f0'>€{m(pos.get('market_value_eur'),0)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0'>{p(pos.get('weight_pct'),1,False)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0;color:{c(day)}'>{p(day,1)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0'>€{m(r.get('cost_basis_eur'),0)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0;color:{c(prof)}'>€{m(prof,0)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0;color:{c(tot)}'>{p(tot,0)}</td>"
            f"<td style='padding:7px 4px;text-align:right;border-bottom:1px solid #e2e8f0;color:{c(irr)}'>{p(irr,1)}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Portfolio</title></head>
<body style="margin:0;padding:0;background:#e2e8f0;font-family:Segoe UI,Roboto,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;padding:14px"><tr><td align="center">
<table width="100%" style="max-width:700px;background:#fff;border-radius:12px;border:1px solid #cbd5e1" cellpadding="0" cellspacing="0">
<tr><td style="background:#0f172a;padding:18px 16px">
<div style="color:#93c5fd;font-size:11px;font-weight:600;letter-spacing:.08em">MY-PORTFOLIO-OVERVIEW</div>
<div style="color:#fff;font-size:20px;font-weight:700;margin-top:4px">Portfolio Dashboard</div>
<div style="color:#cbd5e1;font-size:12px;margin-top:6px">Stand <b style="color:#fff">{esc(d['as_of'])}</b> · EURUSD <b style="color:#fff">{d['eurusd']:.4f}</b> · {s.get('position_count')} Positionen</div>
</td></tr>
<tr><td style="padding:12px 10px 4px">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">MARKTWERT</div><div style="font-size:16px;font-weight:700">€ {m(s.get('market_value_eur'),0)}</div><div style="font-size:10px;color:#94a3b8">$ {m(s.get('market_value_usd'),0)}</div></div></td>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">EINSTAND</div><div style="font-size:16px;font-weight:700">€ {m(s.get('cost_basis_eur'),0)}</div><div style="font-size:10px;color:#94a3b8">mit Lots</div></div></td>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">DIVIDENDEN</div><div style="font-size:16px;font-weight:700">€ {m(s.get('dividends_eur'),0)}</div><div style="font-size:10px;color:#94a3b8">seit Kauf</div></div></td>
</tr><tr>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">GEWINN</div><div style="font-size:16px;font-weight:700">€ {m(s.get('profit_eur'),0)}</div><div style="font-size:10px;color:#94a3b8">Kurs+Div</div></div></td>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">TOTAL RETURN</div><div style="font-size:16px;font-weight:700">{p(s.get('total_return_pct'),1)}</div><div style="font-size:10px;color:#94a3b8">Portfolio</div></div></td>
<td width="33%" style="padding:3px"><div style="background:#f1f5f9;border-radius:8px;padding:10px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b">IRR / JAHR</div><div style="font-size:16px;font-weight:700">{p(s.get('irr_annual_pct'),2)}</div><div style="font-size:10px;color:#94a3b8">gewichtet</div></div></td>
</tr></table></td></tr>
<tr><td style="padding:8px 12px 4px"><div style="font-size:14px;font-weight:700">Holdings (nach Wt %)</div></td></tr>
<tr><td style="padding:0 10px 12px">
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:8px;font-size:11px">
<tr style="background:#0f172a;color:#e2e8f0;font-size:9px;text-transform:uppercase">
<th align="left" style="padding:8px 6px">Ticker</th>
<th align="right" style="padding:8px 4px">Qty</th>
<th align="right" style="padding:8px 4px">MW €</th>
<th align="right" style="padding:8px 4px">Wt%</th>
<th align="right" style="padding:8px 4px">Tag</th>
<th align="right" style="padding:8px 4px">Cost</th>
<th align="right" style="padding:8px 4px">Gewinn</th>
<th align="right" style="padding:8px 4px">Tot%</th>
<th align="right" style="padding:8px 4px">IRR</th>
</tr>
{''.join(rows)}
</table></td></tr>
<tr><td style="padding:0 12px 16px"><div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;font-size:11px;color:#64748b;line-height:1.45">
Tot% und IRR inkl. Dividenden (wo Lots). Kurse yfinance, EUR via EURUSD. Kein Finanzrat.<br>
Dashboard: http://127.0.0.1:8765/ · From: bovespamm@gmail.com · To: matthias.mueller@gmx.de
</div></td></tr>
</table></td></tr></table></body></html>"""

    out = Path.home() / "Downloads" / "portfolio-email-short.html"
    out.write_text(html, encoding="utf-8")
    plain = (
        f"Portfolio Overview HTML – bitte HTML-Ansicht öffnen.\n\n"
        f"Stand: {d['as_of']}\n"
        f"Marktwert: € {m(s.get('market_value_eur'), 2)}\n"
        f"Einstand: € {m(s.get('cost_basis_eur'), 2)}\n"
        f"Gewinn: € {m(s.get('profit_eur'), 2)}\n"
        f"Total Return: {p(s.get('total_return_pct'), 1)}\n"
        f"IRR/Jahr: {p(s.get('irr_annual_pct'), 2)}\n"
    )
    payload = {
        "to": ["matthias.mueller@gmx.de"],
        "subject": f"Portfolio Overview — {d['as_of']} (HTML)",
        "body": plain,
        "body_html": html,
    }
    Path.home().joinpath("Downloads", "gmail_short_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(out)
    print(len(html))


if __name__ == "__main__":
    main()
