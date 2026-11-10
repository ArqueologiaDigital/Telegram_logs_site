#!/usr/bin/env python3
"""Topic index pages from topics/data/*.json (one file per group year, written by the topic
workflows, see topics/README.md).

Writes into <out>/formatted/html/, next to the chat pages it links to:

  topicos.html                    front page: every group year with its summary and main themes
  topicos-ano-<N>.html            one year: its summary, themes and highlights
  topico-ano-<N>-<slug>.html      one theme of a year: its subtopics, each with its conversations
                                  (title, date, participants, summary, links to the messages)
  topico-<slug>.html              one cross-year topic (topics/crossyear.json): a summary of all the
                                  work on it across the years, then year by year its subtopics and
                                  conversations
  projetos.html                   the organisation's GitHub repositories (topics/repos.json), grouped by
                                  subject; topic pages also list the repositories related to them
  comunidade.html                 community gallery: a card per member in topics/profiles_optin.json
                                  (photo, name, role, active years, message count, links to the
                                  profile and to a search of their messages)
  membro-<handle>.html            a profile, only for user ids listed in topics/profiles_optin.json
                                  (handle = the "handle" the member chose there, else the user id;
                                  with a handle, membro-<user id>.html is a redirect to it);
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
import re
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

    def sid(self, t, s):
        return f"{self.n}/{t['slug']}/{s['slug']}"


class Cross:
    """Cross-year topics: topics/crossyear.json (topics/workflow_crossyear.js)."""

    def __init__(self, path, years, problems):
        self.topics = []
        self.of = {}            # subtopic id -> [topic]
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            self.topics = json.load(f)["topics"]
        known = {y.sid(t, s): (y, t, s) for y in years for t in y.tax["themes"] for s in t["subtopics"]}
        for tp in self.topics:
            assert not tp["slug"].startswith("ano-"), tp["slug"]
            tp["members"] = []
            for sid in tp["subtopics"]:
                if sid not in known:
                    problems.append(f"cross-year topic {tp['slug']} lists unknown subtopic {sid}")
                    continue
                tp["members"].append((sid,) + known[sid])
                self.of.setdefault(sid, []).append(tp)
            tp["convs"] = {i for _, y, t, s in tp["members"] for i in s["conversation_ids"] if i in y.convs}
            tp["years"] = sorted({y.n for _, y, t, s in tp["members"]})
        for sid in sorted(set(known) - set(self.of)):
            problems.append(f"subtopic {sid} is in no cross-year topic")
        ipath = os.path.join(os.path.dirname(path), "topic_images.json")
        if os.path.exists(ipath):          # one photo per topic, chosen by hand (image_candidates.py)
            with open(ipath, encoding="utf-8") as f:
                images = json.load(f)["images"]
            for tp in self.topics:
                tp["image"] = (images.get(tp["slug"]) or {}).get("msg_id")

    @staticmethod
    def image(L, tp):
        """(url, message id) of the topic's photo, or None when there is none or it is unusable."""
        mid = tp.get("image")
        entry = L.d.media.get(mid)
        rec = L.d.by_id.get(mid)
        if not entry or entry["store"] != "git" or rec is None or rec["archive"].get("deletion"):
            if mid:
                L.problems.append(f"topic {tp['slug']}: image message #{mid} has no usable photo")
            return None
        return L.opts.media_base + urllib.parse.quote(entry["path"]), mid

    @staticmethod
    def page(tp):
        return f"topico-{tp['slug']}.html"

    def link(self, y, t, s):
        """Where a yearly subtopic leads: its year section on the cross-year topic page."""
        tps = self.of.get(y.sid(t, s))
        if tps:
            return f"{self.page(tps[0])}#ano-{y.n}"
        return f"{y.theme_page(t)}#{q(s['slug'])}"


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
    return (B.head(title).replace("<html>", "<html lang=\"pt\">").replace("<body>", "<body class=\"wide\">")
            .replace("</head>", "  \t<link rel=stylesheet href=\"topicos.css\">\n  </head>"))


def nav():
    return ""      # the site header comes from build.head() (B.SITE_HEADER)


def resource(r):
    ref = r["ref"]
    if ref.startswith("http://arqueologiadigital.org"):      # posted before the site had HTTPS
        ref = "https" + ref[4:]
    if ref.startswith(("http://", "https://")):
        return f"<li><a target='_blank' href='{B.safe_href(ref)}'>{esc(r['what'])}</a></li>"
    return f"<li>{esc(r['what'])} <span class='ref'>({esc(ref)})</span></li>"


