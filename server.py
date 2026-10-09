"""Local clone of https://obol.sh/ — same pages, live sale data proxied from the original."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM = "https://obol.sh"
PORT = 8080

PAGES = {
    "/": ROOT / "index.html",
    "/docs": ROOT / "docs" / "index.html",
    "/docs/": ROOT / "docs" / "index.html",
    "/terms": ROOT / "terms" / "index.html",
    "/terms/": ROOT / "terms" / "index.html",
    "/privacy": ROOT / "privacy" / "index.html",
    "/privacy/": ROOT / "privacy" / "index.html",
    "/risk": ROOT / "risk" / "index.html",
    "/risk/": ROOT / "risk" / "index.html",
}

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".gif": "image/gif",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                self.proxy(self.path)
                return
            image = re.fullmatch(r"/d/(\d+)/image\.gif", path)
            if image:
                self.proxy(path)
                return
            screen = re.fullmatch(r"/d/(\d+)/os/?", path)
            if screen:
                self.daemon_screen(screen.group(1))
                return
            if path in PAGES:
                self.send_bytes(PAGES[path].read_bytes(), "text/html; charset=utf-8")
                return
            target = (ROOT / path.lstrip("/")).resolve()
            if target.is_file() and ROOT in target.parents:
                self.send_bytes(target.read_bytes(), TYPES.get(target.suffix, "application/octet-stream"))
                return
            self.send_error(404)
        except Exception as exc:
            body = str(exc).encode("utf-8", "replace")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def daemon_screen(self, token_id):
        html = (ROOT / "d" / "os.html").read_text(encoding="utf-8").replace("__ID__", token_id)
        self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def proxy(self, upstream_path):
        url = UPSTREAM + upstream_path
        req = urllib.request.Request(url, headers={"User-Agent": "obol-local-clone", "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                body = response.read()
                ctype = response.headers.get("Content-Type", "application/octet-stream")
                self.send_response(response.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def send_bytes(self, data, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Daemon clone  http://127.0.0.1:%d" % PORT)
    server.serve_forever()
