#!/usr/bin/env python3
"""Links inside the topic index's summaries: "o repositório kn5000_homebrew" links to the repository.

The summaries are plain text written by agents; each conversation also lists the URLs posted in
it (`resources`). This links a phrase of a summary to one of those URLs, so a summary only ever
links to something that was posted in the conversations it summarizes (or to a repository in
`repos.json`). The links live in `inline_links.json`, separate from the agent-written text:

    {"links":    {PLACE: [{"phrase": "kn5000_homebrew", "url": "https://github.com/..."}]},
     "rejected": [{"place": PLACE, "phrase": ..., "url": ..., "why": ...}]}

PLACE names the text: `conv:<year>:<first id>` (a conversation summary), `sub:<year>/<theme>/<sub>`,
`theme:<year>/<theme>`, `year:<year>` (a year's intro), `topic:<slug>` (a cross-year summary),
`note:<slug>:<year>` (a cross-year topic's note for one year), `bio:<user id>` (a profile's bio,
from the conversations its `bio_basis` cites; a bio may also link to any URL posted in those
conversations or in the messages it cites, read from the archive, see message_urls). `render.py` links the first
occurrence of each phrase in its text, and reports a phrase that is no longer in the text or a URL
that none of the place's conversations cite.

    python3 -I topics/inline_links.py propose [--dry-run]    # (re)compute the rule-based links
    python3 -I topics/inline_links.py show [PLACE_PREFIX]     # every link with its context

`propose` finds phrases by rules on the URL: a GitHub repository's name ("FlashFloppy"), a pull
request or issue number ("#16552"), a Wikipedia article's title ("CHIP-8"), an Internet Archive
item id, a site's name from its domain ("datassette"). A phrase is linked only when exactly one
of the place's URLs yields it, and never when it is a word of a participant's name ("RicBit" names a person, not a Twitch
channel). Links in "rejected" (read and judged wrong) are not proposed
again; links with `"by": "hand"` are kept as they are.
"""
import argparse
import collections
import glob
import html
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "inline_links.json")

# words that name a place on the web too generally to be a link in a summary
GENERIC = {
    "about", "arcade", "archive", "article", "articles", "blob", "blog", "commit", "commits",
    "details", "docs", "download", "drive", "emulator", "facebook", "files", "forum", "gist",
    "github", "gitlab", "google", "hackaday", "hardware", "home", "html", "index", "instagram",
    "issues", "item", "linkedin", "linux", "main", "mame", "master", "media", "medium", "news",
    "page", "pages", "post", "posts", "product", "products", "project", "projects", "pull", "readme",
    "release", "releases", "reddit", "software", "sourceforge", "status", "tags", "telegram", "topic",
    "tree", "twitter", "vercel", "video", "videos", "view", "watch", "wiki", "wikipedia", "youtu",
    "youtube", "amazon", "mercadolivre", "bios", "manuais", "manual", "manuals", "orgs", "user",
    "users", "search", "nvidia",
}
# names whose mention in a summary is not about the cited page: companies, products and people
# (the text says "Apple II", "Nintendo", "Galaga", not the page a member posted about them), and
# common words; read and judged on 2026-11-13 from the list `show` printed
NOT_LINKS = {
    "adafruit", "aliexpress", "analog", "apple", "arduino", "arm11", "bloomberg", "claude", "dmitry",
    "downloads", "dump", "fapesp", "fuse", "galaga", "gnome", "homebrew", "hypercard", "infocom",
    "irdeto", "libreoffice", "live", "mainframes", "mamedev", "marcan", "microsoft", "mitxela", "molex", "msx1",
    "multicore", "nintendo", "nsc800", "overscan", "patinho", "playlist", "second", "simcity",
    "tectoy", "tms9918", "twitch", "unicode", "unitron", "vectrex", "vision", "wired", "zilog",
}
GITHUB_DEEP = {"commit", "commits", "tree", "blob", "releases", "issues", "wiki", "actions", "tags",
               "branches", "raw", "compare", "discussions", "pulls"}


