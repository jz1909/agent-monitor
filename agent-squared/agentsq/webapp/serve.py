"""Local dashboard for the experiment runs.

    python -m agentsq.webapp.serve

Serves a static page plus a small JSON API backed by the sqlite mirror. Every
API request re-syncs first (a stat of each results.jsonl), so finishing an
experiment and reloading the browser is enough to see it -- every family under
runs/ is synced, whether or not the dashboard is currently showing it.

Binds to localhost only: this exposes local result files and has no auth.
"""

import argparse
import json
import mimetypes
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from agentsq.analysis import db
from agentsq.analysis.results import RUNS_ROOT

STATIC = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    server_version = "agentsq-dashboard"

    # --- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def _error(self, code, message):
        self._json({"error": message}, code)

    # --- routing -----------------------------------------------------------
    def do_GET(self):
        parts = urlparse(self.path)
        path = unquote(parts.path)
        try:
            if path.startswith("/api/"):
                return self._api(path, parse_qs(parts.query))
            return self._static(path)
        except BrokenPipeError:
            pass
        except Exception as exc:                      # keep the server alive
            self._error(500, f"{type(exc).__name__}: {exc}")

    do_HEAD = do_GET

    def _api(self, path, query):
        experiment = (query.get("experiment") or [None])[0]
        conn = db.connect(self.server.db_path)
        try:
            report = db.sync(conn, self.server.runs_root)
            if path == "/api/experiments":
                return self._json({"sync": report,
                                   "experiments": db.experiments(conn)})
            if path == "/api/payload":
                body = db.payload(conn, experiment)
                body["sync"] = report
                return self._json(body)
            if path == "/api/runs":
                return self._json({"sync": report,
                                   "runs": db.all_runs(conn, experiment)})
            if path.startswith("/api/runs/"):
                # /api/runs/<experiment>/<run>
                rest = path[len("/api/runs/"):].strip("/").split("/", 1)
                if len(rest) != 2:
                    return self._error(400, "expected /api/runs/<experiment>/<run>")
                detail = db.run_detail(conn, rest[0], rest[1])
                if detail is None:
                    return self._error(404, f"no such run: {rest[0]}/{rest[1]}")
                return self._json(detail)
            if path == "/api/sync":
                return self._json(report)
            return self._error(404, f"no such endpoint: {path}")
        except sqlite3.Error as exc:
            return self._error(500, f"sqlite: {exc}")
        finally:
            conn.close()

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not target.is_file() or STATIC not in target.parents:
            return self._error(404, f"not found: {path}")
        ctype, _ = mimetypes.guess_type(target.name)
        self._send(200, target.read_bytes(), ctype or "application/octet-stream")


def serve(host="127.0.0.1", port=8000, db_path=db.DB_PATH, runs_root=RUNS_ROOT,
          open_browser=False, verbose=False):
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.db_path, httpd.runs_root, httpd.verbose = db_path, runs_root, verbose

    conn = db.connect(db_path)
    report = db.sync(conn, runs_root)
    families = ", ".join(f"{e['experiment']} ({e['n_runs']})"
                         for e in db.experiments(conn)) or "none found"
    conn.close()

    url = f"http://{host}:{port}/"
    print(f"runs root: {runs_root}")
    print(f"families : {families}")
    print(f"database : {db_path}")
    print(f"synced   : {report['total']} run(s) "
          f"(+{len(report['added'])} new, ~{len(report['updated'])} updated, "
          f"-{len(report['removed'])} removed)")
    print(f"serving  : {url}   (ctrl-c to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--db", type=Path, default=db.DB_PATH)
    p.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    p.add_argument("--open", action="store_true", help="open a browser")
    p.add_argument("--verbose", action="store_true", help="log every request")
    args = p.parse_args(argv)
    serve(args.host, args.port, args.db, args.runs_root, args.open, args.verbose)


if __name__ == "__main__":
    main()
