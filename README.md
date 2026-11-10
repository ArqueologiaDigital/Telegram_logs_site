# Telegram_logs_site: views of the @arqueologiadigital archive

Layer 4 of the archive of the Telegram group [@arqueologiadigital](https://t.me/arqueologiadigital).
`build.py` turns the raw data in [`Telegram_logs`](https://github.com/ArqueologiaDigital/Telegram_logs)
and [`Telegram_logs_media`](https://github.com/ArqueologiaDigital/Telegram_logs_media) into static
HTML. It only reads those repos; everything here can be regenerated, and `build/` is not committed.

## Drop-in replacement for the 2018 pages

The 2018 pages (`telegram-history-dump`) lived at
`arqueologiadigital.org/Telegram_logs/formatted/html/<LEGACY_NAME>-N.html`. The build keeps:

| what       | kept as                                                                                                                              |
|------------|--------------------------------------------------------------------------------------------------------------------------------------|
| file names | `formatted/html/index.html`, `formatted/html/<LEGACY_NAME>-N.html`, `formatted/plaintext/<LEGACY_NAME>/<LEGACY_NAME>_YYYY-MM-DD.log` |
| pagination | 1000 archived messages per page, oldest first, so page N covers the same messages as in 2018                                         |
| look       | the original `telegram-history-dump.css`, plus a few additions at its end                                                            |
| timestamps | local time (America/Sao_Paulo) in each bubble's `title`, a date row every 10 messages                                                |

`tests/compare_old_pages.py` checks the first point against the 2018 HTML: every message bubble
of old pages 0..4 appears, in order, on the new page with the same number (on 2026-11-09: 5 of 5
pages pass; page 4, partial in 2018, is now full).

New compared with 2018: formatting (bold, code, quotes, spoilers), replies linking to the replied
message, a `#m<id>` anchor on every message, forwarded-from names, video/audio players, document
links with sizes, polls, service events as centered rows, an index table of pages and dates, and
sender names in the plaintext logs. Users whose Telegram account was deleted are shown with their
last known name.

Everyone's messages look alike. The 2018 pages showed the archiving account's own messages
(Felipe's) as green bubbles on the right; now every message is a left-hand bubble tinted with
its sender's own colour (a hue fixed per Telegram user id, `hue()` in `build.py`), with the
sender's profile photo beside the name, or their initials when there is no public photo. The
photos come from `Telegram_logs/tools/tg_avatars.py` (`media/avatars.jsonl`, files in the media
repo's `avatars/`).

## Publishing

`./publish.sh` rebuilds into the `gh-pages` branch (a worktree at `../Telegram_logs_site-gh-pages`)
with media linked from `raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/`,
runs the 2018 compatibility test, and commits if the output changed. It never pushes; the daily
job in `Telegram_logs` calls it. GitHub Pages serves `gh-pages` at
<https://arqueologiadigital.org/Telegram_logs_site/>.

The 2018 URLs under `/Telegram_logs/formatted/html/` are redirected to the same file under
`/Telegram_logs_site/formatted/html/` by the `404.html` of the main site's repo
(`ArqueologiaDigital.github.io`), which GitHub Pages serves for any path no repo serves.

## Search

`search_index.py` builds a full-text search with [Pagefind](https://pagefind.app):
`formatted/html/search.html` (linked from the index page and every page's navigation) and its
index in `formatted/html/pagefind/`. The index is split into small files and the browser fetches
only the ones a query needs, so it works on GitHub Pages with no server. Words are stemmed for
Portuguese ("emuladores" finds "emulador", "emulação").

- One record per message, linking to the message on its page (`<page>.html#m<id>`).
- Indexed: the message text as the pages show it (same phone masking, deleted messages left out
  under `--deleted placeholder`), plus a document's file name, a link preview's title and
  description, and a poll's question and answers. Service messages and media without text are
  not indexed.
- Filters: year (`ano`), sender (`autor`), kind (`tipo`: texto, link, foto, vídeo, documento, ...).
  Sorting: relevance, newest or oldest first.
- On 2026-11-09: 38148 of 40975 messages indexed, 38187 files, 13.2 MB, in about 30 seconds.

`search_index.py`'s docstring explains two non-obvious choices: it feeds Pagefind HTML files
through its command-line indexer (the Python API manages ~10 records/s), and records carry no
Pagefind metadata (Pagefind makes metadata searchable; the page, id, date and has-photo flag
travel in the record's path instead, and `search.html` turns them back into a link and title).

`search.html?autor=NAME` preselects the sender filter and, when no word is given, lists that
person's messages newest first (Pagefind's UI shows nothing until a word is typed); the community
gallery links to it. `search.html?q=WORDS` runs a search.

`publish.sh` always rewrites `search.html` (`search_index.py --page-only`) and rebuilds the index on Sundays, when it is missing, or with `SEARCH=1
./publish.sh`; other days keep the previous index. Each rebuild rewrites about 3.6 MB of index
files however few messages arrived (measured with `tests/search_churn.py`: 20 new messages changed 94 of 163 word-index chunks), so a daily rebuild would grow the
`gh-pages` history by ~1.3 GB a year; weekly is ~190 MB. Links in an older index stay valid
because pages never shift; messages newer than the index are found after the next rebuild.

Needs `pip install -r requirements.txt` in `../.venv` (pagefind, which ships the indexer binary).

### Tests and probes

| script                         | question it answers                                                                        | run                                                                                                       |
|--------------------------------|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| `tests/compare_old_pages.py`   | do the 2018 pages' messages all appear, in order, on the same-numbered new pages?          | `python3 -I tests/compare_old_pages.py ../Telegram_logs-2018-private/formatted/html build/formatted/html` |
| `tests/search_churn.py`        | how many index files does a rebuild change when N messages arrive?                         | `../.venv/bin/python -I tests/search_churn.py SCRATCH_DIR 20`                                             |
| `tests/cdp_eval.mjs`           | what does a page show once its scripts ran? (headless Chromium, polls a JS expression)     | serve the build (`python3 -m http.server 8765` in `build/`), then the command below                       |
| `tests/cdp_shot.mjs`           | what does a page look like? (headless Chromium screenshot, lazy images loaded)             | `node --experimental-websocket tests/cdp_shot.mjs URL out.png 800 1100 4000`                              |
| `tests/pagefind_meta_probe.py` | which parts of a page does Pagefind make searchable? (meta: yes; filters, path, title: no) | `../.venv/bin/python -I tests/pagefind_meta_probe.py`                                                     |

```
node --experimental-websocket tests/cdp_eval.mjs \
  'http://127.0.0.1:8765/formatted/html/search.html?q=patinho%20feio' \
  "document.querySelector('.pagefind-ui__result') ? document.querySelector('.pagefind-ui__message').textContent : ''"
```

On 2026-11-09 that printed "207 resultados encontrados para patinho feio"; the first hit linked to
`…-25.html#m26172`. Chromium's `--dump-dom` is no substitute: it dumps at the load event, before
the search has run.

## Building

```
python3 -I build.py --out build                 # local preview; media linked from ../Telegram_logs_media
python3 -I build.py --out build --media-base https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/
python3 -I tests/compare_old_pages.py ../Telegram_logs-2018-private/formatted/html build/formatted/html
../.venv/bin/python -I search_index.py --out build   # search page and index, after build.py
```

Preview with a local web server from the directory that holds all repos (browsers block media
from `file://` pages): `python3 -m http.server 8765` there, then open
<http://127.0.0.1:8765/Telegram_logs_site/build/formatted/html/index.html>.

| option         | values                                  | meaning                                                                                                                                     |
|----------------|-----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `--deleted`    | `placeholder` (default), `show`, `omit` | deleted messages: "[message deleted on … by …]", full content with a note, or nothing. Pagination always counts them, so pages never shift. |
| `--phones`     | `review` (default), `mask`, `show`      | phone numbers typed into messages; see below                                                                                                |
| `--media-base` | URL                                     | prefix for media links (default: relative path to the local media repo)                                                                     |

Media over 10 MB link to archive.org once uploaded (`ia_url` in the manifest); until then the
page says "large file, not yet published".

## Phone numbers in message text

Telegram tags things that look like phone numbers (`MessageEntityPhone`), but most tags in this
group are year ranges ("1980/1990"), prices or file names. `phone_review.json` records a human
verdict per message id: `show` (not a phone number) or `mask` (hidden on the site as
"[phone number]"). The build masks any tag that is not in the file yet and prints a warning
listing those message ids: add them to the file after looking at them. On 2026-11-09: 10 tags,
1 real number (masked), 9 false positives.
