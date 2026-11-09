#!/usr/bin/env python3
"""Material for the cross-year topic agents, from topics/data/*.json (the verified year indexes).

    python3 -I topics/material.py --list                 every yearly subtopic, one line each:
                                                         id | year | theme | subtopic | n conversations | summary
    python3 -I topics/material.py --ids                  just the subtopic ids, comma-separated
    python3 -I topics/material.py --subtopics ID,ID,...  the full material of those subtopics, by year:
                                                         subtopic summaries and every conversation
                                                         (#id, date, title, summary, participants)

A subtopic id is <year>/<theme slug>/<subtopic slug>, e.g. 1/patinho-feio/painel-e-cde-3.
"""
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    years = []
    for p in sorted(glob.glob(os.path.join(HERE, "data", "*.json"))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        convs = {c["first_id"]: c for ch in d["chunks"] for c in ch["conversations"]}
        years.append((d["meta"], d["taxonomy"], convs))
    return sorted(years, key=lambda y: y[0]["year"])


def subtopics(years):
    for meta, tax, convs in years:
        for t in tax["themes"]:
            for s in t["subtopics"]:
                yield f"{meta['year']}/{t['slug']}/{s['slug']}", meta, t, s, convs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--ids", action="store_true")
    g.add_argument("--subtopics")
    a = p.parse_args()
    years = load()
    if a.list:
        for sid, meta, t, s, convs in subtopics(years):
            print(f"{sid} | ano {meta['year']} ({meta['from']}..{meta['to']}) | {t['title']} | {s['title']} | "
                  f"{len(s['conversation_ids'])} conversas | {s['summary']}")
    elif a.ids:
        print(",".join(sid for sid, *_ in subtopics(years)))
    else:
        want = [x.strip() for x in a.subtopics.split(",") if x.strip()]
        found = {sid: (meta, t, s, convs) for sid, meta, t, s, convs in subtopics(years) if sid in want}
        for sid in want:
            if sid not in found:
                print(f"!! unknown subtopic id: {sid}")
        for sid in sorted(found, key=lambda x: (int(x.split("/")[0]), want.index(x))):
            meta, t, s, convs = found[sid]
            print(f"\n=== {sid} — ano {meta['year']} ({meta['from']}..{meta['to']}) — tema \"{t['title']}\" — "
                  f"subtópico \"{s['title']}\"\nResumo do subtópico: {s['summary']}")
            for i in s["conversation_ids"]:
                c = convs.get(i)
                if c:
                    print(f"- #{i} [{c['weight']}★] {c['title']}: {c['summary']} "
                          f"(participantes: {', '.join(c['participants'])})")


if __name__ == "__main__":
    main()
