#!/usr/bin/env python3
"""How many messages have emoji reactions, and how many reaction chips can name who reacted?

Reads the archive's raw.reactions (Telethon MessageReactions) and prints:
  - messages with reactions, per year, and distinct emoji (custom emoji counted as one);
  - chips (one per emoji per message) whose reactors recent_reactions lists in full, in part, or not
    at all;
  - chips chosen by the archiving account (chosen_order set), which Telegram leaves out of
    recent_reactions and build.py names from the sender of the messages marked "out".

    python3 -I tests/reaction_counts.py ../Telegram_logs

On 2026-11-12 (data up to message #42296) it printed: 3174 messages with reactions out of 40994,
45 distinct emoji, 289 chips chosen by the archiving account, 17 chips with no reactor named.
"""
import collections
import glob
import json
import os
import sys


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else os.path.join("..", "Telegram_logs")
    total = with_rx = 0
    per_year = collections.Counter()
    emoji = collections.Counter()
    chips = collections.Counter()
    for path in sorted(glob.glob(os.path.join(data, "messages", "*", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                total += 1
                rx = (rec.get("raw") or {}).get("reactions") or {}
                results = rx.get("results") or []
                if not results:
                    continue
                with_rx += 1
                per_year[rec["date"][:4]] += 1
                recent = rx.get("recent_reactions") or []
                for res in results:
                    r = res.get("reaction") or {}
                    emoji[r.get("emoticon") or f"custom:{r.get('document_id')}"] += res.get("count", 0)
                    named = sum(1 for p in recent if p.get("reaction") == r)
                    named += res.get("chosen_order") is not None   # the archiving account
                    chips["chosen by the archiving account"] += res.get("chosen_order") is not None
                    chips["all reactors named" if named >= res.get("count", 0)
                          else "some reactors named" if named else "no reactor named"] += 1
    print(f"{with_rx} messages with reactions out of {total}; per year {dict(sorted(per_year.items()))}")
    print(f"{len(emoji)} distinct emoji; most used: {emoji.most_common(10)}")
    for k in ("all reactors named", "some reactors named", "no reactor named", "chosen by the archiving account"):
        print(f"chips, {k}: {chips[k]}")


if __name__ == "__main__":
    main()
