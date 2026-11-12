#!/usr/bin/env python3
"""Serve the site locally exactly as it will be published, to look at it before pushing.

On GitHub Pages, arqueologiadigital.org serves two repositories:
  /                       ArqueologiaDigital.github.io (main site: /topicos/, /projetos/, /logs/N/, ...)
  /Telegram_logs_site/    the gh-pages branch of this repository (chat pages, CSS, search index)
and the media (photos, link-preview thumbnails, shared files) comes from
https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/.

This server maps the same paths onto the local checkouts that publish.sh commits to
(../ArqueologiaDigital.github.io and the worktree ../Telegram_logs_site-gh-pages), and, unless
--remote-media is given, rewrites that media URL in every HTML page to /Telegram_logs_media/,
served from ../Telegram_logs_media, so unpushed media shows too. It only reads files.

    TMPDIR=~/compartilhado/tmp ./publish.sh          # build and commit locally (no push)
    python3 -I preview_site.py                        # then open http://127.0.0.1:8000/topicos/
    python3 -I preview_site.py --port 8080 --remote-media
"""
import argparse
import http.server
import os
import posixpath
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MEDIA_URL = b"https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/"
MOUNTS = [  # (URL prefix, local directory); the first match wins, "/" last
    ("/Telegram_logs_site/", os.path.join(ROOT, "Telegram_logs_site-gh-pages")),
    ("/Telegram_logs_media/", os.path.join(ROOT, "Telegram_logs_media")),
    ("/", os.path.join(ROOT, "ArqueologiaDigital.github.io")),
]


class Handler(http.server.SimpleHTTPRequestHandler):
    local_media = True

    def translate_path(self, path):
        path = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        for prefix, base in MOUNTS:
            if path.startswith(prefix) or path + "/" == prefix:
                rest = posixpath.normpath(path[len(prefix):] or "/").lstrip("/")
                if rest.startswith(".."):
                    return os.path.join(base, "__forbidden__")
                if any(part.startswith(".git") for part in rest.split("/")):
                    return os.path.join(base, "__forbidden__")
                return os.path.join(base, *rest.split("/")) if rest not in ("", ".") else base
        return os.path.join(MOUNTS[-1][1], "__forbidden__")

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            if not urllib.parse.urlsplit(self.path).path.endswith("/"):
                return super().send_head()          # redirects to the address with a slash
            path = os.path.join(path, "index.html")
        if not (self.local_media and path.endswith(".html") and os.path.isfile(path)):
            return super().send_head()
        with open(path, "rb") as f:
            body = f.read().replace(MEDIA_URL, b"/Telegram_logs_media/")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return _Body(body)

    def list_directory(self, path):
        self.send_error(404, "No index.html here")   # GitHub Pages does not list directories
        return None


class _Body:
    def __init__(self, data):
        self.data = data

    def read(self, *a):
        data, self.data = self.data, b""
        return data

    def close(self):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--remote-media", action="store_true",
                   help="keep the raw.githubusercontent.com media links (shows only pushed media)")
    a = p.parse_args()
    for _, base in MOUNTS:
        if not os.path.isdir(base):
            raise SystemExit(f"missing {base}: run publish.sh first")
    Handler.local_media = not a.remote_media
    with http.server.ThreadingHTTPServer((a.bind, a.port), Handler) as srv:
        print(f"serving the site at http://{a.bind}:{a.port}/ (topic index: /topicos/); Ctrl-C stops",
              flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
