#!/usr/bin/env python3
"""Full-text search for the built site, with Pagefind (https://pagefind.app).

Writes, next to the chat pages built by build.py:

  <out>/formatted/html/search.html     the search page (static/search.html, filled in)
  <out>/formatted/html/pagefind/       the index, split into small files; the browser fetches
                                       only the pieces a query needs, so no server is involved

One search record per message, linking to <page>.html#m<id>. The text indexed is what the
pages show: phone tags masked exactly as build.py masks them (same phone_review.json), deleted
messages left out when the pages show them as placeholders, service messages left out.
Besides the message text, a record holds a document's file name, a link preview's title and
description, and a poll's question and answers, since those are what people remember.

Filters: ano (year), autor (sender), tipo (texto, link, foto, vídeo, ...). Sort: data.

How records are fed to Pagefind, and why:
  - Pagefind's Python API answers at most ~10 records/s (its reader sleeps 0.1 s per
    response, pagefind 1.6.0): over an hour here. So each message is written as a small HTML
    file to a scratch directory (under $TMPDIR) and the CLI indexer reads them in seconds.
  - Pagefind makes every data-pagefind-meta value searchable (checked: a meta holding the page
    URL made "preserva" match every message, an author meta made the author's name match all
    their messages). Filter values and file paths are not searchable. So records carry no
    meta at all: the author and year are filters, and the page number, message id, date and a
    has-photo flag are the file path, <page>/<id>_<YYYY-MM-DD>_<HHMM>[_p].html. search.html
    turns that path back into the link, the result title and the photo thumbnail.

    ../.venv/bin/python search_index.py --out build          # after build.py --out build
    ../.venv/bin/python search_index.py --out build --media-base https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/

Needs the pagefind package (requirements.txt), which ships the indexer binary.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B  # noqa: E402

LANG = "pt"
KIND_PT = {"photo": "foto", "video": "vídeo", "audio": "áudio", "document": "documento",
           "sticker": "figurinha", "gif": "GIF"}


def extra_text(raw, kind):
    """Searchable words that are not in the message body."""
    m = raw.get("media") or {}
    t = m.get("_")
    out = []
    if t == "MessageMediaDocument" and kind not in ("sticker", "gif"):   # "sticker.webp" etc.
        name = B.doc_filename(m.get("document") or {})
        if name:
            out.append(name)
    elif t == "MessageMediaWebPage":
        w = m.get("webpage") or {}
        out += [w.get("title") or "", w.get("description") or ""]
    elif t == "MessageMediaPoll":
        poll = m.get("poll") or {}
        for x in [poll.get("question")] + [a.get("text") for a in poll.get("answers", [])]:
            out.append((x.get("text") if isinstance(x, dict) else x) or "")
    return [s for s in out if s.strip()]


def kinds(raw, entry):
    out = []
    if entry:
        out.append(KIND_PT.get(entry["kind"], entry["kind"]))
    t = (raw.get("media") or {}).get("_")
    if t == "MessageMediaPoll":
        out.append("enquete")
    if t == "MessageMediaWebPage" or any(e["_"] in ("MessageEntityUrl", "MessageEntityTextUrl")
                                         for e in raw.get("entities") or []):
        out.append("link")
    return out or ["texto"]


def records(d, opts):
    """(staging path, content, filters, sort) per searchable message."""
    for rec in d.records:
        raw = rec.get("raw")
        if raw is None:  # legacy-only record (telegram-cli format)
            leg = rec.get("legacy") or {}
            raw = {"_": "Message", "message": leg.get("text", ""),
                   "from_id": {"user_id": (leg.get("from") or {}).get("peer_id")}}
        if raw["_"] == "MessageService":
            continue
        if rec["archive"].get("deletion") and opts.deleted != "show":
            continue
        entry = d.media.get(rec["id"])
        kind = entry["kind"] if entry else None
        parts = [B.masked_text(raw)] + extra_text(raw, kind)
        content = "\n".join(p for p in parts if p.strip())
        if not content:
            continue          # a sticker or a photo without caption: nothing to find it by
        when = B.local(rec["date"])
        # search.html derives the thumbnail URL as <media base><YYYY>/<YYYY-MM>/<id>.jpg
        photo = kind == "photo" and entry["store"] == "git" and entry["path"] == \
            f"{rec['date'][:4]}/{rec['date'][:7]}/{rec['id']}.jpg"
        path = f"{d.page_of[rec['id']]}/{rec['id']}_{when:%Y-%m-%d_%H%M}{'_p' if photo else ''}.html"
        yield path, content, {"ano": [str(when.year)], "autor": [d.sender(raw)],
                              "tipo": kinds(raw, entry)}, {"data": rec["date"]}


def staging_page(content, filters, sort):
    """One message as an HTML page for the indexer. Only <main> is indexed as text."""
    e = B.esc
    tags = "".join(f"<span data-pagefind-filter='{k}'>{e(v)}</span>" for k, vs in filters.items() for v in vs)
    tags += "".join(f"<span data-pagefind-sort='{k}'>{e(v)}</span>" for k, v in sort.items())
    body = "".join(f"<p>{e(line)}</p>" for line in content.split("\n"))
    return (f"<!DOCTYPE html><html lang='{LANG}'><head><meta charset='utf-8'></head><body>"
            f"<div>{tags}</div><main data-pagefind-body>{body}</main></body></html>\n")


def write_index(recs, bundle):
    staging = tempfile.mkdtemp(prefix="pagefind-staging-")   # honours TMPDIR
    try:
        for path, content, filters, sort in recs:
            full = os.path.join(staging, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(staging_page(content, filters, sort))
        subprocess.run([sys.executable, "-m", "pagefind", "--site", staging, "--output-path", bundle,
                        "--quiet"], check=True)
    finally:
        assert os.path.basename(staging).startswith("pagefind-staging-")
        shutil.rmtree(staging)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--data", default=os.path.join(HERE, "..", "Telegram_logs"))
    p.add_argument("--media-repo", default=os.path.join(HERE, "..", "Telegram_logs_media"))
    p.add_argument("--media-base")
    p.add_argument("--deleted", choices=["placeholder", "show", "omit"], default="placeholder")
    p.add_argument("--phones", choices=["review", "mask", "show"], default="review")
    p.add_argument("--page-only", action="store_true",
                   help="only rewrite search.html (from static/search.html); keep the existing index")
    opts = p.parse_args()
    hdir = os.path.join(os.path.abspath(opts.out), "formatted", "html")
    if opts.media_base is None:
        opts.media_base = urllib.parse.quote(os.path.relpath(os.path.abspath(opts.media_repo), hdir)) + "/"
    elif not opts.media_base.endswith("/"):
        opts.media_base += "/"
    with open(os.path.join(HERE, "static", "search.html"), encoding="utf-8") as f:
        page = f.read()
    config = {"pagePrefix": B.page_href(0)[:-len("0.html")], "mediaBase": opts.media_base}
    B.write(os.path.join(hdir, "search.html"), page.replace("/*CONFIG*/{}", json.dumps(config)))
    if opts.page_only:
        print("search: search.html rewritten, index kept")
        return
    d = B.Data(opts.data)
    B.mark_phones(d, opts)
    recs = list(records(d, opts))
    bundle = os.path.join(hdir, "pagefind")
    if os.path.isdir(bundle):        # stale index files would otherwise linger
        assert os.path.basename(bundle) == "pagefind" and os.path.dirname(bundle) == hdir
        shutil.rmtree(bundle)
    write_index(recs, bundle)
    n_files = sum(len(f) for _, _, f in os.walk(bundle))
    size = sum(os.path.getsize(os.path.join(r, x)) for r, _, f in os.walk(bundle) for x in f)
    print(f"search: {len(recs)} of {len(d.records)} messages indexed -> {n_files} files, "
          f"{size / 1e6:.1f} MB in {bundle}")


if __name__ == "__main__":
    sys.exit(main())
