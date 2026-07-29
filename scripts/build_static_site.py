#!/usr/bin/env python3
"""Build a password-protected static HTML portfolio site for GitHub Pages.

Usage:
  python scripts/build_static_site.py --password "Navigation1!"
  set DASHBOARD_PASSWORD=...
  set PROFILE_JSON=...   # optional; else uses local finance profile

Output: site/  (login + encrypted portfolio payload)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402

PBKDF2_ITERATIONS = 390_000


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def derive_key(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def encrypt_payload(password: str, payload: dict) -> dict:
    salt = secrets.token_bytes(16)
    key = derive_key(password, salt)
    # Store password verify hash (same key material, separate purpose)
    verify = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plain = json.dumps(payload, default=str).encode("utf-8")
    ct = aes.encrypt(nonce, plain, None)
    return {
        "v": 1,
        "kdf": "pbkdf2_sha256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ct).decode("ascii"),
        "verify": base64.b64encode(verify).decode("ascii"),
    }


def build_portfolio_payload(profile_path: Path | None, use_sample: bool, live_prices: bool) -> dict:
    if live_prices:
        try:
            from portfolio_overview.web_data import build_dashboard_data

            return build_dashboard_data(profile_path=profile_path, use_sample=use_sample)
        except Exception as e:
            print(f"Live price build failed ({e}); falling back to holdings-only snapshot.", file=sys.stderr)

    # Holdings-only snapshot from profile (no yfinance)
    import copy

    profile_file = profile_path
    if profile_file is None and not use_sample:
        profile_file = (
            Path.home() / ".grokbuild" / "skills" / "my-finance-profile" / "profile.json"
        )
    if use_sample:
        profile_file = PROJECT_ROOT / "samples" / "sample_profile.json"

    if profile_file is None or not Path(profile_file).is_file():
        raise FileNotFoundError(f"Profile not found: {profile_file}")

    raw = json.loads(Path(profile_file).read_text(encoding="utf-8"))
    holdings = []
    for h in raw.get("holdings") or []:
        if not isinstance(h, dict) or not h.get("ticker"):
            continue
        purchases = h.get("purchases") or []
        shares = h.get("shares")
        if shares is None and purchases:
            shares = sum(float(p.get("shares") or 0) for p in purchases)
        holdings.append(
            {
                "ticker": str(h["ticker"]).upper(),
                "shares": float(shares or 0),
                "avg_cost_eur": h.get("avg_cost_eur"),
                "buy_date": h.get("buy_date"),
                "avg_buy_date_weighted": h.get("avg_buy_date_weighted"),
                "lot_count": len(purchases),
                "purchases": purchases,
                "cost_basis_eur": h.get("cost_basis_eur"),
                "dividends_eur_total": h.get("dividends_eur_total"),
            }
        )

    return {
        "as_of": date.today().isoformat(),
        "source": str(profile_file),
        "live_prices": False,
        "profile": {
            "risk_tolerance": raw.get("risk_tolerance"),
            "investment_horizon": raw.get("investment_horizon"),
            "investment_strategy": raw.get("investment_strategy"),
        },
        "holdings": holdings,
        "built_at": datetime.utcnow().isoformat() + "Z",
    }


def write_site(out_dir: Path, enc: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.enc.json").write_text(
        json.dumps(enc, indent=2) + "\n", encoding="utf-8"
    )
    # index.html is the SPA (login + dashboard)
    template = (PROJECT_ROOT / "static_site" / "index.html").read_text(encoding="utf-8")
    (out_dir / "index.html").write_text(template, encoding="utf-8")
    # 404 redirect for SPA-ish GH pages
    (out_dir / "404.html").write_text(
        '<!DOCTYPE html><meta http-equiv="refresh" content="0;url=./index.html">',
        encoding="utf-8",
    )
    print(f"Wrote {out_dir / 'index.html'}")
    print(f"Wrote {out_dir / 'data.enc.json'}")


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Build password-protected static portfolio site")
    p.add_argument("--password", default=os.environ.get("DASHBOARD_PASSWORD"))
    p.add_argument("--profile", type=Path, default=None)
    p.add_argument("--sample", action="store_true")
    p.add_argument("--out", type=Path, default=PROJECT_ROOT / "site")
    p.add_argument(
        "--no-live-prices",
        action="store_true",
        help="Skip yfinance; embed holdings only",
    )
    p.add_argument(
        "--from-profile-json-env",
        action="store_true",
        help="Read full profile JSON from env PROFILE_JSON",
    )
    args = p.parse_args(argv)

    password = args.password
    if not password:
        print(
            "Error: set --password or DASHBOARD_PASSWORD",
            file=sys.stderr,
        )
        return 1

    profile_path = args.profile
    if args.from_profile_json_env:
        raw = os.environ.get("PROFILE_JSON")
        if not raw:
            print("Error: PROFILE_JSON env empty", file=sys.stderr)
            return 1
        tmp = PROJECT_ROOT / ".local" / "_ci_profile.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(raw, encoding="utf-8")
        profile_path = tmp

    print("Building portfolio payload…")
    payload = build_portfolio_payload(
        profile_path,
        use_sample=args.sample,
        live_prices=not args.no_live_prices,
    )
    n = len(payload.get("positions") or payload.get("holdings") or [])
    print(f"Positions: {n}  as_of={payload.get('as_of')} live={payload.get('live_prices', True)}")

    enc = encrypt_payload(password, payload)
    write_site(args.out, enc)
    print("Done. Deploy the 'site/' folder via GitHub Pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
