#!/usr/bin/env python3
"""Which parts of a page does Pagefind make searchable?

Question it answers: if a word appears only in a data-pagefind-meta value (with and without
data-pagefind-ignore), only in a data-pagefind-filter value, only in the <title>, only in the file
path, or only in the indexed body, does a search for it find the page? search_index.py relies
on the answer: it puts nothing in meta, because meta is searchable.

Builds 3 toy pages in a scratch directory ($TMPDIR), indexes them with the pagefind CLI
(../.venv), serves them on 127.0.0.1 and queries Pagefind's JS API in headless Chromium through
tests/cdp_eval.mjs. Prints the number of hits per word (3 = searchable, 0 = not).

    ../.venv/bin/python -I tests/pagefind_meta_probe.py

Result with pagefind 1.6.0 on 2026-11-09:
    banana (body):3 girafa (meta title):3 zebra (meta):3 tartaruga (meta attr):3
    camelo (meta, ignored element):3 leao (filter):0 hippo1 (file path):0 tituloheadword (<title>):0
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = [("banana", "body"), ("girafa", "meta title"), ("zebra", "meta"), ("tartaruga", "meta attr"),
         ("camelo", "meta, ignored element"), ("leao", "filter"), ("hippo1", "file path"),
         ("tituloheadword", "<title>")]


def main():
    root = tempfile.mkdtemp(prefix="pagefind-probe-")
    try:
        os.makedirs(os.path.join(root, "7"))
        for i in (1, 2, 3):
            with open(os.path.join(root, "7", f"hippo{i}.html"), "w") as f:
                f.write(f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8"><title>tituloheadword</title></head><body>
<div><span data-pagefind-meta="title">girafa</span><span data-pagefind-meta="autor">zebra</span>
<span data-pagefind-filter="autor">leao</span><span data-pagefind-sort="data">2020-01-0{i}</span>
<div data-pagefind-meta="data:tartaruga"></div><span data-pagefind-ignore data-pagefind-meta="ign">camelo</span></div>
<main data-pagefind-body><p>banana number {i}</p></main></body></html>
""")
        subprocess.run([sys.executable, "-m", "pagefind", "--site", root, "--output-path",
                        os.path.join(root, "pagefind"), "--quiet"], check=True)
        words = ",".join(f"'{w}'" for w, _ in WORDS)
        with open(os.path.join(root, "t.html"), "w") as f:
            f.write("<!DOCTYPE html><html lang='pt'><meta charset='utf-8'><body><pre id=o></pre><script type=module>"
                    "const o=document.getElementById('o'); const pf=await import('./pagefind/pagefind.js'); await pf.init();"
                    f"for (const q of [{words}]) {{ const s=await pf.search(q); o.textContent+=q+':'+s.results.length+' '; }}"
                    "o.textContent+='DONE';</script>")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                               cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            out = subprocess.run(["node", "--experimental-websocket", os.path.join(HERE, "cdp_eval.mjs"),
                                  f"http://127.0.0.1:{port}/t.html",
                                  "(t=>t.includes('DONE')?t:'')(document.getElementById('o').textContent)", "30"],
                                 capture_output=True, text=True, check=True).stdout
        finally:
            srv.terminate()
        hits = dict(x.split(":") for x in out.replace("DONE", "").split())
        print(" ".join(f"{w} ({where}):{hits.get(w, '?')}" for w, where in WORDS))
    finally:
        assert os.path.basename(root).startswith("pagefind-probe-")
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
