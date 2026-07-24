"""Local portfolio dashboard HTTP server.

Usage:
  python -m portfolio_overview.server
  python -m portfolio_overview.server --port 8765 --sample
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from portfolio_overview.web_data import build_dashboard_data

WEB_ROOT = Path(__file__).resolve().parent.parent / "web" / "static"


class PortfolioHandler(SimpleHTTPRequestHandler):
    """Serve static UI + /api/portfolio JSON."""

    use_sample: bool = False
    profile_path: Path | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[portfolio-web] " + (fmt % args) + "\n")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/api/portfolio", "/api/portfolio/"):
            self._serve_api(parsed)
            return
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def _serve_api(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        use_sample = self.use_sample or qs.get("sample", ["0"])[0] in (
            "1",
            "true",
            "yes",
        )
        try:
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Portfolio dashboard web server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--sample", action="store_true", help="Use sample profile")
    p.add_argument("--profile", type=Path, default=None)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)

    if not WEB_ROOT.exists():
        print(f"Error: web root missing: {WEB_ROOT}", file=sys.stderr)
        return 1

    PortfolioHandler.use_sample = args.sample
    PortfolioHandler.profile_path = args.profile

    server = ThreadingHTTPServer((args.host, args.port), PortfolioHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Portfolio dashboard: {url}")
    print(f"API:                 {url}api/portfolio")
    print("Ctrl+C to stop.")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
