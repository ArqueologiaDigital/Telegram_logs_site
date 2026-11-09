#!/usr/bin/env python3
"""Topic index pages from topics/data/*.json (written by the topic workflow, see topics/README.md).

Writes into <out>/formatted/html/, next to the chat pages it links to:

  topicos.html              front page: intro, highlights, themes with their subtopics
  topico-<slug>.html        one theme: its subtopics, each with its conversations (title, date,
                            participants, summary, links to the first and key messages, resources)
  membro-<user id>.html     a profile, only for user ids listed in topics/profiles_optin.json

Every message id the agents cite is checked against the archive: an id that does not exist, or a
deleted message (when --deleted is placeholder), is reported and its link left out. Conversations
that no subtopic lists are reported too.

    python3 -I topics/render.py --out build [--data ../Telegram_logs] [--index topics/data/X.json]
"""
import argparse
import glob
import json
import os
import sys
import urllib.parse
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build as B  # noqa: E402

esc, q = B.esc, B.q
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def pt_date(rec):
    d = B.local(rec["date"])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


class Index:
    def __init__(self, path, d, opts):
        with open(path, encoding="utf-8") as f:
            self.raw = json.load(f)
        self.d, self.opts, self.problems = d, opts, []
        self.convs = {}
        for chunk in self.raw["chunks"]:
            for c in chunk["conversations"]:
                self.convs.setdefault(c["first_id"], c)
        self.tax = self.raw["taxonomy"]
        listed = {i for t in self.tax["themes"] for s in t["subtopics"] for i in s["conversation_ids"]}
        for i in sorted(set(self.convs) - listed):
            self.problems.append(f"conversation #{i} ({self.convs[i]['title']}) is in no subtopic")
        for i in sorted(listed - set(self.convs)):
            self.problems.append(f"subtopic lists #{i}, which is not a conversation")

    def link(self, mid, text, cls=""):
        """Link to a message on its chat page, or plain text when the id is not usable."""
        rec = self.d.by_id.get(mid)
        if rec is None:
            self.problems.append(f"message #{mid} does not exist")
            return esc(text)
        if rec["archive"].get("deletion") and self.opts.deleted != "show":
            self.problems.append(f"message #{mid} was deleted; not linked")
            return esc(text)
        href = f"{B.page_href(self.d.page_of[mid])}#m{mid}"
        return f"<a class='{cls}' href='{q(href)}'>{esc(text)}</a>" if cls else f"<a href='{q(href)}'>{esc(text)}</a>"

    def when(self, mid):
        rec = self.d.by_id.get(mid)
        return pt_date(rec) if rec else "?"


def head(title):
    return (B.head(title).replace("<html>", "<html lang=\"pt\">")
            .replace("</head>", "  \t<link rel=stylesheet href=\"topicos.css\">\n  </head>"))


def nav(extra=""):
    return ("\t<div class='navigation-top'><a href=\"topicos.html\">Tópicos</a> | "
            "<a href=\"index.html\">Páginas do log</a> | <a href=\"search.html\">Busca</a> |"
            f"{extra}</div>\n")


def resource(r):
    ref = r["ref"]
    if ref.startswith(("http://", "https://")):
        return f"<li><a target='_blank' href='{B.safe_href(ref)}'>{esc(r['what'])}</a></li>"
    return f"<li>{esc(r['what'])} <span class='ref'>({esc(ref)})</span></li>"


def conversation(ix, c, profiles):
    people = ", ".join(f"<a href='membro-{u}.html'>{esc(n)}</a>" if u else esc(n)
                       for n, u in ((n, profiles.get(n)) for n in c["participants"]))
    keys = [k for k in c.get("key_ids", []) if k != c["first_id"]]
    keylinks = " · ".join(ix.link(k, f"#{k}") for k in keys)
    res = "".join(resource(r) for r in c.get("resources", []))
    weight = "★" * c.get("weight", 1)
    return (f"<details class='conv w{c.get('weight', 1)}'><summary><span class='date'>{ix.when(c['first_id'])}</span> "
            f"<span class='title'>{esc(c['title'])}</span> <span class='weight' title='relevância'>{weight}</span></summary>"
            f"<div class='conv-body'><p>{esc(c['summary'])}</p>"
            f"<p class='meta'>Participantes: {people}</p>"
            f"<p class='meta'>{ix.link(c['first_id'], 'Ir para o início da conversa', 'go')}"
            f"{' · mensagens-chave: ' + keylinks if keylinks else ''}</p>"
            f"{'<ul class=res>' + res + '</ul>' if res else ''}</div></details>\n")


