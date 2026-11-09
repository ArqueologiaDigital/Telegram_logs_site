#!/usr/bin/env python3
"""Topic index pages from topics/data/*.json (one file per group year, written by the topic
workflows, see topics/README.md).

Writes into <out>/formatted/html/, next to the chat pages it links to:

  topicos.html                    front page: every group year with its summary and main themes
  topicos-ano-<N>.html            one year: its summary, themes and highlights
  topico-ano-<N>-<slug>.html      one theme of a year: its subtopics, each with its conversations
                                  (title, date, participants, summary, links to the messages)
  membro-<user id>.html           a profile, only for user ids listed in topics/profiles_optin.json;
                                  its bio is shown only once "bio_approved" is true

Every message id the agents cite is checked against the archive: an id that does not exist, or a
deleted message (when --deleted is placeholder), is reported and its link left out. Conversations
that no subtopic lists are reported too. Also links the front page from the log's index page.

    python3 -I topics/render.py --out build [--data ../Telegram_logs]
"""
import argparse
import glob
import json
import os
import shutil
import sys
import urllib.parse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build as B  # noqa: E402

esc, q = B.esc, B.q
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MONTHS_LONG = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
               "setembro", "outubro", "novembro", "dezembro"]
ORD = ["", "Primeiro", "Segundo", "Terceiro", "Quarto", "Quinto", "Sexto", "Sétimo", "Oitavo",
       "Nono", "Décimo", "Décimo primeiro", "Décimo segundo"]


def pt_date(rec):
    d = B.local(rec["date"])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


class Year:
    """One group year: its verified conversations and its theme tree."""

    def __init__(self, path, d, opts, problems):
        with open(path, encoding="utf-8") as f:
            self.raw = json.load(f)
        meta = self.raw["meta"]
        self.n = meta["year"]
        lo, hi = meta["from"], meta["to"]
        self.span = (f"{MONTHS_LONG[int(lo[5:]) - 1]} de {lo[:4]} a "
                     f"{MONTHS_LONG[int(hi[5:]) - 1]} de {hi[:4]}")
        self.label = f"{ORD[self.n]} ano"
        self.messages = meta["messages"]
        self.d, self.opts, self.problems = d, opts, problems
        self.convs = {}
        for chunk in self.raw["chunks"]:
            for c in chunk["conversations"]:
                self.convs.setdefault(c["first_id"], c)
        self.tax = self.raw["taxonomy"]
        listed = {i for t in self.tax["themes"] for s in t["subtopics"] for i in s["conversation_ids"]}
        for i in sorted(set(self.convs) - listed):
            problems.append(f"year {self.n}: conversation #{i} ({self.convs[i]['title']}) is in no subtopic")
        for i in sorted(listed - set(self.convs)):
            problems.append(f"year {self.n}: a subtopic lists #{i}, which is not a conversation")

    def page(self):
        return f"topicos-ano-{self.n}.html"

    def theme_page(self, t):
        return f"topico-ano-{self.n}-{t['slug']}.html"


class Links:
    def __init__(self, d, opts, problems):
        self.d, self.opts, self.problems = d, opts, problems

    def msg(self, mid, text, cls=""):
        """Link to a message on its chat page, or plain text when the id is not usable."""
        rec = self.d.by_id.get(mid)
        if rec is None:
            self.problems.append(f"message #{mid} does not exist")
            return esc(text)
        if rec["archive"].get("deletion") and self.opts.deleted != "show":
            self.problems.append(f"message #{mid} was deleted; not linked")
            return esc(text)
        href = q(f"{B.page_href(self.d.page_of[mid])}#m{mid}")
        return f"<a class='{cls}' href='{href}'>{esc(text)}</a>" if cls else f"<a href='{href}'>{esc(text)}</a>"

    def when(self, mid):
        rec = self.d.by_id.get(mid)
        return pt_date(rec) if rec else "?"


