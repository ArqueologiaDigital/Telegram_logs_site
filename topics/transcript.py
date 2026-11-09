#!/usr/bin/env python3
"""Plain-text transcripts of the chat, for the agents that write the topic index.

One line per message, as the site shows it (phone tags masked as in build.py, deleted messages
and service events left out), in Brasília time:

    #1234 2018-03-04 18:20 Name (↪#1200) [foto] text, with newlines shown as ⏎

Markers: (↪#id) reply to; [encaminhada de X]; [foto], [vídeo], [áudio], [GIF], [figurinha],
[documento: file name]; [link: preview title]; [enquete: question].

Writes one file per chunk; chunks are lists of months, given as FROM..TO,FROM..TO:

    python3 -I topics/transcript.py --out DIR --chunks 2017-11..2017-11,2017-12..2018-02,...

and prints each chunk's message count, id range and size.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build as B  # noqa: E402

KIND_PT = {"photo": "foto", "video": "vídeo", "audio": "áudio", "document": "documento",
           "sticker": "figurinha", "gif": "GIF"}


def line(rec, raw, d):
    when = B.local(rec["date"])
    out = [f"#{rec['id']} {when:%Y-%m-%d %H:%M} {d.sender(raw)}"]
    reply = (raw.get("reply_to") or {}).get("reply_to_msg_id")
    if reply:
        out.append(f"(↪#{reply})")
    f = raw.get("fwd_from")
    if f:
        fid = f.get("from_id") or {}
        src = d.name(fid["user_id"]) if fid.get("user_id") else f.get("from_name") or "um canal"
        out.append(f"[encaminhada de {src}]")
    m = raw.get("media") or {}
    entry = d.media.get(rec["id"])
    if m.get("_") == "MessageMediaWebPage":
        title = (m.get("webpage") or {}).get("title")
        if title:
            out.append(f"[link: {title}]")
    elif m.get("_") == "MessageMediaPoll":
        q = (m.get("poll") or {}).get("question")
        out.append(f"[enquete: {q.get('text') if isinstance(q, dict) else q}]")
    elif entry:
        kind = KIND_PT.get(entry["kind"], entry["kind"])
        name = B.doc_filename(m.get("document") or {}) if entry["kind"] == "document" else None
        out.append(f"[{kind}: {name}]" if name else f"[{kind}]")
    text = B.masked_text(raw).replace("\r", "").replace("\n", " ⏎ ")
    return " ".join(out) + ": " + text


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--chunks", required=True)
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    p.add_argument("--phones", default="review")
    opts = p.parse_args()
    d = B.Data(opts.data)
    B.mark_phones(d, opts)
    os.makedirs(opts.out, exist_ok=True)
    for spec in opts.chunks.split(","):
        lo, hi = spec.split("..")
        lines, ids = [], []
        for rec in d.records:
            ym = B.local(rec["date"]).strftime("%Y-%m")
            raw = rec.get("raw")
            if not (lo <= ym <= hi) or raw is None or raw["_"] == "MessageService":
                continue
            if rec["archive"].get("deletion"):
                continue
            lines.append(line(rec, raw, d))
            ids.append(rec["id"])
        path = os.path.join(opts.out, f"{lo}_{hi}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        size = os.path.getsize(path)
        print(f"{lo}..{hi}: {len(lines)} messages, #{ids[0]}..#{ids[-1]}, {size / 1e3:.0f} KB, "
              f"~{size / 3.5 / 1e3:.0f}k tokens -> {path}")


if __name__ == "__main__":
    main()
