# my-portfolio-overview

Simple, clean **terminal overview** of your share holdings.

Loads positions from the local **[my-finance-profile](https://github.com)** skill data file, fetches live prices with [yfinance](https://github.com/ranaroussi/yfinance), and prints:

| Column | Meaning |
|--------|---------|
| Ticker | Symbol |
| Qty | Number of shares |
| Ccy | Quote currency of the live price (USD / EUR / …) |
| Price | Latest price in quote currency |
| Price € | Same price converted to EUR via live **EURUSD** |
| Value € | Qty × Price € |
| Day % | Daily change vs previous close |
| Wt % | Weight of EUR market value |

Plus **total portfolio value in EUR** (and USD equivalent at the same FX).

**Buy prices** in the profile (`avg_cost_eur`) are always stored in **euros**.

> **v1 scope:** shares only. Long-term vision is a 360° view (real estate, cash, brokers, dividends, strategy tools). Architecture keeps personal data separate from this public CLI.

---

## Quick start (one-time setup)

```bash
git clone https://github.com/mm-bovespa/my-portfolio-overview.git
cd my-portfolio-overview
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

### Demo without personal data

```bash
python -m portfolio_overview --sample
```

### Your real holdings

1. Maintain holdings with the **my-finance-profile** skill (JSON at  
   `~/.grokbuild/skills/my-finance-profile/profile.json`).
2. Each holding needs at least `ticker` and `shares`.
3. Run:

```bash
python -m portfolio_overview
```

**Custom profile path:**

```bash
python -m portfolio_overview --profile path\to\profile.json
# or
set PORTFOLIO_PROFILE_PATH=path\to\profile.json   # Windows
export PORTFOLIO_PROFILE_PATH=path/to/profile.json  # Unix
python -m portfolio_overview
```

Optional install as a console script:

```bash
pip install -e .
portfolio-overview --sample
```

---

## Holding data format

```json
{
  "holdings": [
    {
      "ticker": "AAPL",
      "shares": 12,
      "avg_cost_eur": 148.5,
      "buy_date": "2022-06-15",
      "notes": "optional"
    }
  ]
}
```

- **Required for the overview:** `ticker`, `shares` (alias: `quantity`)
- **Optional:** `avg_cost_eur` (always euros), `buy_date`, `notes`
- Rows without a valid quantity are **skipped** with a warning

### Managing holdings (my-finance-profile helper)

If you use the Grok skill helper on this machine:

```bash
python "%USERPROFILE%\.grok\skills\my-finance-profile\references\finance_profile.py" list-holdings
python "%USERPROFILE%\.grok\skills\my-finance-profile\references\finance_profile.py" add-holding --ticker AAPL --shares 12 --avg-cost 148.5
python "%USERPROFILE%\.grok\skills\my-finance-profile\references\finance_profile.py" remove-holding --ticker NOV
```

---

## Web dashboard (password-protected)

```bash
cd my-portfolio-overview
.\.venv\Scripts\Activate.ps1   # Windows
python -m portfolio_overview.server --port 8765
```

Open **http://127.0.0.1:8765/login** — the dashboard and APIs require a session cookie after login.

**Password setup**

| Method | Effect |
|--------|--------|
| First start (no config) | Generates a random password, prints it **once**, saves PBKDF2 hash to `.local/auth.json` |
| `--password SECRET` | Sets/resets the password and saves the hash |
| Env `PORTFOLIO_DASHBOARD_PASSWORD` | Same as `--password` |

```bash
python -m portfolio_overview.server --password "your-strong-secret"
```

- Only a **hash** is stored (PBKDF2-SHA256); the plaintext password is never written to disk.
- `.local/auth.json` is **gitignored** — do not commit it.
- Sessions: HttpOnly cookie, 12h sliding expiry, in-process only.
- For HTTPS tunnels (Cloudflare / ngrok), set `PORTFOLIO_COOKIE_SECURE=1` so login cookies work.

### Public static site (GitHub Pages)

Password-protected **static HTML** deploy (works worldwide, no local server):

1. Build (embeds current holdings, AES-encrypted with your dashboard password):
   ```powershell
   python scripts/build_static_site.py --password "YourPassword"
   ```
2. Commit the generated `site/` folder and push to `main`.
3. In GitHub: **Settings → Pages → Source: GitHub Actions**.
4. Workflow `.github/workflows/deploy-pages.yml` publishes automatically.

Public URL (after first successful deploy):  
`https://mm-bovespa.github.io/my-portfolio-overview/`

Optional CI rebuild: store secrets `DASHBOARD_PASSWORD` and `PROFILE_JSON`, then run workflow_dispatch with rebuild=true.

### AI Recommendations

Dashboard button **AI Recommendations** runs an institutional-style portfolio critique via **xAI Grok** (`grok-4.5`).

1. Create `C:\projects\my-portfolio-overview\.env` (gitignored):
   ```
   XAI_API_KEY=your_key_from_console.x.ai
   ```
2. Restart the server.
3. Log in → click **AI Recommendations** (1–3 minutes; uses live holdings/weights/returns from the dashboard).

Not financial advice — AI-generated analysis only.

### Access from anywhere (temporary public URL)

Keep the local server running, then open an HTTPS tunnel to it (password still required):

```powershell
# Terminal 1 — dashboard (from project folder)
$env:PORTFOLIO_COOKIE_SECURE = "1"
.\.venv\Scripts\python.exe -m portfolio_overview.server --port 8765 --no-browser

# Terminal 2 — public tunnel
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8765
```

Cloudflare prints a URL like `https://….trycloudflare.com`. That URL changes each time you restart a **quick** tunnel. For a fixed domain, create a named Cloudflare Tunnel (free account).

## Privacy

- **Never commit** real `profile.json` or broker exports.
- This repo only ships `samples/sample_profile.json` (fictional positions).
- `.gitignore` blocks common personal-data filenames and dashboard auth files.

---

## Project layout

```
my-portfolio-overview/
  portfolio_overview/     # CLI package
    loader.py             # read profile JSON
    prices.py             # yfinance
    display.py            # table + weights
    cli.py
  samples/                # demo data only
  tests/
  requirements.txt
  README.md
```

### Design (ready for later extensions)

| Future feature | Where it plugs in |
|----------------|-------------------|
| Dividend summing | New module; join on ticker |
| Bank/broker connectors | Write normalized `holdings` into the same profile JSON |
| n8n / TradingView strategies | Read-only consumers of profile/signals — not coupled to the table path |
| Real estate / cash (360°) | New top-level arrays in the profile store; overview gains sections |

Personal **mutations** of holdings stay in the skill/helper; this app **reads** and **displays**.

---

## Web dashboard

Local webpage with live prices, EUR conversion, expandable **purchase lots**, total return %, and IRR:

```bash
# from project root, with venv active + yfinance installed
python -m portfolio_overview.server
```

Then open: **http://127.0.0.1:8765/**

Options:

```bash
python -m portfolio_overview.server --port 8765
python -m portfolio_overview.server --sample          # demo data
python -m portfolio_overview.server --no-browser
```

APIs:
- `GET /api/portfolio` → JSON (summary + positions + lots)
- `GET /api/analysis` → sector/region weights + **performance vs indexes** (1y / 5y / 10y / full IRR)

In the UI: **Analyze Portfolio** opens a popup with:
- Portfolio vs S&P 500 (SPY), Dow (DIA), Euro Stoxx 50 (FEZ), World (VT) — total return & annualized IRR
- Sector/region allocation charts (your portfolio only)

## Tests

```bash
python -m unittest discover -s tests -v
```

(Network not required for unit tests.)

---

## Requirements

- Python 3.10+
- Internet access for live prices (yfinance / Yahoo Finance)

---

## License

MIT — see project metadata in `pyproject.toml`.
