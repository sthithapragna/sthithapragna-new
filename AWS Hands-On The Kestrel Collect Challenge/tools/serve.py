#!/usr/bin/env python3
"""Serve the storefront locally, the way CloudFront will serve it.

Any path that isn't a real file (like /bookings or /stores/0023) gets
index.html, so deep links work. Plain `python -m http.server` doesn't do
that, which is the difference episode 05 is about.

    python tools/serve.py            # http://localhost:8000
    python tools/serve.py --port 9000
"""
import argparse
import functools
import http.server
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


class StorefrontHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".svg": "image/svg+xml"}

    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        target = APP / path.lstrip("/")
        if path != "/" and not target.exists() and "." not in pathlib.PurePosixPath(path).name:
            self.path = "/index.html"
        return super().send_head()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    handler = functools.partial(StorefrontHandler, directory=str(APP))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Kestrel Collect on http://localhost:{args.port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
