#!/usr/bin/env python3
"""Per-year numbers of the topic index, from topics/data/*.json.

Question it answers: for each group year, how many conversations survived verification, how
many corrections the verifiers made (to conversations, and to the year summary, themes and
highlights), and how big the theme tree is. These are the numbers quoted in topics/README.md
and in the commit messages that added the data.

    python3 -I topics/stats.py            # aligned Markdown table on stdout

Columns:
  conversations        verified conversations (unique first message ids)
  conv. corrections    lines in chunks[].corrections (one per change a verifier made)
  themes, subtopics    size of the theme tree
  highlights           "momentos marcantes"
  tax. corrections     lines in taxonomy_check.corrections ("-" if that check has not run)
  felipe               conversations whose participants include Felipe "Juca" Sanches
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FELIPE = 'Felipe "Juca" Sanches'


def table(rows):
    head = list(rows[0])
    w = [max(len(str(r[k])) for r in rows + [dict(zip(head, head))]) for k in head]
    line = lambda vals: "| " + " | ".join(str(v).ljust(n) for v, n in zip(vals, w)) + " |"
    return "\n".join([line(head), "|" + "|".join("-" * (n + 2) for n in w) + "|"]
                     + [line([r[k] for k in head]) for r in rows])


def main():
    rows = []
    tot = dict.fromkeys(["conversations", "conv. corrections", "themes", "subtopics", "highlights", "felipe"], 0)
    for p in sorted(glob.glob(os.path.join(HERE, "data", "*.json"))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        convs = {c["first_id"]: c for ch in d["chunks"] for c in ch["conversations"]}
        tax = d["taxonomy"]
        check = d.get("taxonomy_check")
        r = {"year": d["meta"]["year"], "period": f"{d['meta']['from']}..{d['meta']['to']}",
             "conversations": len(convs),
             "conv. corrections": sum(len(ch["corrections"]) for ch in d["chunks"]),
             "themes": len(tax["themes"]),
             "subtopics": sum(len(t["subtopics"]) for t in tax["themes"]),
             "highlights": len(tax["highlights"]),
             "tax. corrections": len(check["corrections"]) if check else "-",
             "felipe": sum(1 for c in convs.values() if FELIPE in c["participants"])}
        for k in tot:
            tot[k] += r[k]
        rows.append(r)
    tc = [r["tax. corrections"] for r in rows if r["tax. corrections"] != "-"]
    rows.append({"year": "all", "period": "", **tot, "tax. corrections": sum(tc)})
    print(table(rows))


if __name__ == "__main__":
    main()
