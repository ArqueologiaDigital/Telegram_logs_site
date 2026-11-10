#!/usr/bin/env python3
"""Contact sheets of candidate photos for each cross-year topic, to choose topics/topic_images.json.

Question it answers: which photos did members post inside the conversations of each topic?
For every topic in topics/crossyear.json it takes the photos (media kind "photo", stored in the
media repo) whose message lies inside one of the topic's conversations (first_id..last_id) and
was posted by one of that conversation's participants, ranks them (a conversation's key message
first, then by the conversation's weight, then photos with a caption), and writes

  OUT/<slug>.jpg     a numbered grid of the best N candidates
  OUT/candidates.json  {slug: [{"n", "msg_id", "path", "conversation", "caption"}, ...]}

    python3 topics/image_candidates.py --out SCRATCH [--n 12] [--only slug,slug] [--skip N]

(needs Pillow; run with the system python3, not -I). The choice itself is made by looking at
the sheets; it is recorded in topics/topic_images.json.
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build as B  # noqa: E402

TILE = 240


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--skip", type=int, default=0, help="skip the best N candidates (to see the next ones)")
    p.add_argument("--only")
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    p.add_argument("--media-repo", default=os.path.join(HERE, "..", "..", "Telegram_logs_media"))
    a = p.parse_args()
    d = B.Data(a.data)
    years = {}
    for f in glob.glob(os.path.join(HERE, "data", "*.json")):
        with open(f, encoding="utf-8") as fh:
            y = json.load(fh)
        convs = {c["first_id"]: c for ch in y["chunks"] for c in ch["conversations"]}
        for t in y["taxonomy"]["themes"]:
            for s in t["subtopics"]:
                years[f"{y['meta']['year']}/{t['slug']}/{s['slug']}"] = [convs[i] for i in s["conversation_ids"] if i in convs]
    photos = sorted(i for i, e in d.media.items() if e["kind"] == "photo" and e["store"] == "git")
    with open(os.path.join(HERE, "crossyear.json"), encoding="utf-8") as fh:
        topics = json.load(fh)["topics"]
    only = set(a.only.split(",")) if a.only else None
    os.makedirs(a.out, exist_ok=True)
    out = {}
    for tp in topics:
        if only and tp["slug"] not in only:
            continue
        cands = {}
        for sid in tp["subtopics"]:
            for c in years.get(sid, []):
                for mid in photos:
                    if not c["first_id"] <= mid <= c["last_id"]:
                        continue
                    rec = d.by_id[mid]
                    raw = rec.get("raw") or {}
                    if rec["archive"].get("deletion") or d.sender(raw) not in c["participants"]:
                        continue
                    score = (mid in c.get("key_ids", []) or mid == c["first_id"], c.get("weight", 1),
                             bool(raw.get("message")))
                    if mid not in cands or score > cands[mid][0]:
                        cands[mid] = (score, c, raw.get("message") or "")
        best = sorted(cands, key=lambda m: cands[m][0], reverse=True)[a.skip:a.skip + a.n]
        cols = 4
        rows = max(1, -(-len(best) // cols))
        sheet = Image.new("RGB", (cols * TILE, rows * TILE), "white")
        draw = ImageDraw.Draw(sheet)
        out[tp["slug"]] = []
        for k, mid in enumerate(best):
            path = d.media[mid]["path"]
            try:
                im = ImageOps.exif_transpose(Image.open(os.path.join(a.media_repo, path))).convert("RGB")
            except OSError:
                continue
            im.thumbnail((TILE - 6, TILE - 6))
            x, y0 = (k % cols) * TILE, (k // cols) * TILE
            sheet.paste(im, (x + (TILE - im.width) // 2, y0 + (TILE - im.height) // 2))
            draw.rectangle([x, y0, x + 30, y0 + 18], fill="black")
            draw.text((x + 4, y0 + 3), str(k + 1), fill="yellow")
            out[tp["slug"]].append({"n": k + 1, "msg_id": mid, "path": path,
                                    "conversation": cands[mid][1]["title"], "caption": cands[mid][2][:120]})
        sheet.save(os.path.join(a.out, tp["slug"] + ".jpg"), quality=80)
        print(f"{tp['slug']}: {len(cands)} candidate photos, {len(best)} on the sheet")
    with open(os.path.join(a.out, "candidates.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
