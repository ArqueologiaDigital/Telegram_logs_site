"""Show each proposed fix with ~250 chars of context: show.py PARTS_DIR FIXES.json"""
import glob, json, os, sys
items = {}
for p in glob.glob(os.path.join(sys.argv[1], "part*.jsonl")):
    for line in open(p, encoding="utf-8"):
        it = json.loads(line); items[it["n"]] = it
for fx in json.load(open(sys.argv[2], encoding="utf-8")):
    t = items[fx["n"]]["text"]; i = t.find(fx["old"])
    print(f"[n={fx['n']} {fx.get('who')} {fx.get('confidence')}] {fx['old']!r} -> {fx['new']!r}\n  ...{t[max(0,i-250):i+len(fx['old'])+80]}...\n")
