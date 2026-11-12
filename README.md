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
| look       | the 2018 markup and class names; since 2026-11 the colours follow the site's dark style (see "Design" below)                         |
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

## Short addresses

The topic, community and project pages are published at short addresses on the main site:
`arqueologiadigital.org/topicos/`, `/topicos/<slug>/`, `/topicos/ano-<N>/`, `/comunidade/`,
`/comunidade/<handle>/` and `/projetos/`. `publish.sh` runs `export_pretty.py`, which copies those
pages into the main site's repository (`../ArqueologiaDigital.github.io`, directories `topicos/`,
`comunidade/`, `projetos/`, `logs/`, `busca/`), rewrites their links, and commits there locally. The copies left in
`gh-pages` under `/Telegram_logs_site/formatted/html/` become redirects to the short addresses, so
links published earlier keep working. The log index, the chat pages and the search page are
published the same way, as `/logs/`, `/logs/<page number>/` and `/busca/`, so no address a visitor
sees contains `/Telegram_logs_site/formatted/html/`. Only files that pages load stay there: the
stylesheets, the search index (`pagefind/`) and the plaintext logs. Push both repositories together: the redirects in `gh-pages` point to pages that
exist only once the main site is pushed.

## Design

Every page shares one header (`SITE_HEADER` in `build.py`: Tópicos, Projetos, Comunidade, Log do
chat, Busca, Galeria) and one style, taken from the photo gallery of the main site: dark
background, serif text, green links, cards. It lives at the end of
`static/telegram-history-dump.css` (chat pages, index, shared variables) and in
`topics/topicos.css` (topic, year, project, community and profile pages).

Layouts adapt to the screen. On desktop the chat pages are up to 980 px wide and the topic-type
pages 1240 px, with text kept to a readable line length and the extra width used for side-by-side
blocks: topic cards in up to 4 columns, a topic's photo and repositories box beside its summary,
conversations and yearly summaries two by two, themes and repositories in card grids. On phones
(under 700 to 900 px, depending on the block) everything is one column. Checked in Chromium at
1300 px and 390 px with `tests/cdp_shot.mjs`.

## Publishing

`./publish.sh` rebuilds into the `gh-pages` branch (a worktree at `../Telegram_logs_site-gh-pages`)
with media linked from `raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/`,
runs the 2018 compatibility test, and commits if the output changed. It never pushes; the daily
job in `Telegram_logs` calls it. GitHub Pages serves `gh-pages` at
<https://arqueologiadigital.org/Telegram_logs_site/>.

The 2018 URLs under `/Telegram_logs/formatted/html/` are redirected to the same file under
`/Telegram_logs_site/formatted/html/` by the `404.html` of the main site's repo
(`ArqueologiaDigital.github.io`), which GitHub Pages serves for any path no repo serves.

## Previewing before pushing

`preview_site.py` serves the local checkouts exactly as GitHub Pages will serve them once pushed,
so a change can be looked at in the browser before anything leaves the machine. It only reads
files; it never builds, commits or pushes.

```
cd Telegram_logs_site
TMPDIR=~/compartilhado/tmp ./publish.sh          # build and commit locally (no push)
python3 -I preview_site.py                        # then open http://127.0.0.1:8000/
python3 -I preview_site.py --port 8080 --remote-media
```

Stop it with Ctrl-C (or, if it was started in the background, by killing that process). Nothing
needs cleaning up afterwards. Because it serves what `publish.sh` committed, rerun `publish.sh`
after a change and reload the page; the server itself does not need restarting.

| URL path                | served from                                 | on the live site                                              |
|-------------------------|---------------------------------------------|---------------------------------------------------------------|
| `/`                     | `../ArqueologiaDigital.github.io`           | main site: `/topicos/`, `/comunidade/`, `/logs/N/`, `/busca/` |
| `/Telegram_logs_site/`  | `../Telegram_logs_site-gh-pages` (worktree) | chat pages, CSS, search index                                 |
| `/Telegram_logs_media/` | `../Telegram_logs_media`                    | not served; media comes from GitHub                           |

| option           | default     | meaning                                                                                 |
|------------------|-------------|-----------------------------------------------------------------------------------------|
| `--port`         | `8000`      | port to listen on                                                                       |
| `--bind`         | `127.0.0.1` | address to listen on; keep the default so the preview is not reachable from the network |
| `--remote-media` | off         | keep the `raw.githubusercontent.com` media links, so only already pushed media shows    |

Without `--remote-media`, every HTML page has the media base
`https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/` rewritten to
`/Telegram_logs_media/`, so photos and link-preview thumbnails not yet pushed show too. Like
GitHub Pages, it lists no directories, and it refuses `.git` paths and paths outside the three
directories.

To look at a branch that must not be published (such as `pagina-arquivos`), do not run
`publish.sh` on it: the daily job publishes whatever branch is checked out. Build it into
`build/` instead and use the plain `http.server` preview under [Building](#building).

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
| `tests/reaction_counts.py`     | how many messages have reactions, and how many chips can name who reacted?                 | `python3 -I tests/reaction_counts.py ../Telegram_logs`                                                    |

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
To see the whole site as it will be published, use `preview_site.py` instead (see
[Previewing before pushing](#previewing-before-pushing)).

| option         | values                                  | meaning                                                                                                                                     |
|----------------|-----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `--deleted`    | `placeholder` (default), `show`, `omit` | deleted messages: "[message deleted on … by …]", full content with a note, or nothing. Pagination always counts them, so pages never shift. |
| `--phones`     | `review` (default), `mask`, `show`      | phone numbers typed into messages; see below                                                                                                |
| `--media-base` | URL                                     | prefix for media links (default: relative path to the local media repo)                                                                     |

Media over 10 MB link to archive.org once uploaded (`ia_url` in the manifest); until then the
page says "large file, not yet published".

Emoji reactions show under the message as chips ("👍 3"), in Telegram's order; hovering a chip
lists who reacted (a `title`, so not on touch screens). They come from `raw.reactions` as of the
last sync that scanned the message: the daily sync rescans the last 30 days, so reactions added
later to older messages appear only after a `tg_sync.py sync --full`. Telegram names reactors in
`recent_reactions`, leaving out the archiving account's own reaction (marked by `chosen_order`,
named by `build.py`) and, on busy messages, all but the latest few ("… and 2 more"). A custom
emoji is a sticker we do not fetch and shows as ✱.

## Phone numbers in message text

Telegram tags things that look like phone numbers (`MessageEntityPhone`), but most tags in this
group are year ranges ("1980/1990"), prices or file names. `phone_review.json` records a human
verdict per message id: `show` (not a phone number) or `mask` (hidden on the site as
"[phone number]"). The build masks any tag that is not in the file yet and prints a warning
listing those message ids: add them to the file after looking at them. On 2026-11-09: 10 tags,
1 real number (masked), 9 false positives.