def head(title):
    return (B.head(title).replace("<html>", "<html lang=\"pt\">")
            .replace("</head>", "  \t<link rel=stylesheet href=\"topicos.css\">\n  </head>"))


def nav():
    return ("\t<div class='navigation-top'><a href=\"topicos.html\">Tópicos</a> | "
            "<a href=\"index.html\">Páginas do log</a> | <a href=\"search.html\">Busca</a> |</div>\n")


def resource(r):
    ref = r["ref"]
    if ref.startswith(("http://", "https://")):
        return f"<li><a target='_blank' href='{B.safe_href(ref)}'>{esc(r['what'])}</a></li>"
    return f"<li>{esc(r['what'])} <span class='ref'>({esc(ref)})</span></li>"


def conversation(L, c, profiles):
    people = ", ".join(f"<a href='membro-{profiles[n]}.html'>{esc(n)}</a>" if n in profiles else esc(n)
                       for n in c["participants"])
    keys = [k for k in c.get("key_ids", []) if k != c["first_id"]]
    keylinks = " · ".join(L.msg(k, f"#{k}") for k in keys)
    res = "".join(resource(r) for r in c.get("resources", []))
    w = c.get("weight", 1)
    return (f"<details class='conv w{w}'><summary><span class='date'>{L.when(c['first_id'])}</span> "
            f"<span class='title'>{esc(c['title'])}</span> <span class='weight' title='relevância'>{'★' * w}</span></summary>"
            f"<div class='conv-body'><p>{esc(c['summary'])}</p>"
            f"<p class='meta'>Participantes: {people}</p>"
            f"<p class='meta'>{L.msg(c['first_id'], 'Ir para o início da conversa', 'go')}"
            f"{' · mensagens-chave: ' + keylinks if keylinks else ''}</p>"
            f"{'<ul class=res>' + res + '</ul>' if res else ''}</div></details>\n")


def year_nav(years, cur):
    items = []
    for y in years:
        label = f"Ano {y.n}"
        items.append(f"<b>{label}</b>" if y is cur else f"<a href='{y.page()}'>{label}</a>")
    return "<p class='years-nav'>" + " · ".join(items) + "</p>\n"


def theme_page(L, y, years, t, profiles):
    parts = [head(f"{t['title']} ({y.label}): tópicos do grupo Arqueologia Digital"), nav(),
             "\t<div class='topics'>", year_nav(years, y),
             f"<p class='crumbs'><a href='topicos.html'>Tópicos</a> › <a href='{y.page()}'>{y.label}</a> › "
             f"{esc(t['title'])}</p><h1>{esc(t['title'])}</h1><p class='lead'>{esc(t['summary'])}</p>"
             f"<p class='period'>{y.label}: {y.span}</p>\n"]
    parts.append("<ul class='toc'>" + "".join(
        f"<li><a href='#{q(s['slug'])}'>{esc(s['title'])}</a> <span class='n'>{len(s['conversation_ids'])}</span></li>"
        for s in t["subtopics"]) + "</ul>\n")
    for s in t["subtopics"]:
        parts.append(f"<section id='{q(s['slug'])}'><h2>{esc(s['title'])}</h2><p>{esc(s['summary'])}</p>\n")
        parts += [conversation(L, y.convs[i], profiles) for i in s["conversation_ids"] if i in y.convs]
        parts.append("</section>\n")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def themes_block(y):
    out = ["<div class='themes'>"]
    for t in y.tax["themes"]:
        n = sum(len(s["conversation_ids"]) for s in t["subtopics"])
        subs = ", ".join(f"<a href='{y.theme_page(t)}#{q(s['slug'])}'>{esc(s['title'])}</a>" for s in t["subtopics"])
        out.append(f"<div class='theme'><h3><a href='{y.theme_page(t)}'>{esc(t['title'])}</a> "
                   f"<span class='n'>{n}</span></h3><p>{esc(t['summary'])}</p><p class='subs'>{subs}</p></div>\n")
    out.append("</div>")
    return "".join(out)


