"""AI portfolio recommendations via xAI (SpaceXAI / Grok).

Requires env ``XAI_API_KEY`` (or project ``.env``). Never expose the key to the browser.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from portfolio_overview.web_data import build_dashboard_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
XAI_BASE = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")

# Exact user-specified institutional prompt (portfolio data appended separately).
INSTITUTIONAL_PROMPT = """You are a senior portfolio manager and former Goldman Sachs / Citadel / Millennium multi-strategy PM with 25+ years of institutional experience across long/short equity, macro, quant, and multi-asset strategies. You have managed billions in AUM, survived multiple market regimes (2000, 2008, 2020, 2022), and are known for brutally honest, high-signal feedback that prioritizes risk-adjusted returns, capital preservation, and asymmetric upside over narrative or consensus.

Your task is to perform a rigorous institutional-grade analysis of the following investment portfolio.

PORTFOLIO (tickers + optional weights/position sizes/cost basis) are given in the Portfolio Dashboard and available to you.

ANALYSIS REQUIREMENTS – execute in this exact order:

1. Immediate High-Level Verdict (3–5 sentences max)
   - Overall quality rating (Institutional / Professional / Retail / Dangerous)
   - Core thesis of the portfolio as currently constructed
   - Biggest structural strength and biggest structural flaw

2. Position-by-Position Honest Assessment
   For every ticker:
   - Current quality of the business / competitive moat / capital allocation track record
   - Valuation regime (cheap / fair / expensive / bubble territory relative to history and peers)
   - Risk/reward asymmetry over 12–36 months
   - Specific verdict: Hold / Trim / Add / Exit (with conviction level: High / Medium / Low)
   - One-sentence institutional rationale (no fluff)

3. Portfolio Construction Critique
   - Concentration risk (single-name, sector, factor, geography, style)
   - Correlation structure and hidden beta exposures
   - Liquidity profile and capacity considerations
   - Missing exposures or over-exposures relative to a sophisticated multi-asset or long-only institutional benchmark
   - Factor exposures (value, growth, quality, momentum, low-vol, size, etc.)

4. Actionable Recommendations (be specific and prioritized)
   - Exact positions to reduce or exit (with suggested size and reasoning)
   - Exact positions to add to (with suggested size)
   - New tickers or instruments to introduce (equities, ETFs, options overlays, hedges, alternatives) with clear rationale and sizing guidance
   - Ideal target allocation ranges after changes
   - Any tactical hedges or risk mitigants that should be considered immediately

5. Forward-Looking Risk & Opportunity Map
   - Key macro, fundamental, or technical risks that could materially impair this book
   - Highest-conviction opportunities the current portfolio is missing
   - Regime dependency (what market environment this portfolio thrives/dies in)

Rules of engagement:
- Zero sugarcoating. If something is mediocre, crowded, or structurally flawed, say it directly.
- Prioritize permanent capital loss risk and opportunity cost over short-term price action.
- Use precise institutional language (drawdown, Sharpe, information ratio, factor loadings, etc.) where relevant.
- Prefer quality + asymmetric setups over pure momentum or narrative trades.
- If data is missing (weights, time horizon, risk tolerance, constraints), explicitly state your assumptions.
- End with a concise “Priority Action List” of the 3–5 highest-leverage changes ranked by impact.

