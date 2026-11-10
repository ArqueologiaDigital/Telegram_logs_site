#!/usr/bin/env python3
"""Publish the topic, community and project pages at short addresses on the main site.

The site is built flat into <flat> (formatted/html of a build: topicos.html, topico-<slug>.html,
membro-<handle>.html, ...), which GitHub Pages serves under /Telegram_logs_site/formatted/html/.
This script copies those pages into the main site's repository (ArqueologiaDigital.github.io,
served at the root of arqueologiadigital.org) as directories, so that these are real addresses
that stay in the address bar:

  topicos.html                 -> /topicos/
  topico-<slug>.html           -> /topicos/<slug>/
  topicos-ano-<N>.html         -> /topicos/ano-<N>/
  topico-ano-<N>-<slug>.html   -> /topicos/ano-<N>/<slug>/
  comunidade.html              -> /comunidade/
  membro-<handle>.html         -> /comunidade/<handle>/
  projetos.html                -> /projetos/

Every relative link in a copied page is rewritten: to the short address when it points to one of
these pages, otherwise to its place under --base (chat pages, search, stylesheets, the index).
In <flat> itself each of these pages is then replaced by a small redirect to its short address
(with --stubs), so the long addresses published before keep working and the chat pages' header
links end up on the short ones.

    python3 -I export_pretty.py --flat WT/formatted/html --out ../ArqueologiaDigital.github.io --stubs

The directories topicos/, comunidade/ and projetos/ of --out are rebuilt from scratch.
"""
import argparse
import os
import re
import shutil
import sys

OWNED = ("topicos", "comunidade", "projetos")       # directories of --out this script rebuilds
ATTR = re.compile(r"""\b(href|src|action)=(['"])([^'"]*)\2""")


def pretty(name):
    """Short path (without slashes at the ends) for a flat file name, or None."""
    m = re.fullmatch(r"topico-ano-(\d+)-([a-z0-9-]+)\.html", name)
    if m:
        return f"topicos/ano-{m.group(1)}/{m.group(2)}"
    m = re.fullmatch(r"topicos-ano-(\d+)\.html", name)
    if m:
        return f"topicos/ano-{m.group(1)}"
    m = re.fullmatch(r"topico-([a-z0-9-]+)\.html", name)
    if m:
        return f"topicos/{m.group(1)}"
    m = re.fullmatch(r"membro-([a-z0-9_]+)\.html", name)
    if m:
        return f"comunidade/{m.group(1)}"
    return {"topicos.html": "topicos", "comunidade.html": "comunidade", "projetos.html": "projetos"}.get(name)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--flat", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--base", default="/Telegram_logs_site/formatted/html/")
    p.add_argument("--stubs", action="store_true", help="replace the flat pages by redirects to the short addresses")
    a = p.parse_args()
    flat, out = os.path.abspath(a.flat), os.path.abspath(a.out)
    assert os.path.isfile(os.path.join(out, "CNAME")), f"{out} does not look like the main site's repository"

    pages, redirects = {}, {}
    for name in sorted(os.listdir(flat)):
        path = pretty(name)
        if not path:
            continue
        with open(os.path.join(flat, name), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', text)
        if m:                       # membro-<user id>.html: a redirect to the page by handle
            redirects[name] = m.group(1)
        else:
            pages[name] = (path, text)
    target = {name: "/" + path + "/" for name, (path, _) in pages.items()}
    for name, to in redirects.items():
        if to in target:
            target[name] = target[to]

    def rewrite(m):
        attr, quote, url = m.groups()
        if not url or url.startswith(("#", "/", "http:", "https:", "mailto:", "data:", "javascript:")):
            return m.group(0)
        file, sep, rest = re.match(r"([^?#]*)([?#]?)(.*)", url, re.S).groups()
        new = target[file] + sep + rest if file in target else a.base + url
        return f"{attr}={quote}{new}{quote}"

    for d in OWNED:
        full = os.path.join(out, d)
        assert os.path.dirname(full) == out and os.path.basename(full) in OWNED
        if os.path.isdir(full):
            shutil.rmtree(full)
    for name, (path, text) in pages.items():
        dest = os.path.join(out, path, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(ATTR.sub(rewrite, text))
    if a.stubs:
        for name, to in target.items():
            with open(os.path.join(flat, name), "w", encoding="utf-8") as f:
                f.write(f'<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={to}">'
                        f'<link rel="canonical" href="{to}"><script>location.replace("{to}" + location.hash);</script>'
                        f'<a href="{to}">{to}</a>\n')
    print(f"short addresses: {len(pages)} pages -> {out}/{{{','.join(OWNED)}}}/"
          + (f"; {len(target)} redirects left in {flat}" if a.stubs else ""))


if __name__ == "__main__":
    sys.exit(main())
