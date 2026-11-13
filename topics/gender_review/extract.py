"""Dump every index string that names given people, to review it for misgendering.

    python3 -I topics/gender_review/extract.py OUT_DIR [PARTS]

Walks topics/**/*.json (skipping "participants" lists) and writes, split into PARTS files of
similar size (default 3, one per reviewer), OUT_DIR/partK.jsonl lines {"file", "path", "text",
"n"}; "path" is the JSON path of the string, "n" a running number that apply_fixes.py and
show.py use. WHO below is the pattern for the names reviewed on 2026-11-13: "L." (also known as
Acidx) and Erin Pinheiro. "L." is matched only when followed by a space, comma, etc., so that
"L.S.D." does not count.
"""
import glob
import json
import os
import re
import sys

WHO = re.compile(r"(?:(?<![\w])L\.(?=[\s,;:)'\"]|$)|\bErin\b|\bAcidx\b)")


def main():
    out = sys.argv[1]
    nparts = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    items = []

    def walk(o, path, f):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [k], f)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + [i], f)
        elif isinstance(o, str) and "participants" not in path and WHO.search(o):
            items.append({"file": f, "path": path, "text": o})

    for f in sorted(glob.glob("topics/**/*.json", recursive=True)):
        if f.startswith("topics/gender_review/"):     # the review's own fix lists
            continue
        with open(f, encoding="utf-8") as fh:
            walk(json.load(fh), [], f)
    parts, sizes = [[] for _ in range(nparts)], [0] * nparts
    for i, it in enumerate(items):
        it["n"] = i
        k = sizes.index(min(sizes))
        parts[k].append(it)
        sizes[k] += len(it["text"])
    os.makedirs(out, exist_ok=True)
    for k, p in enumerate(parts):
        with open(os.path.join(out, f"part{k + 1}.jsonl"), "w", encoding="utf-8") as fh:
            for it in p:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} strings, {sum(sizes)} characters -> {nparts} parts in {out}")


if __name__ == "__main__":
    main()