def year_page(L, y, years):
    parts = [head(f"{y.label} ({y.span}): tópicos do grupo Arqueologia Digital"), nav(),
             "\t<div class='topics'>", year_nav(years, y),
             f"<p class='crumbs'><a href='topicos.html'>Tópicos</a> › {y.label}</p>"
             f"<h1>{y.label} do grupo</h1>"
             f"<p class='period'>{y.span} · {len(y.convs)} conversas em {y.messages} mensagens</p>"
             f"<p class='lead'>{esc(y.tax['intro'])}</p>\n<h2>Temas</h2>", themes_block(y)]
    if y.tax.get("highlights"):
        parts.append("<h2>Momentos marcantes</h2><ul class='highlights'>")
        for h in y.tax["highlights"]:
            title = y.convs.get(h["first_id"], {}).get("title", f"#{h['first_id']}")
            parts.append(f"<li><span class='date'>{L.when(h['first_id'])}</span> "
                         f"{L.msg(h['first_id'], title)}: {esc(h['why'])}</li>")
        parts.append("</ul>")
    parts.append(method_note())
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def method_note():
    return ("<p class='method'>Índice escrito por agentes Claude que leram o log completo de cada período. "
            "Um segundo agente conferiu cada conversa contra as mensagens, e um terceiro conferiu os resumos "
            "do ano e dos temas contra as conversas. Pode conter imprecisões: cada item leva às mensagens "
            "originais. Para procurar palavras específicas, use a <a href='search.html'>busca</a>.</p>")


