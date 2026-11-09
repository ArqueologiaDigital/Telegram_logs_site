#!/usr/bin/env python3
"""Do the new pages 0..4 cover the same messages as the 2018 telegram-history-dump pages?

Question it answers: are old deep links (<LEGACY_NAME>-N.html) still pointing at the same
part of the conversation? For each old page, takes the sequence of message timestamps
(`title` of every `class='msg in|out'` bubble, local time, as rendered in 2018) and checks that
the new page with the same number contains all of them, in the same order.
Service rows and date separators are ignored (the 2018 formatter rendered some service
actions as bubbles and dropped others).

    python3 -I tests/compare_old_pages.py ../Telegram_logs-2018-private/formatted/html build/formatted/html
"""
import glob, os, re, sys

old_dir, new_dir = sys.argv[1], sys.argv[2]
pat = re.compile(r"class='msg (?:in|out)[^']*' (?:id='m\d+' )?title='([^'|]+?)\s*(?:\||')")
# new side also: real service messages (they carry an id; date separators do not). 2018 drew
# some actions, e.g. "pinned the message", as bubbles.
pat_new = re.compile(r"class='msg(?: (?:in|out)[^']*|-service)' id='m\d+' title='([^'|]+?)\s*(?:\||')")
ok = True
for old in sorted(glob.glob(os.path.join(old_dir, "*-[0-9].html"))):
    name = os.path.basename(old)
    o = pat.findall(open(old, encoding="utf-8").read())
    n = pat_new.findall(open(os.path.join(new_dir, name), encoding="utf-8").read())
    it = iter(n)
    in_order = all(t in it for t in o)          # o is a subsequence of n
    missing = len([t for t in o if t not in set(n)])
    same_ends = bool(o) and bool(n) and o[0] == n[0] and o[-1] == n[-1]
    print(f"{name[-7:]}: old {len(o)} bubbles, new {len(n)}; old subsequence of new: {in_order}; "
          f"missing {missing}; same first/last: {same_ends} ({o[0]} .. {o[-1]} | {n[0]} .. {n[-1]})")
    ok &= in_order
sys.exit(0 if ok else 1)