def tokens(url):
    """[(phrase, url to link, rule)] by which a summary could name this URL."""
    s = urllib.parse.urlsplit(url)
    host = (s.hostname or "").lower()
    for p in ("www.", "m.", "en.m.", "pt.m."):
        host = host.removeprefix(p)
    path = [urllib.parse.unquote(p) for p in s.path.split("/") if p]
    if host == "github.com":
        if len(path) < 2 or path[0] in ("orgs", "sponsors", "topics"):
            return []
        repo = path[1].removesuffix(".git")
        if repo.lower() in GENERIC:
            return []
        if len(path) >= 4 and path[2] in ("pull", "issues") and path[3].isdigit():
            return [(f"#{path[3]}", f"https://github.com/{path[0]}/{path[1]}/{path[2]}/{path[3]}", path[2])]
        if len(path) == 2 or path[2] in GITHUB_DEEP:
            return [(repo, f"https://github.com/{path[0]}/{repo}", "repo")]
        return []
    if host.endswith("wikipedia.org") and len(path) >= 2 and path[0] == "wiki":
        return [(path[1].replace("_", " "), url, "wikipedia")]
    if host == "archive.org" and len(path) >= 2 and path[0] == "details":
        return [(path[1], url, "archive")]
    out = []
    labels = host.split(".")
    main = labels[-3] if len(labels) >= 3 and labels[-2] in ("com", "org", "net", "gov", "edu", "co") else (
        labels[-2] if len(labels) >= 2 else "")
    if len(main) >= 5 and main not in GENERIC:     # a site named by its domain: link the site itself
        out.append((main, f"{s.scheme}://{s.hostname}/", "site"))
    if path:
        last = re.sub(r"\.(html?|php|aspx?|pdf)$", "", path[-1])
        if (re.fullmatch(r"[A-Za-z][\w.+]{3,}", last) and last.lower() not in GENERIC
                and not re.search(r"\d{5,}", last)):
            out.append((last, url, "path"))
    return out


def find(text, phrase, flags=0):
    """Positions of phrase in text as a whole word (letters, digits, '_', '-', '.' around it break it)."""
    pat = r"(?<![\w.-])" + re.escape(phrase) + r"(?![\w-]|\.\w)"
    return [m.start() for m in re.finditer(pat, text, flags)]


