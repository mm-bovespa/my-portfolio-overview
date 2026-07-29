"""Local portfolio dashboard HTTP server (password-protected).

Usage:
  python -m portfolio_overview.server
  python -m portfolio_overview.server --port 8765 --password "your-secret"
  set PORTFOLIO_DASHBOARD_PASSWORD=...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from portfolio_overview.analysis import build_allocation_analysis
from portfolio_overview.ai_recommendations import run_ai_recommendations
from portfolio_overview.auth import (
    DEFAULT_AUTH_PATH,
    AuthStore,
    clear_session_cookie_header,
    parse_cookies,
    resolve_auth_store,
    session_cookie_header,
)
from portfolio_overview.web_data import build_dashboard_data

WEB_ROOT = Path(__file__).resolve().parent.parent / "web" / "static"

# Public paths (no session required)
PUBLIC_PATHS = frozenset(
    {
        "/login",
        "/login.html",
        "/api/login",
        "/api/logout",
        "/api/auth/status",
    }
)


class PortfolioHandler(SimpleHTTPRequestHandler):
    """Serve static UI + JSON APIs behind session cookie auth."""

    use_sample: bool = False
    profile_path: Path | None = None
    auth: AuthStore | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[portfolio-web] " + (fmt % args) + "\n")

    # --- HTTP methods ---

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/login", "/login.html"):
            self._serve_login_page()
            return

        if path in ("/api/auth/status", "/api/auth/status/"):
            self._serve_auth_status()
            return

        if path in ("/api/logout", "/api/logout/"):
            # Allow GET logout for simple link
            self._do_logout()
            return

        if not self._is_public(path) and not self._authenticated():
            if path.startswith("/api/"):
                self._json_response(401, {"error": "unauthorized", "login": "/login"})
                return
            self._redirect("/login")
            return

        if path in ("/api/portfolio", "/api/portfolio/"):
            self._serve_json(parsed, kind="portfolio")
            return
        if path in ("/api/analysis", "/api/analysis/"):
            self._serve_json(parsed, kind="analysis")
            return
        if path in ("/api/ai-recommendations", "/api/ai-recommendations/"):
            # Prefer POST; allow GET for convenience
            self._serve_ai_recommendations(parsed)
            return
        if path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()

        # Other static assets under WEB_ROOT require auth
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/api/login",):
            self._do_login()
            return
        if path in ("/api/logout",):
            self._do_logout()
            return
        if path in ("/api/ai-recommendations", "/api/ai-recommendations/"):
            if not self._authenticated():
                self._json_response(401, {"error": "unauthorized", "login": "/login"})
                return
            self._serve_ai_recommendations(parsed)
            return

        self._json_response(404, {"error": "not found"})

    # --- Auth helpers ---

    def _is_public(self, path: str) -> bool:
        if path in PUBLIC_PATHS:
            return True
        # login page only
        return path in ("/login", "/login.html")

    def _session_token(self) -> str | None:
        cookies = parse_cookies(self.headers.get("Cookie"))
        name = self.auth.cookie_name if self.auth else "portfolio_session"
        return cookies.get(name)

    def _authenticated(self) -> bool:
        if self.auth is None:
            return False
        return self.auth.is_authenticated(self._session_token())

    def _redirect(self, location: str, extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()

    def _json_response(
        self,
        status: int,
        payload: dict,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _serve_login_page(self) -> None:
        # If already logged in, go to dashboard
        if self._authenticated():
            self._redirect("/")
            return
        login_path = WEB_ROOT / "login.html"
        if not login_path.is_file():
            self.send_error(500, "login.html missing")
            return
        data = login_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_auth_status(self) -> None:
        self._json_response(
            200,
            {"authenticated": self._authenticated()},
        )

    def _do_login(self) -> None:
        if self.auth is None:
            self._json_response(500, {"error": "auth not configured"})
            return
        data = self._read_json_body()
        # Also accept form-urlencoded
        if not data and self.headers.get("Content-Type", "").startswith(
            "application/x-www-form-urlencoded"
        ):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            qs = parse_qs(raw)
            data = {k: (v[0] if v else "") for k, v in qs.items()}

        password = str(data.get("password") or "")
        if not self.auth.verify_password(password):
            # Constant-ish delay is overkill; avoid leaking timing in response shape
            self._json_response(401, {"error": "invalid password", "ok": False})
            return

        token = self.auth.create_session()
        self._json_response(
            200,
            {"ok": True, "redirect": "/"},
            extra_headers=[("Set-Cookie", session_cookie_header(token))],
        )

    def _do_logout(self) -> None:
        if self.auth is not None:
            self.auth.revoke_session(self._session_token())
        # Prefer redirect for GET, JSON for POST
        if self.command == "GET":
            self._redirect(
                "/login",
                extra_headers=[("Set-Cookie", clear_session_cookie_header())],
            )
            return
        self._json_response(
            200,
            {"ok": True},
            extra_headers=[("Set-Cookie", clear_session_cookie_header())],
        )

    def _serve_json(self, parsed, *, kind: str) -> None:
        qs = parse_qs(parsed.query)
        use_sample = self.use_sample or qs.get("sample", ["0"])[0] in (
            "1",
            "true",
            "yes",
        )
        try:
            if kind == "analysis":
                data = build_allocation_analysis(
                    profile_path=self.profile_path,
                    use_sample=use_sample,
                )
            else:
                data = build_dashboard_data(
                    profile_path=self.profile_path,
                    use_sample=use_sample,
                )
            body = json.dumps(data, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            err = {
                "error": str(exc),
                "trace": traceback.format_exc(),
            }
            body = json.dumps(err).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _serve_ai_recommendations(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        use_sample = self.use_sample or qs.get("sample", ["0"])[0] in (
            "1",
            "true",
            "yes",
        )
        try:
            data = run_ai_recommendations(
                profile_path=self.profile_path,
                use_sample=use_sample,
            )
            self._json_response(200, data)
        except Exception as exc:
            self._json_response(
                500,
                {
                    "error": str(exc),
                    "trace": traceback.format_exc(),
                },
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Portfolio dashboard web server (auth required)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--sample", action="store_true", help="Use sample profile")
    p.add_argument("--profile", type=Path, default=None)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument(
        "--password",
        default=None,
        help="Dashboard password (also env PORTFOLIO_DASHBOARD_PASSWORD). "
        "Saves PBKDF2 hash to .local/auth.json",
    )
    p.add_argument(
        "--auth-file",
        type=Path,
        default=DEFAULT_AUTH_PATH,
        help=f"Path to auth hash file (default: {DEFAULT_AUTH_PATH})",
    )
    args = p.parse_args(argv)

    if not WEB_ROOT.exists():
        print(f"Error: web root missing: {WEB_ROOT}", file=sys.stderr)
        return 1

    password = args.password or os.environ.get("PORTFOLIO_DASHBOARD_PASSWORD")
    try:
        store, generated = resolve_auth_store(
            password=password,
            auth_path=args.auth_file,
            generate_if_missing=True,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    PortfolioHandler.use_sample = args.sample
    PortfolioHandler.profile_path = args.profile
    PortfolioHandler.auth = store

    server = ThreadingHTTPServer((args.host, args.port), PortfolioHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Portfolio dashboard: {url}")
    print(f"Login page:          {url}login")
    print(f"API portfolio:       {url}api/portfolio  (auth required)")
    print(f"API analysis:        {url}api/analysis   (auth required)")
    print(f"Auth file:           {args.auth_file}")
    if generated:
        print()
        print("*** FIRST-TIME PASSWORD (save this; only shown once) ***")
        print(f"    {generated}")
        print("*** Change later with: --password NEW_SECRET ***")
        print()
    print("Ctrl+C to stop.")
    if not args.no_browser:
        try:
            webbrowser.open(url + "login")
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
