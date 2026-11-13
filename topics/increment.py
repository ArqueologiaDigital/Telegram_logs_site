#!/usr/bin/env python3
"""Save the results of topics/workflow_increment.js (the group year in progress) into the index.

    python3 -I topics/increment.py year RESULT.json --year 10 --from 2026-11 --until-id 42296 \
        --messages 250 --run wf_... --transcripts "topics/transcript.py --chunks 2026-11..2026-11"
        -> topics/data/<from>_<from + 11 months>.json, marked "in_progress" up to the date of
           message --until-id (replaced as a whole on each run: the year so far is redone)

    python3 -I topics/increment.py topics RESULT.json --year 10 --run wf_...
        -> topics/crossyear.json: the year's subtopics added to their topics, new topics appended,
           each touched topic's summary extended by the agents' addition (the existing text, read
           by a person, is never rewritten) and its note for the year set; the checker's
           corrections are appended to the topic's "corrections", prefixed with the year

    python3 -I topics/increment.py ids --year 10      # the year's subtopic ids, for stage "topics"

RESULT.json is the workflow's return value. Both commands print what changed. Running "topics"
again for the same year would append a second addition: restore crossyear.json from git first.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build as B  # noqa: E402


def dump(path, doc, newline):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + ("\n" if newline else ""))
    os.replace(path + ".tmp", path)


def year_path(year):
    for name in os.listdir(os.path.join(HERE, "data")):
        with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
            if json.load(f)["meta"]["year"] == year:
                return os.path.join(HERE, "data", name)
    return None


def cmd_year(a, res):
    y, m = int(a.from_[:4]), int(a.from_[5:])
    to = f"{y + (m + 10) // 12}-{(m + 10) % 12 + 1:02d}"
    path = os.path.join(HERE, "data", f"{a.from_}_{to}.json")
    old = year_path(a.year)
    if old and os.path.abspath(old) != os.path.abspath(path):
        sys.exit(f"year {a.year} is already in {old}")
    d = B.Data(a.data)
    until = B.local(d.by_id[a.until_id]["date"]).strftime("%Y-%m-%d")
    doc = {
        "meta": {"year": a.year, "from": a.from_, "to": to, "period": f"{a.from_}..{to}",
                 "messages": a.messages, "in_progress": True, "until": until, "until_id": a.until_id,
                 "made": datetime.date.today().isoformat(),
                 "model": "claude-opus-5-5 (workflow agents, inherited from the session)",
                 "workflow": f"topics/workflow_increment.js stage year (run {a.run})",
                 "transcripts": a.transcripts},
        "chunks": res["chunks"], "taxonomy": res["taxonomy"], "taxonomy_check": res["taxonomy_check"],
    }
    dump(path, doc, newline=False)
    convs = [c for ch in res["chunks"] for c in ch["conversations"]]
    print(f"{path}: {len(convs)} conversations, {sum(len(ch['corrections']) for ch in res['chunks'])} "
          f"verifier corrections, {len(res['taxonomy']['themes'])} themes, "
          f"{sum(len(t['subtopics']) for t in res['taxonomy']['themes'])} subtopics, "
          f"{len(res['taxonomy_check']['corrections'] or [])} taxonomy corrections; up to #{a.until_id} ({until})")


def cmd_topics(a, res):
    path = os.path.join(HERE, "crossyear.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    by = {t["slug"]: t for t in doc["topics"]}
    for n in res["new_topics"]:
        if n["slug"] not in by and any(x["topic"] == n["slug"] for x in res["assign"]):
            t = {"slug": n["slug"], "title": n["title"], "scope": n["scope"], "subtopics": [], "summary": "",
                 "year_notes": [], "corrections": [], "unchecked": False}
            doc["topics"].append(t)
            by[n["slug"]] = t
            print(f"new topic {n['slug']}: {n['title']}")
    for x in res["assign"]:
        t = by[x["topic"]]
        if x["subtopic"] not in t["subtopics"]:
            t["subtopics"].append(x["subtopic"])
    for slug, w in res["texts"].items():
        t = by[slug]
        add = w["addition"].strip()
        if w["placement"] == "new":
            t["summary"] = add
        elif add and w["placement"] == "new-paragraph":
            t["summary"] = t["summary"].rstrip() + "\n\n" + add
        elif add and w["placement"] == "end-of-last-paragraph":
            t["summary"] = t["summary"].rstrip() + " " + add
        t["year_notes"] = [n for n in t.get("year_notes", []) if n["year"] != a.year] + [{"year": a.year, "note": w["note"]}]
        t["year_notes"].sort(key=lambda n: n["year"])
        t["corrections"] = t.get("corrections", []) + [f"Ano {a.year} (run {a.run}): {c}" for c in w["corrections"]]
        print(f"{slug}: {w['placement']}: {add[:300]}\n    note: {w['note']}")
    untouched = sorted({x["topic"] for x in res["assign"]} - set(res["texts"]))
    if untouched:
        print("topics given subtopics but no new text (agent failed?):", ", ".join(untouched))
    doc["meta"].setdefault("increments", []).append(
        {"year": a.year, "made": datetime.date.today().isoformat(),
         "workflow": f"topics/workflow_increment.js stage topics (run {a.run})",
         "topics": sorted(res["texts"])})
    dump(path, doc, newline=True)


def cmd_ids(a):
    with open(year_path(a.year), encoding="utf-8") as f:
        tax = json.load(f)["taxonomy"]
    print(",".join(f"{a.year}/{t['slug']}/{s['slug']}" for t in tax["themes"] for s in t["subtopics"]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["year", "topics", "ids"])
    p.add_argument("result", nargs="?")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--from", dest="from_")
    p.add_argument("--until-id", type=int)
    p.add_argument("--messages", type=int)
    p.add_argument("--run", default="?")
    p.add_argument("--transcripts", default="")
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    a = p.parse_args()
    if a.cmd == "ids":
        return cmd_ids(a)
    with open(a.result, encoding="utf-8") as f:
        res = json.load(f)
    (cmd_year if a.cmd == "year" else cmd_topics)(a, res)


if __name__ == "__main__":
    main()