def load_years(root):
    years = []
    for f in sorted(glob.glob(os.path.join(root, "topics", "data", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        convs = {}
        for ch in d["chunks"]:
            for c in ch["conversations"]:
                convs.setdefault(c["first_id"], c)
        years.append((d["meta"]["year"], convs, d["taxonomy"]))
    return years


def org_repos(root):
    with open(os.path.join(root, "topics", "repos.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return [(f"https://github.com/{doc['org']}/{r['name']}", r["title"])
            for g in doc["groups"] for r in g["repos"]]


def places(root, data=None):
    """Yield (place, [texts], [conversation dicts]) for every summary the topic pages show.

    With data (the Telegram_logs directory), a bio may also link to the URLs posted in the
    messages it is based on (message_urls)."""
    years = load_years(root)
    sub = {}
    for n, convs, tax in years:
        cs = list(convs.values())
        yield f"year:{n}", [tax["intro"]], cs
        for t in tax["themes"]:
            tcs = [convs[i] for s in t["subtopics"] for i in s["conversation_ids"] if i in convs]
            yield f"theme:{n}/{t['slug']}", [t["summary"]], tcs
            for s in t["subtopics"]:
                scs = [convs[i] for i in s["conversation_ids"] if i in convs]
                sub[f"{n}/{t['slug']}/{s['slug']}"] = (n, scs)
                yield f"sub:{n}/{t['slug']}/{s['slug']}", [s["summary"]], scs
        for c in cs:
            yield f"conv:{n}:{c['first_id']}", [c["summary"]], [c]
    cpath = os.path.join(root, "topics", "crossyear.json")
    with open(cpath, encoding="utf-8") as f:
        topics = json.load(f)["topics"]
    for tp in topics:
        members = [sub[sid] for sid in tp["subtopics"] if sid in sub]
        for pk in tp.get("picks", []):
            if pk["subtopic"] in sub:
                n, scs = sub[pk["subtopic"]]
                members.append((n, [c for c in scs if c["first_id"] in pk["conversations"]]))
        allc = [c for _, scs in members for c in scs]
        yield f"topic:{tp['slug']}", [tp.get("summary", "")], allc
        for note in tp.get("year_notes", []):
            ycs = [c for n, scs in members if n == note["year"] for c in scs]
            yield f"note:{tp['slug']}:{note['year']}", [note["note"]], ycs
    # a profile bio: what its "bio_basis" cites (conversations by first id, or the person's own
    # messages, which stand for the conversations that contain them)
    allconv = [c for _, convs, _ in years for c in convs.values()]
    with open(os.path.join(root, "topics", "profiles_optin.json"), encoding="utf-8") as f:
        profiles = json.load(f)
    for uid, info in profiles.items():
        if info.get("bio"):
            ids = {int(x) for x in re.findall(r"#(\d+)", info.get("bio_basis", ""))}
            bcs = [c for c in allconv if c["first_id"] in ids
                   or any(c["first_id"] <= i <= c["last_id"] for i in ids)]
            if data:
                spans = [(c["first_id"], c["last_id"]) for c in bcs] + [(i, i) for i in ids]
                bcs = bcs + [{"participants": [], "resources": [{"ref": u, "what": f"#{mid}"}], "_msg": True}
                             for mid, u in message_urls(data, spans)]
            yield f"bio:{uid}", [info["bio"]], bcs


_ARCHIVE = {}
URL_RE = re.compile(r"https?://[^\s<>\"'`]+")


def message_urls(data, spans):
    """[(message id, URL)] posted in the archive's messages whose ids fall in any (lo, hi) span:
    URLs in the text, hidden links (MessageEntityTextUrl) and link previews. Deleted messages
    are left out."""
    if data not in _ARCHIVE:
        recs = {}
        for f in glob.glob(os.path.join(data, "messages", "*", "*.jsonl")):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    if not (r.get("archive") or {}).get("deletion"):
                        recs[r["id"]] = r["raw"]
        _ARCHIVE[data] = recs
    recs = _ARCHIVE[data]
    out = []
    for mid in sorted({i for lo, hi in spans for i in range(lo, hi + 1) if i in recs}):
        raw = recs[mid]
        urls = [u.rstrip(".,;:!?)]}") for u in URL_RE.findall(raw.get("message") or "")]
        urls += [e.get("url", "") for e in raw.get("entities") or [] if e.get("_") == "MessageEntityTextUrl"]
        w = ((raw.get("media") or {}).get("webpage") or {})
        if w.get("_") == "WebPage" and w.get("url"):
            urls.append(w["url"])
        out += [(mid, u) for u in dict.fromkeys(urls) if u.startswith(("http://", "https://"))]
    return out


def candidates(convs, repos):
    """{url: what} a place may link to: what its conversations cite, and the organisation's repos."""
    out = {}
    for c in convs:
        for r in c.get("resources") or []:
            if r["ref"].startswith(("http://", "https://")):
                out.setdefault(r["ref"], r.get("what", ""))
    for u, w in repos:
        out.setdefault(u, w)
    return out


def name_words(convs):
    return {w.lower() for c in convs for p in c.get("participants", []) for w in re.findall(r"[\w-]+", p)}


def allowed(url, cands):
    """Is url one of the candidates, or what tokens() derives from one (a repo root, a PR)?"""
    if url in cands:
        return True
    return any(url == link for u in cands for _, link, _ in tokens(u))


def propose(root, doc, data=None):
    repos = org_repos(root)
    rejected = {(r["place"], r["phrase"], r["url"]) for r in doc.get("rejected", [])}
    old = doc.get("links", {})
    links = {}
    for place, texts, convs in places(root, data):
        text = "\n".join(texts)
        cited = candidates([c for c in convs if not c.get("_msg")], [])
        posted = [u for u in candidates([c for c in convs if c.get("_msg")], []) if u not in cited]
        names = name_words(convs)
        tags = {t.lower() for c in convs for t in c.get("tags", [])}
        by_phrase = collections.defaultdict(set)
        fallback = collections.defaultdict(set)   # URLs only posted in messages: used for a phrase
        for u in list(cited) + ([] if place.startswith("conv:") else [u for u, _ in repos if u not in cited]) + posted:
            for ph, link, rule in tokens(u):
                if len(ph) >= 3 and ph.lower() not in names and ph.lower() not in NOT_LINKS:
                    # a repository named like the thing it is about ("KN5000", "TK3000") is linked
                    # only where the text says it is the repository; so is one the conversations
                    # never cite (an organisation repository)
                    need_repo = rule == "repo" and bool((u not in cited and u not in posted) or ph.lower() in tags
                                                    or re.fullmatch(r"[A-Z0-9-]+", ph))
                    (fallback if u in posted else by_phrase)[ph.lower()].add((ph, link, rule, need_repo))
        for key, opts in fallback.items():         # ... that the conversations' resources do not name
            by_phrase.setdefault(key, opts)
        found = []
        for key, opts in sorted(by_phrase.items()):
            if len({o[1] for o in opts}) != 1:
                continue
            ph, url, rule, need_repo = sorted(opts)[0]
            if rule in ("pull", "issues"):
                kind = r"(?:PR|pull request|issue)" if rule == "pull" else r"issue"
                m = re.search(kind + r"\s+" + re.escape(ph) + r"(?!\d)", text, re.I)
                if not m:
                    continue
                phrase = m.group(0)
            else:
                # a proper name: the text writes it as the URL does, or capitalised ("Datassette"
                # for datassette.org), never as a lowercase common word ("um byte")
                pos = [p for p in find(text, ph, re.I) if text[p:p + len(ph)] == ph
                       or text[p:p + len(ph)] != text[p:p + len(ph)].lower()]
                if need_repo:
                    pos = [p for p in pos if re.search(r"reposit[óo]rios?\s+(?:\w+\s+){0,2}$", text[max(0, p - 40):p], re.I)]
                if not pos:
                    continue
                p, phrase = pos[0], text[pos[0]:pos[0] + len(ph)]
                owner = url.split("/")[3] + "/" if rule == "repo" else ""
                if owner and text[max(0, p - len(owner)):p].lower() == owner.lower():
                    phrase = text[p - len(owner):p] + phrase       # "ArqueologiaDigital/Mines" as a whole
            if rule == "site" and place.startswith("conv:"):
                # a conversation naming a site it cites one page of means that page ("publicou no
                # Datassette uma versão com OCR"); longer summaries name the site itself
                host = urllib.parse.urlsplit(url).hostname
                pages = {u for u in cited if urllib.parse.urlsplit(u).hostname == host}
                if len(pages) == 1:
                    url = pages.pop()
            if (place, phrase, url) in rejected:
                continue
            found.append({"phrase": phrase, "url": url, "rule": rule})
        hand = [e for e in old.get(place, []) if e.get("by") == "hand"]
        taken = {e["phrase"] for e in hand}
        entries = hand + [e for e in found if e["phrase"] not in taken]
        if entries:
            links[place] = entries
    return links


def linkify(text, entries, esc, href):
    """HTML for text with the first occurrence of each entry's phrase linked. Returns (html, missing)."""
    spans, missing = [], []
    for e in entries:
        pos = [p for p in find(text, e["phrase"]) if not any(a < p + len(e["phrase"]) and p < b for a, b, _ in spans)]
        if not pos:
            missing.append(e["phrase"])
            continue
        spans.append((pos[0], pos[0] + len(e["phrase"]), e["url"]))
    out, at = [], 0
    for a, b, url in sorted(spans):
        out.append(esc(text[at:a]))
        out.append(f"<a class='ext' target='_blank' rel='noopener' href='{href(url)}'>{esc(text[a:b])}</a>")
        at = b
    out.append(esc(text[at:]))
    return "".join(out), missing


def context(text, phrase, width=70):
    p = find(text, phrase)
    if not p:
        return "(phrase not in text)"
    a = max(0, p[0] - width)
    return ("…" if a else "") + text[a:p[0]] + "[[" + phrase + "]]" + text[p[0] + len(phrase):p[0] + len(phrase) + width] + "…"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["propose", "show"])
    ap.add_argument("prefix", nargs="?", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"),
                    help="the archive, for the URLs posted in the messages a bio is based on")
    a = ap.parse_args()
    root = os.path.dirname(HERE)
    doc = {"links": {}, "rejected": []}
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            doc = json.load(f)
    if a.cmd == "propose":
        links = propose(root, doc, a.data)
        kinds = collections.Counter(p.split(":")[0] for p in links)
        n = sum(len(v) for v in links.values())
        print(f"{n} links in {len(links)} texts:", dict(sorted(kinds.items())))
        if not a.dry_run:
            doc["links"] = dict(sorted(links.items()))
            doc["rejected"] = sorted(doc.get("rejected", []), key=lambda r: (r["place"], r["phrase"]))
            with open(PATH + ".tmp", "w", encoding="utf-8") as f:
                f.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
            os.replace(PATH + ".tmp", PATH)
    else:
        texts = {p: "\n".join(t) for p, t, _ in places(root, a.data)}
        for place, entries in doc["links"].items():
            if place.startswith(a.prefix):
                for e in entries:
                    print(f"{place}\t{e['phrase']}\t{e['url']}\n    {context(texts.get(place, ''), e['phrase'])}")


if __name__ == "__main__":
    sys.exit(main())
