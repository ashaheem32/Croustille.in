#!/usr/bin/env python3
"""Dev server for the Croustille landing page.

    python3 serve.py          # → http://localhost:8900

Why this exists instead of `python3 -m http.server`: that server ignores HTTP
Range requests. Chrome's media element opens a video with `Range: bytes=0-`,
gets a plain 200 with no `Accept-Ranges` back, and stalls — the hero video
never starts and never reports an error. Every real host (nginx, Netlify,
Vercel, GitHub Pages, S3) supports Range, so this only affects local preview.

Also threaded, so a large video streaming in one connection cannot block the
CSS and images on another.
"""

import functools
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler + byte-range support for media files."""

    # Must live on the class. Setting it on the functools.partial below has no
    # effect, and the resulting HTTP/1.0 responses close the connection after
    # every reply — which Chrome's media loader will not stream over.
    protocol_version = "HTTP/1.1"

    def send_head(self):
        header = self.headers.get("Range")
        if not header:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        match = RANGE_RE.match(header.strip())
        if not match:
            return super().send_head()

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        first, last = match.group(1), match.group(2)
        start = int(first) if first else 0
        end = int(last) if last else size - 1
        end = min(end, size - 1)

        if start >= size or start > end:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()

        f.seek(start)
        self.copy_range(f, self.wfile, end - start + 1)
        f.close()
        return None

    @staticmethod
    def copy_range(src, dst, length, chunk=64 * 1024):
        while length > 0:
            data = src.read(min(chunk, length))
            if not data:
                break
            dst.write(data)
            length -= len(data)

    def end_headers(self):
        # Never cache during development — edits show up on reload.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "--quiet" not in sys.argv:
            super().log_message(fmt, *args)


def main():
    port = 8900
    for arg in sys.argv[1:]:
        if arg.isdigit():
            port = int(arg)

    root = os.path.dirname(os.path.abspath(__file__))
    handler = functools.partial(RangeRequestHandler, directory=root)

    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Croustille → http://localhost:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