def conversation(L, c, profiles):
    people = ", ".join(f"<a href='{profiles[n]}'>{esc(n)}</a>" if n in profiles else esc(n)
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


def conv_list(items):
    """A list of conversations: one column on phones, two on wide screens (topicos.css)."""
    return "<div class='convs'>" + "".join(items) + "</div>"


def year_nav(years, cur):
    items = []
    for y in years:
        label = f"Ano {y.n}"
        items.append(f"<b>{label}</b>" if y is cur else f"<a href='{y.page()}'>{label}</a>")
    return "<p class='years-nav'>" + " · ".join(items) + "</p>\n"


def theme_page(L, y, years, t, profiles, X):
    parts = [head(f"{t['title']} ({y.label}): tópicos do grupo Arqueologia Digital"), nav(),
             "\t<div class='topics'>", year_nav(years, y),
             f"<p class='crumbs'><a href='topicos.html'>Tópicos</a> › <a href='{y.page()}'>{y.label}</a> › "
             f"{esc(t['title'])}</p><h1>{esc(t['title'])}</h1><p class='lead'>{esc(t['summary'])}</p>"
             f"<p class='period'>{y.label}: {y.span}</p>\n"]
    parts.append("<ul class='toc'>" + "".join(
        f"<li><a href='#{q(s['slug'])}'>{esc(s['title'])}</a> <span class='n'>{len(s['conversation_ids'])}</span></li>"
        for s in t["subtopics"]) + "</ul>\n")
    for s in t["subtopics"]:
        cross = " ".join(f"<a class='cross' href='{X.page(tp)}'>{esc(tp['title'])}: todos os anos ›</a>"
                         for tp in X.of.get(y.sid(t, s), []))
        parts.append(f"<section id='{q(s['slug'])}'><h2>{esc(s['title'])}</h2><p>{esc(s['summary'])}</p>"
                     f"{'<p class=meta>' + cross + '</p>' if cross else ''}\n")
        parts.append(conv_list(conversation(L, y.convs[i], profiles) for i in s["conversation_ids"] if i in y.convs))
        parts.append("</section>\n")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def topic_page(L, years, X, tp, profiles, R):
    span = f"{tp['years'][0]}" if len(tp["years"]) == 1 else f"{tp['years'][0]} a {tp['years'][-1]}"
    notes = {n["year"]: n["note"] for n in tp.get("year_notes", [])}
    parts = [head(f"{tp['title']}: tópicos do grupo Arqueologia Digital"), nav(),
             "\t<div class='topics'>",
             f"<p class='crumbs'><a href='topicos.html'>Tópicos</a> › {esc(tp['title'])}</p>"
             f"<h1>{esc(tp['title'])}</h1>"
             f"<p class='period'>{len(tp['convs'])} conversas · anos {span} do grupo</p>"]
    parts.append(R.box(tp["slug"]))
    img = X.image(L, tp)
    if img:
        rec = L.d.by_id[img[1]]
        cap = f"Foto enviada por {L.d.sender(rec['raw'])} em {pt_date(rec)}"
        parts.append(f"<figure class='topic-image'><a href='{q(img[0])}'><img src='{q(img[0])}' alt=''></a>"
                     f"<figcaption>{L.msg(img[1], cap)}</figcaption></figure>")
    parts += [f"<p class='lead'>{esc(par)}</p>" for par in tp.get("summary", "").split("\n\n") if par.strip()]
    parts.append("<p class='years-nav'>Ano a ano: " + " · ".join(
        f"<a href='#ano-{n}'>Ano {n}</a>" for n in tp["years"]) + "</p>\n")
    by_year = {}
    for sid, y, t, s in tp["members"]:
        by_year.setdefault(y.n, (y, []))[1].append((t, s))
    for n in sorted(by_year):
        y, subs = by_year[n]
        parts.append(f"<section id='ano-{n}' class='topic-year'><h2><a href='{y.page()}'>{y.label}</a> "
                     f"<span class='n'>{y.span}</span></h2>")
        if notes.get(n):
            parts.append(f"<p>{esc(notes[n])}</p>")
        for t, s in subs:
            parts.append(f"<h3>{esc(s['title'])} <span class='n'>no tema <a href='{y.theme_page(t)}#{q(s['slug'])}'>"
                         f"{esc(t['title'])}</a></span></h3><p class='subsum'>{esc(s['summary'])}</p>\n")
            parts.append(conv_list(conversation(L, y.convs[i], profiles) for i in s["conversation_ids"] if i in y.convs))
        parts.append("</section>\n")
    parts.append(method_note())
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def themes_block(y, X):
    out = ["<div class='themes'>"]
    for t in y.tax["themes"]:
        n = sum(len(s["conversation_ids"]) for s in t["subtopics"])
        subs = ", ".join(f"<a href='{X.link(y, t, s)}'>{esc(s['title'])}</a>" for s in t["subtopics"])
        out.append(f"<div class='theme'><h3><a href='{y.theme_page(t)}'>{esc(t['title'])}</a> "
                   f"<span class='n'>{n}</span></h3><p>{esc(t['summary'])}</p><p class='subs'>{subs}</p></div>\n")
    out.append("</div>")
    return "".join(out)


def year_page(L, y, years, X):
    parts = [head(f"{y.label} ({y.span}): tópicos do grupo Arqueologia Digital"), nav(),
             "\t<div class='topics'>", year_nav(years, y),
             f"<p class='crumbs'><a href='topicos.html'>Tópicos</a> › {y.label}</p>"
             f"<h1>{y.label} do grupo</h1>"
             f"<p class='period'>{y.span} · {len(y.convs)} conversas em {y.messages} mensagens</p>"
             f"<p class='lead'>{esc(y.tax['intro'])}</p>\n<h2>Temas</h2>", themes_block(y, X)]
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


def front_page(years, X, L):
    n_conv = sum(len(y.convs) for y in years)
    n_msg = sum(y.messages for y in years)
    parts = [head("Tópicos: Arqueologia Digital (Telegram)"), nav(),
             "\t<div class='topics'><h1>Arqueologia Digital: tópicos das conversas</h1>"
             f"<p class='period'>{len(years)} anos do grupo, de {years[0].span.split(' a ')[0]} a "
             f"{years[-1].span.split(' a ')[1]} · {n_conv} conversas em {n_msg} mensagens</p>"
             "<p class='lead'>O que o grupo conversou e fez, por assunto ao longo de todos os anos ou ano a ano. "
             "Cada assunto e cada ano têm um resumo; abaixo deles estão as conversas, e cada conversa leva às "
             "mensagens originais.</p>\n",
             "<p class='group-links'>O grupo: <a href='https://t.me/arqueologiadigital'>Telegram</a> · "
             "<a href='projetos.html'>Projetos no GitHub</a> · "
             "<a href='https://forum.fiozera.com.br/'>Fórum Fiozera</a> · "
             "<a href='https://arqueologiadigital.org/galeria.html'>Galeria de fotos</a> · "
             "<a href='comunidade.html'>Comunidade</a></p>\n",
             year_nav(years, None)]
    if X.topics:
        parts.append("<h2>Assuntos</h2><p class='period'>Cada assunto reúne tudo o que o grupo conversou e fez "
                     "sobre ele, em todos os anos.</p><ul class='cross-topics'>")
        for tp in X.topics:
            ys = tp["years"]
            span = f"ano {ys[0]}" if len(ys) == 1 else f"anos {ys[0]}–{ys[-1]}"
            img = X.image(L, tp)
            thumb = (f"<a class='thumb' href='{X.page(tp)}' tabindex='-1' aria-hidden='true'>"
                     f"<img src='{q(img[0])}' alt='' loading='lazy'></a>" if img else "")
            parts.append(f"<li>{thumb}<div class='text'><a href='{X.page(tp)}'>{esc(tp['title'])}</a> "
                         f"<span class='n'>{len(tp['convs'])} conversas, {span}</span><br>"
                         f"<span class='scope'>{esc(tp['scope'])}</span></div></li>")
        parts.append("</ul><h2>Ano a ano</h2>")
    for y in years:
        top = ", ".join(f"<a href='{y.theme_page(t)}'>{esc(t['title'])}</a>" for t in y.tax["themes"][:5])  # noqa
        parts.append(f"<div class='year' id='ano-{y.n}'><h2><a href='{y.page()}'>{y.label}</a> "
                     f"<span class='n'>{y.span} · {len(y.convs)} conversas</span></h2>"
                     f"<p>{esc(y.tax['intro'])}</p><p class='subs'>Temas: {top}"
                     f"{' …' if len(y.tax['themes']) > 5 else ''}</p></div>\n")
    parts.append(method_note())
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


class Repos:
    """The organisation's repositories: topics/repos.json, written by hand."""

    def __init__(self, path, X, problems):
        self.groups, self.org = [], ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.groups, self.org = doc["groups"], doc["org"]
        slugs = {tp["slug"] for tp in X.topics}
        self.by_topic = {}
        for g in self.groups:
            for r in g["repos"]:
                for t in r.get("topics", g["topics"]):
                    if X.topics and t not in slugs:
                        problems.append(f"repos.json: {r['name']} names unknown topic {t}")
                    self.by_topic.setdefault(t, []).append(r)

    def url(self, r):
        return f"https://github.com/{self.org}/{r['name']}"

    def item(self, r):
        site = f" · <a href='{q(r['site'])}'>site</a>" if r.get("site") else ""
        return (f"<li><a href='{q(self.url(r))}'>{esc(r['title'])}</a>{site}<br>"
                f"<span class='scope'>{esc(r['about'])}</span></li>")

    def box(self, slug):
        """Repositories related to a topic, for its page."""
        rs = self.by_topic.get(slug)
        if not rs:
            return ""
        return ("<aside class='repos-box'><h2>Repositórios do grupo sobre este assunto</h2><ul class='repos'>"
                + "".join(self.item(r) for r in rs)
                + "</ul><p class='meta'><a href='projetos.html'>Todos os projetos ›</a></p></aside>\n")


def projects_page(R, X, L):
    n = sum(len(g["repos"]) for g in R.groups)
    titles = {tp["slug"]: tp for tp in X.topics}
    parts = [head("Projetos: Arqueologia Digital"), nav(),
             "\t<div class='topics'><h1>Projetos do grupo</h1>"
             f"<p class='period'>{n} repositórios públicos em "
             f"<a href='https://github.com/{R.org}'>github.com/{R.org}</a></p>"
             "<p class='lead'>O que o grupo produz fica em repositórios abertos: documentos históricos digitalizados, "
             "esquemáticos redesenhados, emuladores, engenharia reversa e jogos. Use, estude e contribua.</p>\n"
             "<ul class='toc'>" + "".join(f"<li><a href='#{q(g['slug'])}'>{esc(g['title'])}</a> "
                                          f"<span class='n'>{len(g['repos'])}</span></li>" for g in R.groups) + "</ul>\n"]
    for g in R.groups:
        rel = " · ".join(f"<a href='{X.page(titles[t])}'>{esc(titles[t]['title'])}</a>" for t in g["topics"] if t in titles)
        im = g.get("image") or {}
        if im.get("topic") in titles:
            img = X.image(L, titles[im["topic"]])
        else:
            img = X.image(L, {"slug": "projetos/" + g["slug"], "image": im.get("msg_id")})
        fig = ""
        if img:
            rec = L.d.by_id[img[1]]
            cap = f"Foto enviada por {L.d.sender(rec['raw'])} em {pt_date(rec)}"
            fig = (f"<figure class='topic-image small'><a href='{q(img[0])}'><img src='{q(img[0])}' alt='' "
                   f"loading='lazy'></a><figcaption>{L.msg(img[1], cap)}</figcaption></figure>")
        parts.append(f"<section class='project-group' id='{q(g['slug'])}'><h2>{esc(g['title'])}</h2>{fig}"
                     + (f"<p>{esc(g['intro'])}</p>" if g["intro"] else "")
                     + (f"<p class='meta'>Conversas do grupo sobre isto: {rel}</p>" if rel else "")
                     + "<ul class='repos'>" + "".join(R.item(r) for r in g["repos"]) + "</ul></section>\n")
    parts.append("<p class='method'>Quer ajudar? Cada repositório aceita issues e pull requests no GitHub, "
                 "e as conversas acontecem no <a href='https://t.me/arqueologiadigital'>grupo do Telegram</a>.</p>")
    parts.append("</div>\n  </body>\n</html>\n")
    return "".join(parts)


def member_page(uid, info):
    """File name of a member's profile: by the handle they chose, else by user id."""
    handle = info.get("handle")
    if handle:
        assert re.fullmatch(r"[a-z0-9_]{2,40}", handle), handle
        return f"membro-{handle}.html"
    return f"membro-{uid}.html"


def messages_of(d, uid):
    return [r for r in d.records if r.get("raw") and d.sender_id(r["raw"]) == uid
            and r["raw"]["_"] != "MessageService" and not r["archive"].get("deletion")]


def gallery_page(L, optin, opts):
    """Community gallery: only members who asked to be listed (profiles_optin.json)."""
    d = L.d
    cards = []
    for uid, info in sorted(optin.items(), key=lambda kv: (kv[1].get("opted_in", ""), kv[0])):
        name = d.name(uid)
        mine = messages_of(d, uid)
        ys = sorted({B.local(r["date"]).year for r in mine})
        active = "" if not ys else (str(ys[0]) if len(ys) == 1 else f"{ys[0]}–{ys[-1]}")
        search = "search.html?" + urllib.parse.urlencode({"autor": name})
        big = B.avatar(d, uid, name, opts).replace("'avatar", "'avatar big")
        page = member_page(uid, info)
        cards.append(
            f"<div class='card' style='--h:{B.hue(uid)}'><a href='{page}'>{big}</a>"
            f"<h3><a href='{page}'>{esc(name)}</a></h3>"
            f"<p class='role'>{esc(info.get('role') or '')}</p>"
            f"<p class='meta'>{len(mine)} mensagens{' · ativo em ' + active if active else ''}</p>"
            f"<p class='meta'><a href='{page}'>Perfil</a> · <a href='{q(search)}'>Mensagens</a></p></div>\n")
    return "".join([
        head("Comunidade: Arqueologia Digital (Telegram)"), nav(),
        "\t<div class='topics'><h1>Comunidade</h1>"
        "<p class='lead'>Membros do grupo que pediram para aparecer aqui. Cada cartão leva ao perfil da pessoa "
        "e às mensagens dela no log.</p>\n<div class='gallery'>", "".join(cards), "</div>"
        "<p class='method'>Esta galeria é opt-in: só entra quem pede. Quer aparecer aqui, ou sair? "
        "Fale com os administradores do grupo no Telegram.</p>"
        "</div>\n  </body>\n</html>\n"])


def profile_page(L, years, uid, info, opts, X):
    d = L.d
    name = d.name(uid)
    mine = messages_of(d, uid)
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
    if X.topics:
        mine_t = [(tp, sum(1 for _, y, t, s in tp["members"] for i in s["conversation_ids"]
                           if i in y.convs and name in y.convs[i]["participants"])) for tp in X.topics]
        mine_t = [(tp, k) for tp, k in mine_t if k]
        if mine_t:
            parts.append("<h2>Assuntos em que participou</h2><p class='subs'>" + ", ".join(
                f"<a href='{X.page(tp)}'>{esc(tp['title'])}</a> ({k})"
                for tp, k in sorted(mine_t, key=lambda x: -x[1])) + "</p>")
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
                      + conv_list(conversation(L, c, {}) for c in sorted(convs, key=lambda c: c["first_id"]))
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
    p.add_argument("--drafts", action="store_true",
                   help="also render profiles marked \"published\": false (local previews only)")
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
        optin = {int(k): v for k, v in json.load(f).items() if v.get("published", True) or opts.drafts}
    profiles = {d.name(uid): member_page(uid, info) for uid, info in optin.items()}
    X = Cross(os.path.join(HERE, "crossyear.json"), years, problems)
    R = Repos(os.path.join(HERE, "repos.json"), X, problems)
    B.write(os.path.join(hdir, "projetos.html"), projects_page(R, X, L))
    B.write(os.path.join(hdir, "topicos.html"), front_page(years, X, L))
    for y in years:
        B.write(os.path.join(hdir, y.page()), year_page(L, y, years, X))
        for t in y.tax["themes"]:
            B.write(os.path.join(hdir, y.theme_page(t)), theme_page(L, y, years, t, profiles, X))
    for tp in X.topics:
        B.write(os.path.join(hdir, X.page(tp)), topic_page(L, years, X, tp, profiles, R))
    for uid, info in optin.items():
        page = member_page(uid, info)
        B.write(os.path.join(hdir, page), profile_page(L, years, uid, info, opts, X))
        if page != f"membro-{uid}.html":       # the address by user id keeps working
            B.write(os.path.join(hdir, f"membro-{uid}.html"),
                    f"<!DOCTYPE html><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0; url={page}\">"
                    f"<link rel=\"canonical\" href=\"{page}\"><a href=\"{page}\">{esc(d.name(uid))}</a>\n")
    B.write(os.path.join(hdir, "comunidade.html"), gallery_page(L, optin, opts))
    shutil.copy(os.path.join(HERE, "topicos.css"), os.path.join(hdir, "topicos.css"))
    idx = os.path.join(hdir, "index.html")     # link the front page from the log's index page
    with open(idx, encoding="utf-8") as f:
        page = f.read()
    if "topicos.html" not in page:
        page = page.replace("</form>\n", "</form>\n\t<p class='topics-link'><a href='topicos.html'>"
                            "Tópicos das conversas</a>: o que o grupo conversou e fez, por assunto e ano a ano. "
                            "<a href='comunidade.html'>Comunidade</a>: membros do grupo.</p>\n", 1)
        B.write(idx, page)
    print(f"topics: {len(years)} year(s), {sum(len(y.convs) for y in years)} conversations, "
          f"{sum(len(y.tax['themes']) for y in years)} themes, {len(X.topics)} cross-year topics, "
          f"{len(optin)} profile(s) -> {hdir}")
    for msg in sorted(set(problems)):
        print("  CHECK:", msg)


if __name__ == "__main__":
    main()
