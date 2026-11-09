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

Or plan the chunks: --years FROM..TO splits that span into group years (12 months each, counted
from FROM; the group's year 1 began 2017-11) and each year into chunks of whole months of at most
--target thousand tokens (a month larger than that is a chunk of its own). It writes the
transcripts and DIR/plan.json, the Workflow's args:

    python3 -I topics/transcript.py --out DIR --years 2018-11..2026-10 --target 60
"""
import json
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


def months(lo, hi):
    y, m = map(int, lo.split("-"))
    while f"{y:04d}-{m:02d}" <= hi:
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def write_chunk(out, ms, lines_by_month, ids_by_month):
    lines = [x for m in ms for x in lines_by_month.get(m, [])]
    ids = [x for m in ms for x in ids_by_month.get(m, [])]
    path = os.path.join(out, f"{ms[0]}_{ms[-1]}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    size = os.path.getsize(path)
    label = ms[0] if len(ms) == 1 else f"{ms[0]}..{ms[-1]}"
    print(f"  {label}: {len(lines)} messages, #{ids[0]}..#{ids[-1]}, ~{size / 3.5 / 1e3:.0f}k tokens")
    return {"path": os.path.abspath(path), "label": label, "messages": len(lines), "first": ids[0], "last": ids[-1]}


def plan(opts, lines_by_month, ids_by_month):
    lo, hi = opts.years.split("..")
    all_months = list(months(lo, hi))
    year_no = (int(lo[:4]) - 2017) * 12 + int(lo[5:]) - 11   # months since 2017-11
    years = []
    for i in range(0, len(all_months), 12):
        ms = all_months[i:i + 12]
        n = (year_no + i) // 12 + 1
        print(f"year {n}: {ms[0]}..{ms[-1]}")
        chunks, cur, size = [], [], 0
        for m in ms:
            t = sum(len(x) + 1 for x in lines_by_month.get(m, [])) / 3.5 / 1e3
            if cur and size + t > opts.target:
                chunks.append(write_chunk(opts.out, cur, lines_by_month, ids_by_month))
                cur, size = [], 0
            cur.append(m)
            size += t
        if cur:
            chunks.append(write_chunk(opts.out, cur, lines_by_month, ids_by_month))
        years.append({"year": n, "from": ms[0], "to": ms[-1],
                      "messages": sum(c["messages"] for c in chunks), "chunks": chunks})
    with open(os.path.join(opts.out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump({"years": years}, f, ensure_ascii=False, indent=1)
    print(f"{len(years)} years, {sum(len(y['chunks']) for y in years)} chunks -> {opts.out}/plan.json")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--chunks")
    p.add_argument("--years")
    p.add_argument("--target", type=int, default=60, help="thousand tokens per chunk (--years)")
    p.add_argument("--data", default=os.path.join(HERE, "..", "..", "Telegram_logs"))
    p.add_argument("--phones", default="review")
    opts = p.parse_args()
    d = B.Data(opts.data)
    B.mark_phones(d, opts)
    os.makedirs(opts.out, exist_ok=True)
    lines_by_month, ids_by_month = {}, {}
    for rec in d.records:
        raw = rec.get("raw")
        if raw is None or raw["_"] == "MessageService" or rec["archive"].get("deletion"):
            continue
        ym = B.local(rec["date"]).strftime("%Y-%m")
        lines_by_month.setdefault(ym, []).append(line(rec, raw, d))
        ids_by_month.setdefault(ym, []).append(rec["id"])
    if opts.years:
        plan(opts, lines_by_month, ids_by_month)
        return
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
