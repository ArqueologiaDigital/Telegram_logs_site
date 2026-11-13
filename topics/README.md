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

## Profiles and the community gallery: opt-in only

A member gets a profile page (`membro-<id>.html`: photo, message counts per year, topics and
conversations they took part in, an optional short bio shown once `bio_approved` is true) and a
card in the community gallery (`comunidade.html`: photo, name, role, active years, message count,
links to the profile and to a search of their messages) only if their Telegram user id is in
`profiles_optin.json`, with the date they asked. Names in conversation lists link to a profile
only for those people. Every profile gets a bio (Felipe's request, 2026-11-10): a short summary of what the person
contributed, written from the topic index with every claim traced to conversations listed in
`bio_basis`, and changed or removed if the person asks. `topics/profile_material.py --uid ID --name NAME --out SCRATCH/x` gathers the material: the message count and years, the number of index conversations the person is in (the "aparece em N conversas do índice" of the bios), the index sentences naming them, and their own messages to check each claim against. Profiles waiting for the person's approval live on the branch `perfis-aguardando-aprovacao`, not on
`main` (see that branch's `topics/profiles_optin.json`); merge an entry into `main` once approved.
An entry with `"published": false` is a draft: it is left out of the site and rendered only with
`render.py --drafts`, for a local preview (`tests/cdp_pdf.mjs` saves a page as a PDF to send to the
person). To add someone who asked: add their user id (see `users/users.jsonl` in
`Telegram_logs`) with `role`, `opted_in` and optionally a `handle` (lowercase letters, digits, `_`; the profile is then
`membro-<handle>.html`, short address `arqueologiadigital.org/comunidade/<handle>`); to remove someone,
delete their entry.
A member who wants another picture than their Telegram photo on the profile and the gallery card
gets `"picture": "pictures/<handle>.jpg"` (a file under `topics/`, which `render.py` publishes as
`perfil-<handle>.jpg` next to the pages); it replaces the Telegram photo everywhere: chat pages,
profile and gallery card (`build.py`, `chosen_pictures`).

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

## Topic images

Each cross-year topic has one photo, posted by a member inside one of its conversations:
`topic_images.json` (slug → message id). `python3 topics/image_candidates.py --out SCRATCH` makes a
numbered contact sheet per topic with the 12 best-ranked candidate photos (`--skip 12` shows the
next ones); the choice is made by looking at the sheets, preferring machines and screens over
photos of people. `render.py` shows the photo on the topic page (left of the summary, with a
caption linking to the message) and in the front page's topic list: a grid of cards, up to 4
columns, on wide screens; one column with thumbnails alternating left and right on phones.
To change a topic's image, put another photo message id in `topic_images.json`.

## Updating the year in progress

The daily job (`Telegram_logs/tools/daily.sh`) archives messages and rebuilds the pages, but it
runs no agents: new conversations reach the index only when someone runs this, in Claude Code,
for example once a month. The year so far is redone as a whole each time; the cross-year topics
only grow.

```
python3 -I topics/transcript.py --out SCRATCH --chunks 2026-11..2026-11       # first month of the year .. last
# Workflow topics/workflow_increment.js, args {stage: "year", year, span, chunks: [...]}  (span in pt-BR,
# e.g. "de 1º a 12 de novembro de 2026"); save its result as SCRATCH/stage1.json, then:
python3 -I topics/increment.py year SCRATCH/stage1.json --year 10 --from 2026-11 --until-id ID --messages N --run RUN
python3 -I topics/increment.py ids --year 10                                   # the year's subtopic ids
# restore crossyear.json from the last commit before an earlier increment of the same year, then
# Workflow topics/workflow_increment.js, args {stage: "topics", root, year, span, subtopics, topics: [{slug, title, scope}]}
python3 -I topics/increment.py topics SCRATCH/stage2.json --year 10 --run RUN
python3 -I topics/inline_links.py propose
python3 -I topics/render.py --out build                                        # must report no CHECK lines
```

Read the result before committing: the year's text in `data/<period>.json`, and what
`increment.py topics` prints (each topic's addition and note). The data file is marked
`"in_progress"` up to the date of the last indexed message, and the pages say "ano em andamento".
A topic summary was read by a person, so the agents never rewrite it: they return only the
sentences to add, and `increment.py` appends them. Their writing rules include the gender rule
(feminine forms only for the women Felipe has named, masculine for Jecel; neutral wording for
everyone else).

First run, 2026-11-13, for year 10 up to message #42296 (12 November 2026, 250 messages):

| stage  | run             | agents | tokens  | result                                                                                       |
|--------|-----------------|--------|---------|----------------------------------------------------------------------------------------------|
| year   | wf_93eac5c6-2ad | 4      | 194,445 | 19 conversations (18 verifier corrections); 5 themes, 14 subtopics (18 taxonomy corrections) |
| topics | wf_4c740c82-286 | 25     | 974,808 | 14 subtopics placed in 12 existing topics; 12 additions and notes checked                    |

Changed by hand afterwards, each logged in the corrections of its text: one note that opened with an empty framing sentence, and five sentences that stated as fact what RicBit had said ("nenhum emulador reproduzia"), now attributed to RicBit.

## Links inside the summaries

Summaries name online resources ("o repositório kn5000_homebrew"); `inline_links.py` turns those
names into links, as a style guide would: at the first mention on a page (`render.py`, class
`Inline`). A conversation card is opened and read on its own, so it links its own first mention
too. The list of resources under each conversation stays as it is. A phrase links only to a URL
posted in the conversations the text summarizes (their `resources`), or to a repository of the
organisation (`repos.json`), and render reports any link that breaks that rule or whose phrase is
gone from the text.

```
python3 -I topics/inline_links.py propose     # rules -> inline_links.json (keeps "by": "hand" entries)
python3 -I topics/inline_links.py show topic: # each link in context, for reading
```

The rules (docstring of `inline_links.py`) name a resource by its GitHub repository, pull request
or issue number, Wikipedia title, site name or last path segment; a name that would also be a
person, company, product or common word is skipped (`NOT_LINKS`, read and judged on 2026-11-13).
On 2026-11-13: 660 links in 467 texts, to 292 distinct URLs.

| rule                                             | links |
|--------------------------------------------------|-------|
| GitHub repository name ("FlashFloppy")           | 258   |
| site name ("Datassette", "Garoa")                | 213   |
| last segment of the URL path ("ULX3S")           | 108   |
| pull request ("PR #126")                         | 46    |
| Wikipedia title ("Zezinho")                      | 33    |
| issue                                            | 2     |

By text: 257 conversation summaries, 80 subtopics, 67 per-year topic notes, 37 cross-year
topic summaries, 19 themes, 7 year intros. A random sample of 45 links was read in context and all
were right. The rules miss what a text names only by description ("o documento público", "o vídeo
no YouTube"); those need someone (or an agent) to read the text and its resources, and go into
`inline_links.json` with `"by": "hand"`.

## Projects: the organisation's repositories

`repos.json` is a hand-written catalogue of the public repositories of
[github.com/ArqueologiaDigital](https://github.com/ArqueologiaDigital): groups, a Portuguese title
and one-line description per repository, an optional project site, and the cross-year topics each
relates to (per group, or per repository with its own `topics`). `render.py` writes
`projetos.html` (all of them, by group, each group linking to the group's conversations on the
subject) and puts a "Repositórios do grupo sobre este assunto" box on each related topic page.
It shows no stars or dates, so nothing goes stale between builds.
Each group may have an `image`, a photo from the chat shown left of its text: `{"topic": slug}`
reuses that topic's image, `{"msg_id": N}` names a photo message.

`python3 -I topics/repos_check.py` lists repositories missing from the catalogue (one GitHub API
request); on 2026-11-10: 47 public repositories, 47 in the catalogue.
