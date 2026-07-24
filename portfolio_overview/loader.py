"""Load holdings from my-finance-profile JSON (or a sample file)."""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any


DEFAULT_PROFILE_PATH = (
    pathlib.Path.home()
    / ".grokbuild"
    / "skills"
    / "my-finance-profile"
    / "profile.json"
)

ENV_PROFILE_PATH = "PORTFOLIO_PROFILE_PATH"


def default_profile_path() -> pathlib.Path:
    """Resolve profile path from env or default skill location."""
    override = os.environ.get(ENV_PROFILE_PATH)
    if override:
        return pathlib.Path(override).expanduser()
    return DEFAULT_PROFILE_PATH


def sample_profile_path() -> pathlib.Path:
    """Path to bundled sample profile (repo samples/)."""
    return pathlib.Path(__file__).resolve().parent.parent / "samples" / "sample_profile.json"


def load_profile(path: pathlib.Path) -> dict[str, Any]:
    """Load and parse a profile JSON file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Profile not found: {path}\n"
            f"Populate my-finance-profile or pass --profile / --sample.\n"
            f"Default path: {DEFAULT_PROFILE_PATH}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Profile root must be an object: {path}")
    return data


def extract_holdings(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized holdings usable for pricing.

    Rows without a positive shares/quantity are skipped (caller may warn).
    """
    raw = profile.get("holdings") or []
    if not isinstance(raw, list):
        raise ValueError("profile['holdings'] must be a list")

    usable: list[dict[str, Any]] = []
    skipped: list[str] = []

    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qty_raw = item.get("shares", item.get("quantity"))
        if qty_raw is None or qty_raw == "":
            skipped.append(ticker)
            continue
        try:
            shares = float(qty_raw)
        except (TypeError, ValueError):
            skipped.append(ticker)
            continue
        if shares <= 0:
            skipped.append(ticker)
            continue
        holding: dict[str, Any] = {"ticker": ticker, "shares": shares}
        cost_raw = item.get("avg_cost_usd", item.get("avg_buy_price"))
        if cost_raw not in (None, ""):
            try:
                holding["avg_cost_usd"] = float(cost_raw)
            except (TypeError, ValueError):
                pass
        if item.get("buy_date"):
            holding["buy_date"] = str(item["buy_date"])
        if item.get("notes"):
            holding["notes"] = str(item["notes"])
        usable.append(holding)

    if skipped:
        print(
            "Warning: skipping holdings without valid quantity: "
            + ", ".join(skipped),
            file=sys.stderr,
        )
    return usable


def load_holdings(
    profile_path: pathlib.Path | None = None,
    *,
    use_sample: bool = False,
) -> tuple[list[dict[str, Any]], pathlib.Path]:
    """Load holdings list and the path used.

    Returns (holdings, path).
    """
    if use_sample:
        path = sample_profile_path()
    elif profile_path is not None:
        path = profile_path
    else:
        path = default_profile_path()

    profile = load_profile(path)
    holdings = extract_holdings(profile)
    return holdings, path
