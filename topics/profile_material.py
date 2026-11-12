#!/usr/bin/env python3
"""Gather the material for writing a member's profile bio (profiles_optin.json).

Answers: how many messages has this person sent, since when, per year; in how many conversations
of the topic index do they take part (the "aparece em N conversas do índice" of the bios); and
which sentences of the index summaries name them. Every claim in a bio must then be checked
against the person's own messages, which are listed too.

    python3 -I topics/profile_material.py --uid 625709632 --name RicBit --out SCRATCH/ricbit

--name is matched against the conversation `participants` (as the index spells the person's name,
e.g. "Ranoya" or "Hugo (Agaelebê)") and against the summary sentences. Writes OUT_msgs.txt (their
messages with 60+ characters or a link preview: id, date, text, preview title) and OUT_idx.txt
(#first_id title: sentences naming them) and prints the counts.
"""
import argparse
import collections
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uid", type=int, required=True, help="Telegram user id (users/users.jsonl in Telegram_logs)")
    p.add_argument("--name", required=True, help="name as it appears in the index participants")
    p.add_argument("--out", required=True, help="output prefix (scratch)")
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    a = p.parse_args()
    n, first, years = 0, None, collections.Counter()
    with open(a.out + "_msgs.txt", "w", encoding="utf-8") as out:
        for f in sorted(glob.glob(os.path.join(a.data, "messages", "*", "*.jsonl"))):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line).get("raw") or {}
                    if (r.get("from_id") or {}).get("user_id") != a.uid:
                        continue
                    n += 1
                    d = r.get("date", "")
                    first = first or d
                    years[d[:4]] += 1
                    text = (r.get("message") or "").replace("\n", " ")
                    wp = (r.get("media") or {}).get("webpage") or {}
                    if len(text) >= 60 or wp.get("title"):
                        print(r["id"], d[:10], text[:230], f"[{wp['title']}]" if wp.get("title") else "", file=out)
    convs = []
    with open(a.out + "_idx.txt", "w", encoding="utf-8") as out:
        for f in sorted(glob.glob(os.path.join(HERE, "data", "*.json"))):
            with open(f, encoding="utf-8") as fh:
                year = json.load(fh)
            for ch in year.get("chunks", []):
                for c in ch.get("conversations", []):
                    if any(a.name in x for x in c.get("participants", [])):
                        convs.append(c["first_id"])
                        sents = [s for s in re.split(r"(?<=[.!?])\s+", c.get("summary", "")) if a.name in s]
                        if sents:
                            print(f"#{c['first_id']} {c['title']}: " + " ".join(sents), file=out)
    print(f"{n} messages, first {first}, per year {dict(sorted(years.items()))}; "
          f"{len(convs)} conversations in the index -> {a.out}_msgs.txt, {a.out}_idx.txt")


if __name__ == "__main__":
    main()