Begin analysis now."""


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from project .env into os.environ (no override)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        # utf-8-sig strips optional BOM from Windows editors
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def format_portfolio_for_llm(data: dict[str, Any]) -> str:
    """Compact portfolio dump for the model (weights, MV, cost, returns, day)."""
    s = data.get("summary") or {}
    lines = [
        "=== PORTFOLIO SNAPSHOT (from live Dashboard) ===",
        f"As of: {data.get('as_of')}",
        f"EURUSD: {data.get('eurusd')}",
        f"Positions: {s.get('position_count')}",
        f"Market value EUR: {s.get('market_value_eur')}",
        f"Cost basis EUR: {s.get('cost_basis_eur')}",
        f"Dividends EUR: {s.get('dividends_eur')}",
        f"Profit EUR: {s.get('profit_eur')}",
        f"Total return %: {s.get('total_return_pct')}",
        f"IRR annual %: {s.get('irr_annual_pct')}",
        f"Risk tolerance (profile): {(data.get('profile') or {}).get('risk_tolerance')}",
        f"Horizon (profile): {(data.get('profile') or {}).get('investment_horizon')}",
        f"Strategy (profile): {(data.get('profile') or {}).get('investment_strategy')}",
        "",
        "Columns: Ticker | Qty | Price€ | MV€ | Wt% | Day% | Day€ | Cost€ | Div€ | Profit€ | Tot% | IRR%/y | Wtd buy | Lots",
        "-" * 100,
    ]
    positions = sorted(
        data.get("positions") or [],
        key=lambda p: float(p.get("weight_pct") or 0),
        reverse=True,
    )
    for p in positions:
        r = p.get("returns") or {}
        lines.append(
            f"{p.get('ticker')}\t"
            f"qty={p.get('shares')}\t"
            f"px_eur={_n(p.get('price_eur'))}\t"
            f"mv={_n(p.get('market_value_eur'))}\t"
            f"wt%={_n(p.get('weight_pct'), 1)}\t"
            f"day%={_n(p.get('day_change_pct'), 2)}\t"
            f"day€={_n(p.get('day_change_eur'), 0)}\t"
            f"cost={_n(r.get('cost_basis_eur'), 0)}\t"
            f"div={_n(r.get('dividends_eur_total'), 0)}\t"
            f"profit={_n(r.get('profit_eur'), 0)}\t"
            f"tot%={_n(r.get('total_return_pct'), 1)}\t"
            f"irr%={_n(r.get('irr_annual_pct'), 2)}\t"
            f"wtd_buy={p.get('avg_buy_date_weighted') or '—'}\t"
            f"lots={p.get('lot_count') or 0}"
        )
    lines.append("")
    lines.append(
        "Assumptions you may use if not specified by the user: "
        "EUR reporting currency; long-only; long-term horizon (10+ years); "
        "moderate risk tolerance; no leverage mandate; no explicit sector constraints."
    )
    return "\n".join(lines)


def _n(v: Any, d: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return str(v)


def _chat_completion(api_key: str, user_content: str, model: str) -> str:
    """Call xAI OpenAI-compatible chat completions API."""
    url = f"{XAI_BASE.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are the institutional PM described by the user. Follow their analysis structure exactly. Write in clear English.",
            },
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.35,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "my-portfolio-overview/ai-recommendations",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"xAI API HTTP {e.code}: {err_body[:800]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"xAI API network error: {e}") from e

    choices = raw.get("choices") or []
    if not choices:
        raise RuntimeError(f"xAI API returned no choices: {str(raw)[:400]}")
    msg = choices[0].get("message") or {}
    text = msg.get("content")
    if not text:
        raise RuntimeError("xAI API returned empty content")
    return text


def run_ai_recommendations(
    *,
    profile_path: Path | None = None,
    use_sample: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    """Build live portfolio snapshot and return institutional AI analysis."""
    _load_dotenv()
    api_key = os.environ.get("XAI_API_KEY") or os.environ.get("xai_api_key")
    if not api_key:
        raise RuntimeError(
            "XAI_API_KEY is not set. Create C:\\projects\\my-portfolio-overview\\.env "
            "with line: XAI_API_KEY=your_key  (from https://console.x.ai)"
        )

    data = build_dashboard_data(
        profile_path=profile_path,
        use_sample=use_sample,
    )
    portfolio_block = format_portfolio_for_llm(data)
    user_content = (
        INSTITUTIONAL_PROMPT
        + "\n\n"
        + portfolio_block
        + "\n\n(End of portfolio data from Dashboard.)"
    )

    use_model = model or DEFAULT_MODEL
    analysis = _chat_completion(api_key, user_content, use_model)

    return {
        "ok": True,
        "model": use_model,
        "as_of": data.get("as_of"),
        "eurusd": data.get("eurusd"),
        "summary": data.get("summary"),
        "analysis": analysis,
        "portfolio_snapshot": portfolio_block,
        "disclaimer": (
            "AI-generated institutional-style analysis for informational purposes only. "
            "Not financial advice. Verify independently."
        ),
    }
