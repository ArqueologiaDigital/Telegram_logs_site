# Topic index: conversations and themes, written by Claude agents

Pagefind search (`../search_index.py`) finds words. This directory builds the other way in: an
index of what the group talked about, from broad themes down to single conversations, written by
Claude agents that read the whole log. Readers go front page → theme → subtopic → conversation →
the messages themselves on the chat pages.

## Pipeline

| step           | what                                                                                                                                                                      | file                                                     |
|----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| 1. transcripts | the archive as plain text, one line per message (`#id date name: text`), in chunks of a few months                                                                        | `transcript.py`                                          |
| 2. segment     | one agent per chunk reads ALL of it and splits it into conversations: ids, title, summary, people, tags                                                                   | `workflow.js`                                            |
| 3. verify      | one skeptical agent per chunk re-reads the transcript at every cited id and fixes or drops what is wrong                                                                  | `workflow.js`                                            |
| 4. taxonomy    | one agent groups all conversations into themes and subtopics, writes the intro and picks highlights                                                                       | `workflow.js`                                            |
| 5. store       | the workflow's result, as returned, plus run metadata                                                                                                                     | `data/<period>.json`                                     |
| 5b. cross-year | one agent groups the yearly subtopics into topics (coverage checked in code); per topic, one agent writes an all-years summary from `material.py` and a skeptic checks it | `workflow_crossyear.js`, `material.py`, `crossyear.json` |
| 6. render      | deterministic HTML; re-checks every cited message id against the archive and that every subtopic is in a topic                                                            | `render.py`, `topicos.css`                               |

The agents see the same text as the site: phone tags masked, deleted messages and service events
left out. Their output is data, committed here, so the pages can be rebuilt without rerunning them.

Numbers per year (conversations, corrections, size of the theme tree): `python3 -I topics/stats.py`.

## Profiles: opt-in only

A member gets a profile page (`membro-<id>.html`: photo, message counts per year, themes and
conversations they took part in, an optional short bio) only if their Telegram user id is in
`profiles_optin.json`, with the date they asked. Names in conversation lists link to a profile only
for those people.

## Running

```
python3 -I topics/transcript.py --out SCRATCH --chunks 2017-11..2017-11,2017-12..2018-02,2018-03..2018-06,2018-07..2018-10
# then run workflow.js with the Workflow tool in Claude Code, args = {"chunks": [{path, label, messages, first, last}, ...]}
# (transcript.py prints those numbers), and save its result as data/<period>.json
python3 -I topics/render.py --out build
```

## Publishing

`publish.sh` renders the topic pages into the site only when the file `topics/publish` exists, so
an agent-written index goes public only after a maintainer has read it: `touch topics/publish`,
commit, and the next site build includes them (with a link from the log's index page).

Local preview: build into `build/` (`build.py`, `search_index.py`, `topics/render.py`, each with
`--out build`), then run `python3 -m http.server 8765 --bind 127.0.0.1` in the directory that holds
all the repos and open <http://127.0.0.1:8765/Telegram_logs_site/build/formatted/html/topicos.html>.

## Pilot: the group's first year (2026-11-09)

`data/2017-11_2018-10.json`: 2017-11-06 to 2018-10-31, 7808 messages in 4 chunks (47-63k tokens
each).

| step     | agents | result                                                     |
|----------|--------|------------------------------------------------------------|
| segment  | 4      | conversations per chunk                                    |
| verify   | 4      | 39 + 43 + 49 + 59 = 190 conversations kept, 99 corrections |
| taxonomy | 1      | 10 themes, 48 subtopics, 12 highlights                     |
| total    | 9      | 1,356,191 tokens, 14 minutes                               |

`render.py` found every cited message id present and not deleted, and every conversation in a
subtopic. The corrections (in the data file, per chunk) were mostly overstated outcomes ("the
driver reached MAME" while the PR was still open), credit given to the wrong person, and
details the messages do not support.

Known gap: the taxonomy step is not verified. Its theme summaries can reintroduce a claim a
verifier removed (the MAME theme says "Werner aprendeu a compilar o MAME", which the 2017-11
verifier had corrected to "conseguiu compilar o MAME no Windows"). The full run should add a
verify pass over the theme and subtopic summaries.
