"""Apply reviewed gender fixes to the topic index JSON files.

    python3 -I apply_fixes.py PARTS_DIR FIXES.json [--dry-run]

FIXES.json: [{"n", "old", "new"}] where n is the item number in PARTS_DIR/part*.jsonl (which
records file and JSON path). Each "old" must occur exactly once in the current string at that
path. Files are rewritten in their own format: topics/data/*.json as json.dumps(indent=1) with
no trailing newline, other files with indent=1 or 2 and a trailing newline, detected per file.
"""
import glob
import json
import os
import sys


def fmt_of(text, data):
    for ind in (1, 2):
        s = json.dumps(data, ensure_ascii=False, indent=ind)
        if s == text:
            return ind, ""
        if s + "\n" == text:
            return ind, "\n"
    raise SystemExit("unknown JSON format")


def main():
    parts, fixes_path = sys.argv[1], sys.argv[2]
    dry = "--dry-run" in sys.argv
    items = {}
    for p in glob.glob(os.path.join(parts, "part*.jsonl")):
        for line in open(p, encoding="utf-8"):
            it = json.loads(line)
            items[it["n"]] = it
    fixes = json.load(open(fixes_path, encoding="utf-8"))
    docs = {}
    for fx in fixes:
        it = items[fx["n"]]
        f = it["file"]
        if f not in docs:
            text = open(f, encoding="utf-8").read()
            data = json.loads(text)
            docs[f] = [data, fmt_of(text, data), 0]
        node = docs[f][0]
        for k in it["path"][:-1]:
            node = node[k]
        cur = node[it["path"][-1]]
        if cur.count(fx["old"]) != 1:
            raise SystemExit(f"n={fx['n']}: old occurs {cur.count(fx['old'])} times: {fx['old']!r}")
        node[it["path"][-1]] = cur.replace(fx["old"], fx["new"])
        docs[f][2] += 1
    for f, (data, (ind, nl), n) in sorted(docs.items()):
        print(f"{f}: {n} fixes")
        if not dry:
            with open(f + ".tmp", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False, indent=ind) + nl)
            os.replace(f + ".tmp", f)


if __name__ == "__main__":
    main()