def theme_page(ix, t, profiles, period):
    parts = [head(f"{t['title']}: tópicos do grupo Arqueologia Digital"), nav(),
             f"\t<div class='topics'><p class='crumbs'><a href='topicos.html'>Tópicos</a> › {esc(t['title'])}</p>"
             f"<h1>{esc(t['title'])}</h1><p class='lead'>{esc(t['summary'])}</p><p class='period'>{esc(period)}</p>\n"]
    parts.append("<ul class='toc'>" + "".join(
        f"<li><a href='#{q(s['slug'])}'>{esc(s['title'])}</a> <span class='n'>{len(s['conversation_ids'])}</span></li>"
        for s in t["subtopics"]) + "</ul>\n")
    for s in t["subtopics"]:
        parts.append(f"<section id='{q(s['slug'])}'><h2>{esc(s['title'])}</h2><p>{esc(s['summary'])}</p>\n")
        for i in s["conversation_ids"]:
            if i in ix.convs:
                parts.append(conversation(ix, ix.convs[i], profiles))
        parts.append("</section>\n")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def front_page(ix, period, n_msgs):
    tax = ix.tax
    parts = [head("Tópicos: Arqueologia Digital (Telegram)"), nav(),
             "\t<div class='topics'><h1>Arqueologia Digital: tópicos das conversas</h1>"
             f"<p class='period'>{esc(period)} · {len(ix.convs)} conversas em {n_msgs} mensagens</p>"
             f"<p class='lead'>{esc(tax['intro'])}</p>\n"]
    parts.append("<h2>Temas</h2><div class='themes'>")
    for t in tax["themes"]:
        n = sum(len(s["conversation_ids"]) for s in t["subtopics"])
        subs = ", ".join(f"<a href='topico-{q(t['slug'])}.html#{q(s['slug'])}'>{esc(s['title'])}</a>" for s in t["subtopics"])
        parts.append(f"<div class='theme'><h3><a href='topico-{q(t['slug'])}.html'>{esc(t['title'])}</a> "
                     f"<span class='n'>{n}</span></h3><p>{esc(t['summary'])}</p><p class='subs'>{subs}</p></div>\n")
    parts.append("</div>")
    if tax.get("highlights"):
        parts.append("<h2>Momentos marcantes</h2><ul class='highlights'>")
        for h in tax["highlights"]:
            title = ix.convs.get(h["first_id"], {}).get("title", f"#{h['first_id']}")
            parts.append(f"<li><span class='date'>{ix.when(h['first_id'])}</span> "
                         f"{ix.link(h['first_id'], title)}: {esc(h['why'])}</li>")
        parts.append("</ul>")
    parts.append("<p class='method'>Índice escrito por agentes Claude que leram o log completo do período, "
                 "conferido por um segundo agente contra as mensagens, e organizado em temas. "
                 "Pode conter imprecisões: cada item leva às mensagens originais. "
                 "Para procurar palavras específicas, use a <a href='search.html'>busca</a>.</p>")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def profile_page(ix, uid, info, period, opts):
    d = ix.d
    name = d.name(uid)
    mine = [r for r in d.records if r.get("raw") and d.sender_id(r["raw"]) == uid
            and r["raw"]["_"] != "MessageService" and not r["archive"].get("deletion")]
    years = Counter(B.local(r["date"]).year for r in mine)
    top = max(years.values()) if years else 1
    bars = "".join(f"<tr><td>{y}</td><td><span class='bar' style='width:{100 * n / top:.0f}%'></span></td><td>{n}</td></tr>"
                   for y, n in sorted(years.items()))
    convs = [c for c in ix.convs.values() if name in c["participants"]]
    themes = defaultdict(list)
    for t in ix.tax["themes"]:
        for s in t["subtopics"]:
            k = [i for i in s["conversation_ids"] if i in ix.convs and name in ix.convs[i]["participants"]]
            if k:
                themes[t["slug"], t["title"]].append((s, len(k)))
    first = mine[0] if mine else None
    parts = [head(f"{name}: membro do grupo Arqueologia Digital"), nav(),
             f"\t<div class='topics profile' style='--h:{B.hue(uid)}'>"
             f"<div class='who'>{B.avatar(d, uid, name, opts).replace(chr(39) + 'avatar', chr(39) + 'avatar big')}"
             f"<div><h1>{esc(name)}</h1><p class='role'>{esc(info.get('role', ''))}</p></div></div>\n"]
    if info.get("bio"):
        parts.append(f"<p class='lead'>{esc(info['bio'])}</p><p class='period'>{esc(info.get('bio_basis', ''))}</p>\n")
    parts.append(f"<h2>Mensagens no grupo</h2><p>{len(mine)} mensagens"
                 + (f", desde {ix.link(first['id'], pt_date(first))}" if first else "") + ".</p>"
                 f"<table class='years'>{bars}</table>\n")
    if themes:
        parts.append(f"<h2>Temas em que participou</h2><p class='period'>{esc(period)}</p><ul class='toc'>")
        for (slug, title), subs in themes.items():
            parts.append(f"<li><a href='topico-{q(slug)}.html'>{esc(title)}</a>: " + ", ".join(
                f"<a href='topico-{q(slug)}.html#{q(s['slug'])}'>{esc(s['title'])}</a> ({n})" for s, n in subs) + "</li>")
        parts.append("</ul>")
    if convs:
        parts.append(f"<h2>Conversas ({len(convs)})</h2>")
        for c in sorted(convs, key=lambda c: c["first_id"]):
            parts.append(conversation(ix, c, {}))
    parts.append(f"<p class='method'>Página publicada a pedido de {esc(name)} "
                 f"({esc(info.get('opted_in', ''))}). Perfis só são publicados para quem pede.</p>")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    p.add_argument("--media-repo", default=os.path.join(HERE, "..", "..", "Telegram_logs_media"))
    p.add_argument("--media-base")
    p.add_argument("--index", help="default: the newest topics/data/*.json")
    p.add_argument("--deleted", choices=["placeholder", "show", "omit"], default="placeholder")
    opts = p.parse_args()
    hdir = os.path.join(os.path.abspath(opts.out), "formatted", "html")
    if opts.media_base is None:
        opts.media_base = urllib.parse.quote(os.path.relpath(os.path.abspath(opts.media_repo), hdir)) + "/"
    elif not opts.media_base.endswith("/"):
        opts.media_base += "/"
    path = opts.index or sorted(glob.glob(os.path.join(HERE, "data", "*.json")))[-1]
    d = B.Data(opts.data)
    ix = Index(path, d, opts)
    meta = ix.raw.get("meta", {})
    period = meta.get("period_label", "")
    n_msgs = meta.get("messages", "?")
    with open(os.path.join(HERE, "profiles_optin.json"), encoding="utf-8") as f:
        optin = {int(k): v for k, v in json.load(f).items()}
    profiles = {d.name(uid): uid for uid in optin}
    B.write(os.path.join(hdir, "topicos.html"), front_page(ix, period, n_msgs))
    for t in ix.tax["themes"]:
        B.write(os.path.join(hdir, f"topico-{t['slug']}.html"), theme_page(ix, t, profiles, period))
    for uid, info in optin.items():
        B.write(os.path.join(hdir, f"membro-{uid}.html"), profile_page(ix, uid, info, period, opts))
    import shutil
    shutil.copy(os.path.join(HERE, "topicos.css"), os.path.join(hdir, "topicos.css"))
    idx = os.path.join(hdir, "index.html")     # link the front page from the log's index page
    with open(idx, encoding="utf-8") as f:
        page = f.read()
    if "topicos.html" not in page:
        page = page.replace("</form>\n", "</form>\n\t<p class='topics-link'><a href='topicos.html'>"
                            "Tópicos das conversas</a>: temas, conversas e momentos marcantes, "
                            f"{esc(period[0].lower() + period[1:])}.</p>\n", 1)
        B.write(idx, page)
    print(f"topics: {len(ix.convs)} conversations, {len(ix.tax['themes'])} themes, "
          f"{len(optin)} profile(s) from {os.path.relpath(path, HERE)} -> {hdir}")
    for msg in sorted(set(ix.problems)):
        print("  CHECK:", msg)


if __name__ == "__main__":
    main()