def front_page(years):
    n_conv = sum(len(y.convs) for y in years)
    n_msg = sum(y.messages for y in years)
    parts = [head("Tópicos: Arqueologia Digital (Telegram)"), nav(),
             "\t<div class='topics'><h1>Arqueologia Digital: tópicos das conversas</h1>"
             f"<p class='period'>{len(years)} anos do grupo, de {years[0].span.split(' a ')[0]} a "
             f"{years[-1].span.split(' a ')[1]} · {n_conv} conversas em {n_msg} mensagens</p>"
             "<p class='lead'>O que o grupo conversou e fez, ano a ano. Cada ano tem um resumo e seus temas; "
             "dentro de cada tema estão as conversas, e cada conversa leva às mensagens originais.</p>\n",
             year_nav(years, None)]
    for y in years:
        top = ", ".join(f"<a href='{y.theme_page(t)}'>{esc(t['title'])}</a>" for t in y.tax["themes"][:5])
        parts.append(f"<div class='year' id='ano-{y.n}'><h2><a href='{y.page()}'>{y.label}</a> "
                     f"<span class='n'>{y.span} · {len(y.convs)} conversas</span></h2>"
                     f"<p>{esc(y.tax['intro'])}</p><p class='subs'>Temas: {top}"
                     f"{' …' if len(y.tax['themes']) > 5 else ''}</p></div>\n")
    parts.append(method_note())
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def profile_page(L, years, uid, info, opts):
    d = L.d
    name = d.name(uid)
    mine = [r for r in d.records if r.get("raw") and d.sender_id(r["raw"]) == uid
            and r["raw"]["_"] != "MessageService" and not r["archive"].get("deletion")]
    per_year = Counter(B.local(r["date"]).year for r in mine)
    top = max(per_year.values()) if per_year else 1
    bars = "".join(f"<tr><td>{yy}</td><td><span class='bar' style='width:{100 * n / top:.0f}%'></span></td><td>{n}</td></tr>"
                   for yy, n in sorted(per_year.items()))
    first = mine[0] if mine else None
    parts = [head(f"{name}: membro do grupo Arqueologia Digital"), nav(),
             f"\t<div class='topics profile' style='--h:{B.hue(uid)}'>"
             f"<div class='who'>{B.avatar(d, uid, name, opts).replace(chr(39) + 'avatar', chr(39) + 'avatar big')}"
             f"<div><h1>{esc(name)}</h1><p class='role'>{esc(info.get('role') or '')}</p></div></div>\n"]
    if info.get("bio") and info.get("bio_approved"):
        parts.append(f"<p class='lead'>{esc(info['bio'])}</p>\n")
    parts.append(f"<h2>Mensagens no grupo</h2><p>{len(mine)} mensagens"
                 + (f", desde {L.msg(first['id'], pt_date(first))}" if first else "") + ".</p>"
                 f"<table class='years'>{bars}</table>\n")
    total = 0
    blocks = []
    for y in years:
        convs = [c for c in y.convs.values() if name in c["participants"]]
        if not convs:
            continue
        total += len(convs)
        themes = []
        for t in y.tax["themes"]:
            k = sum(1 for s in t["subtopics"] for i in s["conversation_ids"]
                    if i in y.convs and name in y.convs[i]["participants"])
            if k:
                themes.append(f"<a href='{y.theme_page(t)}'>{esc(t['title'])}</a> ({k})")
        blocks.append(f"<details class='profile-year'><summary><b>{y.label}</b> ({y.span}): "
                      f"{len(convs)} conversas</summary><p class='subs'>Temas: {', '.join(themes)}</p>"
                      + "".join(conversation(L, c, {}) for c in sorted(convs, key=lambda c: c["first_id"]))
                      + "</details>\n")
    if blocks:
        parts.append(f"<h2>Conversas em que participou ({total})</h2>" + "".join(blocks))
    parts.append(f"<p class='method'>Página publicada a pedido de {esc(name)} ({esc(info.get('opted_in', ''))}). "
                 "Perfis só são publicados para quem pede.</p>")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    p.add_argument("--media-repo", default=os.path.join(HERE, "..", "..", "Telegram_logs_media"))
    p.add_argument("--media-base")
    p.add_argument("--deleted", choices=["placeholder", "show", "omit"], default="placeholder")
    opts = p.parse_args()
    hdir = os.path.join(os.path.abspath(opts.out), "formatted", "html")
    if opts.media_base is None:
        opts.media_base = urllib.parse.quote(os.path.relpath(os.path.abspath(opts.media_repo), hdir)) + "/"
    elif not opts.media_base.endswith("/"):
        opts.media_base += "/"
    d = B.Data(opts.data)
    problems = []
    L = Links(d, opts, problems)
    years = sorted((Year(f, d, opts, problems) for f in glob.glob(os.path.join(HERE, "data", "*.json"))),
                   key=lambda y: y.n)
    with open(os.path.join(HERE, "profiles_optin.json"), encoding="utf-8") as f:
        optin = {int(k): v for k, v in json.load(f).items()}
    profiles = {d.name(uid): uid for uid in optin}
    B.write(os.path.join(hdir, "topicos.html"), front_page(years))
    for y in years:
        B.write(os.path.join(hdir, y.page()), year_page(L, y, years))
        for t in y.tax["themes"]:
            B.write(os.path.join(hdir, y.theme_page(t)), theme_page(L, y, years, t, profiles))
    for uid, info in optin.items():
        B.write(os.path.join(hdir, f"membro-{uid}.html"), profile_page(L, years, uid, info, opts))
    shutil.copy(os.path.join(HERE, "topicos.css"), os.path.join(hdir, "topicos.css"))
    idx = os.path.join(hdir, "index.html")     # link the front page from the log's index page
    with open(idx, encoding="utf-8") as f:
        page = f.read()
    if "topicos.html" not in page:
        page = page.replace("</form>\n", "</form>\n\t<p class='topics-link'><a href='topicos.html'>"
                            "Tópicos das conversas</a>: o que o grupo conversou e fez, ano a ano.</p>\n", 1)
        B.write(idx, page)
    print(f"topics: {len(years)} year(s), {sum(len(y.convs) for y in years)} conversations, "
          f"{sum(len(y.tax['themes']) for y in years)} themes, {len(optin)} profile(s) -> {hdir}")
    for msg in sorted(set(problems)):
        print("  CHECK:", msg)


if __name__ == "__main__":
    main()
