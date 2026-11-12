#!/usr/bin/env python3
"""Static views of the @arqueologiadigital archive (layer 4).

Reads ../Telegram_logs (messages, users, media manifest) and never writes there. Writes:

  <out>/formatted/html/index.html
  <out>/formatted/html/<LEGACY_NAME>-<N>.html        1000 archived messages per page, oldest first
  <out>/formatted/html/telegram-history-dump.css
  <out>/formatted/plaintext/<LEGACY_NAME>/<LEGACY_NAME>_YYYY-MM-DD.log   one file per day
  <out>/index.html                                   redirect to formatted/html/index.html

File names, pagination and CSS are those of the 2018 pages (telegram-history-dump), so that
old links such as .../Telegram_logs/formatted/html/<LEGACY_NAME>-0.html keep working: pages
0..4 cover the same messages as in 2018 (checked by tests/compare_old_pages.py).

    python3 -I build.py --out build                                   # local preview
    python3 -I build.py --out build --media-base https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/

Options:
  --data DIR         the text archive (default ../Telegram_logs)
  --media-repo DIR   local media repo, for the default relative media links (default ../Telegram_logs_media)
  --media-base URL   prefix for media links (default: relative path to --media-repo, for previews)
  --deleted MODE     placeholder (default) | show | omit: how to render deleted messages.
                     Pagination always counts them, so page boundaries never move.
  --phones MODE      review (default) | mask | show: phone numbers members typed into messages.
                     Telegram tags many non-phones (year ranges like 1980/1990, prices, file
                     names), so `review` masks only tags marked "mask" in phone_review.json, and
                     masks *and lists* any tag not reviewed yet.
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
from collections import defaultdict
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY_NAME = "Arqueologia_Digital_e_Preservação_Histórica_por_meio_da_Emulação_de_Dispositivos_Eletrônicos"
TITLE = "Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"
PER_PAGE = 1000          # telegram-history-dump "paginate"
TIMESTAMP_EVERY = 10     # telegram-history-dump "timestamps_every"
TZ = ZoneInfo("America/Sao_Paulo")
CSS = "telegram-history-dump.css"

esc = html.escape


def q(s):
    """Escape for a single-quoted attribute."""
    return html.escape(s, quote=True)


def page_name(n):
    return f"{LEGACY_NAME}-{n}.html"


def page_href(n):
    return urllib.parse.quote(page_name(n))


def local(iso):
    return dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(TZ)


def stamp(d):
    return d.strftime("%Y-%m-%d %H:%M:%S %z")


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ---------------------------------------------------------------- data

def chosen_pictures():
    """{user id: (source file, published name)} for members who chose a picture to show instead of
    their Telegram photo ("picture" in topics/profiles_optin.json; drafts are left out). The file is
    published next to the pages as perfil-<handle>.<ext> and used on every page that shows the avatar."""
    path = os.path.join(HERE, "topics", "profiles_optin.json")
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for uid, info in json.load(f).items():
                if info.get("picture") and info.get("published", True):
                    out[int(uid)] = (os.path.join(HERE, "topics", info["picture"]),
                                     f"perfil-{info.get('handle') or uid}{os.path.splitext(info['picture'])[1]}")
    return out


class Data:
    def __init__(self, data_dir):
        self.records = []
        for p in sorted(glob.glob(os.path.join(data_dir, "messages", "*", "*.jsonl"))):
            with open(p, encoding="utf-8") as f:
                self.records += [json.loads(line) for line in f]
        self.records.sort(key=lambda r: r["id"])
        self.users = {}
        with open(os.path.join(data_dir, "users", "users.jsonl"), encoding="utf-8") as f:
            for line in f:
                u = json.loads(line)
                self.users[u["id"]] = u
        self.media = {}
        self.previews = {}      # link-preview thumbnails (manifest kind "preview"), kept apart from
        mpath = os.path.join(data_dir, "media", "manifest.jsonl")   # the message's own media
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                for line in f:
                    e = json.loads(line)
                    (self.previews if e["kind"] == "preview" else self.media)[e["msg_id"]] = e
        self.avatars = {}
        apath = os.path.join(data_dir, "media", "avatars.jsonl")
        if os.path.exists(apath):
            with open(apath, encoding="utf-8") as f:
                for line in f:
                    a = json.loads(line)
                    if a.get("path"):
                        self.avatars[a["user_id"]] = a["path"]
        self.pictures = chosen_pictures()
        self.page_of = {r["id"]: i // PER_PAGE for i, r in enumerate(self.records)}
        self.by_id = {r["id"]: r for r in self.records}

    def name(self, uid):
        """Current name, else the last known one (deleted accounts), else the id."""
        u = self.users.get(uid)
        if not u:
            return f"user {uid}" if uid else "?"
        for n in [u] + list(reversed(u.get("names_seen", []))):
            full = " ".join(filter(None, [n.get("first_name"), n.get("last_name")])) or n.get("title")
            if full:
                return full
            if n.get("username"):
                return "@" + n["username"]
        return "Deleted Account"

    @staticmethod
    def sender_id(raw):
        fid = raw.get("from_id") or {}
        return fid.get("user_id") or fid.get("channel_id") or 0

    def sender(self, raw):
        fid = raw.get("from_id") or {}
        if fid.get("user_id"):
            return self.name(fid["user_id"])
        if fid.get("channel_id"):
            return raw.get("post_author") or self.name(fid["channel_id"])
        return TITLE  # anonymous admin / the group itself


# ---------------------------------------------------------------- text with entities

SAFE_SCHEMES = ("http://", "https://", "tg://", "mailto:", "ftp://")


def safe_href(url):
    url = url.strip()
    if not url.lower().startswith(SAFE_SCHEMES):
        url = "http://" + url
    return q(url)


def plain(s):
    return esc(s).replace("\n", "<br>")


def render_text(text, entities, opts):
    """Telegram entities use UTF-16 offsets; map them to Python indexes, then render nested."""
    if not text:
        return ""
    u2i, u = {}, 0
    for i, ch in enumerate(text):
        u2i[u] = i
        u += 2 if ord(ch) > 0xFFFF else 1
    u2i[u] = len(text)

    def idx(off):
        while off not in u2i and off > 0:
            off -= 1
        return u2i.get(off, 0)

    ents = []
    for e in entities or []:
        s, t = idx(e["offset"]), idx(e["offset"] + e["length"])
        if t > s:
            ents.append((s, t, e))
    ents.sort(key=lambda x: (x[0], -x[1]))

    def render(lo, hi, items):
        out, cur, k = [], lo, 0
        while k < len(items):
            s, t, e = items[k]
            children = []
            k += 1
            while k < len(items) and items[k][0] < t:
                if items[k][1] <= t:
                    children.append(items[k])
                k += 1          # overlapping (not nested) entities are dropped, never crash
            out.append(plain(text[cur:s]))
            out.append(wrap(text[s:t], e, render(s, t, children), opts))
            cur = t
        out.append(plain(text[cur:hi]))
        return "".join(out)

    return render(0, len(text), ents)


def wrap(seg, e, inner, opts):
    t = e["_"]
    if t == "MessageEntityBold":
        return f"<b>{inner}</b>"
    if t == "MessageEntityItalic":
        return f"<i>{inner}</i>"
    if t == "MessageEntityUnderline":
        return f"<u>{inner}</u>"
    if t == "MessageEntityStrike":
        return f"<s>{inner}</s>"
    if t == "MessageEntityCode":
        return f"<code>{inner}</code>"
    if t == "MessageEntityPre":
        return f"<pre>{esc(seg)}</pre>"
    if t == "MessageEntityBlockquote":
        return f"<blockquote>{inner}</blockquote>"
    if t == "MessageEntitySpoiler":
        return f"<span class='spoiler'>{inner}</span>"
    if t == "MessageEntityUrl":
        return f"<a target='_blank' href='{safe_href(seg)}'>{inner}</a>"
    if t == "MessageEntityTextUrl":
        return f"<a target='_blank' href='{safe_href(e.get('url', ''))}'>{inner}</a>"
    if t == "MessageEntityEmail":
        return f"<a href='mailto:{q(seg)}'>{inner}</a>"
    if t == "MessageEntityMention" and re.fullmatch(r"@\w{3,}", seg):
        return f"<a target='_blank' href='https://t.me/{q(seg[1:])}'>{inner}</a>"
    if t == "MessageEntityPhone" and e.get("_mask"):
        return "<span class='masked' title='phone number hidden'>[phone number]</span>"
    return inner  # MentionName, Hashtag, BotCommand, Cashtag, CustomEmoji, ...


# ---------------------------------------------------------------- media

def media_url(entry, opts):
    if entry is None:
        return None
    if entry["store"] == "git":
        return opts.media_base + urllib.parse.quote(entry["path"])
    return entry.get("ia_url")


def doc_filename(doc):
    for at in doc.get("attributes", []):
        if at.get("_") == "DocumentAttributeFilename" and at.get("file_name"):
            return at["file_name"]
    return None


def render_media(rec, d, opts):
    raw = rec["raw"]
    m = raw.get("media")
    prev = d.previews.get(rec["id"])
    if not m or m["_"] == "MessageMediaWebPage":
        w = (m or {}).get("webpage") or {}
        if w.get("_") != "WebPage":
            w = {}
        thumb = ""
        if prev and media_url(prev, opts):
            link = w.get("url") or media_url(prev, opts)
            if prev.get("via") == "ytimg":       # i.ytimg.com/vi/<id>/mqdefault.jpg -> the video
                link = "https://www.youtube.com/watch?v=" + prev["source_url"].split("/")[-2]
            size = f" width='{prev['w']}' height='{prev['h']}'" if prev.get("w") else ""
            # like Telegram: a big image under the text only when the preview has large media
            # (videos, most articles); otherwise a small thumbnail beside it (site logos, avatars)
            small = w and not w.get("has_large_media")
            thumb = (f"<a target='_blank' href='{safe_href(link)}'><img class='preview{' small' if small else ''}' "
                     f"loading='lazy' src='{q(media_url(prev, opts))}'{size} alt=''></a>")
        if not (thumb or w.get("title") or w.get("description")):
            return ""
        title = f"<b>{esc(w['title'])}</b>" if w.get("title") else ""
        desc = plain(w.get("description") or "")
        text = title + ("<br><br>" if title and desc else "") + desc
        if "preview small" in thumb:
            return f"<div class=\"webpage\">{thumb}{text}</div>"
        return f"<div class=\"webpage\">{text}{'<br>' if text and thumb else ''}{thumb}</div>"
    t = m["_"]
    entry = d.media.get(rec["id"])
    url = media_url(entry, opts)
    kind = entry["kind"] if entry else None
    if t == "MessageMediaPoll":
        poll = m.get("poll") or {}
        qtext = poll.get("question")
        qtext = qtext.get("text") if isinstance(qtext, dict) else qtext
        answers = []
        for a in poll.get("answers", []):
            at = a.get("text")
            answers.append(esc(at.get("text") if isinstance(at, dict) else at or ""))
        return (f"<div class='poll'><b>📊 {esc(qtext or '')}</b><ul>"
                + "".join(f"<li>{a}</li>" for a in answers) + "</ul></div>")
    if t == "MessageMediaDice":
        return f"<div class='dice'>{esc(m.get('emoticon', '🎲'))} {m.get('value', '')}</div>"
    if t == "MessageMediaGeo":
        g = m.get("geo") or {}
        lat, lon = g.get("lat"), g.get("long")
        return f"<div class=\"geo\"><a target='_blank' href='https://www.openstreetmap.org/?mlat={lat}&mlon={lon}'>📍 {lat}, {lon}</a></div>"
    if t == "MessageMediaContact":
        name = " ".join(filter(None, [m.get("first_name"), m.get("last_name")]))
        return f"<div class=\"contact\">👤 Contact card: {esc(name)} (number not archived)</div>"

    doc = m.get("document") or {}
    fname = doc_filename(doc) if doc else None
    size = entry["size"] if entry else doc.get("size")
    label = esc(fname or {"photo": "photo", "video": "video", "audio": "audio", "gif": "GIF",
                          "sticker": "sticker"}.get(kind, "file"))
    if url is None:
        why = "large file, not yet published" if entry and entry["store"] == "ia" else "not archived"
        return f"<div class='file missing'>📎 {label}{f' ({human_size(size)})' if size else ''}, {why}</div>"
    u = q(url)
    if kind == "photo" or (kind == "sticker" and url.lower().endswith((".webp", ".png", ".jpg"))):
        return f"<a target='_blank' href='{u}'><img loading='lazy' src='{u}'></a>"
    if kind == "gif" or (kind == "sticker" and url.lower().endswith(".webm")):
        return f"<video src='{u}' autoplay loop muted playsinline></video>"
    if kind == "video":
        return f"<video src='{u}' controls preload='none'></video><br><a target='_blank' href='{u}'>{label}</a> ({human_size(size)})"
    if kind == "audio":
        return f"<audio src='{u}' controls preload='none'></audio><br><a target='_blank' href='{u}'>{label}</a>"
    return f"<div class='file'>📎 <a target='_blank' href='{u}'>{label}</a> ({human_size(size)})</div>"


# ---------------------------------------------------------------- senders

def hue(uid):
    """A fixed colour per sender: golden-angle steps over the colour wheel, by user id."""
    return int(uid * 137.508) % 360


def initials(name):
    words = re.findall(r"[^\W\d_]+", name)
    return "".join(w[0] for w in words[:2]).upper() or "?"


def avatar(d, uid, name, opts):
    if uid in d.pictures:
        return f"<img class='avatar' src='{q(d.pictures[uid][1])}' alt='' loading='lazy'>"
    path = d.avatars.get(uid)
    if path:
        return f"<img class='avatar' src='{q(opts.media_base + urllib.parse.quote(path))}' alt='' loading='lazy'>"
    return f"<span class='avatar initials' aria-hidden='true'>{esc(initials(name))}</span>"


# ---------------------------------------------------------------- messages

def action_text(raw, d):
    a = raw["action"]
    t = a["_"]
    who = d.sender(raw)
    actor = (raw.get("from_id") or {}).get("user_id")
    if t == "MessageActionChatAddUser":
        ids = a.get("users") or []
        if ids == [actor]:
            return f"{who} joined the group"
        return f"{who} added " + ", ".join(d.name(i) for i in ids)
    if t == "MessageActionChatJoinedByLink":
        return f"{who} joined the group via invite link"
    if t == "MessageActionChatJoinedByRequest":
        return f"{who} joined the group (request approved)"
    if t == "MessageActionChatDeleteUser":
        uid = a.get("user_id")
        return f"{who} left the group" if uid == actor else f"{who} removed {d.name(uid)}"
    if t == "MessageActionPinMessage":
        return f"{who} pinned a message"
    if t == "MessageActionChatEditTitle":
        return f"{who} changed the group name to “{a.get('title', '')}”"
    if t == "MessageActionChatEditPhoto":
        return f"{who} changed the group photo"
    if t == "MessageActionChannelMigrateFrom":
        return f"Group upgraded to supergroup (was “{a.get('title', '')}”)"
    if t == "MessageActionChatCreate":
        return f"{who} created the group “{a.get('title', '')}”"
    return f"{who}: {t.replace('MessageAction', '')}"


def link_to(d, mid, cur_page):
    if mid not in d.page_of:
        return None
    p = d.page_of[mid]
    return f"#m{mid}" if p == cur_page else f"{page_href(p)}#m{mid}"


def snippet(d, mid):
    r = d.by_id.get(mid)
    if not r or not r.get("raw"):
        return ""
    text = (r["raw"].get("message") or "").replace("\n", " ")
    if not text and r["raw"].get("media"):
        text = "[media]"
    return text[:80] + ("…" if len(text) > 80 else "")


def deletion_note(dl, d):
    when = dl.get("deleted_at")
    if when:
        s = f"deleted on {local(when).strftime('%Y-%m-%d %H:%M')}"
    else:
        s = f"deleted (noticed {local(dl['detected_at']).strftime('%Y-%m-%d')})"
    if dl.get("deleted_by"):
        s += f" by {d.name(dl['deleted_by'])}"
    return s


def render_message(rec, d, page, opts):
    raw = rec.get("raw")
    when = local(rec["date"])
    title = stamp(when)
    dl = rec["archive"].get("deletion")
    if raw is None:  # legacy-only record (telegram-cli format)
        leg = rec.get("legacy") or {}
        raw = {"_": "Message", "message": leg.get("text", ""), "from_id": {"user_id": (leg.get("from") or {}).get("peer_id")}}
    if dl and opts.deleted == "omit":
        return ""
    if raw["_"] == "MessageService":
        link = ""
        reply = (raw.get("reply_to") or {}).get("reply_to_msg_id")
        if reply and link_to(d, reply, page):
            link = f" (<a href='{link_to(d, reply, page)}'>see message</a>)"
        return (f"<div class='msg-service' id='m{rec['id']}' title='{title}'><div class=inner>"
                f"{esc(action_text(raw, d))}{link}</div></div>\n")

    cls = "in"   # everyone alike: the archiving account's own messages are not set apart
    if dl:
        cls += " deleted"
        title += " | " + deletion_note(dl, d)
    if raw.get("edit_date"):
        title += f" | edited {stamp(local(raw['edit_date']))}"
    uid = d.sender_id(raw)
    who = d.sender(raw)
    style = f" style='--h:{hue(uid)}'"
    parts = [f"<div class=\"author\">{avatar(d, uid, who, opts)}<span class='name'>{esc(who)}</span></div>"]

    if dl and opts.deleted == "placeholder":
        parts.append(f"<span class='deleted-note'>[message {esc(deletion_note(dl, d))}]</span>")
        return f"<div class='msg {cls}' id='m{rec['id']}' title='{q(title)}'{style}>{''.join(parts)}</div>\n"

    f = raw.get("fwd_from")
    if f:
        fid = f.get("from_id") or {}
        src = (d.name(fid["user_id"]) if fid.get("user_id")
               else f.get("from_name") or (d.name(fid["channel_id"]) if fid.get("channel_id") in d.users else "a channel"))
        parts.append(f"<div class=\"fwd\">Forwarded message from <span class=\"fwd-name\">{esc(src)}</span>:</div>")
    reply = (raw.get("reply_to") or {}).get("reply_to_msg_id")
    if reply:
        href = link_to(d, reply, page)
        r = d.by_id.get(reply)
        who = d.sender(r["raw"]) if r and r.get("raw") else "a message"
        text = f"↪ {esc(who)}: {esc(snippet(d, reply))}"
        parts.append(f"<div class='reply'>{f'<a href={chr(39)}{href}{chr(39)}>{text}</a>' if href else text}</div>")
    med = render_media(rec, d, opts)
    body = render_text(raw.get("message") or "", raw.get("entities"), opts)
    is_preview = (raw.get("media") or {}).get("_") in ("MessageMediaWebPage", None)
    if med and not is_preview:
        parts.append(("<br>" if parts else "") + med + ("<br>" if body else ""))
    parts.append(body)
    if med and is_preview:
        parts.append(med)
    if dl:
        parts.append(f"<div class='deleted-note'>[{esc(deletion_note(dl, d))}]</div>")
    return f"<div class='msg {cls}' id='m{rec['id']}' title='{q(title)}'{style}>{''.join(parts)}</div>\n"


# ---------------------------------------------------------------- pages

def nav(cls, n, last):
    items = ["<a href=\"index.html\">Back to index</a>", "<a href=\"search.html\">Search</a>"]
    if n > 0:
        items += [f"<a href='{page_href(0)}'>First</a>", f"<a href='{page_href(n - 1)}'>Previous</a>"]
    items.append(f"Page {n + 1} of {last + 1}")
    if n < last:
        items += [f"<a href='{page_href(n + 1)}'>Next</a>", f"<a href='{page_href(last)}'>Last</a>"]
    return f"\t<div class='{cls}'>{' | '.join(items)} |</div>\n"


def head(title):
    return ("<!DOCTYPE html>\n<html>\n  <head>\n  \t<meta charset=\"utf-8\">\n"
            "  \t<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"  \t<title>{esc(title)}</title>\n  \t<link rel=stylesheet href=\"{CSS}\">\n  </head>\n  <body>\n"
            + SITE_HEADER)


# The same header on every page of the site (chat pages, index, topics, projects, community).
SITE_HEADER = ("\t<header class=\"site\"><a class=\"brand\" href=\"topicos.html\">Arqueologia Digital</a><nav><a href=\"topicos.html\">Tópicos</a><a href=\"projetos.html\">Projetos</a><a href=\"comunidade.html\">Comunidade</a><a href=\"index.html\">Log do chat</a><a href=\"search.html\">Busca</a><a href=\"https://arqueologiadigital.org/galeria.html\">Galeria</a></nav></header>\n")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_html(d, out, opts):
    hdir = os.path.join(out, "formatted", "html")
    pages = [d.records[i:i + PER_PAGE] for i in range(0, len(d.records), PER_PAGE)]
    last = len(pages) - 1
    for n, recs in enumerate(pages):
        body, since_stamp, prev_day = [], TIMESTAMP_EVERY, None
        for rec in recs:
            when = local(rec["date"])
            if since_stamp >= TIMESTAMP_EVERY or when.date() != prev_day:
                body.append(f"<div class='msg-service' title='{stamp(when)}'><div class=inner>"
                            f"{when.strftime('%a %Y-%m-%d, %H:%M')}</div></div>\n")
                since_stamp = 0
            prev_day = when.date()
            html_msg = render_message(rec, d, n, opts)
            if html_msg:
                body.append(html_msg)
                since_stamp += 1
        write(os.path.join(hdir, page_name(n)),
              head(f"Chat: {TITLE}") + nav("navigation-top", n, last)
              + f"\t<h1>Group chat: {esc(TITLE)}</h1>\n" + "".join(body)
              + nav("navigation-bottom", n, last) + "  </body>\n</html>\n")

    rows = []
    for n, recs in enumerate(pages):
        a, b = local(recs[0]["date"]), local(recs[-1]["date"])
        rows.append(f"<tr><td><a href='{page_href(n)}'>Page {n + 1}</a></td>"
                    f"<td>{a:%Y-%m-%d}</td><td>{b:%Y-%m-%d}</td><td>{len(recs)}</td></tr>")
    first, newest = local(d.records[0]["date"]), local(d.records[-1]["date"])
    write(os.path.join(hdir, "index.html"),
          head("Telegram History Dump") + "\t<h1>Telegram History Dump</h1>\n"
          f"\t<div class='dialog msg '><span class=\"icon img-group\"></span> <a href='{page_href(0)}'>{esc(TITLE)}</a></div>\n"
          f"\t<div class='index-info'><p>{len(d.records)} messages, {first:%Y-%m-%d} to {newest:%Y-%m-%d}. "
          f"Times in Brasília time (America/Sao_Paulo). Raw data: "
          f"<a href='https://github.com/ArqueologiaDigital/Telegram_logs'>Telegram_logs</a>, "
          f"<a href='https://github.com/ArqueologiaDigital/Telegram_logs_media'>Telegram_logs_media</a>.</p>\n"
          "\t<form class='search-box' action='search.html'><input name='q' type='search' "
          "placeholder='Buscar no chat (palavras, arquivos, links)' aria-label='Buscar no chat'> "
          "<button>Buscar</button></form>\n"
          "\t<table class='pages'><tr><th>page</th><th>from</th><th>to</th><th>messages</th></tr>\n\t"
          + "\n\t".join(rows) + "\n\t</table></div>\n  </body>\n</html>\n")
    shutil.copy(os.path.join(HERE, "static", CSS), os.path.join(hdir, CSS))
    for src, name in d.pictures.values():
        shutil.copy(src, os.path.join(hdir, name))
    return len(pages)


def mark_phones(d, opts):
    """Set e["_mask"] on phone entities to hide; return ids of tags missing from the review file."""
    with open(os.path.join(HERE, "phone_review.json"), encoding="utf-8") as f:
        review = json.load(f)
    unreviewed = set()
    for rec in d.records:
        for e in (rec.get("raw") or {}).get("entities") or []:
            if e["_"] != "MessageEntityPhone":
                continue
            verdict = review.get(str(rec["id"]))
            if verdict is None:
                unreviewed.add(rec["id"])
            e["_mask"] = opts.phones == "mask" or (opts.phones == "review" and verdict != "show")
    return unreviewed


def masked_text(raw):
    """Message text as plain text, with phone tags marked by mark_phones() replaced."""
    text = raw.get("message") or ""
    for e in sorted(raw.get("entities") or [], key=lambda e: -e["offset"]):
        if e["_"] == "MessageEntityPhone" and e.get("_mask"):
            b = text.encode("utf-16-le")
            text = (b[:2 * e["offset"]] + "[phone number]".encode("utf-16-le")
                    + b[2 * (e["offset"] + e["length"]):]).decode("utf-16-le")
    return text


def build_plaintext(d, out, opts):
    pdir = os.path.join(out, "formatted", "plaintext", LEGACY_NAME)
    days = defaultdict(list)
    for rec in d.records:
        raw = rec.get("raw")
        if raw is None:
            continue
        when = local(rec["date"])
        dl = rec["archive"].get("deletion")
        if dl and opts.deleted == "omit":
            continue
        ts = when.strftime("%Y-%m-%d %H:%M:%S")
        if raw["_"] == "MessageService":
            days[when.date()].append(f"[{ts}] * {action_text(raw, d)}")
            continue
        who = d.sender(raw)
        if dl and opts.deleted == "placeholder":
            days[when.date()].append(f"[{ts}] {who}: [message {deletion_note(dl, d)}]")
            continue
        text = masked_text(raw)
        entry = d.media.get(rec["id"])
        if entry:
            url = media_url(entry, opts) or "(not yet published)"
            days[when.date()].append(f"[{ts}] {who}: {entry['kind']}: {url}")
        if text:
            fwd = " [forwarded]" if raw.get("fwd_from") else ""
            days[when.date()].append(f"[{ts}] {who}{fwd}: {text}")
    for day, lines in days.items():
        write(os.path.join(pdir, f"{LEGACY_NAME}_{day:%Y-%m-%d}.log"), "\n".join(lines) + "\n")
    return len(days)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--data", default=os.path.join(HERE, "..", "Telegram_logs"))
    p.add_argument("--media-repo", default=os.path.join(HERE, "..", "Telegram_logs_media"))
    p.add_argument("--media-base")
    p.add_argument("--deleted", choices=["placeholder", "show", "omit"], default="placeholder")
    p.add_argument("--phones", choices=["review", "mask", "show"], default="review")
    opts = p.parse_args()
    out = os.path.abspath(opts.out)
    if opts.media_base is None:
        rel = os.path.relpath(os.path.abspath(opts.media_repo), os.path.join(out, "formatted", "html"))
        opts.media_base = urllib.parse.quote(rel) + "/"
    elif not opts.media_base.endswith("/"):
        opts.media_base += "/"
    d = Data(opts.data)
    unreviewed = mark_phones(d, opts)
    n_pages = build_html(d, out, opts)
    n_days = build_plaintext(d, out, opts)
    write(os.path.join(out, "index.html"),
          "<!DOCTYPE html><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0; url=formatted/html/index.html\">"
          "<a href=\"formatted/html/index.html\">Telegram logs</a>\n")
    write(os.path.join(out, ".nojekyll"), "")
    print(f"{len(d.records)} messages -> {n_pages} HTML pages, {n_days} plaintext days in {out}")
    print(f"media links: {opts.media_base}  deleted: {opts.deleted}  phones: {opts.phones}")
    if unreviewed:
        print(f"WARNING: {len(unreviewed)} phone tag(s) not in phone_review.json (masked for now): "
              f"message ids {sorted(unreviewed)}")


if __name__ == "__main__":
    sys.exit(main())
