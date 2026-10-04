"""Localhost-only, read-only HTTP replay. Exact routes; never a file browser."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

from .replay import ReplayLibrary, SLOTS

ASSETS = {"/": ("index.html", "text/html"), "/demo.css": ("demo.css", "text/css"), "/demo.js": ("demo.js", "text/javascript")}


def make_server(library, choices=None, port=8765):
    defaults = choices or {}
    library.select(defaults)  # Validate explicit choices before opening the socket.
    assets = {route: (files("soc_guard").joinpath("presentation", name).read_bytes(), mime) for route, (name, mime) in ASSETS.items()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log request paths or untrusted payloads.

        def do_GET(self):
            allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in allowed_hosts or (origin and origin not in {"http://" + h for h in allowed_hosts}) or self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_error(403, "Local origin required")
                return
            if len(self.path) > 2048:
                self.send_error(400)
                return
            parsed = urlsplit(self.path)
            try:
                if parsed.path in assets and not parsed.query:
                    body, mime = assets[parsed.path]
                elif parsed.path == "/api/catalog" and not parsed.query:
                    body, mime = json.dumps(library.catalog()).encode(), "application/json"
                elif parsed.path == "/api/replay":
                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) - SLOTS.keys() or any(len(v) != 1 or not v[0] for v in query.values()):
                        raise ValueError("Invalid selection")
                    selection = defaults | {k: v[0] for k, v in query.items()}
                    body, mime = json.dumps(library.select(selection)).encode(), "application/json"
                else:
                    self.send_error(404)
                    return
            except ValueError:
                self.send_error(400, "Invalid recorded run selection")
                return
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src blob:; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def launch(args):
    choices = {slot: getattr(args, slot + "_run") for slot in SLOTS if getattr(args, slot + "_run")}
    library = ReplayLibrary()
    if args.list_runs:
        for run in library.catalog()["runs"]:
            print(f"{run['run_id']}  {run['kind']}  {run['scenario']} / {run['mode']}  {run['status']}  {run['model'] if run['kind'] == 'live_model' else 'No AI'}")
        return
    try:
        server = make_server(library, choices, args.port)
    except (ValueError, OSError) as exc:
        print("Cannot start replay: " + (str(exc) if isinstance(exc, ValueError) else "local port unavailable; choose --port"))
        raise SystemExit(2)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"MCP SOC Guard · Recorded run replay\n{url}\nSynthetic data · Local export simulation\nNo model calls. Ctrl+C stops the server.", flush=True)
    if args.open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
